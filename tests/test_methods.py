import numpy as np
import pandas as pd
import pytest

from src.config import CATEGORICAL, FEATURES
from src.data import assign_splits, sample_positions, validate_chunk
from src.experiment import difference_ci, relative_lift_ci, wilson
from src.metrics import adjusted_outcome, bootstrap_fixed_rankings, gain_curve, rank_scores
from src.models import FeatureEncoder


def test_uniform_sample_is_reproducible_and_spans_source():
    a = sample_positions(10000, 1000, 42)
    np.testing.assert_array_equal(a, sample_positions(10000, 1000, 42))
    assert len(np.unique(a)) == 1000 and a[0] < 100 and a[-1] > 9900
    assert not np.array_equal(a, sample_positions(10000, 1000, 43))


@pytest.mark.parametrize("size", [0, -1, 10001])
def test_invalid_sample_size(size):
    with pytest.raises(ValueError):
        sample_positions(10000, size, 42)


def test_splits_keep_all_rows_and_all_joint_strata():
    frame = pd.DataFrame({"treatment": np.tile([0, 1], 300), "visit": np.tile([0, 0, 1, 1, 1, 1], 100), "conversion": np.tile([0, 0, 0, 0, 1, 1], 100)})
    labels = assign_splits(frame, 42)
    assert pd.Series(labels).value_counts().to_dict() == {"train": 360, "validation": 120, "test": 120}
    np.testing.assert_array_equal(labels, assign_splits(frame, 42))
    for split in ["train", "validation", "test"]:
        assert len(frame.loc[labels == split].groupby(["treatment", "visit", "conversion"])) == 6


def test_wilson_boundary_and_newcombe_difference():
    lower, upper = wilson(0, 100)
    assert abs(lower) < 1e-12 and 0 < upper < 0.04
    lower, upper = wilson(100, 100)
    assert lower > 0.96 and abs(upper - 1) < 1e-12
    lower, upper = difference_ci(3000, 10000, 2000, 10000)
    assert 0.08 < lower < 0.1 < upper < 0.12


def test_relative_lift_interval_reciprocity_and_undefined_zero_events():
    lo, hi = relative_lift_ci(300, 1000, 200, 1000)
    swapped_lo, swapped_hi = relative_lift_ci(200, 1000, 300, 1000)
    assert 0 < lo < 0.5 < hi
    assert swapped_lo + 1 == pytest.approx(1 / (hi + 1))
    assert swapped_hi + 1 == pytest.approx(1 / (lo + 1))
    assert np.isnan(relative_lift_ci(0, 100, 20, 100)).all()
    with pytest.raises(ValueError):
        relative_lift_ci(120, 100, 20, 100)


def test_ipw_adjusts_unequal_arms_and_full_endpoint_matches_rate_difference():
    t, y = np.array([1, 0, 1, 1, 0, 1]), np.array([1, 0, 0, 1, 1, 0])
    curve = gain_curve(y, t, np.arange(6, 0, -1), np.arange(6), [0, 0.5, 1])
    np.testing.assert_allclose(curve["gain"], [0, 0.25, 0], atol=1e-12)
    assert curve["gain"][-1] == pytest.approx(y[t == 1].mean() - y[t == 0].mean())


@pytest.mark.parametrize("t", [np.ones(8), np.zeros(8), np.array([0, 1, 2, 0, 1, 1, 0, 0])])
def test_missing_or_invalid_treatment_arm_is_rejected(t):
    with pytest.raises(ValueError):
        adjusted_outcome(np.ones(8), t)


def test_tied_ranking_is_independent_of_input_row_order():
    ids, scores = np.arange(100), np.ones(100)
    permutation = np.random.default_rng(42).permutation(100)
    ranked_a = ids[rank_scores(scores, ids)]
    ranked_b = ids[permutation][rank_scores(scores[permutation], ids[permutation])]
    np.testing.assert_array_equal(ranked_a, ranked_b)


def test_out_of_range_budget_rejected():
    with pytest.raises(ValueError):
        gain_curve(np.array([0, 1]), np.array([0, 1]), np.array([0.2, 0.3]), np.arange(2), [1.1])


def test_paired_bootstrap_same_policy_has_exactly_zero_difference():
    t, y = np.array([1, 0, 1, 1, 0, 1]), np.array([1, 0, 0, 1, 1, 0])
    scores = np.arange(6, 0, -1)
    draws = bootstrap_fixed_rankings(y, t, {"a": scores, "b": scores}, np.arange(6), np.array([0, 0.5, 1]), 2000, 42)
    np.testing.assert_array_equal(draws["a"], draws["b"])
    np.testing.assert_allclose(draws["a"][:, 0], 0)
    assert draws["a"][:, 1].mean() == pytest.approx(0.25, abs=0.015)
    assert draws["a"][:, -1].mean() == pytest.approx(0, abs=0.03)


def test_randomized_synthetic_known_ate_and_targeting_advantage():
    rng = np.random.default_rng(11)
    n = 200000
    group = rng.integers(0, 2, n)
    treatment = (rng.random(n) < 0.85).astype(int)
    true_effect = np.where(group == 1, 0.2, 0.0)
    outcome = (rng.random(n) < (0.2 + treatment * true_effect)).astype(int)
    curve = gain_curve(outcome, treatment, true_effect, np.arange(n), [0, 0.5, 1])
    assert curve["gain"][-1] == pytest.approx(0.1, abs=0.006)
    assert curve["gain"][1] > curve["random_gain"][1] + 0.04


def test_full_budget_is_same_policy_for_opposite_rankings():
    rng = np.random.default_rng(73)
    t = (rng.random(20000) < 0.85).astype(int)
    y = (rng.random(20000) < (0.2 + 0.1 * t)).astype(int)
    scores = rng.random(len(t))
    ids = np.arange(len(t))
    forward = gain_curve(y, t, scores, ids, [0, 0.2, 1])
    reverse = gain_curve(y, t, -scores, ids, [0, 0.2, 1])
    assert forward["gain"][-1] == reverse["gain"][-1]
    assert forward["gain"][-1] - forward["random_gain"][-1] == 0
    draws = bootstrap_fixed_rankings(y, t, {"a": scores, "b": -scores}, ids, np.array([0, 0.2, 1]), 30, 42)
    np.testing.assert_array_equal(draws["a"][:, -1], draws["b"][:, -1])


def test_encoder_preserves_nominal_tokens_and_never_adds_post_treatment_fields():
    training = pd.DataFrame({name: [1.25, 2.5, 1.25] for name in FEATURES})
    training["exposure"], training["visit"], training["conversion"] = 1, 1, 1
    encoder = FeatureEncoder().fit(training)
    test = training.copy()
    test.loc[0, CATEGORICAL[0]] = 900.0
    encoded = encoder.transform(test)
    assert list(encoded) == FEATURES
    assert pd.isna(encoded.loc[0, CATEGORICAL[0]])
    assert encoder.categories[CATEGORICAL[0]] == [1.25, 2.5]


def test_quality_checks_detect_structural_violations():
    frame = pd.DataFrame({name: [0.0, 0.0] for name in FEATURES})
    frame["treatment"], frame["exposure"], frame["visit"], frame["conversion"] = [0, 1], [1, 1], [0, 0], [1, 0]
    values = validate_chunk(frame)
    assert values["control_exposed"] == 1 and values["conversion_without_visit"] == 1
