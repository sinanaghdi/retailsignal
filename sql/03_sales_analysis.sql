-- 03 | Executive sales analysis. Values are recorded GBP line values, not profit.

-- Monthly signed recorded value versus positive eligible sales and line/invoice volumes.
WITH monthly AS (
    SELECT DATE_TRUNC('month', invoice_date)::date AS month,
           SUM(line_value) AS net_recorded_sales_gbp,
           SUM(line_value) FILTER (WHERE is_positive_sales_line) AS gross_positive_line_sales_gbp,
           SUM(ABS(line_value)) FILTER (WHERE line_value < 0) AS negative_line_value_gbp,
           COUNT(DISTINCT invoice_no) AS recorded_invoices,
           COUNT(DISTINCT invoice_no) FILTER (WHERE is_positive_sales_line) AS sales_invoices,
           COUNT(*) AS line_count
    FROM retailsignal.fact_sales_line
    WHERE invoice_date IS NOT NULL
    GROUP BY 1
)
SELECT *,
       100.0 * (net_recorded_sales_gbp - LAG(net_recorded_sales_gbp) OVER (ORDER BY month))
            / NULLIF(LAG(net_recorded_sales_gbp) OVER (ORDER BY month), 0) AS mom_net_sales_change_pct,
       gross_positive_line_sales_gbp / NULLIF(sales_invoices, 0) AS positive_sales_per_invoice_gbp
FROM monthly ORDER BY month;

-- Month of year comparisons: do not call this seasonality evidence without assessing partial periods.
SELECT EXTRACT(MONTH FROM invoice_date)::int AS calendar_month,
       COUNT(DISTINCT DATE_TRUNC('month', invoice_date)) AS observed_months,
       AVG(monthly_value) AS average_monthly_net_recorded_sales_gbp
FROM (
    SELECT DATE_TRUNC('month', invoice_date) AS invoice_date, SUM(line_value) AS monthly_value
    FROM retailsignal.fact_sales_line
    WHERE invoice_date IS NOT NULL
    GROUP BY 1
) m
GROUP BY 1 ORDER BY 1;

-- Positive line-sales by month with an invoice-volume comparison.
SELECT DATE_TRUNC('month', invoice_date)::date AS month,
       SUM(line_value) FILTER (WHERE is_positive_sales_line) AS gross_positive_line_sales_gbp,
       COUNT(DISTINCT invoice_no) FILTER (WHERE is_positive_sales_line) AS sales_invoice_count,
       COUNT(DISTINCT customer_id) FILTER (WHERE is_positive_sales_line) AS identified_customers
FROM retailsignal.fact_sales_line
WHERE invoice_date IS NOT NULL
GROUP BY 1 ORDER BY 1;
