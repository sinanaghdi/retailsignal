"""Schema normalization and transparent data-quality audit helpers."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
from src.config import COLUMN_ALIASES, REQUIRED_COLUMNS, DEFAULT_INGESTED, PROCESSED_DIR


def normalize_column_name(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower().replace("_", " "))


def canonicalize_columns(frame: pd.DataFrame, strict: bool = True) -> tuple[pd.DataFrame, dict[str, str]]:
    """Rename known UCI header variants to canonical names; reject ambiguous collisions."""
    alias_map = {normalize_column_name(alias): canonical for canonical, aliases in COLUMN_ALIASES.items() for alias in aliases}
    rename = {}
    for col in frame.columns:
        normalized = normalize_column_name(col)
        if normalized in alias_map:
            rename[col] = alias_map[normalized]
    target_counts = pd.Series(list(rename.values())).value_counts() if rename else pd.Series(dtype=int)
    collisions = sorted(target_counts[target_counts > 1].index.tolist())
    if collisions:
        raise ValueError(f"Multiple input columns map to the same canonical field: {collisions}")
    renamed = frame.rename(columns=rename).copy()
    found = {str(old): new for old, new in rename.items()}
    missing = sorted(set(REQUIRED_COLUMNS) - set(renamed.columns))
    if strict and missing:
        raise ValueError(f"Missing required source columns: {missing}. Detected columns: {list(frame.columns)}")
    return renamed, found


def _pct(count: int, total: int) -> float:
    return round((100.0 * count / total), 4) if total else 0.0


def audit_dataframe(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return row-count audit metrics without deleting or repairing source records."""
    df, _ = canonicalize_columns(frame, strict=False)
    total = len(df)
    records: list[dict] = []
    details: dict = {"row_count": total, "columns": [str(c) for c in df.columns]}

    def add(metric: str, count: int, treatment: str, rationale: str,
            denominator_count: int | None = None, count_unit: str = "rows") -> None:
        base = total if denominator_count is None else denominator_count
        records.append({
            "metric": metric, "affected_count": int(count), "count_unit": count_unit,
            "pct_of_rows": _pct(int(count), total) if count_unit == "rows" else None,
            "pct_of_denominator": _pct(int(count), base), "denominator_count": int(base),
            "treatment": treatment, "rationale": rationale,
        })

    for col in REQUIRED_COLUMNS:
        if col in df.columns:
            missing_mask = df[col].isna() | df[col].astype("string").str.strip().eq("").fillna(False)
            count = int(missing_mask.sum())
            add(f"missing_{col}", count, "Retain and flag; use a metric-specific eligibility rule.",
                "Nulls and blank-string representations are both treated as missing; records are not discarded globally.")
        else:
            add(f"missing_column_{col}", total, "Stop the pipeline until the source schema is reconciled.",
                "A required field is absent; downstream metrics would be incomplete.")

    comparable = [c for c in REQUIRED_COLUMNS if c in df.columns]
    exact_extra = int(df.duplicated(subset=comparable, keep="first").sum()) if comparable else 0
    add("exact_duplicate_extra_rows", exact_extra, "Flag; preserve in the primary observed-records view and run a sensitivity analysis.",
        "Identical rows may be duplicate exports or repeated source records; evidence is insufficient for automatic deletion.")
    if "InvoiceNo" in df.columns:
        invoice_groups = df.loc[df["InvoiceNo"].notna()].groupby("InvoiceNo", dropna=False)
        for source_col, metric in (("InvoiceDate", "invoices_with_multiple_dates"), ("CustomerID", "invoices_with_multiple_customer_ids"), ("Country", "invoices_with_multiple_countries")):
            if source_col in df.columns:
                conflicting = int((invoice_groups[source_col].nunique(dropna=True) > 1).sum())
                add(metric, conflicting, "Flag invoice for review; do not silently overwrite its line-level values.",
                    "An invoice-level summary would require a deterministic representative when source rows disagree.",
                    denominator_count=max(1, int(df["InvoiceNo"].dropna().nunique())), count_unit="invoices")

    invoice = df.get("InvoiceNo", pd.Series(index=df.index, dtype="string")).astype("string").str.strip().str.upper()
    qty = pd.to_numeric(df.get("Quantity", pd.Series(index=df.index)), errors="coerce")
    price = pd.to_numeric(df.get("UnitPrice", pd.Series(index=df.index)), errors="coerce")
    date = pd.to_datetime(df.get("InvoiceDate", pd.Series(index=df.index)), errors="coerce", format="mixed")
    cancellation = invoice.str.startswith("C", na=False)
    line_value = qty * price
    add("cancellation_invoice_rows", int(cancellation.sum()), "Flag using InvoiceNo prefix C; keep signed value exactly once.",
        "The UCI documentation says invoice identifiers beginning with C indicate cancellations; this does not establish physical return completion.")
    add("negative_quantity_rows", int((qty < 0).sum()), "Flag separately from cancellation invoice status.",
        "Negative quantity is credit/return-like evidence, not proof of a completed physical return.")
    add("zero_quantity_rows", int((qty == 0).sum()), "Retain and flag.", "Zero quantity contributes zero line value but may signal a nonstandard record.")
    add("zero_unit_price_rows", int((price == 0).sum()), "Retain and flag; exclude from positive-sales-line metric.",
        "A zero price may represent a free item or an operational record.")
    add("negative_unit_price_rows", int((price < 0).sum()), "Retain and flag; investigate before commercial interpretation.",
        "Negative prices are nonstandard and should not silently be converted to positive values.")
    add("invalid_quantity_rows", int(qty.isna().sum()), "Retain with null normalized quantity; exclude from monetary calculation.",
        "A missing or nonnumeric quantity prevents reliable line-value calculation.")
    add("invalid_unit_price_rows", int(price.isna().sum()), "Retain with null normalized price; exclude from monetary calculation.",
        "A missing or nonnumeric unit price prevents reliable line-value calculation.")
    add("invalid_invoice_date_rows", int(date.isna().sum()), "Retain in row-level table; exclude from time-series and recency calculations.",
        "A missing or unparsable timestamp cannot be assigned to a period.")
    add("negative_signed_line_value_rows", int((line_value < 0).sum()), "Retain signed line value; quantify once as negative recorded value.",
        "Negative signed line values can arise from negative quantities or prices; inspect both source fields and invoice prefix.")
    for col in ("StockCode", "Description", "Country"):
        if col in df.columns:
            normalized = df[col].astype("string").str.strip()
            count = int((df[col].isna() | normalized.eq("")).sum())
            add(f"missing_or_blank_{col}", count, "Retain; exclude from dimension labels or report as unknown.",
                "Missing labels limit product or geographic attribution without invalidating every other field.")

    valid_values = line_value.dropna()
    if len(valid_values):
        q1, q3 = valid_values.quantile([0.25, 0.75])
        upper = q3 + 3 * (q3 - q1)
        lower = q1 - 3 * (q3 - q1)
        outliers = int(((line_value < lower) | (line_value > upper)).sum())
        details["line_value_iqr_3x_lower"] = float(lower)
        details["line_value_iqr_3x_upper"] = float(upper)
    else:
        outliers = 0
        details["line_value_iqr_3x_lower"] = None
        details["line_value_iqr_3x_upper"] = None
    add("line_value_iqr_outlier_rows", outliers, "Flag for review; do not delete or winsorize by default.",
        "IQR outliers can be legitimate bulk orders, unusual prices, or data errors; investigate their source context.")

    if "StockCode" in df.columns:
        stock = df["StockCode"].astype("string").str.strip()
        stock_nonblank = stock.notna() & stock.ne("")
        standard_stock = stock.str.fullmatch(r"\d{5}[A-Za-z]?", na=False)
        add("nonstandard_stock_code_rows", int((stock_nonblank & ~standard_stock).sum()),
            "Flag for profiling; do not assume every nonstandard code is an error or merchandise item.",
            "The documented product-code pattern is a heuristic; operational codes may use letters or other formats.")
        if "Description" in df.columns:
            product_rows = df.loc[stock_nonblank].assign(_stock=stock[stock_nonblank].values)
            product_variants = product_rows.groupby("_stock")["Description"].nunique(dropna=True)
            add("stock_codes_with_multiple_descriptions", int((product_variants > 1).sum()),
                "Profile descriptions by stock code; keep line-level text and use a documented display label in dimensions.",
                "A code with changing descriptions may indicate wording variants or source inconsistencies.",
                denominator_count=max(1, int(stock[stock_nonblank].nunique())), count_unit="stock_codes")

    if "CustomerID" in df.columns:
        cust = df["CustomerID"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
        cust = cust.mask(cust.isin(["", "nan", "NaN", "None", "<NA>"]))
        anomalies = cust.notna() & ~cust.str.fullmatch(r"\d{5}", na=False)
        add("customer_id_format_anomaly_rows", int(anomalies.sum()),
            "Flag for inspection; retain the source identifier and do not reassign customer identity.",
            "UCI describes CustomerID as a five-digit identifier; this shape check is a warning, not proof of invalid identity.")

    details["value_profiles"] = {}
    if "Country" in df.columns:
        details["value_profiles"]["country_top_20"] = [
            {"value": str(k), "rows": int(v)} for k, v in df["Country"].astype("string").value_counts(dropna=False).head(20).items()
        ]
        details["value_profiles"]["distinct_nonmissing_countries"] = int(df["Country"].dropna().astype("string").str.strip().nunique())
    if "StockCode" in df.columns:
        details["value_profiles"]["stock_code_top_20"] = [
            {"value": str(k), "rows": int(v)} for k, v in df["StockCode"].astype("string").value_counts(dropna=False).head(20).items()
        ]
        details["value_profiles"]["distinct_nonmissing_stock_codes"] = int(df["StockCode"].dropna().astype("string").str.strip().nunique())
    if "InvoiceNo" in df.columns:
        details["value_profiles"]["invoice_prefix_top_20"] = [
            {"value": str(k), "rows": int(v)} for k, v in df["InvoiceNo"].astype("string").str.strip().str[:1].value_counts(dropna=False).head(20).items()
        ]
    details["numeric_and_date_ranges"] = {
        "minimum_invoice_date": str(date.min()) if date.notna().any() else None,
        "maximum_invoice_date": str(date.max()) if date.notna().any() else None,
        "minimum_quantity": float(qty.min()) if qty.notna().any() else None,
        "maximum_quantity": float(qty.max()) if qty.notna().any() else None,
        "minimum_unit_price": float(price.min()) if price.notna().any() else None,
        "maximum_unit_price": float(price.max()) if price.notna().any() else None,
    }

    summary = pd.DataFrame(records)
    details["audit_metrics"] = records
    details["calculation_notes"] = {
        "duplicate_definition": "Extra copies after the first exact match across available canonical source columns; source_row_id and source_sheet excluded.",
        "line_value": "Quantity multiplied by UnitPrice after numeric coercion.",
        "cancellation_definition": "InvoiceNo starts with C after trimming and uppercasing.",
        "outlier_definition": "Line value outside Q1 - 3*IQR or Q3 + 3*IQR; flagged, not removed.",
    }
    return summary, details


def run_audit(input_path: str | Path = DEFAULT_INGESTED, output_dir: str | Path = PROCESSED_DIR) -> tuple[pd.DataFrame, dict]:
    input_path, output_dir = Path(input_path), Path(output_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Ingested file not found: {input_path}. Run python -m src.ingest first.")
    output_dir.mkdir(parents=True, exist_ok=True)
    # Read identifiers as strings so leading zeros are not lost after CSV staging.
    frame = pd.read_csv(input_path, low_memory=False, dtype={"InvoiceNo": "string", "StockCode": "string", "CustomerID": "string"})
    summary, details = audit_dataframe(frame)
    summary.to_csv(output_dir / "data_quality_audit.csv", index=False)
    (output_dir / "data_quality_audit.json").write_text(json.dumps(details, indent=2, default=str), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"\nAudit outputs: {output_dir / 'data_quality_audit.csv'} and data_quality_audit.json")
    return summary, details


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INGESTED)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args()
    run_audit(args.input, args.output_dir)

if __name__ == "__main__":
    main()
