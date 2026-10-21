import pandas as pd
from src.clean import clean_dataframe
from src.statistics import paired_month_comparison, customer_spend_comparison


def test_statistical_checks_fail_softly_on_small_synthetic_sample():
    # Small synthetic fixture for software-path testing only; never treated as UCI findings.
    source = pd.DataFrame([
        {"InvoiceNo": "30001", "StockCode": "X1", "Description": "X", "Quantity": 2, "InvoiceDate": "2010-01-05", "UnitPrice": 5.0, "CustomerID": "10001", "Country": "UK"},
        {"InvoiceNo": "30002", "StockCode": "X1", "Description": "X", "Quantity": 1, "InvoiceDate": "2010-02-05", "UnitPrice": 5.0, "CustomerID": "10001", "Country": "UK"},
        {"InvoiceNo": "30003", "StockCode": "X2", "Description": "Y", "Quantity": 1, "InvoiceDate": "2010-02-10", "UnitPrice": 7.0, "CustomerID": "10002", "Country": "France"},
    ])
    lines = clean_dataframe(source)
    month_result = paired_month_comparison(lines)
    customer_result = customer_spend_comparison(lines)
    assert month_result["test"] == "paired Wilcoxon signed-rank"
    assert month_result["status"] in {"computed", "not_tested"}
    assert customer_result["test"] == "Mann-Whitney U"
    assert customer_result["status"] == "not_tested"


def test_customer_spend_comparison_excludes_ambiguous_invoice_attribution():
    rows = []
    # Five single-invoice customers.
    for i in range(1, 6):
        rows.append({"InvoiceNo": f"S{i}", "StockCode": "X", "Description": "Item",
                     "Quantity": 1, "InvoiceDate": "2010-01-01", "UnitPrice": 10.0,
                     "CustomerID": f"SINGLE{i}", "Country": "UK"})
    # Five repeat customers with two eligible purchase invoices each.
    for i in range(1, 6):
        for j, date in enumerate(("2010-01-02", "2010-02-02"), start=1):
            rows.append({"InvoiceNo": f"R{i}{j}", "StockCode": "X", "Description": "Item",
                         "Quantity": 1, "InvoiceDate": date, "UnitPrice": 10.0,
                         "CustomerID": f"REPEAT{i}", "Country": "UK"})
    # Conflicting customer attribution should not inflate purchase frequency.
    rows.extend([
        {"InvoiceNo": "AMBIG-1", "StockCode": "X", "Description": "Item", "Quantity": 1,
         "InvoiceDate": "2010-01-03", "UnitPrice": 10.0, "CustomerID": "AMBIG", "Country": "UK"},
        {"InvoiceNo": "AMBIG-2", "StockCode": "X", "Description": "Item", "Quantity": 1,
         "InvoiceDate": "2010-02-03", "UnitPrice": 20.0, "CustomerID": "AMBIG", "Country": "UK"},
        {"InvoiceNo": "AMBIG-2", "StockCode": "Y", "Description": "Item Y", "Quantity": 1,
         "InvoiceDate": "2010-02-03", "UnitPrice": 30.0, "CustomerID": "OTHER", "Country": "UK"},
    ])
    result = customer_spend_comparison(clean_dataframe(pd.DataFrame(rows)))
    assert result["status"] == "computed"
    assert result["one_time_customers"] == 6
    assert result["repeat_customers"] == 5


def test_statistics_cli_accepts_custom_input_and_output_paths(tmp_path, monkeypatch):
    import sys
    from src.statistics import main

    source = pd.DataFrame([
        {"InvoiceNo": "70001", "StockCode": "X1", "Description": "X", "Quantity": 2,
         "InvoiceDate": "2010-01-05", "UnitPrice": 5.0, "CustomerID": "10001", "Country": "UK"},
        {"InvoiceNo": "70002", "StockCode": "X1", "Description": "X", "Quantity": 1,
         "InvoiceDate": "2010-02-05", "UnitPrice": 5.0, "CustomerID": "10001", "Country": "UK"},
    ])
    cleaned = clean_dataframe(source)
    input_path = tmp_path / "cleaned.csv"
    output_dir = tmp_path / "statistics_output"
    cleaned.to_csv(input_path, index=False)
    monkeypatch.setattr(sys, "argv", ["statistics", "--input", str(input_path), "--output-dir", str(output_dir)])

    main()

    assert (output_dir / "statistical_checks.json").exists()
