"""Shared paths, schema requirements, and dataset metadata for RetailSignal."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MARTS_DIR = PROJECT_ROOT / "data" / "marts"
DEFAULT_WORKBOOK = RAW_DIR / "online_retail_II.xlsx"
DEFAULT_INGESTED = PROCESSED_DIR / "01_ingested.csv"
DEFAULT_CLEANED = PROCESSED_DIR / "fact_sales_lines.csv"

REQUIRED_COLUMNS = (
    "InvoiceNo", "StockCode", "Description", "Quantity",
    "InvoiceDate", "UnitPrice", "CustomerID", "Country",
)

COLUMN_ALIASES = {
    "InvoiceNo": {"invoiceno", "invoice", "invoice no", "invoice_no", "invoice number"},
    "StockCode": {"stockcode", "stock code", "stock_code", "item code"},
    "Description": {"description", "product description", "item description"},
    "Quantity": {"quantity", "qty", "units"},
    "InvoiceDate": {"invoicedate", "invoice date", "invoice_date", "date"},
    "UnitPrice": {"unitprice", "unit price", "price", "unit_price"},
    "CustomerID": {"customerid", "customer id", "customer_id", "customer number"},
    "Country": {"country", "customer country"},
}

DATASET_URL = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
DATASET_DOWNLOAD_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
DATASET_DOI = "https://doi.org/10.24432/C5CG6D"
CURRENCY = "GBP"
