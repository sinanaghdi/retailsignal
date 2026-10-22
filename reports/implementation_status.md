# Implementation Status and Validation Evidence

**Last checked:** 2026-10-22

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

- **41 tests passed** on Python 3.12 and Python 3.13 in [GitHub Actions run 39746559724](https://github.com/sinanaghdi/retailsignal/actions/runs/39746559724).
- The new regression test confirms that missing product descriptions are quality defects but do not silently remove otherwise computable financial lines.
- An additional SQL contract test checks product-description lookup through dim_product rather than the fact table.

## PostgreSQL end-to-end status

The first real-data PostgreSQL execution successfully loaded all source rows to staging and ran transformation/analysis SQL files 02–05. Execution of SQL file 06 then exposed an actual schema bug: it attempted to read description from fact_sales_line, where that column does not exist. The query has been fixed to join retailsignal.dim_product for descriptions and now has a regression contract test.

The end-to-end workflow is being rerun after the fix at [RetailSignal real-data validation](https://github.com/sinanaghdi/retailsignal/actions/runs/39746779309). Until the final run passes, do **not** claim the PostgreSQL analytical SQL and final Python/PostgreSQL aggregate reconciliation are fully accepted. The rerun workflow was also simplified to avoid invoking the same million-row ingestion/clean/statistics pipeline twice.

## Not executed / not claimed

- Latest end-to-end PostgreSQL SQL execution and final reconciliation have not yet been verified as successful.
- No real-data Power BI PBIX was built or verified.
- No business-impact or causal claim is established by these descriptive analyses.
- The UCI dataset is historical UK retail data; it is not evidence of current Iranian market demand.
- Raw workbook and customer-level files are excluded from public Git. CI artifacts are limited to aggregate metrics, quality summaries, and manifest details.

## Data interpretation caveats

Recorded transaction line amounts are not verified collected cash, recognized accounting revenue, gross margin, or profit. Cancellation prefixes, negative quantity, negative line value and exact-duplicate candidates can overlap and must not be summed as if they were disjoint categories. Repeated-purchase status and cohorts are subject to missing customer identifiers and unequal follow-up, especially around the final December 2011 coverage. Statistical comparisons are observational and do not establish causality.
