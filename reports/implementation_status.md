# Implementation Status and Validation Evidence

**Last checked:** 2026-10-24

## Implemented

- Project charter, architecture, source attribution, metric dictionary, limitations, setup guide, README, MIT code license, .env.example, and .gitignore.
- Official UCI workbook downloader: streamed download, bounded retries, ZIP validation, extraction of only online_retail_II.xlsx, fail-fast schema inspection, SHA-256 manifest, and no-overwrite default.
- Canonical column normalization and multi-sheet ingestion with source-row IDs and no intentional row deletion.
- Data-quality audit with counts/percentages and rationale for missing/blank values, exact duplicate candidates, invoice attribute variations, cancellation prefixes, negative quantities/values, invalid fields, line-value outliers, nonstandard stock codes, and customer-ID shape anomalies.
- Row-preserving transaction cleaning, signed line values, defined positive-sale eligibility, customer-attribution ambiguity flags, and 15 generated analytical marts.
- Python metrics for monthly sales, product/country performance, cancellation/negative-record diagnostics, repeat purchases, cohorts, RFM, customer concentration, duplicate sensitivity, and alternative RFM monetary definitions.
- PostgreSQL staging schema, fact/dimension model, transformations, analytical queries, reconciliation checks, and Python SQL execution/loading utilities.
- Three notebooks, five-page Power BI specification, DAX dictionary, interview walkthrough, LinkedIn drafts, case-study outline, and honest resume bullet templates.
- GitHub Actions unit tests and official-source + PostgreSQL end-to-end workflow.

## Executed on the official source

Source: [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), DOI 10.24432/C5CG6D, CC BY 4.0.

The official workbook was downloaded in GitHub Actions. Schema inspection passed for both worksheets, Year 2009-2010 and Year 2010-2011. Ingest produced **1,067,371 rows**. Cleaning retained **1,067,371 rows** (no intentional row deletion).

Actual run output:
- Signed recorded line value: **GBP 19,287,250.57**.
- Gross positive eligible line sales: **GBP 20,972,594.57**.
- 15 analytical marts were written.
- Statistical check for January–November 2010 versus January–November 2011: 11 paired months, Wilcoxon signed-rank p=0.51953125; the test does not support a conventional p<0.05 claim of a paired-month difference.
- Per-customer mean positive invoice value comparison: one-time purchasers n=1,623, median GBP 232.48; repeat purchasers n=4,255, median GBP 300.88; Mann–Whitney p=1.533525e-31, rank-biserial effect 0.1968. This is observational association, not causal evidence.

Detailed interpretation and source limitations: [reports/real_dataset_benchmark.md](real_dataset_benchmark.md).

## Software tests

- **41 tests passed** on Python 3.12 and Python 3.13 in [GitHub Actions run 39748609139](https://github.com/sinanaghdi/retailsignal/actions/runs/39748609139).
- The new regression test confirms that missing product descriptions are quality defects but do not silently remove otherwise computable financial lines.
- Regression contracts verify that the SQL product analysis reads source descriptions through source_row_id, selects the most frequent label among eligible positive-sale lines, and orders product ties deterministically.

## PostgreSQL end-to-end status

**End-to-end validation passed:** [GitHub Actions run 39748609227](https://github.com/sinanaghdi/retailsignal/actions/runs/39748609227).

- All 1,067,371 source rows were loaded in staging and retained in fact.
- All SQL files 02–07 executed against PostgreSQL 16.15.
- Signed totals reconcile: staging and fact both equal GBP 19,287,250.57.
- Eligible positive line sales reconcile to GBP 20,972,594.57 in Python and PostgreSQL.
- Positive invoice count matches at 40,077 and no cancellation-prefixed invoice row is classified as positive sales.
- All 7 PostgreSQL reconciliation checks, all 10 real-data acceptance checks, and the additional top-10 parity check passed. The top 10 products matched Python vs PostgreSQL across 7 fields per product with no mismatches.

The live dataset run exposed two product-query defects: reading description from fact_sales_line (a column that does not exist there) and selecting a label from a generic dimension that could differ from the most frequent description among positive-sale lines. The current query uses source descriptions joined through source_row_id and ranks the mode description; the latest successful real-data acceptance check compared top-10 labels and metrics with Python, with no mismatches. The initial workflow also ran the million-row pipeline twice; that duplicate work has been removed.

Detailed results, hashes, quality counts, statistical tests, and caveats: [reports/real_dataset_benchmark.md](real_dataset_benchmark.md). The aggregate-only CI artifact is [available for 14 days](https://github.com/sinanaghdi/retailsignal/actions/runs/39748609227/artifacts/12412073337).

## Not executed / not claimed

- No real-data Power BI PBIX was built or verified.
- The branch fix/docs-product-parity-atomic-staging adds a full-catalog Python/PostgreSQL product comparison, tests the deterministic product-description rule, and makes staging refresh transactional. These changes are pending branch CI; update this section with the actual run outcome before merging.
- No business-impact or causal claim is established by these descriptive analyses.
- The UCI dataset is historical UK retail data; it is not evidence of current Iranian market demand.
- Raw workbook and customer-level files are excluded from public Git. CI artifacts are limited to aggregate metrics, quality summaries, and manifest details.

## Data interpretation caveats

Recorded transaction line amounts are not verified collected cash, recognized accounting revenue, gross margin, or profit. Cancellation prefixes, negative quantity, negative line value and exact-duplicate candidates can overlap and must not be summed as if they were disjoint categories. Repeated-purchase status and cohorts are subject to missing customer identifiers and unequal follow-up, especially around the final December 2011 coverage. Statistical comparisons are observational and do not establish causality.
