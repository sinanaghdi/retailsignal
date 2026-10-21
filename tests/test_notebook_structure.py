from pathlib import Path
import nbformat

ROOT = Path(__file__).resolve().parents[1]


def test_notebook_files_are_valid_nbformat_documents():
    paths = sorted((ROOT / "notebooks").glob("*.ipynb"))
    assert len(paths) == 3
    for path in paths:
        notebook = nbformat.read(path, as_version=4)
        nbformat.validate(notebook)
        assert notebook.cells
        assert notebook.cells[0].cell_type == "markdown"


def test_invoice_variation_notebook_cell_handles_multiple_fields():
    import pandas as pd

    notebook = nbformat.read(ROOT / "notebooks" / "01_data_quality_audit.ipynb", as_version=4)
    cell = next(
        c for c in notebook.cells
        if c.cell_type == "code" and "variation_summary = pd.DataFrame" in c.source
    )
    raw = pd.DataFrame({
        "InvoiceNo": ["10001", "10001", "10002"],
        "InvoiceDate": ["2010-01-01", "2010-01-02", "2010-02-01"],
        "CustomerID": ["11111", "22222", "33333"],
        "Country": ["United Kingdom", "France", "Germany"],
    })
    namespace = {"pd": pd, "raw": raw, "display": lambda _value: None}
    exec(cell.source, namespace)
    summary = namespace["variation_summary"]
    assert set(summary.index) == {"InvoiceDate_parsed", "CustomerID", "Country"}
    assert (summary["invoice_count"] == 2).all()
    assert int(namespace["variation"].loc["10001", "CustomerID"]) == 2
