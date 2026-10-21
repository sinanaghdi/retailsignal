# Implementation Status and Validation Evidence

**Last local validation:** 2026-10-21

## Implemented

- Project charter, architecture, source attribution, metric dictionary, limitations, setup guide, README, MIT code license, `.env.example`, and `.gitignore`.
- Official UCI workbook downloader: streamed download, bounded retries, ZIP validation, extraction of only `online_retail_II.xlsx`, fail-fast schema inspection, SHA-256 manifest, and no-overwrite default.
- Canonical column normalization and multi-sheet ingestion with source-row IDs and no intentional row deletion.
- Data-quality audit with counts/percentages and rationale for missing/blank values, exact duplicate candidates, invoice attribute variations, cancellation prefixes, negative quantities/values, invalid fields, line-value outliers, nonstandard stock codes, and customer-ID shape anomalies.
- Row-preserving transaction cleaning, signed line values, defined positive-sale eligibility, customer-attribution ambiguity flags, and 15 generated analytical marts.
- Python metrics for monthly sales, product/country performance, cancellation/negative-record diagnostics, repeat purchases, cohorts, RFM, customer concentration, duplicate sensitivity, and alternative RFM monetary definitions.
- PostgreSQL staging schema, fact/dimension model, transformations, analytical queries, reconciliation checks, and Python SQL execution/loading utilities.
- Three notebooks, five-page Power BI specification, DAX dictionary, interview walkthrough, LinkedIn drafts, case-study outline, and honest resume bullet templates.
- GitHub Actions workflow configured for Python 3.12 and 3.13.

## Executed local checks

| Check | Result | Scope |
|---|---|---|
| `python -m pytest -q` | **36 passed** | Unit tests, isolated synthetic fixtures, SQL/source contracts, downloader behavior, and notebook regression cell |
| `python -m compileall -q src tests` | Passed | Python syntax compilation |
| Notebook format validation | Passed | All 3 notebooks validated with `nbformat` |
| Notebook execution | Passed | All 3 notebooks executed with no cell errors against local synthetic-only fixture outputs; results saved outside the project bundle |
| Synthetic CLI pipeline | Passed | Ingest → audit → clean → statistics executed from command line using a 15-row synthetic workbook |
| Synthetic row reconciliation | 15 input rows = 15 cleaned rows | No rows dropped in the test fixture |
| Synthetic mart generation | 15 CSV marts | Output coverage check only |
| Synthetic audit output | 28 metrics | Output coverage check only |
| SQL statement splitting | 40 statements across 7 SQL files | Parser utility check only; not PostgreSQL execution |
| Downloader success path | Passed using an in-memory test ZIP | Mocked network response; does not establish source availability |

The synthetic CLI fixture's signed line value was GBP 146.50. This is **only a software reconciliation value from synthetic rows**, not a business finding and not a result from Online Retail II. The customer-group statistical comparison was correctly marked `not_tested` on the undersized fixture.

## Fixes discovered during validation

1. Corrected the configured UCI archive endpoint to match the plus-separated filename on the official download link.
2. Added `src.download_data` and tests for extraction, manifest hashing, invalid archives, existing-file handling, and transient retry behavior.
3. Added `--input` and `--output-dir` CLI arguments to `src.statistics`; previously the module ignored supplied paths, causing a custom-path smoke run to fail.
4. Fixed a notebook summary cell that mixed a Series and one-item list in a DataFrame constructor; added a focused regression test and re-executed all 3 notebooks.

## Not executed / blocked

- The official workbook has **not** been downloaded into this execution environment. Direct container access failed at DNS resolution, and the official download click request timed out. No real-data schema or transaction row has therefore been inspected here.
- No actual Online Retail II totals, data-quality counts, cohorts, RFM summaries, statistical results, or evidence-backed recommendations have been generated.
- PostgreSQL execution is pending. `psql` and `pg_isready` are not installed in this environment, and no live server is configured. SQL contract tests and statement splitting are not substitutes for a live database run.
- Power BI Desktop is unavailable; no `.pbix` file or real-data screenshot is included.
- GitHub returned 404 for `sinanaghdi/retailsignal`; available connected GitHub actions do not include repository creation. No remote push has occurred.
- The GitHub Actions workflow is committed to the local source bundle but has not run on GitHub because the repository has not been created/published.

## Exact acceptance path from here

1. On Windows, run `python -m src.download_data`. If the official endpoint remains unavailable, manually download the ZIP from the official UCI dataset page and place the original workbook at `data/raw/online_retail_II.xlsx`.
2. Run `python -m src.ingest --inspect-only`, then `python -m src.ingest`, `python -m src.validate`, `python -m src.clean`, and `python -m src.statistics`.
3. Inspect the generated audit before interpreting any business metric; retain the raw workbook and generated local source manifest outside Git.
4. Run `python -m pytest -q`, then initialize PostgreSQL and execute the schema, transformations, and all analytical SQL scripts.
5. Reconcile Python and PostgreSQL totals under identical eligibility definitions, then create and validate the Power BI report against those outputs.
6. Replace pending findings and recommendation hypotheses only after their values, denominators, time periods, sensitivities, and limitations are reviewed.
7. Create the public GitHub repository and push the source bundle. Confirm raw/processed data and `.env` are not staged; then verify CI and README links on GitHub.
