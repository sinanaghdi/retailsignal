-- 07 | Run after staging and after transformations. Each query should be reviewed.

-- Row-count and signed-value reconciliation.
SELECT 'staging' AS layer, COUNT(*) AS rows, SUM(quantity * unit_price) AS signed_line_value_gbp
FROM retailsignal.stg_online_retail
UNION ALL
SELECT 'fact', COUNT(*), SUM(line_value) FROM retailsignal.fact_sales_line;

-- Check referential integrity and missing join keys.
SELECT COUNT(*) FILTER (WHERE invoice_no IS NULL) AS rows_missing_invoice_no,
       COUNT(*) FILTER (WHERE stock_code IS NULL) AS rows_missing_stock_code,
       COUNT(*) FILTER (WHERE customer_id IS NULL) AS rows_missing_customer_id,
       COUNT(*) FILTER (WHERE country IS NULL) AS rows_missing_country,
       COUNT(*) FILTER (WHERE invoice_date IS NULL) AS rows_missing_or_invalid_invoice_date
FROM retailsignal.fact_sales_line;

-- Invoice-level metadata variation; counts above one indicate conflicting source values.
SELECT COUNT(*) FILTER (WHERE date_variants > 1) AS invoices_with_multiple_dates,
       COUNT(*) FILTER (WHERE customer_variants > 1) AS invoices_with_multiple_customer_ids,
       COUNT(*) FILTER (WHERE country_variants > 1) AS invoices_with_multiple_countries
FROM retailsignal.dim_invoice;

-- Exact duplicate candidates: staging source values excluding trace identifiers.
WITH marked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY invoice_no, stock_code, description, quantity, invoice_date, unit_price, customer_id, country
        ORDER BY source_row_id
    ) AS duplicate_sequence
    FROM retailsignal.stg_online_retail
)
SELECT COUNT(*) FILTER (WHERE duplicate_sequence > 1) AS exact_duplicate_extra_rows
FROM marked;

-- Check classification overlap. A cancellation invoice should not qualify as a positive sales line.
SELECT COUNT(*) AS cancellation_rows_misclassified_as_positive_sales
FROM retailsignal.fact_sales_line
WHERE is_cancellation_invoice AND is_positive_sales_line;

-- Independent diagnostics overlap by design: a C-prefixed invoice can also have a negative quantity.
-- These diagnostic amounts are NOT additive; the signed net total above already includes each line once.
SELECT 'Cancellation-prefixed invoice rows' AS diagnostic, COUNT(*) AS rows,
       COUNT(DISTINCT invoice_no) AS invoices, SUM(line_value) AS signed_line_value_gbp,
       -SUM(line_value) FILTER (WHERE line_value < 0) AS absolute_negative_value_gbp
FROM retailsignal.fact_sales_line WHERE is_cancellation_invoice
UNION ALL
SELECT 'Negative quantity rows', COUNT(*), COUNT(DISTINCT invoice_no), SUM(line_value),
       -SUM(line_value) FILTER (WHERE line_value < 0)
FROM retailsignal.fact_sales_line WHERE is_negative_quantity
UNION ALL
SELECT 'Negative signed line-value rows', COUNT(*), COUNT(DISTINCT invoice_no), SUM(line_value),
       -SUM(line_value) FILTER (WHERE line_value < 0)
FROM retailsignal.fact_sales_line WHERE is_negative_line_value;
