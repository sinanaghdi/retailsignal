from __future__ import annotations
import pandas as pd
import pytest
from src.ingest import inspect_workbook, ingest_workbook


def _rows(invoice, customer):
    return pd.DataFrame([{
        "Invoice": invoice, "StockCode": "12345", "Description": "Test item",
        "Quantity": 2, "InvoiceDate": "2010-01-01 10:00:00", "Price": 4.5,
        "Customer ID": customer, "Country": "United Kingdom",
    }])


def test_workbook_schema_inspection_and_multisheet_ingestion(tmp_path):
    workbook = tmp_path / "synthetic_fixture.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        _rows("10001", 12345).to_excel(writer, sheet_name="Period A", index=False)
        _rows("10002", 67890).rename(columns={
            "Invoice": "InvoiceNo", "Price": "UnitPrice", "Customer ID": "CustomerID"
        }).to_excel(writer, sheet_name="Period B", index=False)

    inspection = inspect_workbook(workbook)
    assert [sheet["sheet"] for sheet in inspection["sheets"]] == ["Period A", "Period B"]
    assert all(not sheet["missing_required"] for sheet in inspection["sheets"])

    output = tmp_path / "ingested.csv"
    result = ingest_workbook(workbook, output)
    assert len(result) == 2
    assert result["source_row_id"].tolist() == [1, 2]
    assert set(result["source_sheet"]) == {"Period A", "Period B"}
    assert {"InvoiceNo", "UnitPrice", "CustomerID"}.issubset(result.columns)
    assert output.exists()


def test_workbook_schema_gate_rejects_missing_required_header(tmp_path):
    workbook = tmp_path / "bad_fixture.xlsx"
    bad = _rows("10001", 12345).drop(columns=["Country"])
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        bad.to_excel(writer, sheet_name="Broken", index=False)
    with pytest.raises(ValueError, match="Workbook headers do not match"):
        inspect_workbook(workbook)
