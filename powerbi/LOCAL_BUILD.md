# RetailSignal: local Power BI build and data preflight

This repository includes the Python/SQL analytics and a five-page Power BI design specification. The actual PBIX must be saved and visually inspected in Power BI Desktop. The Python preflight below is not a substitute for Desktop or for validating DAX and visual interactions.

## 1. Generate the local exports

Run these commands from the repository root in Windows PowerShell after activating the project virtual environment and installing requirements.txt:

    python -m src.download_data
    python -m src.ingest --inspect-only
    python -m src.ingest
    python -m src.validate
    python -m src.clean
    python powerbi/prepare_data_model.py

Do not skip the schema-inspection gate. The downloaded workbook and generated line-level/customer-level CSVs are intentionally excluded from Git.

## 2. What the preflight does

The script powerbi/prepare_data_model.py checks that required CSV exports exist and have expected columns; checks source-row identifiers; re-evaluates the documented positive-sales rule and cancellation prefix; checks line_value = quantity × unit_price; verifies dimension keys are unique; and reconciles monthly mart totals against date-valid fact rows. It also creates a contiguous daily calendar.

Generated outputs are local only and ignored by Git:

- data/marts/powerbi_date.csv
- data/processed/powerbi_model_validation.json

The JSON report records values found locally, date coverage, table checks, and failed checks. Continue only when the command reports **Power BI preflight: PASSED**. The script does not test Power BI visuals or execute DAX.

## 3. Import tables into Power BI Desktop

Use **Get data → Text/CSV** and import these local exports:

| Power BI table name | Local CSV |
|---|---|
| FactSalesLine | data/processed/fact_sales_lines.csv |
| DimInvoice | data/marts/dim_invoice.csv |
| DimProduct | data/marts/dim_product.csv |
| DimCustomer | data/marts/dim_customer.csv |
| DimCountry | data/marts/dim_country.csv |
| MonthlySales | data/marts/monthly_sales.csv |
| CustomerRFM | data/marts/customer_rfm.csv |
| CohortRetention | data/marts/cohort_retention.csv |
| ProductPerformance | data/marts/product_performance.csv |
| CountryPerformance | data/marts/country_performance.csv |
| DataQualityAudit | data/processed/data_quality_audit.csv |
| Date | data/marts/powerbi_date.csv |

Set Date[Date] to **Date**, FactSalesLine[invoice_date] to **Date/Time**, identifiers to **Text**, Boolean flags to **True/False**, and monetary values to **Decimal number**. Do not change IDs to numeric values: product codes can include letters and leading zeroes.

In Power Query, add InvoiceDateDate to FactSalesLine using Date.From([invoice_date]) and set the new column to Date. Mark Date as the model's date table using Date[Date].

Create single-direction one-to-many relationships from dimensions to the line fact:

- Date[Date] → FactSalesLine[InvoiceDateDate]
- DimProduct[stock_code] → FactSalesLine[stock_code]
- DimCustomer[customer_id] → FactSalesLine[customer_id]
- DimCountry[country] → FactSalesLine[country]
- DimInvoice[invoice_no] → FactSalesLine[invoice_no]

The precomputed MonthlySales, CustomerRFM, and CohortRetention marts have different grains. Do not assume country/product slicers dynamically recalculate those tables. Keep cohort/RFM full-window unless dynamic measures are built and tested; do not sync fact slicers to cohort/RFM by default.

## 4. Add measures, layout, and validate the report

Create the measures documented in powerbi/measures.md, then implement the five-page layout in powerbi/README.md: Executive Overview; Sales Trends; Customer Retention and Cohorts; Product and Country Performance; Returns and Data Quality.

Before calling the report complete, compare these no-filter KPIs against powerbi_model_validation.json and the SQL/Python outputs: net recorded line value, gross positive line sales, eligible sales invoice count, and negative-line magnitude. Also test one month and one country; confirm the C-prefixed invoice filter yields zero gross positive line sales; inspect cohort denominators and final partial-month labeling; and save the PBIX only after opening and reviewing every page in Power BI Desktop.

## Reference end-to-end benchmark

The latest automated UCI + PostgreSQL run is [GitHub Actions run 40089797883](https://github.com/sinanaghdi/retailsignal/actions/runs/40089797883). It processed 1,067,371 rows, reconciled net recorded line value at GBP 19,287,250.57 and gross positive eligible line sales at GBP 20,972,594.57, and matched all 4,916 product rows between Python and PostgreSQL. The local preflight report is the source of truth for local exports; investigate differences rather than overwriting local results with benchmark values.
