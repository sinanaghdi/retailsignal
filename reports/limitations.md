# Limitations and Release Gates

## Environment/data limitations at initial build

- The official 43.5 MB workbook could not be downloaded from this execution environment. Its public schema was checked on the UCI page, but the workbook itself has not been inspected or run here.
- The real-data audit, analytical metrics, significance tests, findings, recommendations, and dashboard screenshots remain pending.
- PostgreSQL server-side scripts have been authored but not executed against a live PostgreSQL instance.
- A Power BI `.pbix` binary has not been created or validated in Power BI Desktop.
- GitHub repository `sinanaghdi/retailsignal` did not exist at the time of the initial check, and the available GitHub connector tools do not expose a repository-creation action. The local project bundle is provided instead; a real push requires creating the repository or using `git push` from a configured local clone.

## Analytical limitations inherent to source

- The observation period is finite and ends during December 2011; later customer cohorts are right-censored.
- The exact share of rows with missing `CustomerID` is unknown until the audit runs; those rows cannot be confidently attributed to customers. Do not claim universal retention coverage.
- Invoice prefix and negative quantities are transaction-record signals and do not prove physical returns, refund completion, or inventory disposition.
- The dataset lacks unit cost, shipping/fulfillment expenses, payment settlement, acquisition spending, campaign exposures, channel attribution, and reliable customer acquisition dates. Profit, margin, CAC, and marketing ROI are out of scope.
- Exact duplicates may be data issues or legitimate same-value repeated lines; primary pipeline flags instead of deleting them. A sensitivity run is required for final conclusions.
- Same invoice IDs with conflicting dates, customer IDs, or countries require review before invoice-level aggregations are trusted.
- A UK-based retailer's dataset does not represent all e-commerce businesses, modern periods, or every country's market behavior.
- The analysis is observational and cannot establish causal effects of actions or customer segments.

## Release gates

1. Place official workbook in `data/raw/` and save the SHA-256 and file size in a local, non-sensitive run log.
2. Run `python -m src.ingest --inspect-only`; resolve schema issues before full ingestion.
3. Run audit, cleaning, synthetic tests, and export real results. Record exact command outputs and versions.
4. Review invoice-level conflicting metadata and duplicate sensitivity before writing any numerical finding.
5. Load PostgreSQL and verify row-count, amount, and foreign-key reconciliation.
6. Run all SQL analyses and compare totals with Python.
7. Build the five Power BI pages and validate DAX against independently computed metrics.
8. Replace pending sections in the executive summary/recommendations only with supported, traceable calculations. Cite query/notebook/metric in each finding.
9. Save clean screenshots from the actual Power BI report and add them after verifying they contain no sensitive identifiers.
10. Update README status from pending to verified only for steps actually executed.
