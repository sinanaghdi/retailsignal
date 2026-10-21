"""Inspect and ingest the official UCI Online Retail II workbook."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from src.config import DEFAULT_WORKBOOK, DEFAULT_INGESTED, REQUIRED_COLUMNS
from src.validate import normalize_column_name, canonicalize_columns


def inspect_workbook(path: str | Path) -> dict:
    """Inspect workbook sheet names and headers without loading all rows."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {path}\nDownload the official UCI file and save it at this path; see docs/setup.md."
        )
    book = pd.ExcelFile(path)
    result = {"path": str(path), "sheets": []}
    missing_by_sheet = []
    for sheet in book.sheet_names:
        sample = pd.read_excel(book, sheet_name=sheet, nrows=5)
        _, mapped = canonicalize_columns(sample, strict=False)
        missing = sorted(set(REQUIRED_COLUMNS) - set(mapped.values()))
        result["sheets"].append({"sheet": sheet, "columns": [str(c) for c in sample.columns], "missing_required": missing})
        if missing:
            missing_by_sheet.append((sheet, missing))
    if missing_by_sheet:
        details = "; ".join(f"{s}: {', '.join(m)}" for s, m in missing_by_sheet)
        raise ValueError(f"Workbook headers do not match the expected schema ({details}). Review the printed headers before continuing.")
    return result


def ingest_workbook(path: str | Path, output: str | Path) -> pd.DataFrame:
    """Load each workbook sheet after schema inspection; keep all source rows."""
    report = inspect_workbook(path)
    frames = []
    with pd.ExcelFile(path) as book:
        for sheet in book.sheet_names:
            frame = pd.read_excel(book, sheet_name=sheet)
            frame, _ = canonicalize_columns(frame, strict=True)
            frame["source_sheet"] = sheet
            frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    # A stable row identifier is for traceability, not a claim of source-system identity.
    combined.insert(0, "source_row_id", range(1, len(combined) + 1))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False, encoding="utf-8")
    print(f"Schema inspection passed for {len(report['sheets'])} worksheet(s).")
    print(f"Sheets: {[x['sheet'] for x in report['sheets']]}")
    print(f"Detected columns (canonical): {list(combined.columns)}")
    print(f"Rows ingested: {len(combined):,}")
    print(f"Output: {output}")
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--output", type=Path, default=DEFAULT_INGESTED)
    parser.add_argument("--inspect-only", action="store_true", help="Show workbook schema without loading the full dataset")
    args = parser.parse_args()
    if args.inspect_only:
        report = inspect_workbook(args.input)
        for sheet in report["sheets"]:
            print(f"\nSheet: {sheet['sheet']}\nColumns: {sheet['columns']}\nMissing required: {sheet['missing_required']}")
        print("Schema inspection passed. Next, run ingestion without --inspect-only.")
        return
    ingest_workbook(args.input, args.output)

if __name__ == "__main__":
    main()
