-- Rebuild downstream tables from staging. This does not deduplicate or delete source rows.
BEGIN;
TRUNCATE TABLE retailsignal.fact_sales_line, retailsignal.dim_invoice,
    retailsignal.dim_product, retailsignal.dim_customer, retailsignal.dim_country;

INSERT INTO retailsignal.dim_customer (customer_id)
SELECT DISTINCT NULLIF(BTRIM(customer_id), '')
FROM retailsignal.stg_online_retail
WHERE NULLIF(BTRIM(customer_id), '') IS NOT NULL;

-- Match Python's dimension rule: most frequent nonblank description,
-- with deterministic C-collation ascending order as the tie-breaker.
INSERT INTO retailsignal.dim_product (stock_code, description, source_line_count)
WITH description_counts AS (
    SELECT stock_code, NULLIF(BTRIM(description), '') AS description, COUNT(*) AS description_rows
    FROM retailsignal.stg_online_retail
    WHERE NULLIF(BTRIM(stock_code), '') IS NOT NULL
    GROUP BY stock_code, NULLIF(BTRIM(description), '')
), ranked_descriptions AS (
    SELECT stock_code, description,
           ROW_NUMBER() OVER (
               PARTITION BY stock_code
               ORDER BY description_rows DESC, description COLLATE "C" ASC NULLS LAST
           ) AS label_rank
    FROM description_counts
)
SELECT s.stock_code, d.description, COUNT(*)
FROM retailsignal.stg_online_retail AS s
LEFT JOIN ranked_descriptions AS d
  ON d.stock_code = s.stock_code AND d.label_rank = 1
WHERE NULLIF(BTRIM(s.stock_code), '') IS NOT NULL
GROUP BY s.stock_code, d.description;

INSERT INTO retailsignal.dim_country (country)
SELECT DISTINCT NULLIF(BTRIM(country), '')
FROM retailsignal.stg_online_retail
WHERE NULLIF(BTRIM(country), '') IS NOT NULL;

-- MIN is a deterministic representative when source rows disagree. The *_variants columns
-- make such disagreement visible; downstream customer attribution should be caveated if > 1.
INSERT INTO retailsignal.dim_invoice (
    invoice_no, invoice_date, customer_id, country, is_cancellation_invoice,
    source_line_count, date_variants, customer_variants, country_variants
)
SELECT invoice_no,
       MIN(invoice_date),
       MIN(NULLIF(BTRIM(customer_id), '')),
       MIN(NULLIF(BTRIM(country), '')),
       UPPER(BTRIM(invoice_no)) LIKE 'C%',
       COUNT(*),
       COUNT(DISTINCT invoice_date),
       COUNT(DISTINCT NULLIF(BTRIM(customer_id), '')),
       COUNT(DISTINCT NULLIF(BTRIM(country), ''))
FROM retailsignal.stg_online_retail
WHERE NULLIF(BTRIM(invoice_no), '') IS NOT NULL
GROUP BY invoice_no;

INSERT INTO retailsignal.fact_sales_line (
    source_row_id, invoice_no, stock_code, customer_id, country, invoice_date,
    quantity, unit_price, line_value, is_cancellation_invoice,
    is_negative_quantity, is_negative_line_value, is_positive_sales_line,
    is_customer_analytics_eligible, is_exact_duplicate_extra_row
)
WITH marked AS (
    SELECT s.*, ROW_NUMBER() OVER (
        PARTITION BY invoice_no, stock_code, description, quantity, invoice_date, unit_price, customer_id, country
        ORDER BY source_row_id
    ) AS duplicate_sequence
    FROM retailsignal.stg_online_retail s
)
SELECT s.source_row_id,
       NULLIF(BTRIM(s.invoice_no), ''),
       NULLIF(BTRIM(s.stock_code), ''),
       NULLIF(BTRIM(s.customer_id), ''),
       NULLIF(BTRIM(s.country), ''),
       s.invoice_date,
       s.quantity,
       s.unit_price,
       s.quantity * s.unit_price,
       UPPER(BTRIM(COALESCE(s.invoice_no, ''))) LIKE 'C%',
       COALESCE(s.quantity < 0, FALSE),
       COALESCE(s.quantity * s.unit_price < 0, FALSE),
       COALESCE(s.quantity > 0 AND s.unit_price > 0
                AND UPPER(BTRIM(COALESCE(s.invoice_no, ''))) NOT LIKE 'C%', FALSE),
       COALESCE(NULLIF(BTRIM(s.customer_id), '') IS NOT NULL
                AND i.customer_variants <= 1, FALSE),
       s.is_exact_duplicate_extra_row OR s.duplicate_sequence > 1
FROM marked s
LEFT JOIN retailsignal.dim_invoice i ON i.invoice_no = NULLIF(BTRIM(s.invoice_no), '');
COMMIT;

-- Pipeline reconciliation: these should match after the transformation.
SELECT 'staging_rows' AS check_name, COUNT(*)::BIGINT AS row_count FROM retailsignal.stg_online_retail
UNION ALL
SELECT 'fact_rows', COUNT(*)::BIGINT FROM retailsignal.fact_sales_line;

SELECT
    (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM retailsignal.stg_online_retail) AS staging_signed_value_gbp,
    (SELECT COALESCE(SUM(line_value), 0) FROM retailsignal.fact_sales_line) AS fact_signed_value_gbp;
