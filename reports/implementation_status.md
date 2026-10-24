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
- Three notebooks, five-page Power BI specification, DAX dictionary, local Power BI preflight and Date-table generator, synthetic tests for that utility, interview walkthrough, LinkedIn drafts, case-study outline, and honest resume bullet templates.
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

- **49 tests passed** on Python 3.12 and Python 3.13 in [GitHub Actions run 40091296366](https://github.com/sinanaghdi/retailsignal/actions/runs/40091296366), including four tests for the local Power BI preflight helper. The project-level NumPy timedelta warning no longer appeared; Node.js deprecation messages from the GitHub Actions runner are toolchain warnings, not Python test failures.
- The new regression test confirms that missing product descriptions are quality defects but do not silently remove otherwise computable financial lines.
- Regression contracts verify that the SQL product analysis reads source descriptions through source_row_id, selects the most frequent label among eligible positive-sale lines, and orders product ties deterministically.

## PostgreSQL end-to-end status

**End-to-end validation passed:** [GitHub Actions run 40089797883](https://github.com/sinanaghdi/retailsignal/actions/runs/40089797883).

- All 1,067,371 source rows were loaded in staging and retained in fact.
- All SQL files 02–07 executed against PostgreSQL 16.15.
- Signed totals reconcile: staging and fact both equal GBP 19,287,250.57.
- Eligible positive line sales reconcile to GBP 20,972,594.57 in Python and PostgreSQL.
- Positive invoice count matches at 40,077 and no cancellation-prefixed invoice row is classified as positive sales.
- All 7 PostgreSQL reconciliation checks, all 10 real-data acceptance checks, and full product-catalog parity passed in [GitHub Actions run 40089797883](https://github.com/sinanaghdi/retailsignal/actions/runs/40089797883). All **4,916 of 4,916 products** matched Python and PostgreSQL, across the reconciled product fields, with zero mismatches.

The live dataset run exposed product-query and currency-ranking differences. Product descriptions now use the same deterministic mode rule in Python and PostgreSQL, and product sales are rounded to two GBP decimal places before ranking. The latest full-data reconciliation confirms all 4,916 products match with no mismatches. The staging refresh is transactional, so a failed load or row-count check rolls back rather than leaving a partially refreshed staging table.

Detailed results, hashes, quality counts, statistical tests, and caveats: [reports/real_dataset_benchmark.md](real_dataset_benchmark.md). The aggregate-only CI artifact is [available for 14 days](https://github.com/sinanaghdi/retailsignal/actions/runs/40089797883/artifacts/12557784399).

## Not executed / not claimed

- No real-data Power BI PBIX was built or verified.
- The Power BI preflight has passed on the full UCI-generated exports in [CI run 40091630962](https://github.com/sinanaghdi/retailsignal/actions/runs/40091630962): 1,067,371 fact rows were checked, the preflight reported GBP 19,287,250.57 net recorded value and GBP 20,972,594.57 eligible positive sales, and a 739-day date dimension was generated. The aggregate-only JSON and date table are in [the run artifact](https://github.com/sinanaghdi/retailsignal/actions/runs/40091630962/artifacts/12558834610). This is a CI run rather than a separate local run. The actual PBIX and visual/DAX verification remain a separate Desktop task.
- The full-catalog comparison, deterministic product-description rule, and transactional staging refresh are merged and validated in [PR #3](https://github.com/sinanaghdi/retailsignal/pull/3) and [real-data CI run 40089797883](https://github.com/sinanaghdi/retailsignal/actions/runs/40089797883).
- No business-impact or causal claim is established by these descriptive analyses.
- The UCI dataset is historical UK retail data; it is not evidence of current Iranian market demand.
- Raw workbook and customer-level files are excluded from public Git. CI artifacts are limited to aggregate metrics, quality summaries, and manifest details.

## Data interpretation caveats

Recorded transaction line amounts are not verified collected cash, recognized accounting revenue, gross margin, or profit. Cancellation prefixes, negative quantity, negative line value and exact-duplicate candidates can overlap and must not be summed as if they were disjoint categories. Repeated-purchase status and cohorts are subject to missing customer identifiers and unequal follow-up, especially around the final December 2011 coverage. Statistical comparisons are observational and do not establish causality.
