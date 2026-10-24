# Executive Summary — RetailSignal

**Status: Python and PostgreSQL real-data pipeline validated; Power BI dashboard remains pending.**

The official UCI Online Retail II workbook was processed in GitHub Actions. The reproducible run retained all 1,067,371 source rows, generated 15 analytical marts, executed SQL files 02–07 against PostgreSQL 16, and reconciled Python and PostgreSQL totals. The evidence and definitions are in [the real-data benchmark report](real_dataset_benchmark.md).

## Business question

How can a historical online retailer distinguish changes in recorded sales activity from order-volume changes, identify concentrated product/customer contributions, and describe observed repeat purchasing without overstating the evidence?

## Verified descriptive results

| Measure | Observed result | Interpretation |
|---|---:|---|
| Source rows | 1,067,371 | All rows retained through ingestion and cleaning |
| Net signed line value | £19,287,250.57 | Sum of recorded line values, including negative values |
| Gross positive eligible line sales | £20,972,594.57 | Positive quantity, positive price, non-cancellation-prefixed lines |
| Eligible positive-sales invoices | 40,077 | Distinct invoice IDs with qualifying positive sales |
| Identified customers in customer analysis | 5,878 | Only records that support customer-level attribution |
| Repeat purchasers | 4,255 / 5,878 (72.3886%) | At least two eligible purchase invoices within the observed window |
| Product codes in product mart | 4,916 | Ranking is by code; descriptions may vary within a code |
| PostgreSQL reconciliation | 7 / 7 checks passed | See the linked CI evidence in the benchmark report |
| Python real-data acceptance checks | 10 / 10 passed | See the linked CI evidence in the benchmark report |

All amounts are recorded transaction-line values in GBP. They are not verified collected cash, recognized accounting revenue, gross margin, or profit.

## Statistical checks and limits

- For matched January–November months in 2010 versus 2011, the paired Wilcoxon test used 11 pairs and returned p = 0.51953125. This does not support a conventional p < 0.05 claim of a difference in those matched monthly observations.
- Mean positive invoice value per customer differed between one-time and repeat purchasers in this historical sample (medians £232.48 and £300.88; Mann–Whitney p = 1.533525×10⁻³¹; rank-biserial effect 0.1968). This is observational association, not evidence that repeat purchasing causes higher spending.
- December 2011 is incomplete; later cohorts have unequal follow-up. Missing customer identifiers and conflicting invoice metadata constrain attribution.

## Potential follow-up questions—not business recommendations

After reviewing the detailed product/customer outputs and validating the dashboard, the analysis may help formulate hypotheses about product concentration, observed repeat purchase, and differences by country. Any intervention should be treated as a testable hypothesis, not a proven business action.

## Data not available in this source

The dataset does not establish actual profit/margin, customer acquisition cost, marketing ROI, payment collection, or completed physical returns/refunds. Those require cost, campaign, settlement, and operational records.

## Delivery status

- **Validated:** Python processing, 15 marts, PostgreSQL transformations, row/value reconciliation, and full product-catalog parity: 4,916/4,916 products match between Python and PostgreSQL in [CI run 40089142209](https://github.com/sinanaghdi/retailsignal/actions/runs/40089142209). The Python test matrix passed 45 tests on each of Python 3.12 and 3.13 in [CI run 40089142207](https://github.com/sinanaghdi/retailsignal/actions/runs/40089142207).
- **Still pending:** build and visual validation of a Power BI .pbix report. This project does not claim a finished dashboard.
- **Still pending:** build and visual validation of a Power BI `.pbix` report in Power BI Desktop. The repository contains the dashboard specification and DAX definitions, not a verified finished dashboard.
