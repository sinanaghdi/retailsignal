-- 05 | Monthly customer cohorts, using the first eligible identified purchase month.
WITH purchase_invoices AS (
    SELECT customer_id, invoice_no, DATE_TRUNC('month', MIN(invoice_date))::date AS activity_month
    FROM retailsignal.fact_sales_line
    WHERE is_customer_analytics_eligible AND invoice_no IS NOT NULL
      AND invoice_date IS NOT NULL AND is_positive_sales_line
    GROUP BY customer_id, invoice_no
), first_purchase AS (
    SELECT customer_id, MIN(activity_month) AS cohort_month
    FROM purchase_invoices GROUP BY customer_id
), cohort_activity AS (
    SELECT fp.cohort_month, pi.activity_month,
           ((EXTRACT(YEAR FROM pi.activity_month) - EXTRACT(YEAR FROM fp.cohort_month)) * 12
            + EXTRACT(MONTH FROM pi.activity_month) - EXTRACT(MONTH FROM fp.cohort_month) + 1)::int AS cohort_index,
           COUNT(DISTINCT pi.customer_id) AS active_customers
    FROM purchase_invoices pi
    JOIN first_purchase fp USING (customer_id)
    GROUP BY 1, 2, 3
), cohort_sizes AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_size
    FROM first_purchase GROUP BY cohort_month
)
SELECT ca.cohort_month, ca.activity_month, ca.cohort_index,
       ca.active_customers, cs.cohort_size,
       ca.active_customers::numeric / NULLIF(cs.cohort_size, 0) AS retention_rate
FROM cohort_activity ca JOIN cohort_sizes cs USING (cohort_month)
ORDER BY ca.cohort_month, ca.cohort_index;

-- Cohort completeness guard: recent cohorts have fewer observed follow-up months.
SELECT DATE_TRUNC('month', MAX(invoice_date))::date AS final_observed_month,
       DATE_TRUNC('month', MIN(invoice_date))::date AS first_observed_month,
       COUNT(DISTINCT DATE_TRUNC('month', invoice_date)) AS observed_calendar_months
FROM retailsignal.fact_sales_line WHERE invoice_date IS NOT NULL;
