"""Check real-data row/value reconciliation and product-ranking parity for Python/PostgreSQL."""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.config import MARTS_DIR


PRODUCT_TOP10_SQL = r"""
WITH sales_description_counts AS (
    SELECT f.stock_code, NULLIF(BTRIM(s.description), '') AS description, COUNT(*) AS description_rows
    FROM retailsignal.fact_sales_line AS f
    JOIN retailsignal.stg_online_retail AS s ON s.source_row_id = f.source_row_id
    WHERE f.is_positive_sales_line
      AND f.stock_code IS NOT NULL
      AND NULLIF(BTRIM(s.description), '') IS NOT NULL
    GROUP BY f.stock_code, NULLIF(BTRIM(s.description), '')
), ranked_descriptions AS (
    SELECT stock_code, description, description_rows,
           ROW_NUMBER() OVER (
               PARTITION BY stock_code
               ORDER BY description_rows DESC, description COLLATE "C" ASC
           ) AS label_rank
    FROM sales_description_counts
), product_sales AS (
    SELECT f.stock_code, d.description,
           SUM(f.line_value) AS gross_positive_line_sales_gbp,
           SUM(f.quantity) AS positive_units,
           COUNT(DISTINCT f.invoice_no) AS invoice_count
    FROM retailsignal.fact_sales_line AS f
    LEFT JOIN ranked_descriptions AS d
      ON d.stock_code = f.stock_code AND d.label_rank = 1
    WHERE f.is_positive_sales_line AND f.stock_code IS NOT NULL
    GROUP BY f.stock_code, d.description
), ranked AS (
    SELECT *,
           SUM(gross_positive_line_sales_gbp) OVER () AS total_sales,
           ROW_NUMBER() OVER (
               ORDER BY gross_positive_line_sales_gbp DESC, stock_code COLLATE "C" ASC
           ) AS sales_rank,
           SUM(gross_positive_line_sales_gbp) OVER (
               ORDER BY gross_positive_line_sales_gbp DESC, stock_code COLLATE "C" ASC
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS cumulative_sales
    FROM product_sales
)
SELECT stock_code, description, gross_positive_line_sales_gbp, positive_units, invoice_count,
       100.0 * gross_positive_line_sales_gbp / NULLIF(total_sales, 0) AS sales_contribution_pct,
       100.0 * cumulative_sales / NULLIF(total_sales, 0) AS cumulative_contribution_pct
FROM ranked
ORDER BY sales_rank
LIMIT 10;
"""

def _same_number(left: object, right: object, *, amount: bool = False) -> bool:
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(a) or not math.isfinite(b):
        return False
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=0.02 if amount else 1e-6)

def _clean_label(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None

def _compare_product_top10(sql_rows: list[tuple], python_csv: Path) -> dict:
    if not python_csv.exists():
        raise FileNotFoundError(f"Python product mart missing: {python_csv}")
    products = pd.read_csv(python_csv, dtype={"stock_code": "string", "description": "string"})
    products["stock_code"] = products["stock_code"].astype("string")
    products["gross_positive_line_sales_gbp"] = pd.to_numeric(products["gross_positive_line_sales_gbp"], errors="coerce")
    products["units_sold_positive"] = pd.to_numeric(products["units_sold_positive"], errors="coerce")
    products["invoice_count"] = pd.to_numeric(products["invoice_count"], errors="coerce")
    products["sales_contribution_pct"] = pd.to_numeric(products["sales_contribution_pct"], errors="coerce")
    products["cumulative_contribution_pct"] = pd.to_numeric(products["cumulative_contribution_pct"], errors="coerce")
    products = products.sort_values(
        ["gross_positive_line_sales_gbp", "stock_code"],
        ascending=[False, True], kind="mergesort"
    ).head(10).reset_index(drop=True)
    if len(sql_rows) != len(products):
        return {"passed": False, "matched_products": 0, "expected_products": len(products), "sql_products": len(sql_rows), "mismatches": ["top-10 row count differs"]}
    mismatches = []
    compared = []
    for position, (sql_row, (_, py_row)) in enumerate(zip(sql_rows, products.iterrows()), start=1):
        sql_code, sql_desc, sql_sales, sql_units, sql_invoices, sql_share, sql_cumulative = sql_row
        py_code = str(py_row["stock_code"]) if not pd.isna(py_row["stock_code"]) else None
        py_desc = _clean_label(py_row["description"])
        checks = {
            "stock_code": str(sql_code) == py_code,
            "description_mode": _clean_label(sql_desc) == py_desc,
            "positive_sales_amount": _same_number(sql_sales, py_row["gross_positive_line_sales_gbp"], amount=True),
            "positive_units": _same_number(sql_units, py_row["units_sold_positive"]),
            "distinct_invoices": _same_number(sql_invoices, py_row["invoice_count"]),
            "sales_contribution_pct": _same_number(sql_share, py_row["sales_contribution_pct"]),
            "cumulative_contribution_pct": _same_number(sql_cumulative, py_row["cumulative_contribution_pct"]),
        }
        for name, ok in checks.items():
            if not ok:
                mismatches.append({"rank": position, "product_code_sql": str(sql_code), "product_code_python": py_code, "field": name,
                                   "sql": _clean_label(sql_desc) if name == "description_mode" else (float(sql_row[2]) if name == "positive_sales_amount" else str(sql_row)),
                                   "python": py_desc if name == "description_mode" else (float(py_row["gross_positive_line_sales_gbp"]) if name == "positive_sales_amount" else str(py_row.to_dict()))})
        compared.append({"rank":position,"stock_code":py_code,"description":py_desc,
                         "gross_positive_line_sales_gbp":round(float(py_row["gross_positive_line_sales_gbp"]),2),
                         "invoice_count":int(py_row["invoice_count"])})
    return {"passed": not mismatches, "matched_products": len(sql_rows) if not mismatches else len(sql_rows)-len({x["rank"] for x in mismatches}),
            "expected_products": len(products), "sql_products": len(sql_rows), "compared_fields_per_product": 7,
            "mismatches": mismatches, "top_10_sample": compared}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=Path("data/processed/real_dataset_validation.json"))
    args = parser.parse_args()
    root = PROJECT_ROOT
    summary = json.loads((root / args.summary).read_text(encoding="utf-8"))
    dsn = os.environ.get("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://", 1)
    if not dsn:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL reconciliation.")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COALESCE(SUM(quantity * unit_price),0) FROM retailsignal.stg_online_retail")
            staging_rows, staging_signed = cur.fetchone()
            cur.execute("""SELECT COUNT(*),
                COALESCE(SUM(line_value),0),
                COALESCE(SUM(line_value) FILTER (WHERE is_positive_sales_line),0),
                COUNT(*) FILTER (WHERE is_cancellation_invoice AND is_positive_sales_line)
                FROM retailsignal.fact_sales_line""")
            fact_rows, fact_signed, fact_positive, cancellation_positive = cur.fetchone()
            cur.execute("SELECT COUNT(DISTINCT invoice_no) FROM retailsignal.fact_sales_line WHERE is_positive_sales_line AND invoice_no IS NOT NULL")
            invoice_count = cur.fetchone()[0]
            cur.execute(PRODUCT_TOP10_SQL)
            sql_products = cur.fetchall()
    product_parity = _compare_product_top10(sql_products, MARTS_DIR / "product_performance.csv")
    checks = {
        "staging_row_count_matches": int(staging_rows) == int(summary["source_rows_ingested"]),
        "fact_row_count_matches": int(fact_rows) == int(summary["source_rows_ingested"]),
        "staging_and_fact_signed_amounts_match": abs(float(staging_signed) - float(fact_signed)) <= max(0.02, abs(float(staging_signed))*1e-9),
        "fact_signed_amount_matches_python": abs(float(fact_signed) - float(summary["key_metrics"]["signed_recorded_line_value_gbp"])) <= max(0.02, abs(float(fact_signed))*1e-9),
        "fact_positive_amount_matches_python": abs(float(fact_positive) - float(summary["key_metrics"]["gross_positive_eligible_line_sales_gbp"])) <= max(0.02, abs(float(fact_positive))*1e-9),
        "cancellation_rows_never_positive_sales": int(cancellation_positive) == 0,
        "positive_invoice_count_matches_python": int(invoice_count) == int(summary["key_metrics"]["positive_sales_invoices"]),
        "product_top10_matches_python": bool(product_parity["passed"]),
    }
    result = {
        "status": "passed" if all(checks.values()) else "failed",
        "postgres_row_counts": {"staging": int(staging_rows), "fact": int(fact_rows)},
        "signed_staging_gbp": round(float(staging_signed),2),
        "signed_fact_gbp": round(float(fact_signed),2),
        "positive_fact_gbp": round(float(fact_positive),2),
        "positive_invoice_count": int(invoice_count),
        "cancellation_positive_rows": int(cancellation_positive),
        "product_top10_parity": product_parity,
        "checks": checks,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    path = root / "data" / "processed" / "postgres_real_data_reconciliation.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if not all(checks.values()):
        raise AssertionError("PostgreSQL reconciliation failed; inspect the JSON output.")

if __name__ == "__main__":
    main()
