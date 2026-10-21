from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from src.clean import clean_dataframe, build_dimensions_and_marts, run_clean
from src.validate import canonicalize_columns, audit_dataframe
from src.metrics import build_monthly_sales, build_customer_rfm, build_cohort_retention, build_product_performance, build_rfm_sensitivity, build_customer_concentration, build_rfm_segment_summary, build_duplicate_sensitivity


@pytest.fixture
def synthetic_source() -> pd.DataFrame:
    """Tiny synthetic records for software tests only; never mixed into real analysis."""
    return pd.DataFrame([
        {"Invoice": "10001", "StockCode": "A1", "Description": "Item A", "Quantity": 2, "InvoiceDate": "2010-01-02 10:00:00", "Price": 10.0, "Customer ID": 1001, "Country": "UK"},
        {"Invoice": "10001", "StockCode": "B1", "Description": "Item B", "Quantity": 1, "InvoiceDate": "2010-01-02 10:00:00", "Price": 5.0, "Customer ID": 1001, "Country": "UK"},
        {"Invoice": "10002", "StockCode": "A1", "Description": "Item A", "Quantity": 3, "InvoiceDate": "2010-02-03 11:00:00", "Price": 10.0, "Customer ID": 1001, "Country": "UK"},
        {"Invoice": "10003", "StockCode": "C1", "Description": "Item C", "Quantity": -1, "InvoiceDate": "2010-02-04 12:00:00", "Price": 7.0, "Customer ID": 1002, "Country": "France"},
        {"Invoice": "C10004", "StockCode": "A1", "Description": "Item A", "Quantity": -2, "InvoiceDate": "2010-02-05 12:00:00", "Price": 10.0, "Customer ID": 1001, "Country": "UK"},
        {"Invoice": "10005", "StockCode": "D1", "Description": "Item D", "Quantity": 0, "InvoiceDate": "not-a-date", "Price": 3.0, "Customer ID": None, "Country": None},
        {"Invoice": "10006", "StockCode": "E1", "Description": "Item E", "Quantity": 1, "InvoiceDate": "2010-03-01 10:00:00", "Price": 0.0, "Customer ID": 1003, "Country": "UK"},
    ])


def test_schema_aliases_map_to_canonical_fields(synthetic_source):
    mapped, changes = canonicalize_columns(synthetic_source, strict=True)
    assert set(["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]).issubset(mapped.columns)
    assert changes["Invoice"] == "InvoiceNo"
    assert changes["Price"] == "UnitPrice"


def test_missing_required_column_fails_fast(synthetic_source):
    with pytest.raises(ValueError, match="Missing required source columns"):
        canonicalize_columns(synthetic_source.drop(columns=["Price"]), strict=True)


def test_clean_schema_uses_numeric_dates_and_stable_row_key(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    assert pd.api.types.is_integer_dtype(clean["source_row_id"])
    assert pd.api.types.is_numeric_dtype(clean["quantity"])
    assert pd.api.types.is_numeric_dtype(clean["unit_price"])
    assert pd.api.types.is_datetime64_any_dtype(clean["invoice_date"])


def test_cleaning_preserves_all_rows_and_signed_line_value(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    assert len(clean) == len(synthetic_source)
    assert clean["source_row_id"].is_unique
    assert np.isclose(clean.loc[clean["invoice_no"] == "10001", "line_value"].sum(), 25.0)
    assert np.isclose(clean.loc[clean["invoice_no"] == "C10004", "line_value"].iloc[0], -20.0)
    assert not bool(clean.loc[clean["invoice_no"] == "C10004", "is_positive_sales_line"].iloc[0])


def test_cancellation_negative_quantity_and_zero_price_flags_are_separate(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    cancel = clean.loc[clean["invoice_no"] == "C10004"].iloc[0]
    credit = clean.loc[clean["invoice_no"] == "10003"].iloc[0]
    zero = clean.loc[clean["invoice_no"] == "10006"].iloc[0]
    assert bool(cancel["is_cancellation_invoice"])
    assert bool(cancel["is_negative_quantity"])
    assert bool(credit["is_negative_quantity"])
    assert not bool(credit["is_cancellation_invoice"])
    assert bool(zero["is_nonpositive_unit_price"])
    assert not bool(zero["is_positive_sales_line"])


def test_duplicate_candidates_are_flagged_but_not_dropped(synthetic_source):
    duplicated = pd.concat([synthetic_source, synthetic_source.iloc[[0]]], ignore_index=True)
    clean = clean_dataframe(duplicated)
    assert len(clean) == len(duplicated)
    assert int(clean["is_exact_duplicate_extra_row"].sum()) == 1


def test_audit_reports_missing_invalid_and_duplicate_rows(synthetic_source):
    duplicated = pd.concat([synthetic_source, synthetic_source.iloc[[0]]], ignore_index=True)
    audit, detail = audit_dataframe(duplicated)
    metrics = audit.set_index("metric")["affected_count"].to_dict()
    assert metrics["exact_duplicate_extra_rows"] == 1
    assert metrics["invalid_invoice_date_rows"] == 1
    assert metrics["missing_CustomerID"] >= 1
    assert "country_top_20" in detail["value_profiles"]
    assert "minimum_invoice_date" in detail["numeric_and_date_ranges"]
    assert detail["row_count"] == len(duplicated)


def test_monthly_metrics_separate_signed_and_positive_sales(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    monthly = build_monthly_sales(clean)
    jan = monthly.loc[monthly["month"] == pd.Timestamp("2010-01-01")].iloc[0]
    assert np.isclose(jan["gross_positive_line_sales_gbp"], 25.0)
    assert np.isclose(jan["net_recorded_sales_gbp"], 25.0)
    assert jan["sales_invoices"] == 1


def test_rfm_counts_only_eligible_purchase_invoices(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    rfm = build_customer_rfm(clean)
    row = rfm.loc[rfm["customer_id"] == "1001"].iloc[0]
    assert row["frequency_invoices"] == 2
    assert row["recency_days"] >= 0
    assert row["segment"]
    assert set(rfm[["r_score", "f_score", "m_score"]].stack().astype(int)).issubset({1, 2, 3, 4, 5})


def test_cohort_index_starts_at_one_and_retention_is_bounded(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    cohorts = build_cohort_retention(clean)
    assert not cohorts.empty
    assert (cohorts["cohort_index"] >= 1).all()
    assert cohorts["retention_rate"].between(0, 1).all()
    assert (cohorts.loc[cohorts["cohort_index"] == 1, "retention_rate"] == 1).all()


def test_product_contribution_is_ordered_and_cumulative(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    products = build_product_performance(clean)
    assert products["gross_positive_line_sales_gbp"].is_monotonic_decreasing
    assert products["cumulative_contribution_pct"].is_monotonic_increasing
    assert np.isclose(products["sales_contribution_pct"].sum(), 100.0)


def test_dimensions_and_marts_do_not_multiply_rows(synthetic_source, tmp_path):
    clean = clean_dataframe(synthetic_source)
    marts = build_dimensions_and_marts(clean, tmp_path)
    assert len(clean) == len(synthetic_source)
    assert marts["dim_invoice"]["invoice_no"].is_unique
    assert marts["dim_product"]["stock_code"].is_unique
    assert (tmp_path / "cohort_retention.csv").exists()


def test_conflicting_customer_ids_disable_customer_attribution_but_preserve_sales():
    source = pd.DataFrame([
        {"InvoiceNo": "20001", "StockCode": "X", "Description": "X", "Quantity": 1, "InvoiceDate": "2010-01-01", "UnitPrice": 10, "CustomerID": "A", "Country": "UK"},
        {"InvoiceNo": "20001", "StockCode": "Y", "Description": "Y", "Quantity": 1, "InvoiceDate": "2010-01-01", "UnitPrice": 20, "CustomerID": "B", "Country": "UK"},
        {"InvoiceNo": "20002", "StockCode": "X", "Description": "X", "Quantity": 1, "InvoiceDate": "2010-02-01", "UnitPrice": 7, "CustomerID": "A", "Country": "UK"},
    ])
    clean = clean_dataframe(source)
    conflicted = clean.loc[clean["invoice_no"] == "20001"]
    assert len(conflicted) == 2
    assert not conflicted["is_customer_analytics_eligible"].any()
    assert np.isclose(clean["line_value"].sum(), 37.0)
    rfm = build_customer_rfm(clean)
    customer_a = rfm.loc[rfm["customer_id"] == "A"].iloc[0]
    assert customer_a["frequency_invoices"] == 1
    assert np.isclose(customer_a["monetary_recorded_gbp"], 7.0)


def test_mart_joins_preserve_fact_row_count(synthetic_source, tmp_path):
    clean = clean_dataframe(synthetic_source)
    marts = build_dimensions_and_marts(clean, tmp_path)
    joined = clean.merge(marts["dim_product"], on="stock_code", how="left", validate="many_to_one", suffixes=("", "_dim"))
    joined = joined.merge(marts["dim_country"], on="country", how="left", validate="many_to_one", suffixes=("", "_dim"))
    assert len(joined) == len(clean)


def test_signed_line_value_reconciliation_has_no_double_subtraction(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    expected = (pd.to_numeric(clean["quantity"], errors="coerce") * pd.to_numeric(clean["unit_price"], errors="coerce")).sum(skipna=True)
    assert np.isclose(clean["line_value"].sum(skipna=True), expected)
    # Negative magnitude is a diagnostic, not a second deduction from the net amount.
    net = clean["line_value"].sum(skipna=True)
    neg_magnitude = -clean.loc[clean["line_value"] < 0, "line_value"].sum()
    assert neg_magnitude >= 0
    assert not np.isclose(net - neg_magnitude, net) if neg_magnitude else np.isclose(net, net)


def test_rfm_sensitivity_compares_signed_and_positive_only_monetary(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    sensitivity, summary = build_rfm_sensitivity(clean)
    assert not sensitivity.empty
    assert {"m_score_positive_only", "segment_positive_only_monetary", "m_score_changed", "segment_changed"}.issubset(sensitivity.columns)
    assert summary.loc[0, "customers"] == len(sensitivity)
    assert summary.loc[0, "m_score_changed_pct"] >= 0


def test_customer_concentration_and_duplicate_sensitivity_outputs_are_reproducible(synthetic_source):
    clean = clean_dataframe(synthetic_source)
    concentration = build_customer_concentration(clean)
    assert concentration["gross_positive_line_sales_gbp"].is_monotonic_decreasing
    if not concentration.empty:
        assert np.isclose(concentration["sales_contribution_pct"].sum(), 100.0)
    rfm = build_customer_rfm(clean)
    segment_summary = build_rfm_segment_summary(rfm)
    if not segment_summary.empty:
        assert np.isclose(segment_summary["segment_share_pct"].sum(), 100.0)
    sensitivity = build_duplicate_sensitivity(clean)
    metrics = sensitivity.set_index("metric")
    assert metrics.loc["source_rows", "baseline_all_rows"] == len(clean)
    assert metrics.loc["source_rows", "sensitivity_excluding_duplicate_extras"] <= len(clean)


def test_clean_pipeline_writes_fact_audit_and_marts(synthetic_source, tmp_path):
    source_path = tmp_path / "source_fixture.csv"
    output_path = tmp_path / "processed" / "fact_sales_lines.csv"
    marts_path = tmp_path / "marts"
    synthetic_source.to_csv(source_path, index=False)

    result = run_clean(source_path, output_path, marts_path)
    reloaded = pd.read_csv(output_path, dtype={"invoice_no": "string", "customer_id": "string"})
    assert len(result) == len(synthetic_source) == len(reloaded)
    assert (tmp_path / "processed" / "data_quality_audit.csv").exists()
    for filename in (
        "monthly_sales.csv", "customer_rfm.csv", "cohort_retention.csv",
        "product_performance.csv", "country_performance.csv", "duplicate_sensitivity.csv",
        "customer_rfm_sensitivity.csv", "customer_concentration.csv",
    ):
        assert (marts_path / filename).exists(), filename
    assert np.isclose(reloaded["line_value"].sum(skipna=True), 28.0)


def test_audit_treats_blank_customer_ids_as_missing(synthetic_source):
    source = synthetic_source.copy()
    source["Customer ID"] = source["Customer ID"].astype("string")
    source.loc[0, "Customer ID"] = "   "
    audit, _ = audit_dataframe(source)
    metrics = audit.set_index("metric")["affected_count"]
    assert int(metrics["missing_CustomerID"]) == 2
