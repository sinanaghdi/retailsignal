"""Canonicalize source rows, preserve anomalies, and generate repeatable data marts."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from src.config import DEFAULT_INGESTED, DEFAULT_CLEANED, MARTS_DIR, REQUIRED_COLUMNS
from src.validate import canonicalize_columns, audit_dataframe
from src.metrics import (build_monthly_sales, build_customer_rfm, build_cohort_retention,
                         build_product_performance, build_country_performance, build_cancellation_summary,
                         build_rfm_sensitivity, build_customer_concentration,
                         build_rfm_segment_summary, build_duplicate_sensitivity)


def normalize_identifier(series: pd.Series) -> pd.Series:
    result = series.astype("string").str.strip()
    result = result.str.replace(r"\.0$", "", regex=True)
    result = result.mask(result.isin(["", "nan", "NaN", "None", "<NA>"]))
    return result


def clean_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize data types and add analytical flags without dropping source rows."""
    df, _ = canonicalize_columns(frame, strict=True)
    df = df.copy()
    if "source_row_id" not in df.columns:
        df.insert(0, "source_row_id", range(1, len(df) + 1))
    for col in ("InvoiceNo", "StockCode", "CustomerID"):
        df[col] = normalize_identifier(df[col])
    df["InvoiceNo"] = df["InvoiceNo"].str.upper()
    for col in ("Description", "Country"):
        df[col] = df[col].astype("string").str.strip()
        df[col] = df[col].mask(df[col].eq(""))
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce", format="mixed")
    df["source_row_id"] = pd.to_numeric(df["source_row_id"], errors="raise").astype("int64")

    source_cols = [c for c in REQUIRED_COLUMNS if c in df.columns]
    df["is_exact_duplicate_extra_row"] = df.duplicated(subset=source_cols, keep="first")
    df["is_cancellation_invoice"] = df["InvoiceNo"].str.startswith("C", na=False)
    df["line_value"] = df["Quantity"] * df["UnitPrice"]
    df["is_negative_quantity"] = df["Quantity"] < 0
    df["is_zero_quantity"] = df["Quantity"] == 0
    df["is_nonpositive_unit_price"] = df["UnitPrice"] <= 0
    df["is_negative_line_value"] = df["line_value"] < 0
    df["is_positive_sales_line"] = (
        df["Quantity"].gt(0) & df["UnitPrice"].gt(0) & ~df["is_cancellation_invoice"]
        & df["line_value"].notna()
    )
    df["is_credit_or_return_like"] = df["is_negative_line_value"] | df["is_cancellation_invoice"]
    # Exclude invoices with conflicting nonmissing customer IDs from customer-level attribution;
    # preserve their line values in the all-records sales facts.
    customer_variants = df.groupby("InvoiceNo")["CustomerID"].nunique(dropna=True) if "InvoiceNo" in df.columns else pd.Series(dtype=int)
    ambiguous_invoice_ids = set(customer_variants[customer_variants > 1].index.tolist())
    df["is_customer_analytics_eligible"] = (
        df["CustomerID"].notna() & df["InvoiceNo"].notna() & ~df["InvoiceNo"].isin(ambiguous_invoice_ids)
    )
    # Standardized lower-case names for SQL/Python model outputs.
    df = df.rename(columns={
        "InvoiceNo": "invoice_no", "StockCode": "stock_code", "Description": "description",
        "Quantity": "quantity", "InvoiceDate": "invoice_date", "UnitPrice": "unit_price",
        "CustomerID": "customer_id", "Country": "country",
    })
    return df


def build_dimensions_and_marts(lines: pd.DataFrame, marts_dir: str | Path = MARTS_DIR) -> dict[str, pd.DataFrame]:
    marts_dir = Path(marts_dir)
    marts_dir.mkdir(parents=True, exist_ok=True)
    nonnull_invoice = lines.loc[lines["invoice_no"].notna()].copy()
    dim_invoice = nonnull_invoice.groupby("invoice_no", as_index=False).agg(
        invoice_date=("invoice_date", "min"), customer_id=("customer_id", "min"), country=("country", "min"),
        is_cancellation_invoice=("is_cancellation_invoice", "max"), source_line_count=("source_row_id", "count"),
        date_variants=("invoice_date", "nunique"), customer_variants=("customer_id", "nunique"), country_variants=("country", "nunique"),
    )
    dim_product = lines.loc[lines["stock_code"].notna()].groupby("stock_code", as_index=False).agg(
        description=("description", lambda x: x.dropna().mode().iloc[0] if not x.dropna().mode().empty else pd.NA),
        source_line_count=("source_row_id", "count"),
    )
    dim_customer = lines.loc[lines["customer_id"].notna()].groupby("customer_id", as_index=False).agg(
        country_count=("country", "nunique"), first_recorded_date=("invoice_date", "min"), last_recorded_date=("invoice_date", "max"),
    )
    dim_country = lines.loc[lines["country"].notna(), ["country"]].drop_duplicates().sort_values("country").reset_index(drop=True)
    customer_rfm = build_customer_rfm(lines)
    rfm_sensitivity, rfm_sensitivity_summary = build_rfm_sensitivity(lines)
    marts = {
        "dim_invoice": dim_invoice,
        "dim_product": dim_product,
        "dim_customer": dim_customer,
        "dim_country": dim_country,
        "monthly_sales": build_monthly_sales(lines),
        "customer_rfm": customer_rfm,
        "customer_rfm_segment_summary": build_rfm_segment_summary(customer_rfm),
        "customer_rfm_sensitivity": rfm_sensitivity,
        "customer_rfm_sensitivity_summary": rfm_sensitivity_summary,
        "customer_concentration": build_customer_concentration(lines),
        "duplicate_sensitivity": build_duplicate_sensitivity(lines),
        "cohort_retention": build_cohort_retention(lines),
        "product_performance": build_product_performance(lines),
        "country_performance": build_country_performance(lines),
        "cancellation_summary": build_cancellation_summary(lines),
    }
    # Line facts are saved separately; each source row remains represented exactly once.
    for name, table in marts.items():
        table.to_csv(marts_dir / f"{name}.csv", index=False, encoding="utf-8")
    return marts


def run_clean(input_path: str | Path = DEFAULT_INGESTED, output_path: str | Path = DEFAULT_CLEANED, marts_dir: str | Path = MARTS_DIR) -> pd.DataFrame:
    input_path, output_path = Path(input_path), Path(output_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Ingested file not found: {input_path}. Run python -m src.ingest first.")
    raw_frame = pd.read_csv(input_path, low_memory=False, dtype={"InvoiceNo": "string", "StockCode": "string", "CustomerID": "string"})
    before = len(raw_frame)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit, _ = audit_dataframe(raw_frame)
    audit.to_csv(output_path.parent / "data_quality_audit.csv", index=False)
    clean = clean_dataframe(raw_frame)
    if len(clean) != before:
        raise AssertionError(f"Row preservation failed: {before} source rows versus {len(clean)} output rows.")
    recalculated = clean["quantity"] * clean["unit_price"]
    valid_values = clean["line_value"].notna() & recalculated.notna()
    if not np.allclose(clean.loc[valid_values, "line_value"], recalculated[valid_values], rtol=1e-10, atol=1e-8):
        raise AssertionError("Monetary reconciliation failed: line_value != quantity * unit_price.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(output_path, index=False, encoding="utf-8", date_format="%Y-%m-%d %H:%M:%S")
    marts = build_dimensions_and_marts(clean, marts_dir)
    print(f"Source rows: {before:,}; cleaned fact rows: {len(clean):,}; dropped rows: 0")
    print(f"Net recorded line value (GBP): {clean['line_value'].sum(skipna=True):,.2f}")
    print(f"Gross positive eligible line sales (GBP): {clean.loc[clean['is_positive_sales_line'], 'line_value'].sum(skipna=True):,.2f}")
    print(f"Output: {output_path}; marts written: {len(marts)} to {marts_dir}")
    print("Important: reported amounts are recorded line values, not profit or verified cash collected.")
    return clean


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INGESTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_CLEANED)
    parser.add_argument("--marts-dir", type=Path, default=MARTS_DIR)
    args = parser.parse_args()
    run_clean(args.input, args.output, args.marts_dir)

if __name__ == "__main__":
    main()
