import hashlib

import numpy as np
import pandas as pd

from .config import FEATURES, ROOT, SOURCE_SHA256
from .data import load_sample
from .metrics import adjusted_outcome
from .utils import read_json, write_json


def verify_artifacts():
    sample = load_sample()
    manifest = read_json(ROOT / "data/sample_manifest.json")
    checks = []
    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})
    check("source_hash_identity", read_json(ROOT / "data/source_manifest.json")["sha256"] == SOURCE_SHA256)
    check("sample_file_sha256", hashlib.sha256((ROOT / "data/processed/sample.parquet").read_bytes()).hexdigest() == manifest["parquet_sha256"])
    check("sample_positions_sha256", hashlib.sha256(sample.row_id.to_numpy(dtype="<i8").tobytes()).hexdigest() == manifest["positions_sha256"])
    check("split_proportions", sample.groupby("split").size().to_dict() == manifest["split_counts"])
    check("finite_features", np.isfinite(sample[FEATURES].to_numpy()).all())
    encoder = read_json(ROOT / "models/feature_encoder.json")
    check("twelve_pre_assignment_predictors", set(encoder["continuous_features"] + encoder["categorical_features"]) == set(FEATURES))
    curves = pd.read_csv(ROOT / "reports/tables/uplift_curves.csv")
    choices = read_json(ROOT / "models/model_selection.json")
    model_metrics = pd.read_csv(ROOT / "reports/tables/model_evaluation.csv")
    for outcome in ["visit", "conversion"]:
        predictions = pd.read_parquet(ROOT / "data/processed" / f"predictions_{outcome}.parquet")
        expected = sample.loc[sample.split.isin(["validation", "test"]), ["row_id", "split", "treatment", "visit", "conversion"]]
        merged = expected.merge(predictions, on="row_id", suffixes=("_source", "_prediction"), validate="one_to_one")
        check(outcome + "_heldout_ids", len(merged) == len(expected) == len(predictions))
        for column in ["split", "treatment", "visit", "conversion"]:
            check(outcome + "_labels_" + column, merged[column + "_source"].equals(merged[column + "_prediction"]))
        check(outcome + "_validation_test_disjoint", set(predictions.loc[predictions.split == "validation", "row_id"]).isdisjoint(predictions.loc[predictions.split == "test", "row_id"]))
        test = predictions.loc[predictions.split == "test"]
        ate = adjusted_outcome(test[outcome].to_numpy(), test.treatment.to_numpy()).mean()
        for name in [column.removeprefix("score_") for column in predictions if column.startswith("score_")]:
            check(outcome + "_finite_" + name, np.isfinite(predictions["score_" + name]).all())
            subset = curves.loc[(curves.outcome == outcome) & (curves.model == name)]
            check(outcome + "_zero_budget_" + name, abs(float(subset.loc[subset.budget_fraction == 0, "gain"].iloc[0])) < 1e-12)
            check(outcome + "_full_budget_" + name, np.isclose(float(subset.loc[subset.budget_fraction == 1, "gain"].iloc[0]), ate, atol=1e-12))
        validation = model_metrics.loc[(model_metrics.outcome == outcome) & (model_metrics.split == "validation") & (model_metrics.model != "response")]
        best = validation.sort_values(["qini", "model"], ascending=[False, False]).iloc[0].model
        check(outcome + "_validation_selection", choices[outcome]["model"] == best)
    budgets = pd.read_csv(ROOT / "reports/tables/budget_strategies.csv")
    check("normalized_cost", np.allclose(budgets.normalized_cost_per_10000, budgets.budget_fraction * 10000))
    zero = budgets.loc[budgets.budget_fraction == 0]
    check("zero_budget_no_effect_or_efficiency", np.allclose(zero.gain, 0) and zero.incremental_per_1000_targeted.isna().all())
    for column in ["incremental_per_10000", "ci_lower_per_10000", "ci_upper_per_10000"]:
        check(column + "_finite", np.isfinite(budgets[column]).all())
    status = "PASS" if all(x["passed"] for x in checks) else "FAIL"
    write_json(ROOT / "reports/artifact_verification.json", {"status": status, "checks": checks, "n_checks": len(checks)})
    if status != "PASS":
        raise AssertionError([x["check"] for x in checks if not x["passed"]])
    print(f"Artifact reconciliation: {len(checks)}/{len(checks)} passed")
    return checks
