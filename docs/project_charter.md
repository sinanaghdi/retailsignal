# RetailSignal — Project Charter

## Purpose and intended audience

RetailSignal is a reproducible, business-oriented analytics case study for a junior analyst portfolio. It demonstrates source verification, data-quality reasoning, Python transformation, PostgreSQL analytics, customer behavior metrics, statistical caution, and a management-facing Power BI design. The primary audience is a hiring manager or analytics practitioner reviewing whether the work can be independently reproduced and defended.

## Business problem

A historical online retailer needs to distinguish changes in signed recorded transaction value from changes in positive sales activity and order volume; understand product/country/customer concentration; describe repeat-purchase behavior among customers with reliable identifiers; and investigate cancellation-like and negative-line records without over-claiming that they prove physical returns or refunds.

## Research questions

1. How did monthly recorded sales and qualifying positive line sales change over time, and how did invoice volume move alongside them?
2. Which countries and products contribute most to qualifying positive line sales, and how concentrated is the contribution?
3. What share of identifiable purchasers placed two or more qualifying purchase invoices in the observed period?
4. How does observed cohort activity vary by first eligible purchase month, accounting for incomplete follow-up windows?
5. How do customer recency, qualifying purchase-invoice frequency, and signed recorded monetary value vary across rule-based RFM groupings?
6. How are cancellation-prefixed invoices, negative quantities, negative signed line values, missing IDs, conflicting invoice metadata, and exact duplicate candidates distributed?
7. Which observed differences are sufficiently stable under alternate definitions to justify a small, measurable commercial investigation?
8. What additional data is required to measure profit, margin, customer acquisition cost, refunds, or marketing return on investment?

## Dataset and verification gate

- **Official source:** [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- **Citation:** Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. <https://doi.org/10.24432/C5CG6D>
- **License:** CC BY 4.0 as listed by UCI. Preserve attribution.
- **Source grain:** transaction line, not invoice or customer.
- **Expected columns:** `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`. Verified header aliases are normalized by code; unexpected/missing headers stop the pipeline.
- **Required gate:** download the official workbook, run `python -m src.ingest --inspect-only`, inspect all sheet names/headers, and only then ingest all rows. Do not replace the source with synthetic or third-party data. The build environment could not download the workbook, so real-data results remain pending.

## Technology decisions

| Need | Decision | Reason |
|---|---|---|
| Data access and profiling | Python, pandas, NumPy, openpyxl | Clear, repeatable source inspection and data-quality summaries |
| Exploratory analysis | Jupyter, matplotlib | Interactive review and traceable plots without a complex visualization stack |
| Analytical storage | PostgreSQL | Relational keys, window functions, reproducible analytical queries, reconciliation |
| Database access | SQLAlchemy + psycopg | Standard Python-to-PostgreSQL connection and chunked staging load |
| Customer metrics | pandas + SQL | Independently computed metrics and cross-checks |
| Executive reporting | Power BI Desktop | Familiar filterable management dashboard; `.pbix` must be built and validated in Desktop |
| Quality gates | pytest | Test schema, definitions, edge cases, and row/value reconciliation using isolated synthetic fixtures |
| Reproducibility | Git, requirements.txt, documented commands | Rebuild from official data without committing data or credentials |

Optional forecasting, Docker, and CI are out of the core scope until the core pipeline and reconciliation checks pass.

## Metric contract

| Metric | Definition | Required caveat |
|---|---|---|
| Signed line value | `Quantity * UnitPrice` for each valid numeric row | A recorded amount, not profit or proof of cash settlement |
| Net recorded value | Sum signed line values once | Negative values already reduce the signed sum; do not subtract them a second time |
| Gross positive line sales | Sum lines with quantity > 0, unit price > 0, and invoice ID not starting with `C` | Analytical inclusion rule, not a full accounting-revenue definition |
| Eligible sales invoice | Distinct invoice with at least one qualifying positive line | Different from all recorded invoices |
| Average positive invoice value | Gross positive line sales divided by eligible sales invoices | State filter context and denominator |
| Repeat-purchase rate | Customers with 2+ distinct eligible purchase invoices divided by customers with 1+ eligible purchase invoice | Identified customers only; historical window, not universal retention |
| Cohort activity rate | Cohort customers active in a month divided by cohort size | Later cohorts have less follow-up; not lifetime value |
| RFM Monetary | Signed non-cancellation line value among reliably attributed identified customers | Not contribution margin; compare with positive-only sensitivity |
| Product/country contribution | Eligible positive sales for the label divided by total eligible sales among nonmissing labels | Missing-label population is disclosed |
| Cancellation/negative diagnostics | Independent flags and magnitudes for C-prefixed IDs, negative quantities, and negative signed line values | Categories overlap and are not additive; do not infer a completed physical return |

## Quality risks and treatment

- Missing `CustomerID`: retain; exclude from identified-customer numerators and denominators where identification is required; report coverage.
- Exact duplicate candidates: flag and compare totals with/without extra copies; never delete automatically.
- Invoice-level customer/date/country conflicts: preserve source lines; exclude conflicting customer attribution from customer-level analysis; expose counts.
- Negative quantities, negative values, zero prices, cancellations: separate flags; retain signed values and quantify independently.
- Invalid dates/numeric fields: retain in row-level outputs; exclude only from time-dependent calculations or line-value calculations that require them.
- Outliers and nonstandard stock codes: flag using documented heuristics; investigate, do not auto-remove or infer categories.
- Join multiplication: use unique dimensions and explicit `validate="many_to_one"` assertions, row-count comparisons, and signed-value reconciliation.
- Partial time windows: disclose end date and compare matched month periods only; avoid treating later cohorts as fully observed.

## Architecture and repository contents

```text
UCI workbook → schema gate/ingestion → quality audit → row-preserving fact lines
                                              ├→ Python data marts and notebooks
                                              └→ PostgreSQL staging → dimensions/fact → SQL analyses
Python/SQL reconciled outputs → Power BI model/pages → evidence-backed executive summary
```

See [`architecture.md`](architecture.md) for the model and [`setup.md`](setup.md) for exact commands.

## Milestones and completion criteria

| Milestone | Completion gate | Current status at initial bundle build |
|---|---|---|
| 0 — Charter | Scope, metric rules, source gate, risks, and acceptance criteria documented | Implemented |
| 1 — Environment and audit | Official workbook header gate passes; real audit report produced and reviewed | Code and synthetic tests implemented; source file/schema inspection pending |
| 2 — Cleaning and model | No silent row loss; signed values reconcile; duplicate and invoice-conflict sensitivities exported | Code implemented; synthetic tests pass; real-data verification pending |
| 3 — PostgreSQL | DDL and transformations execute; stage/fact row counts and signed values reconcile | SQL authored and statement-parsed; live PostgreSQL validation pending |
| 4 — Python analysis | EDA, RFM, cohorts, descriptive tables, and at least two statistical checks reviewed from real results | Code and notebooks implemented; real execution pending |
| 5 — Power BI | Five pages built; DAX reconciles to Python/SQL under cleared and filtered contexts | Detailed build guide and measures implemented; Desktop report pending |
| 6 — Findings | Three-to-five evidence-backed recommendations, limitations, and executive narrative completed | Templates only; dependent on real results |
| 7 — Release | Public repository, verified screenshots, clean README, test record, and interview summary | Local bundle created; remote repository and `.pbix` pending |

## Final acceptance checklist

- [ ] Official workbook downloaded from UCI and its path, size, and SHA-256 recorded locally.
- [ ] All workbook sheets pass header checks; source row count is recorded.
- [ ] Audit counts and percentages reviewed; no unexplained row deletion.
- [ ] `line_value = quantity * unit_price` holds for valid numeric rows and totals reconcile.
- [ ] Exact duplicate and alternative RFM-money definitions have sensitivity results.
- [ ] PostgreSQL stage and fact row counts and signed values reconcile exactly within chosen numeric precision.
- [ ] SQL and Python results agree for headline metrics and selected filtered queries.
- [ ] Cohort truncation, missing customer coverage, and metric denominators are disclosed.
- [ ] Statistical checks include group sizes, effect size, assumptions, p-value, and limitations.
- [ ] Five-page Power BI report is built in Desktop and its DAX measures independently checked.
- [ ] Each final recommendation cites its calculation, period, population, caveat, next action, and success evidence.
- [ ] Git repository contains code/docs/tests, not the raw workbook, derived customer-level data, `.env`, or credentials.
