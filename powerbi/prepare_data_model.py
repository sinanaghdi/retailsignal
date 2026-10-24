"""Prepare and preflight RetailSignal data exports before loading them into Power BI Desktop."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

FACT_REQUIRED = {
    "source_row_id", "invoice_no", "stock_code", "quantity", "invoice_date",
    "unit_price", "customer_id", "country", "line_value", "is_cancellation_invoice",
    "is_positive_sales_line", "is_customer_analytics_eligible",
}
REQUIRED_TABLES: dict[str, set[str]] = {
    "data/marts/dim_invoice.csv": {"invoice_no", "invoice_date", "customer_id", "country"},
    "data/marts/dim_product.csv": {"stock_code", "description"},
    "data/marts/dim_customer.csv": {"customer_id"},
    "data/marts/dim_country.csv": {"country"},
    "data/marts/monthly_sales.csv": {"month", "net_recorded_sales_gbp", "gross_positive_line_sales_gbp", "sales_invoices"},
    "data/marts/customer_rfm.csv": {"customer_id", "recency_days", "frequency_invoices", "monetary_recorded_gbp", "segment"},
    "data/marts/cohort_retention.csv": {"cohort_month", "activity_month", "retention_rate"},
    "data/marts/product_performance.csv": {"stock_code", "gross_positive_line_sales_gbp"},
    "data/marts/country_performance.csv": {"country", "gross_positive_line_sales_gbp"},
    "data/processed/data_quality_audit.csv": set(),
}
DIMENSION_KEYS = {
    "data/marts/dim_invoice.csv": "invoice_no",
    "data/marts/dim_product.csv": "stock_code",
    "data/marts/dim_customer.csv": "customer_id",
    "data/marts/dim_country.csv": "country",
}


def _bool_series(series: pd.Series, column_name: str) -> pd.Series:
    """Parse CSV booleans strictly instead of relying on truthiness of strings."""
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).astype(bool)
    normalized = series.astype("string").str.strip().str.lower()
    mapping = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False}
    unknown = normalized.notna() & ~normalized.isin(mapping)
    if unknown.any():
        values = sorted(normalized.loc[unknown].dropna().unique().tolist())[:5]
        raise ValueError(f"Column {column_name!r} contains unrecognized boolean values: {values}")
    return normalized.map(mapping).fillna(False).astype(bool)


def build_date_dimension(invoice_dates: pd.Series) -> pd.DataFrame:
    """Build a contiguous day-grain calendar ending at the latest valid source date."""
    dates = pd.to_datetime(invoice_dates, errors="coerce", format="mixed").dropna().dt.normalize()
    if dates.empty:
        raise ValueError("No valid invoice_date values exist; cannot generate a Date table.")
    first_date, last_date = dates.min(), dates.max()
    calendar = pd.DataFrame({"Date": pd.date_range(first_date, last_date, freq="D")})
    calendar["Year"] = calendar["Date"].dt.year.astype("int64")
    calendar["QuarterNumber"] = calendar["Date"].dt.quarter.astype("int64")
    calendar["Quarter"] = "Q" + calendar["QuarterNumber"].astype(str)
    calendar["MonthNumber"] = calendar["Date"].dt.month.astype("int64")
    calendar["MonthName"] = calendar["Date"].dt.month_name()
    calendar["MonthShort"] = calendar["Date"].dt.strftime("%b")
    calendar["YearMonth"] = calendar["Date"].dt.strftime("%Y-%m")
    calendar["YearMonthKey"] = (calendar["Year"] * 100 + calendar["MonthNumber"]).astype("int64")
    calendar["DayOfMonth"] = calendar["Date"].dt.day.astype("int64")
    calendar["DayOfWeekNumber"] = (calendar["Date"].dt.dayofweek + 1).astype("int64")
    calendar["DayOfWeekName"] = calendar["Date"].dt.day_name()
    calendar["IsWeekend"] = calendar["DayOfWeekNumber"].isin([6, 7])
    calendar_month_end = last_date + pd.offsets.MonthEnd(0)
    partial_last_month = last_date.normalize() < calendar_month_end.normalize()
    calendar["IsFinalObservedMonth"] = (calendar["Date"].dt.to_period("M") == last_date.to_period("M"))
    calendar["IsPartialObservedMonth"] = bool(partial_last_month) & calendar["IsFinalObservedMonth"]
    # ISO dates import reliably as a Date type in Power Query without locale ambiguity.
    calendar["Date"] = calendar["Date"].dt.strftime("%Y-%m-%d")
    return calendar


def _table_header(path: Path) -> set[str]:
    return set(pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns)


def prepare_powerbi_assets(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    fact_path = root / "data/processed/fact_sales_lines.csv"
    if not fact_path.exists():
        raise FileNotFoundError(
            f"Missing {fact_path}. Run the pipeline first: python -m src.download_data, "
            "python -m src.ingest, then python -m src.clean."
        )

    missing_files: list[str] = []
    table_audits: list[dict[str, Any]] = []
    errors: list[str] = []
    for relative_path, required_columns in REQUIRED_TABLES.items():
        path = root / relative_path
        if not path.exists():
            missing_files.append(relative_path)
            continue
        headers = _table_header(path)
        absent = sorted(required_columns - headers)
        table_audits.append({"file": relative_path, "headers_found": len(headers), "missing_columns": absent})
        if absent:
            errors.append(f"{relative_path}: missing required columns {absent}")
    if missing_files:
        raise FileNotFoundError(
            "Missing Power BI input(s): " + ", ".join(missing_files) + ". Run python -m src.clean first."
        )
    if errors:
        raise ValueError("Power BI input schema check failed: " + " | ".join(errors))

    fact = pd.read_csv(
        fact_path,
        low_memory=False,
        encoding="utf-8-sig",
        dtype={"invoice_no": "string", "stock_code": "string", "customer_id": "string", "country": "string"},
    )
    missing_fact_columns = sorted(FACT_REQUIRED - set(fact.columns))
    if missing_fact_columns:
        raise ValueError(f"fact_sales_lines.csv is missing required columns: {missing_fact_columns}")

    quantity = pd.to_numeric(fact["quantity"], errors="coerce")
    unit_price = pd.to_numeric(fact["unit_price"], errors="coerce")
    line_value = pd.to_numeric(fact["line_value"], errors="coerce")
    valid_amounts = quantity.notna() & unit_price.notna() & line_value.notna()
    amounts_match = bool(
        ((line_value[valid_amounts] - quantity[valid_amounts] * unit_price[valid_amounts]).abs() <= 1e-7).all()
    )
    if not amounts_match:
        errors.append("Some valid rows do not satisfy line_value = quantity * unit_price.")

    positive_flag = _bool_series(fact["is_positive_sales_line"], "is_positive_sales_line")
    cancellation_flag = _bool_series(fact["is_cancellation_invoice"], "is_cancellation_invoice")
    invoice_ids = fact["invoice_no"].astype("string").str.strip().str.upper()
    cancellation_expected = invoice_ids.str.startswith("C", na=False)
    cancellation_mismatches = int((cancellation_flag != cancellation_expected).sum())
    if cancellation_mismatches:
        errors.append(f"Cancellation classification differs from invoice prefix on {cancellation_mismatches:,} rows.")
    positive_expected = (
        quantity.gt(0) & unit_price.gt(0) & ~invoice_ids.str.startswith("C", na=False) & line_value.notna()
    )
    positive_mismatches = int((positive_flag != positive_expected.fillna(False)).sum())
    if positive_mismatches:
        errors.append(f"Positive-sales classification differs from the documented rule on {positive_mismatches:,} rows.")
    cancellation_positive_rows = int((cancellation_flag & positive_flag).sum())
    if cancellation_positive_rows:
        errors.append(f"{cancellation_positive_rows:,} cancellation-prefixed rows are flagged as positive sales.")

    source_row_ids = pd.to_numeric(fact["source_row_id"], errors="coerce")
    duplicate_source_ids = int(source_row_ids.duplicated(keep=False).sum())
    missing_source_ids = int(source_row_ids.isna().sum())
    if duplicate_source_ids:
        errors.append(f"{duplicate_source_ids:,} rows share a source_row_id.")
    if missing_source_ids:
        errors.append(f"{missing_source_ids:,} rows have a missing or invalid source_row_id.")

    date_dimension = build_date_dimension(fact["invoice_date"])
    date_output = root / "data/marts/powerbi_date.csv"
    date_output.parent.mkdir(parents=True, exist_ok=True)
    date_dimension.to_csv(date_output, index=False, encoding="utf-8")

    # Read only keys for dimension uniqueness checks; customer-level files stay local.
    for relative_path, key in DIMENSION_KEYS.items():
        dimension = pd.read_csv(
            root / relative_path, usecols=[key], dtype={key: "string"}, encoding="utf-8-sig"
        )
        populated = dimension[key].dropna().astype("string").str.strip()
        populated = populated.loc[populated.ne("")]
        duplicate_count = int(populated.duplicated(keep=False).sum())
        table_audits.append({
            "file": relative_path, "primary_key": key,
            "rows": len(dimension), "duplicate_key_rows": duplicate_count,
        })
        if duplicate_count:
            errors.append(
                f"{relative_path}: {duplicate_count:,} rows have duplicate nonblank key values in {key!r}."
            )

    eligible_invoice_count = int(fact.loc[positive_flag, "invoice_no"].dropna().nunique())
    parsed_dates = pd.to_datetime(fact["invoice_date"], errors="coerce", format="mixed")
    valid_date_rows = parsed_dates.notna()
    latest_date = parsed_dates.max()
    monthly_sales = pd.read_csv(
        root / "data/marts/monthly_sales.csv", low_memory=False, encoding="utf-8-sig"
    )
    monthly_net = round(float(pd.to_numeric(monthly_sales["net_recorded_sales_gbp"], errors="coerce").sum()), 2)
    monthly_positive = round(
        float(pd.to_numeric(monthly_sales["gross_positive_line_sales_gbp"], errors="coerce").sum()), 2
    )
    fact_dated_net = round(float(line_value.loc[valid_date_rows].sum(skipna=True)), 2)
    fact_dated_positive = round(float(line_value.loc[valid_date_rows & positive_flag].sum(skipna=True)), 2)
    monthly_net_matches = abs(monthly_net - fact_dated_net) <= 0.01
    monthly_positive_matches = abs(monthly_positive - fact_dated_positive) <= 0.01
    if not monthly_net_matches:
        errors.append(
            f"Monthly net sales GBP {monthly_net:,.2f} does not reconcile to date-valid fact GBP {fact_dated_net:,.2f}."
        )
    if not monthly_positive_matches:
        errors.append(
            f"Monthly eligible positive sales GBP {monthly_positive:,.2f} does not reconcile "
            f"to date-valid fact GBP {fact_dated_positive:,.2f}."
        )

    date_values = pd.to_datetime(date_dimension["Date"])
    report: dict[str, Any] = {
        "status": "failed" if errors else "passed",
        "scope": "Local Power BI preflight; does not validate Power BI Desktop visuals or DAX execution.",
        "fact_rows": int(len(fact)),
        "valid_invoice_date_rows": int(valid_date_rows.sum()),
        "date_range": {
            "first": str(parsed_dates.min().date()),
            "last": str(latest_date.date()),
            "date_dimension_rows": int(len(date_dimension)),
            "is_last_observed_month_partial": bool(date_dimension["IsPartialObservedMonth"].any()),
        },
        "metrics_gbp": {
            "net_recorded_line_value": round(float(line_value.sum(skipna=True)), 2),
            "gross_positive_line_sales": round(float(line_value.loc[positive_flag].sum(skipna=True)), 2),
            "negative_line_value_magnitude": round(float(-line_value.loc[line_value < 0].sum(skipna=True)), 2),
            "eligible_sales_invoices": eligible_invoice_count,
            "date_valid_fact_net_recorded_line_value": fact_dated_net,
            "monthly_mart_net_recorded_line_value": monthly_net,
            "date_valid_fact_gross_positive_line_sales": fact_dated_positive,
            "monthly_mart_gross_positive_line_sales": monthly_positive,
        },
        "checks": {
            "line_value_equals_quantity_times_unit_price": amounts_match,
            "positive_sales_flag_matches_documented_rule": positive_mismatches == 0,
            "positive_sales_classification_mismatches": positive_mismatches,
            "cancellation_flag_matches_invoice_prefix": cancellation_mismatches == 0,
            "cancellation_classification_mismatches": cancellation_mismatches,
            "cancellation_rows_misclassified_as_positive_sales": cancellation_positive_rows,
            "source_row_id_unique": duplicate_source_ids == 0 and missing_source_ids == 0,
            "source_row_id_duplicate_rows": duplicate_source_ids,
            "source_row_id_missing_rows": missing_source_ids,
            "monthly_net_sales_reconciles_to_date_valid_fact": monthly_net_matches,
            "monthly_positive_sales_reconciles_to_date_valid_fact": monthly_positive_matches,
            "date_dimension_is_contiguous": len(date_dimension) == (date_values.max() - date_values.min()).days + 1,
            "required_input_tables_present": len(table_audits) >= len(REQUIRED_TABLES),
        },
        "input_tables": table_audits,
        "errors": errors,
        "outputs": [
            "data/marts/powerbi_date.csv",
            "data/processed/powerbi_model_validation.json",
        ],
    }
    validation_output = root / "data/processed/powerbi_model_validation.json"
    validation_output.parent.mkdir(parents=True, exist_ok=True)
    validation_output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        report = prepare_powerbi_assets(args.project_root)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"Power BI preflight could not complete: {exc}")
        return 2
    print(f"Power BI preflight: {report['status'].upper()}")
    print(f"Fact rows: {report['fact_rows']:,}")
    print(f"Net recorded line value: GBP {report['metrics_gbp']['net_recorded_line_value']:,.2f}")
    print(f"Gross positive line sales: GBP {report['metrics_gbp']['gross_positive_line_sales']:,.2f}")
    print(f"Eligible sales invoices: {report['metrics_gbp']['eligible_sales_invoices']:,}")
    print(f"Date dimension: {report['date_range']['date_dimension_rows']:,} days")
    print(f"Validation report: {Path(args.project_root) / 'data/processed/powerbi_model_validation.json'}")
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}")
        return 1
    print("Note: this preflight does not open Power BI Desktop or verify report visuals/DAX.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
