# Power BI Executive Dashboard Build Guide

> The `.pbix` file is **not** generated in this environment. This specification is designed for implementation and validation in Power BI Desktop after the CSV marts exist.

## 1. Recommended model

Import the following CSVs from the project folder after running `python -m src.clean`:

- `data/processed/fact_sales_lines.csv`
- `data/marts/dim_invoice.csv`
- `data/marts/dim_product.csv`
- `data/marts/dim_customer.csv`
- `data/marts/dim_country.csv`
- `data/marts/monthly_sales.csv`
- `data/marts/customer_rfm.csv`
- `data/marts/cohort_retention.csv`

Rename Power BI tables to `FactSalesLine`, `DimInvoice`, `DimProduct`, `DimCustomer`, `DimCountry`, `MonthlySales`, `CustomerRFM`, and `CohortRetention`. Set date columns to Date or Date/Time, `is_*` columns to True/False, identifiers to Text, amounts to Decimal Number, and contribution percentages to Percentage only if values are divided by 100 in the model. Python exports `retention_rate` as a 0–1 fraction.

Create a dedicated Date table. Mark it as the date table and relate `Date[Date]` (1) to `FactSalesLine[invoice_date date-only]` (*). Keep the date table contiguous through the final observed day; label the last partial month visibly. Use single-direction dimension-to-fact filter paths. Avoid bidirectional and many-to-many relationships unless a specific tested reason exists.

Recommended one-to-many relationships:

| One side | Many side | Key |
|---|---|---|
| `DimProduct[stock_code]` | `FactSalesLine[stock_code]` | Stock code |
| `DimCustomer[customer_id]` | `FactSalesLine[customer_id]` | Customer ID |
| `DimCountry[country]` | `FactSalesLine[country]` | Country |
| `DimInvoice[invoice_no]` | `FactSalesLine[invoice_no]` | Invoice number |
| `Date[Date]` | `FactSalesLine[InvoiceDateDate]` | Date |

Add `InvoiceDateDate` in Power Query by converting `invoice_date` to Date. If using invoice-date filters that are expected to work at line grain, prefer the fact table's line-level `invoice_date` over the invoice dimension's representative date when invoice-level date variants exist. Keep `date_variants`, `customer_variants`, and `country_variants` available for data-quality reporting.

## 2. Design system

Use a restrained professional style: near-white background, charcoal text, one dark navy accent, and one muted teal for positive comparisons. Reserve red/orange for negative values or quality warnings. Use one font family consistently, 8/16/24 px spacing units, clear GBP labels, high contrast, and no 3D charts. Avoid decorative gauges and excessive slicers. Do not present any value without its metric definition or its relevant filter context.

Suggested canvas: 16:9 widescreen (1280 × 720 or Power BI default 16:9). Keep a consistent top header, page title, date coverage subtitle, slicer rail, KPI row, main chart area, and footer containing source/method note.

## 3. Page specifications

### Page 1 — Executive Overview

**Management question:** What happened to recorded commercial activity during the observed period, and where is it concentrated?

- KPI cards: Gross Positive Line Sales (GBP), Net Recorded Sales (GBP), Eligible Sales Invoices, Identified Customers With Purchase, Repeat-Purchase Customer Rate.
- Line chart: monthly gross positive line sales and monthly net recorded line value; if the scale masks the signed series, use two aligned small multiples instead of one distorted axis.
- Column chart: monthly eligible invoice count.
- Bar chart: top five countries by gross positive line sales.
- Bar chart: top ten products by gross positive line sales.
- Slicers: Date, Country, cancellation-related flag (for quality exploration only), Product. Include a visible note that identified-customer KPIs exclude missing CustomerID values.

### Page 2 — Sales Trends and Seasonality

- Line chart: monthly gross positive line sales.
- Combo chart/small multiples: eligible invoice count and average gross positive invoice value.
- Matrix: year × calendar month; blank for unobserved months, distinguish incomplete December 2011.
- Decomposition view: recorded sales alongside eligible line counts; avoid a causal “driver” label.
- Slicers: year, country, product. Use the prior-month metric only if the prior month is in the filtered context; show `N/A` rather than infinite growth for a zero baseline.

### Page 3 — Customer Retention and Cohorts

- KPI cards: Identified Customers With Purchase, Repeat Customers, Repeat-Purchase Customer Rate, Median Purchase-Invoice Count.
- Cohort heatmap: rows = cohort month, columns = elapsed month index, value = `retention_rate`; format as percentage, label the cohort denominator.
- Histogram/column chart: number of customers by eligible purchase-invoice count.
- Bar chart: customers by RFM behavioral segment, annotated “rule-based segment; not verified intent.”
- Scatter: recency days vs signed RFM monetary value, with point transparency and tooltips; consider log scaling only if explained.
- Caveat: cohort cells are observed activity in this finite history; recent cohorts have fewer follow-up months and must not be compared as complete retention curves.

### Page 4 — Product and Country Performance

- Ranked horizontal bars: top 10 products by gross positive line sales.
- Pareto visual: product sales contribution bars and cumulative contribution line; clearly state denominator (all eligible product sales).
- Ranked horizontal bars: top 10 countries, with sales contribution percentage.
- Scatter/bubble: country gross positive line sales vs eligible invoices or identified customers; do not use bubble size unless it adds a defined metric.
- Slicers: date, country, product. Tooltips should show GBP sales, units, invoice count, and contribution %.

### Page 5 — Returns, Cancellations, and Data Quality

- Cards: cancellation-prefixed invoice count, rows with negative quantity, negative signed line value magnitude (GBP), exact duplicate candidate extras, missing CustomerID row share.
- Monthly line/column: signed negative line value magnitude and cancellation-prefixed invoice count; treat them as separate overlapping classifications only when metrics are not additive.
- Matrix: issue metric, affected rows, percent of rows, treatment rationale.
- Bar chart: negative line value by country/product only if adequate nonmissing attribution exists.
- Text: cancellation prefix and negative quantity indicate source-record patterns, not definitive proof of physical returns, customer refunds, or inventory disposition.

## 4. DAX measures

Create a `Measures` table and add the formulas in [`measures.md`](measures.md). Verify boolean and date column names after importing CSVs; rename accordingly.

## 5. Filter behavior and accessibility

- Sync Date, Country, and Product slicers across the fact-based pages (Executive Overview, Sales Trends, Product/Country Performance, and Returns/Data Quality) where the underlying fact table supports the selected filter.
- **Do not sync those slicers to the cohort/RFM page by default.** `CustomerRFM` and `CohortRetention` are precomputed over the full observed history; the current cohort mart has cohort/activity month but no country, and the RFM mart is not dynamically recomputed by a Date slicer. On Page 3, use a separate `cohort_month` slicer and an optional cohort-index filter. Label RFM as full-window unless dynamic RFM is implemented and validated.
- Cross-filter by selecting a bar; use Edit interactions to prevent a selection on a quality chart from silently redefining executive KPIs unless intended. Explicitly review any interaction between precomputed marts and fact-based measures.
- Add report-page tooltips for definitions, denominators, currency, and source period.
- Use descriptive titles and alt text; don't rely on color alone for positive/negative distinctions.
- Make missing-ID coverage visible on customer pages; use full-precision calculations and formatting for GBP.
- Display the last source date and warn that Dec 2011 is partial.

## 6. Validation checklist

1. Check each relationship has the expected cardinality and no accidental many-to-many paths.
2. Compare Power BI gross positive sales, signed net recorded value, invoice count, and negative-line magnitude against Python/SQL exports with all slicers cleared.
3. Filter to one month and one country, then compare the corresponding SQL query manually.
4. Check missing customer IDs do not enter identified-customer counts.
5. Check C-prefixed rows are not counted in gross positive line sales.
6. Check `negative_line_value_gbp` is a magnitude diagnostic; do not subtract it from signed net value again.
7. Confirm all currency labels say GBP and no FX conversion is implied.
8. Save the actual `.pbix` and screenshots only after the validation above is complete. Do not add placeholder screenshots to the portfolio as though they were generated charts.
