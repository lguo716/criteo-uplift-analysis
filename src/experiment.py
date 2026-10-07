import logging

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import CATEGORICAL, CONTINUOUS
from .data import load_sample
from .utils import write_table


def wilson(successes, n, alpha=0.05):
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("Invalid binomial counts")
    z = norm.ppf(1 - alpha / 2)
    rate = successes / n
    denominator = 1 + z * z / n
    center = (rate + z * z / (2 * n)) / denominator
    half = z * np.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denominator
    return float(center - half), float(center + half)


def difference_ci(success_t, n_t, success_c, n_c):
    pt, pc = success_t / n_t, success_c / n_c
    lt, ut = wilson(success_t, n_t)
    lc, uc = wilson(success_c, n_c)
    delta = pt - pc
    # Newcombe hybrid score interval for two independent proportions.
    return float(delta - np.hypot(pt - lt, uc - pc)), float(delta + np.hypot(ut - pt, pc - lc))


def relative_lift_ci(success_t, n_t, success_c, n_c, alpha=0.05):
    """Log-risk-ratio normal interval, shifted by -1 to relative lift.

    Zero-success arms have no finite log interval; do not invent a correction.
    """
    if n_t <= 0 or n_c <= 0 or not 0 <= success_t <= n_t or not 0 <= success_c <= n_c or not 0 < alpha < 1:
        raise ValueError("Invalid binomial counts or confidence level")
    if success_t == 0 or success_c == 0:
        return np.nan, np.nan
    log_ratio = np.log((success_t / n_t) / (success_c / n_c))
    se = np.sqrt(1 / success_t - 1 / n_t + 1 / success_c - 1 / n_c)
    half = norm.ppf(1 - alpha / 2) * se
    return float(np.exp(log_ratio - half) - 1), float(np.exp(log_ratio + half) - 1)


def continuous_smd(a, b):
    scale = np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2)
    return float((np.mean(a) - np.mean(b)) / scale) if scale else 0.0


def experiment():
    frame = load_sample()
    group_rows, rows, balance, categories, intervals = [], [], [], [], []
    for outcome in ["visit", "conversion"]:
        counts = {}
        for arm, group in frame.groupby("treatment"):
            n, positive = len(group), int(group[outcome].sum())
            lower, upper = wilson(positive, n)
            counts[int(arm)] = (positive, n)
            group_rows.append({"outcome": outcome, "outcome_label": "访问" if outcome == "visit" else "转化", "treatment": int(arm), "group_label": "实验组" if arm else "对照组", "n": n, "positive": positive, "rate": positive / n, "ci_lower": lower, "ci_upper": upper})
        st, nt = counts[1]
        sc, nc = counts[0]
        delta = st / nt - sc / nc
        lower, upper = difference_ci(st, nt, sc, nc)
        pooled = (st + sc) / (nt + nc)
        se = np.sqrt(pooled * (1 - pooled) * (1 / nt + 1 / nc))
        p_value = float(2 * norm.sf(abs(delta / se))) if se else 1.0
        rows.append({"outcome": outcome, "outcome_label": "访问" if outcome == "visit" else "转化", "n": nt + nc, "n_treatment": nt, "n_control": nc, "positive_treatment": st, "positive_control": sc, "rate_treatment": st / nt, "rate_control": sc / nc, "ate": delta, "relative_lift": delta / (sc / nc) if sc else np.nan, "ci_lower": lower, "ci_upper": upper, "p_value": p_value, "incremental_per_10000": delta * 10000, "analysis_role": "预设主指标" if outcome == "visit" else "探索性辅助指标"})
        relative_lower, relative_upper = relative_lift_ci(st, nt, sc, nc)
        effect_rows = [
            ("rate_treatment", st / nt, *wilson(st, nt), "Wilson", "proportion"),
            ("rate_control", sc / nc, *wilson(sc, nc), "Wilson", "proportion"),
            ("absolute_difference", delta, lower, upper, "Newcombe hybrid score", "proportion_difference"),
            ("relative_lift", delta / (sc / nc) if sc else np.nan, relative_lower, relative_upper, "log-risk-ratio normal, minus one", "relative_change"),
        ]
        for metric, estimate, lo, hi, method, unit in effect_rows:
            intervals.append({"outcome": outcome, "outcome_label": rows[-1]["outcome_label"], "metric": metric, "estimate": estimate, "ci_lower": lo, "ci_upper": hi, "confidence_level": 0.95, "method": method, "unit": unit, "n": nt + nc, "n_treatment": nt, "n_control": nc})
    for name in CONTINUOUS:
        t, c = frame.loc[frame.treatment == 1, name], frame.loc[frame.treatment == 0, name]
        smd = continuous_smd(t.to_numpy(), c.to_numpy())
        balance.append({"feature": name, "kind": "continuous", "metric": "absolute_SMD", "difference": abs(smd), "mean_treatment": t.mean(), "mean_control": c.mean(), "reference_threshold": 0.1, "balanced_descriptively": abs(smd) < 0.1})
    for name in CATEGORICAL:
        distribution = frame.groupby([name, "treatment"], observed=True).size().unstack(fill_value=0)
        pt = distribution[1] / distribution[1].sum()
        pc = distribution[0] / distribution[0].sum()
        tv = float((pt - pc).abs().sum() / 2)
        balance.append({"feature": name, "kind": "categorical", "metric": "total_variation_distance", "difference": tv, "mean_treatment": np.nan, "mean_control": np.nan, "reference_threshold": 0.1, "balanced_descriptively": tv < 0.1})
        for value in distribution.index:
            categories.append({"feature": name, "category_token": float(value), "n_treatment": int(distribution.loc[value, 1]), "n_control": int(distribution.loc[value, 0]), "proportion_treatment": float(pt.loc[value]), "proportion_control": float(pc.loc[value])})
    exposure = frame.groupby(["treatment", "exposure"]).agg(n=("row_id", "size"), visits=("visit", "sum"), conversions=("conversion", "sum")).reset_index()
    write_table("experiment_summary", pd.DataFrame(rows))
    write_table("experiment_groups", pd.DataFrame(group_rows))
    write_table("experiment_effect_intervals", pd.DataFrame(intervals))
    write_table("feature_balance", pd.DataFrame(balance))
    write_table("category_balance", pd.DataFrame(categories))
    write_table("exposure_description", exposure)
    logging.info("Experiment results: %s", [{"outcome": r["outcome"], "ate": r["ate"], "ci": [r["ci_lower"], r["ci_upper"]]} for r in rows])
    return pd.DataFrame(rows)
