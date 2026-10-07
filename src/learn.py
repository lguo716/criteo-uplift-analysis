import argparse

from .config import ROOT


def main():
    parser = argparse.ArgumentParser(description="Read one learning stage and inspect its actual result tables")
    parser.add_argument("--stage", type=int, choices=range(1, 10), required=True)
    args = parser.parse_args()
    files = sorted((ROOT / "docs").glob(f"learning_stage_{args.stage:02d}_*.md"))
    if len(files) != 1:
        raise FileNotFoundError("Learning document missing or ambiguous")
    print(files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
