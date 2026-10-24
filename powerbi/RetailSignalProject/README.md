# RetailSignal Power BI project (PBIP source)

This folder contains an **editable Power BI Project** source scaffold, not a binary `.pbix`. It includes a TMDL semantic model and a PBIR report with five pages: Executive Overview, Sales Trends, Customer Retention, Product & Country Performance, and Returns & Data Quality.

## Before opening

1. From the repository root, activate the project environment and run the documented dataset pipeline, including `python powerbi/prepare_data_model.py`. This creates the local CSV marts and `data/marts/powerbi_date.csv`.
2. In Power BI Desktop, open `RetailSignal.pbip` from this folder.
3. In the Power Query/parameter prompt or semantic model parameters, set `ProjectRoot` to the absolute path of the cloned repository root, for example `C:/Users/your-user/source/retailsignal`. Replace the placeholder in `RetailSignal.SemanticModel/definition/expressions.tmdl` if Desktop does not expose the parameter prompt on first open.
4. Refresh the model and address any local path or data-type prompt.

## Important validation boundary

The PBIP files are hand-authored source and passed repository-level structural checks (JSON parsing, page/visual references, and model table names). They **have not been opened in Power BI Desktop**, so the DAX, TMDL import behavior, visual rendering, filters, and model relationships still require Desktop validation. Save as `.pbix` only after all five pages render and the no-filter KPIs reconcile to `data/processed/powerbi_model_validation.json` and the Python/PostgreSQL results.

The cohort and RFM segment visuals use precomputed full-window marts; do not imply that the fact-table date slicer dynamically recalculates those mart tables.
