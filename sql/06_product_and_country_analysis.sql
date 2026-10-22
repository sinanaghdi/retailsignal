-- 06 | Product and country performance, using eligible positive sales lines.
WITH sales_description_counts AS (
    -- Match the Python product mart: most common description among eligible positive-sales source rows.
    SELECT f.stock_code, NULLIF(BTRIM(s.description), '') AS description, COUNT(*) AS description_rows
    FROM retailsignal.fact_sales_line AS f
    JOIN retailsignal.stg_online_retail AS s ON s.source_row_id = f.source_row_id
    WHERE f.is_positive_sales_line
      AND f.stock_code IS NOT NULL
      AND NULLIF(BTRIM(s.description), '') IS NOT NULL
    GROUP BY f.stock_code, NULLIF(BTRIM(s.description), '')
), ranked_descriptions AS (
    SELECT stock_code, description, description_rows,
           ROW_NUMBER() OVER (
               PARTITION BY stock_code
               ORDER BY description_rows DESC, description COLLATE "C" ASC
           ) AS label_rank
    FROM sales_description_counts
), product_sales AS (
    SELECT f.stock_code, d.description,
           SUM(f.line_value) AS gross_positive_line_sales_gbp,
           SUM(f.quantity) AS positive_units,
           COUNT(DISTINCT f.invoice_no) AS invoice_count
    FROM retailsignal.fact_sales_line AS f
    LEFT JOIN ranked_descriptions AS d
      ON d.stock_code = f.stock_code AND d.label_rank = 1
    WHERE f.is_positive_sales_line AND f.stock_code IS NOT NULL
    GROUP BY f.stock_code, d.description
), ranked AS (
    SELECT *, SUM(gross_positive_line_sales_gbp) OVER () AS total_sales,
           ROW_NUMBER() OVER (ORDER BY gross_positive_line_sales_gbp DESC, stock_code COLLATE "C") AS sales_rank,
           SUM(gross_positive_line_sales_gbp) OVER (ORDER BY gross_positive_line_sales_gbp DESC, stock_code COLLATE "C"
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_sales
    FROM product_sales
)
SELECT stock_code, description, sales_rank, gross_positive_line_sales_gbp,
       100.0 * gross_positive_line_sales_gbp / NULLIF(total_sales, 0) AS sales_contribution_pct,
       100.0 * cumulative_sales / NULLIF(total_sales, 0) AS cumulative_contribution_pct,
       positive_units, invoice_count
FROM ranked ORDER BY sales_rank;

-- Country contribution; missing country records are excluded from this attribution table, not from totals.
WITH country_sales AS (
    SELECT country, SUM(line_value) AS gross_positive_line_sales_gbp,
           SUM(quantity) AS positive_units,
           COUNT(DISTINCT invoice_no) AS invoice_count,
           COUNT(DISTINCT customer_id) AS identified_customers
    FROM retailsignal.fact_sales_line
    WHERE is_positive_sales_line AND country IS NOT NULL
    GROUP BY country
)
SELECT *, 100.0 * gross_positive_line_sales_gbp / NULLIF(SUM(gross_positive_line_sales_gbp) OVER (), 0) AS sales_contribution_pct,
       RANK() OVER (ORDER BY gross_positive_line_sales_gbp DESC) AS sales_rank
FROM country_sales ORDER BY gross_positive_line_sales_gbp DESC;

-- Customer positive-sales contribution and concentration among reliably identified purchasers.
-- Anonymous records are not allocated to invented customers; this denominator is identified customers only.
WITH customer_values AS (
    SELECT customer_id, SUM(line_value) AS gross_positive_line_sales_gbp,
           COUNT(DISTINCT invoice_no) AS eligible_invoices
    FROM retailsignal.fact_sales_line
    WHERE is_customer_analytics_eligible AND is_positive_sales_line AND customer_id IS NOT NULL
    GROUP BY customer_id
), ranked AS (
    SELECT *, SUM(gross_positive_line_sales_gbp) OVER () AS total_value,
           SUM(gross_positive_line_sales_gbp) OVER (ORDER BY gross_positive_line_sales_gbp DESC, customer_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_value,
           ROW_NUMBER() OVER (ORDER BY gross_positive_line_sales_gbp DESC, customer_id) AS customer_rank,
           COUNT(*) OVER () AS customer_count
    FROM customer_values
)
SELECT customer_id, customer_rank, gross_positive_line_sales_gbp, eligible_invoices,
       100.0 * gross_positive_line_sales_gbp / NULLIF(total_value, 0) AS contribution_pct,
       100.0 * cumulative_value / NULLIF(total_value, 0) AS cumulative_contribution_pct,
       100.0 * customer_rank / NULLIF(customer_count, 0) AS cumulative_customer_pct
FROM ranked ORDER BY customer_rank;

-- Distribution of cancellation/negative records across time, product, and country where labels exist.
-- Classifications overlap; do not add these category counts together.
SELECT DATE_TRUNC('month', invoice_date)::date AS month, country, stock_code,
       COUNT(*) FILTER (WHERE is_cancellation_invoice) AS cancellation_prefixed_rows,
       COUNT(DISTINCT invoice_no) FILTER (WHERE is_cancellation_invoice) AS cancellation_prefixed_invoices,
       COUNT(*) FILTER (WHERE is_negative_quantity) AS negative_quantity_rows,
       COUNT(*) FILTER (WHERE is_negative_line_value) AS negative_signed_line_rows,
       -SUM(line_value) FILTER (WHERE line_value < 0) AS negative_line_value_magnitude_gbp
FROM retailsignal.fact_sales_line
WHERE is_cancellation_invoice OR is_negative_quantity OR is_negative_line_value
GROUP BY 1, 2, 3
ORDER BY month, negative_line_value_magnitude_gbp DESC NULLS LAST;
