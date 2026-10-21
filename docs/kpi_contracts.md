# KPI Contracts and Publication Rules

This document defines the denominator, grain, inclusion rules, and caveats for metrics exposed by RetailSignal. All currency values are recorded GBP line values, not accounting revenue, cash receipts, profit, or marketing return.

## Transaction-line measures

| Metric | Formula / numerator | Denominator | Grain and eligibility | Caveat |
|---|---|---|---|---|
| Signed recorded line value | Sum of non-null quantity × unit price | Not applicable (additive amount) | Source line; all rows with computable line value | Keeps negative quantities/prices and cancellation-prefixed invoice rows. A negative amount is not automatically a confirmed physical return. |
| Eligible positive line sales | Sum of line value where quantity > 0, unit price > 0, invoice number does not start with C, and line value is valid | Not applicable (additive amount) | Eligible source line | It is a positive-sales proxy, not recognized accounting revenue. |
| Negative line-value magnitude | Sum of absolute line value for rows where line value < 0 | Not applicable (diagnostic amount) | Source line with negative line value | Report separately; do not subtract it again from signed recorded line value. |
| Recorded invoice count | Count distinct non-null invoice identifiers | Not applicable (count) | Invoices represented by rows with valid dates in the selected period | Does not mean paid or fulfilled invoices. |
| Eligible sales invoice count | Count distinct non-null invoice identifiers with at least one eligible positive sales line | Not applicable (count) | Invoice containing one or more eligible positive lines | Multiple lines in one invoice count once. |
| Average eligible invoice value | Eligible positive line sales / eligible sales invoice count | Distinct eligible sales invoices | Period/invoice population must match numerator | Null when the denominator is zero; do not report zero as if a sale occurred. |

## Customer measures

| Metric | Numerator | Denominator | Eligibility |
|---|---|---|---|
| Identified purchasers | Distinct non-null customer IDs with at least one qualifying positive invoice | Not applicable (count) | Excludes missing customer IDs and invoices with conflicting customer attribution. |
| Repeat-purchaser rate | Identified purchasers with at least 2 distinct qualifying invoices during the observation window | Identified purchasers with at least 1 qualifying invoice | Not a retention/churn rate and not forward-looking lifetime value. |
| Cohort retention at month N | Distinct customers in a first-purchase cohort with an eligible invoice in cohort month + N | Distinct eligible customers whose first qualifying purchase is in that cohort month | Month 0 should be 100%; show the cohort size and label cohorts with incomplete follow-up. |
| RFM frequency | Count distinct qualifying purchase invoices | Not a ratio | Identifiable customers only; customer attribution conflicts are excluded. |
| RFM monetary (baseline) | Sum signed line values on non-cancellation lines attributed to eligible identified customers | Not a ratio | This is recorded monetary value, not profit. Also compare to positive-sales-only monetary because negative lines can change rankings. |

## Data quality and coverage measures

- Invalid-row rate = rows classified invalid / parsed data rows. Rows that fail before parsing must be counted separately because they are not in this denominator.
- Exact-duplicate candidate rate = extra exact-matching rows / parsed data rows. Candidates remain preserved unless a documented sensitivity analysis justifies an alternate view.
- Missing-customer share = rows with missing customer ID / parsed data rows; do not imply that missing IDs are distinct customers.
- Any KPI without a populated, schema-approved real-data manifest must be labelled PENDING — real dataset not validated.
- SQL/Pandas reconciliation is required on the same fixed fixture before claims are published. PostgreSQL-specific SQL is not considered validated until it is executed against PostgreSQL.

## Publication checklist

1. Confirm the source URL, attribution, terms, file hash, worksheets, header map and row counts.
2. Run schema checks, row-preserving audit, cleaning and all tests.
3. Record the command, runtime, versions and result in the implementation report.
4. Reconcile denominator and numerator for every published KPI.
5. Keep findings pending if the official workbook cannot be validated. Never substitute synthetic fixture values for real business findings.
