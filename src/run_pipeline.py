import argparse
import logging
import time

from .config import ROOT
from .utils import configure_logging, read_json, utc_now, write_json


def main():
    parser = argparse.ArgumentParser(description="Criteo v2.1 reproducible incrementality pipeline")
    parser.add_argument("--stage", choices=["all", "download", "prepare", "experiment", "train", "evaluate", "report", "verify"], default="all")
    parser.add_argument("--sample-size", type=int, default=3_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap", type=int, default=500)
    args = parser.parse_args()
    configure_logging()
    write_json(ROOT / "run_config.json", {**vars(args), "started_at": utc_now()})
    stages = ["download", "prepare", "experiment", "train", "evaluate", "report", "verify"] if args.stage == "all" else [args.stage]
    timing_path = ROOT / "reports/stage_timings.json"
    timings = read_json(timing_path) if timing_path.exists() else {}
    for stage in stages:
        started = time.perf_counter()
        logging.info("START stage %s", stage)
        if stage == "download":
            from .download import download
            download()
        elif stage == "prepare":
            from .data import prepare
            prepare(args.sample_size, args.seed)
        else:
            manifest = read_json(ROOT / "data/sample_manifest.json")
            if manifest["sample_size"] != args.sample_size or manifest["seed"] != args.seed:
                raise ValueError("Sample manifest does not match CLI arguments; rerun prepare")
            if stage == "experiment":
                from .experiment import experiment
                experiment()
            elif stage == "train":
                from .models import train
                train(args.seed)
            elif stage == "evaluate":
                from .evaluate import evaluate
                evaluate(args.seed, args.bootstrap)
            elif stage == "report":
                from .reporting import report
                report()
            elif stage == "verify":
                from .sql_checks import sql_checks
                from .verify import verify_artifacts
                sql_checks()
                verify_artifacts()
        timings[stage] = {"seconds": round(time.perf_counter() - started, 3), "completed_at": utc_now()}
        write_json(timing_path, timings)
        logging.info("DONE stage %s in %.1f seconds", stage, timings[stage]["seconds"])


if __name__ == "__main__":
    main()
