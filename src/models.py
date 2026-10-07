"""Small, explicit meta-learners; no causal-library black box is required."""
import logging
import os

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from .config import CATEGORICAL, CONTINUOUS, FEATURES, ROOT
from .data import load_sample
from .utils import write_json, write_table


class FeatureEncoder:
    def fit(self, frame):
        self.categories = {name: sorted(frame[name].dropna().unique().tolist()) for name in CATEGORICAL}
        return self

    def transform(self, frame):
        result = frame[FEATURES].copy()
        for name in CONTINUOUS:
            result[name] = result[name].astype("float32")
        for name in CATEGORICAL:
            result[name] = pd.Categorical(result[name], categories=self.categories[name])
        return result


def parameters(seed, regression=False):
    return dict(objective="regression" if regression else "binary", n_estimators=600, learning_rate=0.05, num_leaves=31, min_child_samples=200, reg_lambda=2.0, verbosity=-1, random_state=seed, n_jobs=min(8, os.cpu_count() or 1), deterministic=True, force_col_wise=True)


def fit_model(x, y, vx, vy, seed, regression=False):
    model = (lgb.LGBMRegressor if regression else lgb.LGBMClassifier)(**parameters(seed, regression))
    model.fit(x, y, eval_set=[(vx, vy)], eval_metric="l2" if regression else "binary_logloss", callbacks=[lgb.early_stopping(50, verbose=False)])
    return model


def predict_scores(artifact, x):
    s1, s0 = x.copy(), x.copy()
    s1["treatment"], s0["treatment"] = np.int8(1), np.int8(0)
    mu0 = artifact["t0"].predict_proba(x)[:, 1]
    mu1 = artifact["t1"].predict_proba(x)[:, 1]
    scores = {"s_learner": artifact["s"].predict_proba(s1)[:, 1] - artifact["s"].predict_proba(s0)[:, 1], "t_learner": mu1 - mu0, "response": artifact["response"].predict_proba(x)[:, 1]}
    if "x0" in artifact:
        p = artifact["treatment_ratio_train"]
        scores["x_learner"] = p * artifact["x0"].predict(x) + (1 - p) * artifact["x1"].predict(x)
    return scores


def train(seed=42):
    frame = load_sample()
    training, validation = frame.loc[frame.split == "train"], frame.loc[frame.split == "validation"]
    encoder = FeatureEncoder().fit(training)
    x, vx = encoder.transform(training), encoder.transform(validation)
    tx, tv = training.treatment.to_numpy(), validation.treatment.to_numpy()
    joblib.dump(encoder, ROOT / "models/encoder.joblib")
    write_json(ROOT / "models/feature_encoder.json", {"continuous_features": CONTINUOUS, "categorical_features": CATEGORICAL, "train_categories": encoder.categories, "unseen_category": "missing", "prohibited_predictors": ["exposure", "visit", "conversion", "row_id", "split"]})
    training_records, importance = [], []
    for outcome in ["visit", "conversion"]:
        y, vy = training[outcome].to_numpy(), validation[outcome].to_numpy()
        artifact_path = ROOT / "models" / f"{outcome}_learners.joblib"
        logging.info("Training %s learners; train=%d validation=%d", outcome, len(x), len(vx))
        artifact = {"treatment_ratio_train": float(tx.mean()), "outcome": outcome}
        sx, svx = x.copy(), vx.copy()
        sx["treatment"], svx["treatment"] = tx, tv
        logging.info("%s: S-Learner", outcome)
        artifact["s"] = fit_model(sx, y, svx, vy, seed)
        for arm in [0, 1]:
            logging.info("%s: T-Learner arm %d", outcome, arm)
            artifact[f"t{arm}"] = fit_model(x.loc[tx == arm], y[tx == arm], vx.loc[tv == arm], vy[tv == arm], seed + arm)
        logging.info("%s: ordinary response baseline", outcome)
        artifact["response"] = fit_model(x, y, vx, vy, seed + 3)
        if outcome == "visit":
            # Opposite-arm outcome models cannot see the labels used as pseudo-outcomes.
            d0 = artifact["t1"].predict_proba(x.loc[tx == 0])[:, 1] - y[tx == 0]
            d1 = y[tx == 1] - artifact["t0"].predict_proba(x.loc[tx == 1])[:, 1]
            vd0 = artifact["t1"].predict_proba(vx.loc[tv == 0])[:, 1] - vy[tv == 0]
            vd1 = vy[tv == 1] - artifact["t0"].predict_proba(vx.loc[tv == 1])[:, 1]
            for arm, d, vd in [(0, d0, vd0), (1, d1, vd1)]:
                logging.info("%s: X-Learner effect model %d", outcome, arm)
                artifact[f"x{arm}"] = fit_model(x.loc[tx == arm], d, vx.loc[tv == arm], vd, seed + 5 + arm, regression=True)
        joblib.dump(artifact, artifact_path, compress=3)
        for key, model in artifact.items():
            if hasattr(model, "booster_"):
                model.booster_.save_model(str(ROOT / "models" / f"{outcome}_{key}.txt"))
                training_records.append({"outcome": outcome, "component": key, "best_iteration": model.best_iteration_, "n_features": model.n_features_in_, "objective": model.get_params()["objective"]})
        gain = (artifact["t0"].booster_.feature_importance(importance_type="gain") + artifact["t1"].booster_.feature_importance(importance_type="gain")) / 2
        for name, value in zip(FEATURES, gain / max(gain.sum(), 1e-12)):
            importance.append({"outcome": outcome, "feature": name, "response_gain_importance": float(value), "interpretation": "响应预测关联；不表示特征因果效应"})
        predictions = []
        for split in ["validation", "test"]:
            subset = frame.loc[frame.split == split]
            scores = predict_scores(artifact, encoder.transform(subset))
            result = subset[["row_id", "treatment", "visit", "conversion", "split"]].copy()
            for name, score in scores.items():
                if not np.isfinite(score).all():
                    raise ValueError("Non-finite model scores")
                result[f"score_{name}"] = score
            predictions.append(result)
        pd.concat(predictions, ignore_index=True).to_parquet(ROOT / "data/processed" / f"predictions_{outcome}.parquet", index=False, compression="zstd")
        write_table("training_iterations", pd.DataFrame(training_records))
        write_table("feature_importance", pd.DataFrame(importance))
        logging.info("Saved %s models and held-out predictions", outcome)
    write_json(ROOT / "models/training_config.json", {"seed": seed, "fixed_parameters": parameters(seed), "primary_outcome": "visit", "secondary_outcome": "conversion", "class_rebalancing": "none; preserve probability estimation", "early_stopping": {"rounds": 50, "criterion": "validation loss"}, "selection": "validation Qini, only among uplift learners", "training_rows": len(training), "validation_rows": len(validation)})
