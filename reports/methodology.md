# Analytical Methodology and Metric Dictionary

## Analysis status

Real-data values remain **pending** until `online_retail_II.xlsx` is downloaded, its schema gate passes, and the reproducible pipeline has run. All thresholds and definitions below are specified before reviewing findings to reduce ad hoc metric switching.

## Grain, source, and currency

- Source: UCI Online Retail II, cited in the root README.
- Grain: one source line per row; invoice numbers repeat across item lines.
- Currency: GBP sterling as specified by UCI's price field. No conversion is performed.
- Monetary primitive: `line_value = quantity × unit_price` for numeric quantity and unit price.
- `source_row_id` is a generated trace identifier after sheet concatenation; it is not an original order key.

## Metric dictionary

| Metric | Operational definition | Population/denominator |
|---|---|---|
| Recorded line value | `Quantity × UnitPrice`, signed; sum each row once | All rows with valid numeric quantity and price; optional date filter only if stated |
| Net recorded sales (GBP) | Sum of signed line values | All rows included by the current report filter; negative rows are already signed |
| Gross positive line sales (GBP) | Sum line value where quantity > 0, unit price > 0, and invoice ID does not begin with C | Eligible positive lines, as a source-consistent comparison metric |
| Invoice count | Distinct nonblank invoice identifiers | State if all invoice IDs or qualifying sales invoices only |
| Identified customers | Distinct nonblank `CustomerID` | Rows/invoices that support the particular metric; missing IDs are not imputed |
| Negative line value | Sum of absolute values where signed line value < 0 | Negative signed line rows, counted as a magnitude summary, never subtracted twice |
| Cancellation-related invoice count | Distinct invoice IDs beginning with C after trim/uppercase | Records with usable invoice ID; the flag may coexist with negative quantity |
| Average recorded order value | Gross positive line sales / distinct invoices with at least one qualifying positive line | Qualifying sales invoices; do not use all records as the denominator |
| Month-over-month change | `(current_month_metric / previous_month_metric - 1) × 100` | Adjacent observed calendar months; undefined when prior metric is zero or missing |
| Repeat-purchase customer rate | Identified customers with ≥2 distinct eligible purchase invoices / identified customers with ≥1 eligible purchase invoice | Full observed window; report the time window, do not call this contractual retention |
| Purchase frequency | Count of distinct eligible purchase invoices per identified customer | Customer with at least one eligible purchase invoice |
| Recency | Observation date minus last eligible purchase date, in days | Observation date = max valid source timestamp normalized to date + one day unless explicitly overridden |
| RFM monetary | Signed value on all non-cancellation rows for an identified customer | Not profit; includes ordinary-invoice negative line values and is bounded by missing IDs/history |
| Product/country contribution | Positive line sales for product/country divided by the same metric's included-population total | Missing product/country labels excluded from attribution tables, not globally deleted from line facts |
| Product concentration | Sum of the top N product contributions and cumulative contribution rank | Positive eligible product sales; N must be stated |
| Cohort size | Distinct identified customers whose first eligible purchase is in the cohort month | First eligible purchase month within the dataset window |
| Cohort active customers | Cohort customers with at least one eligible purchase invoice in the activity month | Identified customers only |
| Cohort activity rate | Active customers / original cohort size | Observed window only; later cohort periods are right-censored |

## Classification rules

- **Cancellation-prefixed invoice:** normalized `InvoiceNo` begins with `C`, based on UCI's documented convention.
- **Negative quantity:** `Quantity < 0`.
- **Negative signed line:** `Quantity × UnitPrice < 0`.
- **Credit/return-like flag:** cancellation-prefix OR negative signed line. These are observed record patterns, not confirmation of completed physical return or refund.
- **Qualifying positive sales line:** quantity > 0, unit price > 0, and not cancellation-prefixed. Zero and negative unit prices are excluded from this gross-positive measure but retained in the signed record total when numeric.
- **Exact duplicate candidate:** rows identical across the available canonical source fields; the extra copies are flagged, not removed. Primary totals should be accompanied by a sensitivity comparison excluding flagged extras before a final claim about duplicate impact.

## Customer activity and cohorts

Only nonblank customer identifiers can support customer-level calculations. Purchase frequency is based on distinct invoices with at least one eligible positive line, not every invoice prefix or negative record. A cohort is assigned by the first eligible identifiable purchase month. Month 1 should be 100% active by construction; subsequent months represent observed activity, not a promise or prediction of future retention. Because the data ends during December 2011, December 2011 is incomplete and should not be compared with full months as if the exposure windows were identical.

Repeat purchase, retention, and customer lifetime value are different: repeat purchase is a threshold event during observed history; cohort activity is the share observed active by elapsed month; lifetime value usually requires a well-defined customer-level contribution value and assumptions about future behavior, cost, and censoring that this source alone does not provide.

## RFM scoring

- Recency is measured at maximum valid `InvoiceDate` + one calendar day; smaller is better.
- Frequency is qualifying purchase-invoice count; larger is better.
- Monetary is the signed non-cancellation recorded line value for identified customers; larger values receive higher scores even though the metric is not contribution margin.
- Quintile scores are 1–5 using rank-based quantile bins, with ties broken by rank order for deterministic assignment. If fewer than five customers exist, all scores fall back to 3 to avoid fake precision.
- Labels such as “Champions (behavioral)” and “At-risk frequent” are rule-based behavioral groupings only; they are not verified preferences or intent.
- Sensitivity analysis should compare alternative monetary definitions (positive-only vs signed non-cancellation value), different observation dates, and quintile boundaries before management uses segment labels.

## Statistical checks

1. **Paired month comparison:** two-sided Wilcoxon signed-rank test on matched monthly gross positive line sales for January–November 2010 versus January–November 2011. December 2011 is excluded because the source ends during that month. There are at most 11 pairs; month-level dependence and low power limit inference.
2. **Customer-level spending comparison:** Mann–Whitney U test comparing per-customer mean positive invoice value for one-time purchasers versus repeat purchasers (≥2 eligible invoices). Each customer contributes one summary value. It is still observational, affected by customer tenure and right-censoring, and cannot establish that repeat behavior causes higher order values.

Report group sizes, medians, effect-size context, p-values, and assumptions together. Do not interpret `p < 0.05` as practical importance or causation. A real run may not support either difference as statistically robust.

## Sensitivity and audit requirements before publication

- Report core amounts including all source rows and a separate sensitivity excluding exact duplicate extras.
- Compare sales totals under positive-line and signed-recorded definitions.
- Inspect invoice IDs with more than one customer/date/country value.
- Show identified-customer metrics beside the missing-`CustomerID` share.
- State the final observed timestamp and partial-month caveats.
- Reconcile Python, PostgreSQL, and Power BI with the same filter and metric name.

## RFM sensitivity analysis

`customer_rfm_sensitivity.csv` compares baseline signed non-cancellation monetary values against an alternative that includes only qualifying positive sales lines. It reports changes in the monetary quintile score and in the RFM segment label. Treat any observed segment movement as methodology sensitivity, not as customer behavior changing. Missing/ambiguous invoice attribution is excluded from customer-level metrics while all underlying line values remain in the sales fact.
