import hashlib
import logging

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .config import FEATURES, LABELS, ROOT, SOURCE_FILE, SOURCE_ROWS, SOURCE_SHA256
from .utils import read_json, utc_now, write_json, write_table


def sample_positions(total, size, seed):
    if not 0 < size <= total:
        raise ValueError("sample-size must be between 1 and the verified source row count")
    return np.sort(np.random.default_rng(seed).choice(total, size=size, replace=False))


def assign_splits(frame, seed):
    # Exposure is post-assignment and is intentionally absent even from stratification.
    strata = frame.treatment.astype(str) + frame.visit.astype(str) + frame.conversion.astype(str)
    counts = strata.value_counts()
    if counts.min() < 10:
        raise ValueError("Too few rows in an outcome/assignment stratum; increase sample-size")
    train, remaining = train_test_split(np.arange(len(frame)), test_size=0.4, random_state=seed, stratify=strata)
    validation, test = train_test_split(remaining, test_size=0.5, random_state=seed + 1, stratify=strata.iloc[remaining])
    split = np.empty(len(frame), dtype=object)
    split[train], split[validation], split[test] = "train", "validation", "test"
    return split


def validate_chunk(frame):
    return {
        "missing_cells": int(frame.isna().sum().sum()),
        "nonfinite_features": int((~np.isfinite(frame[FEATURES].to_numpy())).sum()),
        "nonbinary_labels": int((~frame[LABELS].isin([0, 1])).sum().sum()),
        "control_exposed": int(((frame.treatment == 0) & (frame.exposure == 1)).sum()),
        "conversion_without_visit": int(((frame.conversion == 1) & (frame.visit == 0)).sum()),
    }


def prepare(sample_size=3_000_000, seed=42, chunk_size=250_000):
    source = ROOT / "data/raw" / SOURCE_FILE
    if not source.exists():
        raise FileNotFoundError("Run the download stage first")
    manifest_path = ROOT / "data/sample_manifest.json"
    output = ROOT / "data/processed/sample.parquet"
    if manifest_path.exists() and output.exists():
        old = read_json(manifest_path)
        if old.get("sample_size") == sample_size and old.get("seed") == seed and old.get("source_sha256") == SOURCE_SHA256:
            logging.info("Using verified sample manifest; rows=%s seed=%s", sample_size, seed)
            return output
    positions = sample_positions(SOURCE_ROWS, sample_size, seed)
    totals = dict.fromkeys(["missing_cells", "nonfinite_features", "nonbinary_labels", "control_exposed", "conversion_without_visit"], 0)
    dtype = {**{name: "float64" for name in FEATURES}, **{name: "int8" for name in LABELS}}
    frames, offset, treated, visited, converted = [], 0, 0, 0, 0
    for chunk_number, chunk in enumerate(pd.read_csv(source, dtype=dtype, chunksize=chunk_size)):
        if set(chunk.columns) != set(FEATURES + LABELS) or len(chunk.columns) != 16:
            raise ValueError("Unexpected source schema")
        for key, value in validate_chunk(chunk).items():
            totals[key] += value
        treated += int(chunk.treatment.sum())
        visited += int(chunk.visit.sum())
        converted += int(chunk.conversion.sum())
        start, end = np.searchsorted(positions, [offset, offset + len(chunk)])
        local_positions = positions[start:end] - offset
        part = chunk.iloc[local_positions].copy()
        part.insert(0, "row_id", positions[start:end])
        frames.append(part)
        offset += len(chunk)
        if chunk_number % 8 == 0:
            logging.info("Scanned %s source rows; sampled %s", offset, end)
    checks = [{"check": key, "scope": "full_source", "value": value, "passed": value == 0} for key, value in totals.items()]
    checks.append({"check": "source_rows_match", "scope": "full_source", "value": offset, "passed": offset == SOURCE_ROWS})
    write_table("data_quality_checks", pd.DataFrame(checks))
    if not all(check["passed"] for check in checks):
        raise ValueError("Source failed quality checks; see reports/tables/data_quality_checks.csv")
    sample = pd.concat(frames, ignore_index=True)
    if len(sample) != sample_size or not sample.row_id.is_unique:
        raise ValueError("Sampling did not produce exactly the requested unique source positions")
    sample["split"] = assign_splits(sample, seed)
    duplicate_profiles = int(sample.duplicated(subset=FEATURES + LABELS).sum())
    # Identical anonymized profiles need not represent duplicate people: retain them.
    sample.to_parquet(output, index=False, compression="zstd")
    split_counts = sample.groupby(["split", "treatment", "visit", "conversion"], observed=True).size().rename("n").reset_index()
    write_table("split_counts", split_counts)
    fingerprint = hashlib.sha256(sample.row_id.to_numpy(dtype="<i8").tobytes()).hexdigest()
    manifest = {"source_sha256": SOURCE_SHA256, "source_rows": offset, "sample_size": sample_size, "seed": seed, "sampling": "uniform_without_replacement_over_all_verified_source_positions", "positions_sha256": fingerprint, "split_counts": sample.groupby("split").size().to_dict(), "duplicate_anonymized_profiles_retained": duplicate_profiles, "source_treatment_rate": treated / offset, "source_visit_rate": visited / offset, "source_conversion_rate": converted / offset, "prepared_at": utc_now(), "parquet_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    write_json(manifest_path, manifest)
    logging.info("Prepared %s rows; splits=%s", sample_size, manifest["split_counts"])
    return output


def load_sample():
    frame = pd.read_parquet(ROOT / "data/processed/sample.parquet")
    manifest = read_json(ROOT / "data/sample_manifest.json")
    if len(frame) != manifest["sample_size"] or not frame.row_id.is_unique:
        raise ValueError("Sample integrity failed")
    return frame
