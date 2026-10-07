import logging

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from .config import BUDGETS, ROOT
from .metrics import adjusted_outcome, bootstrap_fixed_rankings, gain_curve
from .utils import write_json, write_table


def interval(values):
    return np.quantile(values, [0.025, 0.975], axis=0)


def evaluate(seed=42, n_bootstrap=500):
    model_rows, curves, budgets, deciles, winners, uncertainty = [], [], [], [], {}, []
    fractions = np.unique(np.round(np.r_[np.linspace(0, 1, 101), BUDGETS], 12))
    for outcome in ["visit", "conversion"]:
        predictions = pd.read_parquet(ROOT / "data/processed" / f"predictions_{outcome}.parquet")
        names = [column.removeprefix("score_") for column in predictions if column.startswith("score_")]
        validation = predictions.loc[predictions.split == "validation"]
        validation_metrics = {}
        # Model selection is completed BEFORE looking at any test outcome metrics.
        for name in names:
            value = gain_curve(validation[outcome].to_numpy(), validation.treatment.to_numpy(), validation[f"score_{name}"].to_numpy(), validation.row_id.to_numpy(), fractions, seed)
            validation_metrics[name] = value
        eligible = [name for name in names if name != "response"]
        winner = max(eligible, key=lambda name: (validation_metrics[name]["qini"], name))
        winners[outcome] = {"model": winner, "validation_qini": validation_metrics[winner]["qini"], "selection_set": "validation", "criterion": "normalized Qini area", "primary": outcome == "visit"}
        write_json(ROOT / "models/model_selection.json", winners)
        logging.info("Locked %s winner: %s (validation Qini %.8f)", outcome, winner, validation_metrics[winner]["qini"])
        test = predictions.loc[predictions.split == "test"]
        y, t, ids = test[outcome].to_numpy(), test.treatment.to_numpy(), test.row_id.to_numpy()
        scores = {name: test[f"score_{name}"].to_numpy() for name in names}
        draws = bootstrap_fixed_rankings(y, t, scores, ids, fractions, n_bootstrap, seed)
        n, p = len(test), float(t.mean())
        full_ate = float(adjusted_outcome(y, t).mean())
        random_draws = fractions[None, :] * draws["response"][:, -1, None]
        integral = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
        test_metrics = {name: gain_curve(y, t, scores[name], ids, fractions, seed) for name in names}
        for split, values, subset in [("validation", validation_metrics, validation), ("test", test_metrics, test)]:
            for name, value in values.items():
                index20 = int(np.flatnonzero(fractions == 0.2)[0])
                record = {"outcome": outcome, "model": name, "split": split, "n": len(subset), "auuc": value["auuc"], "qini": value["qini"], "gain_at_20": float(value["gain"][index20]), "incremental_per_10000_at_20": float(value["gain"][index20]) * 10000, "selected_on_validation": name == winner, "response_roc_auc": roc_auc_score(subset[outcome], subset[f"score_{name}"]) if name == "response" else np.nan, "response_pr_auc": average_precision_score(subset[outcome], subset[f"score_{name}"]) if name == "response" else np.nan}
                if split == "test":
                    lower, upper = interval(integral(draws[name] - random_draws, fractions, axis=1))
                    record.update(qini_ci_lower=float(lower), qini_ci_upper=float(upper))
                model_rows.append(record)
        for name, value in test_metrics.items():
            lower, upper = interval(draws[name])
            dlower, dupper = interval(draws[name] - random_draws)
            rlower, rupper = interval(draws[name] - draws["response"])
            for j, fraction in enumerate(fractions):
                curves.append({"outcome": outcome, "model": name, "split": "test", "n": n, "budget_fraction": float(fraction), "targeted_n": int(value["counts"][j]), "gain": float(value["gain"][j]), "random_gain": float(value["random_gain"][j]), "gain_vs_random": float(value["gain"][j] - value["random_gain"][j]), "ci_lower": float(lower[j]), "ci_upper": float(upper[j]), "vs_random_ci_lower": float(dlower[j]), "vs_random_ci_upper": float(dupper[j]), "vs_response_ci_lower": float(rlower[j]), "vs_response_ci_upper": float(rupper[j]), "selected_model": name == winner})
            order = value["order"]
            for decile in range(10):
                selected = order[int(decile * n / 10):int((decile + 1) * n / 10)]
                nt, nc = int((t[selected] == 1).sum()), int((t[selected] == 0).sum())
                st, sc = int(y[selected][t[selected] == 1].sum()), int(y[selected][t[selected] == 0].sum())
                deciles.append({"outcome": outcome, "model": name, "decile": decile + 1, "n": len(selected), "n_treatment": nt, "n_control": nc, "positive_treatment": st, "positive_control": sc, "rate_treatment": st / nt if nt else np.nan, "rate_control": sc / nc if nc else np.nan, "observed_rate_difference": st / nt - sc / nc if nt and nc else np.nan, "ipw_uplift": float(adjusted_outcome(y, t)[selected].sum() / len(selected)), "mean_predicted_score": float(scores[name][selected].mean()), "low_outcome_support": min(st, sc) < 30, "selected_model": name == winner})
        for strategy in ["no_treatment", "all_treatment", "random", "response", "uplift"]:
            model_name = winner if strategy == "uplift" else "response" if strategy == "response" else "none"
            allowed = [0.0] if strategy == "no_treatment" else [1.0] if strategy == "all_treatment" else BUDGETS
            for fraction in allowed:
                j = int(np.flatnonzero(fractions == fraction)[0])
                if strategy in ["random", "all_treatment", "no_treatment"]:
                    gain = fraction * full_ate
                    samples = random_draws[:, j]
                    difference = np.zeros(n_bootstrap)
                else:
                    gain = float(test_metrics[model_name]["gain"][j])
                    samples = draws[model_name][:, j]
                    difference = samples - random_draws[:, j]
                lower, upper = interval(samples)
                dlow, dhigh = interval(difference)
                budgets.append({"outcome": outcome, "strategy": strategy, "model": model_name, "budget_fraction": fraction, "evaluation_n": n, "targeted_n": int(np.floor(fraction * n + 1e-8)), "gain": gain, "incremental_per_10000": gain * 10000, "ci_lower_per_10000": float(lower) * 10000, "ci_upper_per_10000": float(upper) * 10000, "vs_random_per_10000": (gain - fraction * full_ate) * 10000, "vs_random_ci_lower_per_10000": float(dlow) * 10000, "vs_random_ci_upper_per_10000": float(dhigh) * 10000, "incremental_per_1000_targeted": gain / fraction * 1000 if fraction else np.nan, "normalized_cost_per_10000": fraction * 10000, "default_budget": fraction == 0.2})
        for name in names:
            j = int(np.flatnonzero(fractions == 0.2)[0])
            lo, hi = interval(draws[name][:, j] - random_draws[:, j])
            rlo, rhi = interval(draws[name][:, j] - draws["response"][:, j])
            uncertainty.append({"outcome": outcome, "model": name, "budget_fraction": 0.2, "paired_vs_random_ci_lower": float(lo), "paired_vs_random_ci_upper": float(hi), "paired_vs_response_ci_lower": float(rlo), "paired_vs_response_ci_upper": float(rhi), "n_bootstrap": n_bootstrap, "interval_scope": "conditional_on_fitted_models_and_fixed_topK_masks"})
        logging.info("Evaluated %s: test n=%d; 500-replicate paired intervals completed", outcome, n)
    write_table("model_evaluation", pd.DataFrame(model_rows))
    write_table("uplift_curves", pd.DataFrame(curves))
    write_table("budget_strategies", pd.DataFrame(budgets))
    write_table("decile_profiles", pd.DataFrame(deciles))
    write_table("paired_uncertainty", pd.DataFrame(uncertainty))
    write_json(ROOT / "reports/evaluation_protocol.json", {"primary_outcome": "visit", "secondary_outcome": "conversion", "selection": winners, "seed": seed, "bootstrap_replicates": n_bootstrap, "budgets_prespecified": BUDGETS, "default_budget": 0.2, "propensity": "each evaluation split's global empirical treatment ratio, fixed across its Top-K points", "gain_formula": "G(q) = sum_{top_q} Y*(T/p-(1-T)/(1-p))/N", "auuc_formula": "integral_0^1 G(q) dq", "qini_formula": "integral_0^1 [G(q)-q*G(1)] dq", "random_strategy": "expected performance q*G(1), not a lucky single random draw", "bootstrap": "exact multinomial treatment-stratified paired resampling; fixed model scores and Top-K memberships; does not include retraining uncertainty", "source_context": "public, nonuniformly sampled benchmark; no reconstruction of original campaigns or real ROI"})
