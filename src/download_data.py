"""Download and verify the official UCI Online Retail II workbook."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from src.config import DATASET_DOWNLOAD_URL, DEFAULT_WORKBOOK, RAW_DIR

EXPECTED_MEMBER = "online_retail_II.xlsx"
USER_AGENT = "RetailSignal-Portfolio-Project/1.0 (UCI dataset acquisition)"


def _stream_download(url: str, target: Path, timeout: int = 60, retries: int = 3) -> None:
    """Stream a URL to disk with bounded retries; never hold the full archive in RAM."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as out:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    raise OSError(f"Download endpoint returned HTTP {status}.")
                shutil.copyfileobj(response, out, length=1024 * 1024)
            if not temporary.exists() or temporary.stat().st_size == 0:
                raise OSError("Download completed with an empty file.")
            temporary.replace(target)
            return
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            temporary.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 4))
    raise RuntimeError(
        f"Could not download the official UCI archive after {retries} attempt(s): {last_error}. "
        "Open the official dataset page and manually download its ZIP file; do not substitute a pre-cleaned or synthetic dataset."
    ) from last_error


def _extract_expected_workbook(archive_path: Path, raw_dir: Path, workbook_path: Path) -> Path:
    """Extract only the known workbook member; reject invalid archives and unsafe paths."""
    if not zipfile.is_zipfile(archive_path):
        raise ValueError(f"Downloaded file is not a valid ZIP archive: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        candidates = [info for info in archive.infolist() if Path(info.filename).name.casefold() == EXPECTED_MEMBER.casefold()]
        if len(candidates) != 1:
            names = [info.filename for info in archive.infolist()[:30]]
            raise ValueError(
                f"Expected exactly one {EXPECTED_MEMBER!r} in the official ZIP; found {len(candidates)}. "
                f"First archive entries: {names}"
            )
        member = candidates[0]
        if member.is_dir() or member.file_size <= 0:
            raise ValueError(f"The workbook entry is empty or invalid: {member.filename}")
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = workbook_path.with_suffix(workbook_path.suffix + ".part")
        with archive.open(member, "r") as source, temporary.open("wb") as out:
            shutil.copyfileobj(source, out, length=1024 * 1024)
        if temporary.stat().st_size != member.file_size:
            temporary.unlink(missing_ok=True)
            raise OSError(
                f"Extracted workbook size mismatch: expected {member.file_size:,}, got {temporary.stat().st_size:,} bytes."
            )
        temporary.replace(workbook_path)
    return workbook_path


def download_uci_workbook(
    raw_dir: str | Path = RAW_DIR,
    workbook_path: str | Path = DEFAULT_WORKBOOK,
    download_url: str = DATASET_DOWNLOAD_URL,
    force: bool = False,
    timeout: int = 60,
    retries: int = 3,
) -> Path:
    """Download ZIP, safely extract the named workbook, and run the ingestion schema gate."""
    raw_dir, workbook_path = Path(raw_dir), Path(workbook_path)
    if workbook_path.exists() and not force:
        print(f"Workbook already exists: {workbook_path}")
        print("No download performed. Run `python -m src.ingest --inspect-only` to verify its schema.")
        return workbook_path

    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / "online_retail_ii.zip"
    print(f"Downloading official UCI archive from: {download_url}")
    _stream_download(download_url, archive_path, timeout=timeout, retries=retries)
    _extract_expected_workbook(archive_path, raw_dir, workbook_path)

    # Avoid a circular module import at import time, while reusing the same schema gate.
    from src.ingest import inspect_workbook

    try:
        inspection = inspect_workbook(workbook_path)
    except Exception:
        workbook_path.unlink(missing_ok=True)
        raise

    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    manifest = {
        "dataset": "Online Retail II",
        "creator": "Daqing Chen",
        "citation": "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D",
        "license": "CC BY 4.0",
        "dataset_page": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
        "download_url": download_url,
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "acquisition_method": "RetailSignal src.download_data; official UCI ZIP endpoint",
        "archive": {"path": str(archive_path.name), "size_bytes": archive_path.stat().st_size, "sha256": sha256_file(archive_path)},
        "workbook": {"path": str(workbook_path.name), "size_bytes": workbook_path.stat().st_size, "sha256": sha256_file(workbook_path)},
        "sheets": inspection["sheets"],
        "warning": "This manifest records file identity and schema headers; it does not replace the upstream dataset citation or license.",
    }
    manifest_path = raw_dir / "source_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Schema gate passed. Workbook: {workbook_path} ({workbook_path.stat().st_size:,} bytes)")
    print(f"Workbook SHA-256: {manifest['workbook']['sha256']}")
    print(f"Workbook sheets: {[sheet['sheet'] for sheet in inspection['sheets']]}")
    print(f"Local ZIP retained for provenance/retry: {archive_path}")
    print(f"Acquisition manifest written: {manifest_path}")
    print("The raw source is unchanged. Do not commit the workbook or ZIP to GitHub.")
    return workbook_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--url", default=DATASET_DOWNLOAD_URL, help="Official UCI ZIP URL; change only to a verified official mirror")
    parser.add_argument("--force", action="store_true", help="Redownload and replace an existing workbook")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    download_uci_workbook(args.raw_dir, args.output, args.url, args.force, args.timeout, args.retries)


if __name__ == "__main__":
    main()
