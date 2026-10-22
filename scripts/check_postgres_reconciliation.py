"""Check real-data row/value reconciliation between Python and PostgreSQL staging/fact layers."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
import psycopg

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary",type=Path,default=Path("data/processed/real_dataset_validation.json"))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    summary=json.loads((root/args.summary).read_text(encoding="utf-8"))
    dsn=os.environ.get("DATABASE_URL","").replace("postgresql+psycopg://","postgresql://",1)
    if not dsn: raise RuntimeError("DATABASE_URL is required for PostgreSQL reconciliation.")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COALESCE(SUM(quantity * unit_price),0) FROM retailsignal.stg_online_retail")
            staging_rows, staging_signed=cur.fetchone()
            cur.execute("SELECT COUNT(*), COALESCE(SUM(line_value),0), COALESCE(SUM(line_value) FILTER (WHERE is_positive_sales_line),0), COUNT(*) FILTER (WHERE is_cancellation_invoice AND is_positive_sales_line) FROM retailsignal.fact_sales_line")
            fact_rows, fact_signed, fact_positive, cancellation_positive=cur.fetchone()
            cur.execute("SELECT COUNT(DISTINCT invoice_no) FROM retailsignal.fact_sales_line WHERE is_positive_sales_line AND invoice_no IS NOT NULL")
            invoice_count=cur.fetchone()[0]
    checks={
        "staging_row_count_matches": int(staging_rows)==int(summary["source_rows_ingested"]),
        "fact_row_count_matches": int(fact_rows)==int(summary["source_rows_ingested"]),
        "staging_and_fact_signed_amounts_match": abs(float(staging_signed)-float(fact_signed))<=max(0.02,abs(float(staging_signed))*1e-9),
        "fact_signed_amount_matches_python": abs(float(fact_signed)-float(summary["key_metrics"]["signed_recorded_line_value_gbp"]))<=max(0.02,abs(float(fact_signed))*1e-9),
        "fact_positive_amount_matches_python": abs(float(fact_positive)-float(summary["key_metrics"]["gross_positive_eligible_line_sales_gbp"]))<=max(0.02,abs(float(fact_positive))*1e-9),
        "cancellation_rows_never_positive_sales": int(cancellation_positive)==0,
        "positive_invoice_count_matches_python": int(invoice_count)==int(summary["key_metrics"]["positive_sales_invoices"]),
    }
    result={"status":"passed" if all(checks.values()) else "failed","postgres_row_counts":{"staging":int(staging_rows),"fact":int(fact_rows)},"signed_staging_gbp":round(float(staging_signed),2),"signed_fact_gbp":round(float(fact_signed),2),"positive_fact_gbp":round(float(fact_positive),2),"positive_invoice_count":int(invoice_count),"cancellation_positive_rows":int(cancellation_positive),"checks":checks}
    print(json.dumps(result,indent=2))
    path=root/"data/processed/postgres_real_data_reconciliation.json"
    path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    if not all(checks.values()):
        raise AssertionError("PostgreSQL reconciliation failed; inspect the JSON output.")
if __name__=="__main__":
    main()
