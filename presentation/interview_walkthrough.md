# Interview Walkthrough (Approximately 3 Minutes)

## Opening

“RetailSignal is an e-commerce analytics case study using the UCI Online Retail II dataset. I structured it around management questions—sales trends, concentration, repeat purchasing, cohort activity, and negative transaction patterns—then built a reproducible Python-to-PostgreSQL workflow and a Power BI dashboard specification.”

## Technical walkthrough

“I started by inspecting the workbook’s actual sheet headers and checking them against the documented eight-field schema before ingestion. The audit quantifies missing values, exact duplicate candidates, invalid dates and prices, negative quantities, cancellation-prefixed invoice identifiers, and invoice-level inconsistencies. Cleaning preserves each source row and adds flags instead of silently deleting unusual records.

“On the money side, I define line value as quantity multiplied by unit price. I report the signed sum as net recorded line value, separately from gross positive line sales under a documented eligibility rule. That prevents negative transaction values from being subtracted twice and prevents recorded sales from being described as profit.”

## Analytical choices

“Customer metrics exclude missing customer IDs instead of inventing identities. A repeat purchaser needs two distinct eligible purchase invoices during the observed window. Cohort activity is reported by elapsed month, with more recent cohorts marked as having shorter follow-up. RFM segments are rule-based behavioral summaries, not claims about intent. I use pre-specified nonparametric checks and discuss sample size, censoring, and observational limitations.”

## Business communication

“The final dashboard is organized by executive overview, sales trends, cohorts and RFM, product/country contribution, and cancellations/data quality. Any recommendation must cite the exact metric and query, explain uncertainty, and state what additional data or test would verify whether an action worked.”

## Before using this script

Replace general wording with actual measured findings only after the dataset run is complete. Be ready to explain one SQL window function, one data-quality decision, one metric denominator, one failed test/fix, and the difference between observed association and causation. Never claim the Power BI `.pbix`, database run, or business impact unless verified.
