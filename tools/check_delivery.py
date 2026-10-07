"""Audit local delivery files, notebook execution, report source, and PBIX package.

Run from any directory with the project virtual environment. This writes only
reports/delivery_verification.json, with SHA256 identities of the final files.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
from zipfile import ZipFile

import nbformat
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
checks = []


def check(name, passed, detail=None):
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


for relative in ["reports/artifact_verification.json", "reports/sql_verification.json", "powerbi/desktop_verification.json", "powerbi/desktop_interaction_verification.json"]:
    data = read_json(ROOT / relative)
    check(relative, data["status"] == "PASS" and all(item["passed"] for item in data["checks"]))

status = read_json(ROOT / "powerbi/desktop_saved_status.json")
check("native_pbix_saved", any(item["currentFilePath"].replace("\\", "/").endswith("/criteo_uplift_analysis.pbix") and not item["hasUnsavedChanges"] for item in status["instances"]))

pbix = ROOT / "powerbi/criteo_uplift_analysis.pbix"
with ZipFile(pbix) as package:
    check("pbix_package_integrity", package.testzip() is None)
    check("pbix_has_native_model", "DataModel" in package.namelist() and package.getinfo("DataModel").file_size > 0)
    pages = json.loads(package.read("Report/definition/pages/pages.json").decode("utf-8-sig"))
    check("pbix_three_editable_pages", pages["pageOrder"] == ["experiment", "models", "budget"])
    for name in pages["pageOrder"]:
        visuals = [item for item in package.namelist() if item.startswith(f"Report/definition/pages/{name}/visuals/") and item.endswith("visual.json")]
        check(f"pbix_{name}_visuals", len(visuals) >= 9, len(visuals))
        image_path = ROOT / f"reports/figures/powerbi/report_{name}.png"
        with Image.open(image_path) as screenshot:
            check(f"{name}_screenshot_resolution", screenshot.size == (2892, 1624), screenshot.size)

model = read_json(ROOT / "powerbi/Criteo.SemanticModel/model.bim")["model"]
check("semantic_model_tables", len(model["tables"]) == 13)
measures = next(table for table in model["tables"] if table["name"] == "Metrics")["measures"]
check("saved_dax_catalog_complete", len(measures) == 39 and all(measure["name"] + " =" in (ROOT / "powerbi/measures.dax").read_text(encoding="utf-8") for measure in measures))
intervals = pd.read_csv(ROOT / "reports/tables/experiment_effect_intervals.csv")
check("complete_experiment_intervals", len(intervals) == 8 and set(intervals.metric) == {"rate_treatment", "rate_control", "absolute_difference", "relative_lift"} and (intervals.ci_lower <= intervals.estimate).all() and (intervals.estimate <= intervals.ci_upper).all())
check("experiment_interval_population", (intervals.n == 3000000).all() and (intervals.confidence_level == .95).all())

notebook_paths = sorted((ROOT / "notebooks").glob("*.ipynb"))
check("two_notebooks", len(notebook_paths) == 2)
for path in notebook_paths:
    notebook = nbformat.read(path, as_version=4)
    cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    check(path.name + "_executed", all(cell.execution_count is not None and not any(output.output_type == "error" for output in cell.outputs) for cell in cells), len(cells))
check("nine_learning_stages", len(list((ROOT / "docs").glob("learning_stage_*.md"))) == 9)

documents = [ROOT / "README.md", ROOT / "NOTICE.md", ROOT / "data/README.md", ROOT / "powerbi/README.md", *sorted((ROOT / "docs").glob("*.md")), *sorted((ROOT / "reports").glob("*.md"))]
missing = []
for path in documents:
    content = path.read_text(encoding="utf-8")
    check(path.relative_to(ROOT).as_posix() + "_substantial", len(content) > 150)
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
        if target.startswith(("http:", "https:", "mailto:", "#")):
            continue
        target = target.strip("<>").split("#")[0]
        if not (path.parent / target).exists():
            missing.append({"document": path.relative_to(ROOT).as_posix(), "target": target})
check("local_document_links", not missing, missing)
validation = read_json(ROOT / "powerbi/validation_offline.json")["data"]
check("official_local_structure_validation", validation["errorCount"] == validation["warningCount"] == 0)
online = read_json(ROOT / "powerbi/validation.json")["data"]
check("online_validation_no_errors", online["errorCount"] == 0, {"warningCount": online["warningCount"], "scope": "remote schema availability warnings retained"})

identity_files = [*documents, pbix, ROOT / "requirements.txt", ROOT / "requirements.in", ROOT / "powerbi/Criteo.pbip", ROOT / "powerbi/measures.dax", ROOT / "data/source_manifest.json", ROOT / "data/sample_manifest.json", *sorted((ROOT / "src").glob("*.py")), *sorted((ROOT / "tests").glob("*.py")), *sorted((ROOT / "sql").glob("*.sql")), *sorted((ROOT / "powerbi").glob("*.py")), *sorted((ROOT / "powerbi").glob("*.mjs")), *sorted((ROOT / "powerbi").glob("*.ps1")), *sorted((ROOT / "powerbi/Criteo.Report").rglob("*.json")), *sorted((ROOT / "powerbi/Criteo.SemanticModel").glob("*.bim")), *sorted((ROOT / "notebooks").glob("*.ipynb")), *sorted((ROOT / "reports/tables").glob("*.csv")), *sorted((ROOT / "reports/figures/powerbi").glob("report_*.png"))]
identity_files = [path for path in identity_files if ".pbi" not in path.relative_to(ROOT).parts]
files = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in identity_files]
output = {"status": "PASS" if all(item["passed"] for item in checks) else "FAIL", "checked_at": datetime.now(timezone.utc).isoformat(), "checks": checks, "files": files}
(ROOT / "reports/delivery_verification.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Delivery: {sum(item['passed'] for item in checks)}/{len(checks)} passed; {len(files)} file identities saved")
if output["status"] != "PASS":
    raise AssertionError([item for item in checks if not item["passed"]])
