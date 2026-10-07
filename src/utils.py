import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT, ensure_dirs


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    def encode(value):
        if hasattr(value, "item"):
            return value.item()
        if isinstance(value, Path):
            return str(value)
        raise TypeError(type(value).__name__)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=encode, allow_nan=False), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_table(name, frame):
    path = ROOT / "reports/tables" / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.12g")
    return path


def configure_logging():
    ensure_dirs()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "logs/pipeline.log", encoding="utf-8")], force=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat()
