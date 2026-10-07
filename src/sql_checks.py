import duckdb
import numpy as np
import pandas as pd

from .config import ROOT
from .data import load_sample
from .utils import write_json, write_table


def sql_checks():
    connection = duckdb.connect()
    source = (ROOT / "data/processed/sample.parquet").as_posix().replace("'", "''")
    connection.execute(f"CREATE VIEW sample AS SELECT * FROM read_parquet('{source}')")
    results = {}
    for name in ["01_quality_checks", "02_experiment_metrics", "03_split_checks"]:
        query = (ROOT / "sql" / f"{name}.sql").read_text(encoding="utf-8")
        results[name] = connection.execute(query).df()
        write_table("sql_" + name, results[name])
    sample = load_sample()
    quality = results["01_quality_checks"].iloc[0]
    checks = [{"check": "sql_row_count", "passed": int(quality.n) == len(sample)}, {"check": "sql_unique_ids", "passed": int(quality.unique_rows) == len(sample)}, {"check": "sql_logical_constraints", "passed": int(quality.control_exposed) == 0 and int(quality.conversion_without_visit) == 0}]
    sql_summary = results["02_experiment_metrics"]
    python_summary = pd.read_csv(ROOT / "reports/tables/experiment_summary.csv")
    for _, row in python_summary.iterrows():
        metric = sql_summary.loc[sql_summary.outcome == row.outcome].iloc[0]
        checks.extend([{"check": f"{row.outcome}_sql_ate", "passed": bool(np.isclose(metric.ate, row.ate, atol=1e-12))}, {"check": f"{row.outcome}_sql_counts", "passed": int(metric.n_treatment) == int(row.n_treatment) and int(metric.n_control) == int(row.n_control)}])
    write_json(ROOT / "reports/sql_verification.json", {"status": "PASS" if all(x["passed"] for x in checks) else "FAIL", "checks": checks})
    connection.close()
    if not all(x["passed"] for x in checks):
        raise AssertionError("SQL and Python reconciliation failed")
    return checks
