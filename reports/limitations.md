# Limitations and Release Gates

## Current implementation and validation status

- The official UCI Online Retail II workbook has been executed in GitHub Actions. The successful recorded run retained all 1,067,371 rows, generated 15 analytical marts, executed SQL files 02–07 against PostgreSQL 16, and reconciled Python/PostgreSQL totals. See [the real-data benchmark](real_dataset_benchmark.md).
- The recorded Python CI matrix passed 41 tests on each of Python 3.12 and 3.13. The recorded real-data run passed 7 PostgreSQL reconciliation checks and 10 source acceptance checks; its additional product comparison covered the top 10 products across 7 fields each.
- The Power BI .pbix file has **not** been built or validated in Power BI Desktop. The repository contains a specification and DAX definitions, not a verified finished dashboard.
- The branch fix/docs-product-parity-atomic-staging adds full product-catalog parity validation, an explicit product-description tie-break rule, an atomic staging refresh, and related tests. These changes must not be described as passed until the branch CI has completed successfully.

## Analytical limitations inherent to the source

- The observation period is finite and ends during December 2011; later customer cohorts are right-censored.
- 243,007 source rows have missing customer identifiers in the recorded audit. Customer-level measures therefore do not cover all source rows.
- Invoice prefixes, negative quantities, and negative line values are transaction-record signals; they do not prove physical returns, refund completion, or inventory disposition.
- The dataset lacks unit cost, shipping/fulfillment expenses, payment settlement, acquisition spending, campaign exposures, channel attribution, and reliable customer acquisition dates. Profit, margin, CAC, and marketing ROI are out of scope.
- Exact duplicate candidates may be data issues or legitimate repeated source lines; they are flagged rather than deleted. The impact of excluding them should be reported as a sensitivity analysis.
- Invoice IDs with conflicting dates, customer IDs, or countries require review before invoice-level aggregations are trusted.
- This historical UK retailer dataset does not represent all e-commerce businesses, current periods, or every country's market behavior.
- The analysis is observational and cannot establish causal effects of actions or customer segments.

## Release gates

1. Preserve the source manifest, workbook hash, and schema-inspection evidence for every new data run.
2. Run the synthetic Python tests and record the exact CI run/commit.
3. Verify that Python and SQL choose the same nonblank product description: highest frequency first, then ascending deterministic string order for ties.
4. Compare **every product row**, not only the top 10, across Python and PostgreSQL for label, positive sales amount, units, invoice count, contribution, and cumulative contribution.
5. Verify that PostgreSQL staging refresh is transactional: if insertion or row-count reconciliation fails, the previous staging data must remain intact.
6. Inspect invoice-level conflicting metadata and duplicate sensitivity before writing numerical findings.
7. Build the five Power BI pages and validate DAX against independently computed metrics; do not claim the .pbix is finished until it is opened and checked in Power BI Desktop.
8. Keep executive claims tied to traceable calculations, definitions, denominators, observed periods, and uncertainty.
9. Do not commit the raw workbook or customer-level generated records to the public repository.
