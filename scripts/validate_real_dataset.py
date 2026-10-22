"""End-to-end audit of the official UCI Online Retail II data; emits aggregate evidence only."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from src.config import DEFAULT_WORKBOOK, DEFAULT_INGESTED, DEFAULT_CLEANED, MARTS_DIR, PROCESSED_DIR, RAW_DIR
from src.download_data import download_uci_workbook
from src.ingest import ingest_workbook
from src.clean import run_clean
from src.statistics import run_statistical_checks


EXPECTED_ROWS = 1_067_371
DATASET_URL = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
DATASET_DOI = "https://doi.org/10.24432/C5CG6D"

def _sha(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()

def run(output: Path) -> dict:
    workbook = download_uci_workbook()
    source = ingest_workbook(workbook, DEFAULT_INGESTED)
    cleaned = run_clean(DEFAULT_INGESTED, DEFAULT_CLEANED, MARTS_DIR)
    statistics = run_statistical_checks(DEFAULT_CLEANED, PROCESSED_DIR)
    audit_frame = pd.read_csv(PROCESSED_DIR / "data_quality_audit.csv")
    audit_map = {row["metric"]: int(row["affected_count"]) for _,row in audit_frame.iterrows()}
    monthly = pd.read_csv(MARTS_DIR / "monthly_sales.csv")
    products = pd.read_csv(MARTS_DIR / "product_performance.csv")
    countries = pd.read_csv(MARTS_DIR / "country_performance.csv")
    rfm = pd.read_csv(MARTS_DIR / "customer_rfm.csv")
    cohorts = pd.read_csv(MARTS_DIR / "cohort_retention.csv")
    line_value = pd.to_numeric(cleaned["line_value"], errors="coerce")
    date_valid = pd.to_datetime(cleaned["invoice_date"], errors="coerce", format="mixed").notna()
    pos = cleaned["is_positive_sales_line"].astype(bool) & date_valid
    cancellation_positive = cleaned["is_cancellation_invoice"].astype(bool) & cleaned["is_positive_sales_line"].astype(bool)
    expected_positive_gross = float(line_value.loc[pos].sum())
    expected_signed_valid_date = float(line_value.loc[date_valid].sum())
    monthly_positive = float(pd.to_numeric(monthly["gross_positive_line_sales_gbp"], errors="coerce").sum())
    monthly_signed = float(pd.to_numeric(monthly["net_recorded_sales_gbp"], errors="coerce").sum())
    invoice_values = cleaned.loc[pos, "invoice_no"].astype("string")
    invoice_values = invoice_values.loc[invoice_values.notna() & invoice_values.str.strip().ne("")]
    check_values = {
        "official_source_row_count": len(source) == EXPECTED_ROWS,
        "row_preservation_ingestion_cleaning": len(source) == len(cleaned) == EXPECTED_ROWS,
        "stable_unique_source_row_id": cleaned["source_row_id"].is_unique and len(cleaned["source_row_id"]) == EXPECTED_ROWS,
        "monthly_positive_sales_reconciles": bool(np.isclose(monthly_positive, expected_positive_gross, rtol=1e-9, atol=0.02)),
        "monthly_signed_value_reconciles": bool(np.isclose(monthly_signed, expected_signed_valid_date, rtol=1e-9, atol=0.02)),
        "cancellation_invoice_not_positive_sales": int(cancellation_positive.sum()) == 0,
        "rfm_recency_nonnegative": bool(rfm.empty or (pd.to_numeric(rfm["recency_days"],errors="coerce").dropna() >= 0).all()),
        "cohort_retention_in_bounds": bool(cohorts.empty or pd.to_numeric(cohorts["retention_rate"],errors="coerce").dropna().between(0,1).all()),
        "first_cohort_month_retention_is_one": bool(cohorts.empty or np.isclose(pd.to_numeric(cohorts.loc[cohorts["cohort_index"] == 1,"retention_rate"],errors="coerce").dropna(),1.0).all()),
        "no_empty_month_rows": bool(monthly["month"].notna().all()),
    }
    manifest_path = RAW_DIR / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    sheet_rows = source.groupby("source_sheet", dropna=False).size().astype(int).to_dict() if "source_sheet" in source.columns else {}
    summary = {
        "dataset": "UCI Online Retail II",
        "dataset_url": DATASET_URL,
        "dataset_doi": DATASET_DOI,
        "license": "CC BY 4.0",
        "source_workbook_sha256": _sha(workbook),
        "source_workbook_bytes": workbook.stat().st_size,
        "expected_source_rows": EXPECTED_ROWS,
        "source_rows_ingested": len(source),
        "cleaned_rows": len(cleaned),
        "sheet_row_counts": sheet_rows,
        "source_date_min": str(pd.to_datetime(cleaned["invoice_date"],errors="coerce",format="mixed").min()),
        "source_date_max": str(pd.to_datetime(cleaned["invoice_date"],errors="coerce",format="mixed").max()),
        "currency_code": "GBP",
        "key_metrics": {
            "signed_recorded_line_value_gbp": round(float(line_value.sum(skipna=True)),2),
            "gross_positive_eligible_line_sales_gbp": round(float(pd.to_numeric(cleaned.loc[cleaned["is_positive_sales_line"],"line_value"],errors="coerce").sum()),2),
            "positive_sales_invoices": int(cleaned.loc[cleaned["is_positive_sales_line"],"invoice_no"].nunique(dropna=True)),
            "identified_customers_with_eligible_purchase": int(rfm["customer_id"].nunique()) if not rfm.empty else 0,
            "product_count_in_performance_mart": int(products["stock_code"].nunique()) if not products.empty else 0,
            "country_count": int(countries["country"].nunique()) if not countries.empty else 0,
            "customer_rfm_rows": int(len(rfm)),
            "cohort_rows": int(len(cohorts)),
            "monthly_rows": int(len(monthly)),
        },
        "quality_audit_counts": audit_map,
        "statistical_checks": statistics,
        "reconciliation": {
            "monthly_positive_sales_gbp": round(monthly_positive,2),
            "expected_monthly_positive_sales_gbp": round(expected_positive_gross,2),
            "monthly_signed_value_gbp": round(monthly_signed,2),
            "expected_signed_value_on_valid_dates_gbp": round(expected_signed_valid_date,2),
            "cancellation_positive_rows": int(cancellation_positive.sum()),
        },
        "checks": check_values,
        "source_manifest": {k:manifest.get(k) for k in ["archive","workbook","sheets","acquired_at_utc","license"]},
        "privacy_note": "This validation file contains aggregate metrics and source-file hashes only. The raw workbook and customer-level exports are not uploaded as artifacts or committed to Git.",
        "limitations": [
            "Recorded transaction-line amounts are not verified cash receipts, recognized accounting revenue, or profit.",
            "Customer analyses cover only records with sufficiently attributable identifiers; missing/conflicting IDs affect coverage.",
            "The two-year window ends during December 2011; December comparisons/cohorts have unequal follow-up.",
            "Real-data execution does not by itself validate Power BI or prove a business recommendation causally.",
        ]
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print("REAL-DATA VALIDATION SUMMARY")
    print(json.dumps(summary,indent=2,ensure_ascii=False,default=str))
    if not all(check_values.values()):
        failed=[name for name,passed in check_values.items() if not passed]
        raise AssertionError(f"Real-data acceptance checks failed: {failed}. Aggregate summary saved to {output}.")
    return summary

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=PROCESSED_DIR/"real_dataset_validation.json")
    args=parser.parse_args()
    run(args.output if args.output.is_absolute() else (Path(__file__).resolve().parents[1]/args.output))
