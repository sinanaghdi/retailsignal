"""Phase 3 KPI contract tests. All rows in this file are synthetic software fixtures."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.clean import clean_dataframe
from src.metrics import build_monthly_sales, build_purchase_invoices, build_cohort_retention


def _fixture() -> pd.DataFrame:
    return pd.DataFrame([
        {"Invoice": "10001", "StockCode": "A", "Description": "Item A", "Quantity": 2, "InvoiceDate": "2010-01-02 10:00:00", "Price": 10.0, "Customer ID": "A", "Country": "UK"},
        {"Invoice": "10001", "StockCode": "B", "Description": "Item B", "Quantity": 1, "InvoiceDate": "2010-01-02 10:00:00", "Price": 5.0, "Customer ID": "A", "Country": "UK"},
        {"Invoice": "10002", "StockCode": "A", "Description": "Item A", "Quantity": 3, "InvoiceDate": "2010-01-15 10:00:00", "Price": 10.0, "Customer ID": "A", "Country": "UK"},
        {"Invoice": "10003", "StockCode": "C", "Description": "Item C", "Quantity": 1, "InvoiceDate": "2010-02-03 12:00:00", "Price": 20.0, "Customer ID": "B", "Country": "France"},
        {"Invoice": "C10004", "StockCode": "A", "Description": "Item A", "Quantity": -1, "InvoiceDate": "2010-02-04 12:00:00", "Price": 10.0, "Customer ID": "A", "Country": "UK"},
    ])


def test_monthly_aov_uses_distinct_eligible_invoices_as_denominator() -> None:
    clean = clean_dataframe(_fixture())
    monthly = build_monthly_sales(clean)
    jan = monthly.loc[monthly["month"] == pd.Timestamp("2010-01-01")].iloc[0]
    feb = monthly.loc[monthly["month"] == pd.Timestamp("2010-02-01")].iloc[0]

    # January has 55 of eligible sales over two distinct eligible invoices, not three lines.
    assert np.isclose(jan["gross_positive_line_sales_gbp"], 55.0)
    assert jan["sales_invoices"] == 2
    assert np.isclose(jan["average_positive_invoice_value_gbp"], 27.5)
    # Cancellation line stays in signed recorded value but is not eligible positive sales.
    assert np.isclose(feb["net_recorded_sales_gbp"], 10.0)
    assert np.isclose(feb["gross_positive_line_sales_gbp"], 20.0)
    assert feb["sales_invoices"] == 1


def test_customer_invoice_grain_deduplicates_lines_within_invoice() -> None:
    clean = clean_dataframe(_fixture())
    purchases = build_purchase_invoices(clean)
    customer_a = purchases.loc[purchases["customer_id"] == "A"]
    assert customer_a["invoice_no"].nunique() == 2
    assert len(customer_a) == 2


def test_cohort_month_zero_is_one_and_retention_has_valid_denominator() -> None:
    clean = clean_dataframe(_fixture())
    cohorts = build_cohort_retention(clean)
    assert not cohorts.empty
    assert (cohorts["cohort_index"] >= 1).all()
    assert cohorts["retention_rate"].between(0.0, 1.0).all()
    month_zero = cohorts.loc[cohorts["cohort_index"] == 1, "retention_rate"]
    assert len(month_zero) > 0
    assert np.allclose(month_zero, 1.0)
