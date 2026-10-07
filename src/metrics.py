"""A single treatment-adjusted gain convention shared by every strategy."""
import numpy as np


def tie_keys(row_ids, seed=42):
    values = np.asarray(row_ids, dtype=np.uint64) ^ np.uint64(seed)
    # Stateless hashing avoids favoring source file order when scores tie.
    values = (values ^ (values >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
    values = (values ^ (values >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    return values ^ (values >> np.uint64(31))


def rank_scores(scores, row_ids, seed=42):
    if not np.isfinite(scores).all():
        raise ValueError("Scores must be finite")
    return np.lexsort((tie_keys(row_ids, seed), -np.asarray(scores)))


def adjusted_outcome(y, t):
    y, t = np.asarray(y), np.asarray(t)
    if len(y) != len(t) or len(y) == 0 or not np.isin(t, [0, 1]).all() or not np.isin(y, [0, 1]).all():
        raise ValueError("Binary, nonempty, equal-length outcome / treatment arrays required")
    p = t.mean()
    if not 0 < p < 1:
        raise ValueError("Both treatment arms are required")
    return y * (t / p - (1 - t) / (1 - p))


def gain_curve(y, t, scores, row_ids, fractions=None, seed=42):
    fractions = np.linspace(0, 1, 101) if fractions is None else np.asarray(fractions)
    if np.any((fractions < 0) | (fractions > 1)):
        raise ValueError("Fractions must be in [0,1]")
    order = rank_scores(scores, row_ids, seed)
    transformed = adjusted_outcome(y, t)
    cumulative = np.r_[0.0, np.cumsum(transformed[order])] / len(y)
    # Full targeting is independent of rank. Avoid accumulation-order roundoff
    # appearing as a nonzero advantage over random at the 100% boundary.
    cumulative[-1] = float(transformed.mean())
    counts = np.floor(fractions * len(y) + 1e-8).astype(int)
    gain = cumulative[counts]
    random_gain = fractions * cumulative[-1]
    trapezoid = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    return {"fractions": fractions, "gain": gain, "random_gain": random_gain, "auuc": float(trapezoid(gain, fractions)), "qini": float(trapezoid(gain - random_gain, fractions)), "order": order, "counts": counts}


def bootstrap_fixed_rankings(y, t, scores_by_model, row_ids, fractions, n_bootstrap=500, seed=42):
    """Exact arm-stratified resampling for fixed score thresholds / memberships.

    Only outcome-positive rows contribute to the IPW numerator. Aggregating all
    outcome-negative rows into one residual multinomial category is EXACT, not
    a Poisson approximation. Every model uses identical resampling weights.
    Intervals condition on fitted models and the observed Top-K masks.
    """
    y, t, fractions = np.asarray(y), np.asarray(t), np.asarray(fractions)
    adjusted_outcome(y, t)  # validates both arms
    n, p = len(y), t.mean()
    positives = np.flatnonzero(y == 1)
    positive_t = t[positives]
    ranks = {}
    for name, scores in scores_by_model.items():
        order = rank_scores(scores, row_ids, seed)
        inverse = np.empty(n, dtype=int)
        inverse[order] = np.arange(n)
        # The first evaluation point including each positive row.
        bins = np.searchsorted(np.floor(fractions * n + 1e-8).astype(int), inverse[positives] + 1, side="left")
        ranks[name] = bins
    rng = np.random.default_rng(seed + 1000)
    draws = {name: np.empty((n_bootstrap, len(fractions))) for name in scores_by_model}
    coefficients = np.where(positive_t == 1, 1 / p, -1 / (1 - p)) / n
    for iteration in range(n_bootstrap):
        weights = np.zeros(len(positives), dtype=float)
        for arm in [0, 1]:
            mask = positive_t == arm
            na, ma = int((t == arm).sum()), int(mask.sum())
            probabilities = np.r_[np.full(ma, 1 / na), max(0.0, 1 - ma / na)]
            probabilities /= probabilities.sum()
            weights[mask] = rng.multinomial(na, probabilities)[:-1]
        weighted = weights * coefficients
        full_gain = float(weighted.sum())
        for name, bins in ranks.items():
            draws[name][iteration] = np.cumsum(np.bincount(bins, weights=weighted, minlength=len(fractions) + 1))[:len(fractions)]
            draws[name][iteration, np.floor(fractions * n + 1e-8).astype(int) == n] = full_gain
    return draws
