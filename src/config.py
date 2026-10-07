from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [f"f{i}" for i in range(12)]
CONTINUOUS = ["f0", "f2", "f7", "f10"]
CATEGORICAL = [x for x in FEATURES if x not in CONTINUOUS]
LABELS = ["treatment", "conversion", "visit", "exposure"]
SOURCE_ROWS = 13_979_592
SOURCE_BYTES = 311_422_618
SOURCE_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"
SOURCE_FILE = "criteo-research-uplift-v2.1.csv.gz"
SOURCE_URL = "https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/" + SOURCE_FILE
BUDGETS = [0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 1.0]


def ensure_dirs():
    for name in ["data/raw", "data/processed", "reports/tables", "reports/figures", "docs", "models", "logs", "notebooks", "sql", "powerbi", "tests"]:
        (ROOT / name).mkdir(parents=True, exist_ok=True)
