-- 04 | Customer analytics. Missing CustomerID rows are excluded from identified-customer rates.

-- Identified customer order frequency and monetary value.
WITH purchase_invoices AS (
    SELECT f.customer_id, f.invoice_no, MIN(f.invoice_date) AS invoice_date
    FROM retailsignal.fact_sales_line f
    WHERE f.is_customer_analytics_eligible AND f.invoice_no IS NOT NULL
      AND f.invoice_date IS NOT NULL AND f.is_positive_sales_line
    GROUP BY f.customer_id, f.invoice_no
), customer_frequency AS (
    SELECT customer_id, COUNT(DISTINCT invoice_no) AS frequency_invoices,
           MIN(invoice_date) AS first_purchase_date, MAX(invoice_date) AS last_purchase_date
    FROM purchase_invoices GROUP BY customer_id
), customer_monetary AS (
    SELECT customer_id, SUM(line_value) AS monetary_recorded_gbp
    FROM retailsignal.fact_sales_line
    WHERE is_customer_analytics_eligible AND NOT is_cancellation_invoice AND line_value IS NOT NULL
    GROUP BY customer_id
), observation AS (
    SELECT MAX(invoice_date)::date + 1 AS observation_date FROM retailsignal.fact_sales_line
)
SELECT f.customer_id,
       (o.observation_date - f.last_purchase_date::date) AS recency_days,
       f.frequency_invoices,
       COALESCE(m.monetary_recorded_gbp, 0) AS monetary_recorded_gbp,
       f.first_purchase_date, f.last_purchase_date,
       o.observation_date
FROM customer_frequency f
LEFT JOIN customer_monetary m USING (customer_id)
CROSS JOIN observation o
ORDER BY monetary_recorded_gbp DESC;

-- Repeat-purchase customer rate among customers with a known ID and >=1 eligible purchase.
WITH frequency AS (
    SELECT customer_id, COUNT(DISTINCT invoice_no) AS purchase_invoices
    FROM retailsignal.fact_sales_line
    WHERE is_customer_analytics_eligible AND invoice_no IS NOT NULL AND is_positive_sales_line
    GROUP BY customer_id
)
SELECT COUNT(*) AS identified_customers_with_purchase,
       COUNT(*) FILTER (WHERE purchase_invoices >= 2) AS repeat_customers,
       100.0 * COUNT(*) FILTER (WHERE purchase_invoices >= 2) / NULLIF(COUNT(*), 0) AS repeat_customer_rate_pct,
       AVG(purchase_invoices::numeric) AS mean_purchase_invoices,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY purchase_invoices) AS median_purchase_invoices
FROM frequency;

-- Invoice value distribution: only invoices containing >=1 qualifying positive line.
WITH invoice_values AS (
    SELECT invoice_no, MIN(invoice_date) AS invoice_date,
           SUM(line_value) FILTER (WHERE is_positive_sales_line) AS gross_positive_invoice_value_gbp
    FROM retailsignal.fact_sales_line
    WHERE is_positive_sales_line AND invoice_no IS NOT NULL
    GROUP BY invoice_no
)
SELECT COUNT(*) AS eligible_invoices,
       AVG(gross_positive_invoice_value_gbp) AS mean_positive_invoice_value_gbp,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY gross_positive_invoice_value_gbp) AS median_positive_invoice_value_gbp
FROM invoice_values;
