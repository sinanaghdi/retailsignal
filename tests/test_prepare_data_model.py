import json
from pathlib import Path

import pandas as pd
import pytest

from powerbi.prepare_data_model import build_date_dimension, prepare_powerbi_assets


def test_date_dimension_is_contiguous_and_flags_partial_month():
    dates = pd.Series(pd.to_datetime(["2020-01-01 10:00:00", "2020-01-03 09:00:00"]))
    calendar = build_date_dimension(dates)
    assert calendar["Date"].tolist() == ["2020-01-01", "2020-01-02", "2020-01-03"]
    assert calendar["YearMonthKey"].tolist() == [202001, 202001, 202001]
    assert calendar["IsPartialObservedMonth"].all()
    assert calendar["IsFinalObservedMonth"].all()


def test_date_dimension_marks_full_final_month_as_not_partial():
    calendar = build_date_dimension(pd.Series(pd.to_datetime(["2020-01-31"])))
    assert not calendar["IsPartialObservedMonth"].any()


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def test_prepare_powerbi_assets_writes_report_and_reconciles_synthetic_fixture(tmp_path):
    root = tmp_path
    fact = pd.DataFrame({
        "source_row_id": [1, 2, 3],
        "invoice_no": ["A001", "C002", "A003"],
        "stock_code": ["P1", "P2", "P1"],
        "description": ["Item 1", "Item 2", "Item 1"],
        "quantity": [2, -1, 1],
        "invoice_date": ["2020-01-01 10:00:00", "2020-01-02 10:00:00", "2020-01-03 10:00:00"],
        "unit_price": [10.0, 5.0, 8.0],
        "customer_id": ["C1", "C1", "C2"],
        "country": ["United Kingdom"] * 3,
        "is_cancellation_invoice": [False, True, False],
        "line_value": [20.0, -5.0, 8.0],
        "is_positive_sales_line": [True, False, True],
        "is_customer_analytics_eligible": [True, True, True],
    })
    _write_csv(root / "data/processed/fact_sales_lines.csv", fact)
    _write_csv(root / "data/processed/data_quality_audit.csv", pd.DataFrame({"check": ["example"]}))
    tables = {
        "dim_invoice.csv": pd.DataFrame({"invoice_no": ["A001", "C002", "A003"], "invoice_date": fact["invoice_date"], "customer_id": fact["customer_id"], "country": fact["country"]}),
        "dim_product.csv": pd.DataFrame({"stock_code": ["P1", "P2"], "description": ["Item 1", "Item 2"]}),
        "dim_customer.csv": pd.DataFrame({"customer_id": ["C1", "C2"]}),
        "dim_country.csv": pd.DataFrame({"country": ["United Kingdom"]}),
        "monthly_sales.csv": pd.DataFrame({"month": ["2020-01-01"], "net_recorded_sales_gbp": [23.0], "gross_positive_line_sales_gbp": [28.0], "sales_invoices": [2]}),
        "customer_rfm.csv": pd.DataFrame({"customer_id": ["C1"], "recency_days": [1], "frequency_invoices": [1], "monetary_recorded_gbp": [20.0], "segment": ["example"]}),
        "cohort_retention.csv": pd.DataFrame({"cohort_month": ["2020-01-01"], "activity_month": ["2020-01-01"], "retention_rate": [1.0]}),
        "product_performance.csv": pd.DataFrame({"stock_code": ["P1", "P2"], "gross_positive_line_sales_gbp": [28.0, 0.0]}),
        "country_performance.csv": pd.DataFrame({"country": ["United Kingdom"], "gross_positive_line_sales_gbp": [28.0]}),
    }
    for name, frame in tables.items():
        _write_csv(root / "data/marts" / name, frame)

    report = prepare_powerbi_assets(root)
    assert report["status"] == "passed", report["errors"]
    assert report["fact_rows"] == 3
    assert report["metrics_gbp"]["net_recorded_line_value"] == 23.0
    assert report["metrics_gbp"]["gross_positive_line_sales"] == 28.0
    assert report["metrics_gbp"]["eligible_sales_invoices"] == 2
    assert (root / "data/marts/powerbi_date.csv").exists()
    written_report = json.loads((root / "data/processed/powerbi_model_validation.json").read_text(encoding="utf-8"))
    assert written_report["status"] == "passed"


def test_prepare_powerbi_assets_rejects_bad_boolean_value():
    from powerbi.prepare_data_model import _bool_series
    with pytest.raises(ValueError, match="unrecognized boolean"):
        _bool_series(pd.Series(["not-a-bool"]), "example")
