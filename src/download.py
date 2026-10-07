"""Download a data file, never executable code, from the verified publisher mirror."""
import hashlib
import logging
import time
import urllib.request

from .config import ROOT, SOURCE_BYTES, SOURCE_FILE, SOURCE_SHA256, SOURCE_URL, ensure_dirs
from .utils import configure_logging, utc_now, write_json


def sha256(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download():
    ensure_dirs()
    target = ROOT / "data/raw" / SOURCE_FILE
    if target.exists():
        if target.stat().st_size != SOURCE_BYTES or sha256(target) != SOURCE_SHA256:
            raise ValueError("Existing source fails identity verification; preserve it for inspection.")
        logging.info("Verified cached source: %s", target)
    else:
        partial = target.with_suffix(target.suffix + ".part")
        for attempt in range(3):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset == SOURCE_BYTES:
                break
            request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "criteo-uplift-portfolio/1.0", "Range": f"bytes={offset}-"})
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    # Servers that ignore Range must start a fresh file.
                    resume = offset > 0 and response.status == 206
                    if resume and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise ValueError("Incorrect Content-Range")
                    with open(partial, "ab" if resume else "wb") as handle:
                        total = offset if resume else 0
                        next_message = total + 25 * 1024 * 1024
                        for block in iter(lambda: response.read(1024 * 1024), b""):
                            handle.write(block)
                            total += len(block)
                            if total >= next_message:
                                logging.info("Downloaded %.1f / %.1f MB", total / 1e6, SOURCE_BYTES / 1e6)
                                next_message = total + 25 * 1024 * 1024
                break
            except Exception:
                logging.exception("Download attempt %d failed", attempt + 1)
                if attempt == 2:
                    raise
                time.sleep(2)
        if partial.stat().st_size != SOURCE_BYTES or sha256(partial) != SOURCE_SHA256:
            raise ValueError("Downloaded source does not match published size / SHA256.")
        partial.replace(target)
    write_json(ROOT / "data/source_manifest.json", {"publisher": "Criteo AI Lab", "version": "v2.1", "url": SOURCE_URL, "file": SOURCE_FILE, "bytes": SOURCE_BYTES, "sha256": SOURCE_SHA256, "expected_rows": 13_979_592, "license": "CC BY-NC-SA 4.0", "verified_at": utc_now()})
    return target


if __name__ == "__main__":
    configure_logging()
    download()
