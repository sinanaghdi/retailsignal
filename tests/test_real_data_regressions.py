import pandas as pd
from src.clean import clean_dataframe
from src.metrics import build_monthly_sales
from src.validate import audit_dataframe

def test_missing_product_description_preserves_financial_line_value():
    source = pd.DataFrame([
        {"InvoiceNo":"1001","StockCode":"A1","Description":None,"Quantity":2,"InvoiceDate":"2010-12-01 08:00:00","UnitPrice":3.5,"CustomerID":"100","Country":"United Kingdom"},
        {"InvoiceNo":"1002","StockCode":"A2","Description":"Item","Quantity":1,"InvoiceDate":"2010-12-01 09:00:00","UnitPrice":5.0,"CustomerID":"100","Country":"United Kingdom"}
    ])
    audit,_=audit_dataframe(source)
    clean=clean_dataframe(source)
    monthly=build_monthly_sales(clean)
    assert len(clean)==len(source)
    assert clean["line_value"].sum()==12.0
    assert monthly["gross_positive_line_sales_gbp"].sum()==12.0
    missing_desc=audit.loc[audit["metric"]=="missing_Description","affected_count"].iloc[0]
    assert int(missing_desc)==1
