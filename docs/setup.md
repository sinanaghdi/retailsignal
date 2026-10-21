# Setup and Reproduction Guide

## 1. Prerequisites

- Windows 10/11 with PowerShell.
- Python 3.12 recommended (Python 3.13 is acceptable if the selected wheels install successfully).
- Git.
- PostgreSQL 15+ for the SQL milestone; Power BI Desktop for the dashboard milestone.
- The official UCI workbook. Do not substitute a similarly named or pre-cleaned third-party copy.

## 2. Create the environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python --version
python -c "import pandas, numpy, sqlalchemy, pytest; print('pandas', pandas.__version__, '| numpy', numpy.__version__)"
```

If PowerShell blocks activation for the current process, use this session-only command, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Download the official data

Preferred: run the reproducible downloader. It downloads the official UCI ZIP to `data\raw\online_retail_ii.zip`, extracts only `online_retail_II.xlsx`, and calls the schema gate before accepting the workbook.

```powershell
python -m src.download_data
```

The downloader uses the official UCI endpoint configured in `src/config.py`, streams the archive to disk, retries transient failures, checks that the file is a valid ZIP with exactly one expected workbook, and verifies the worksheet headers. After a successful acquisition, it writes a local `source_manifest.json` with acquisition time, sheet/header metadata, byte sizes, and SHA-256 hashes. The manifest, raw archive, and workbook are kept locally and ignored by Git. If the workbook already exists, it does not overwrite it unless `--force` is supplied.

Manual alternative: open the [UCI Online Retail II page](https://archive.ics.uci.edu/dataset/502/online+retail+ii), select **Download**, and save/extract its ZIP. Copy the original `online_retail_II.xlsx` into `data\raw\online_retail_II.xlsx`. Do not substitute a pre-cleaned third-party dataset.

If the official endpoint is unavailable, use the manual download from UCI in a browser. The project does not ship or commit the workbook. The raw workbook and ZIP are ignored by Git.

## 4. Inspect before transforming

```powershell
python -m src.ingest --inspect-only
```

Expected result: each workbook sheet is listed with its source headers and an empty `Missing required` list. Known source aliases such as `Invoice`/`InvoiceNo`, `Price`/`UnitPrice`, and `Customer ID`/`CustomerID` are handled by the schema normalizer. If the script stops with missing or conflicting fields, inspect the actual workbook headers and update `src/config.py` only after verifying their meaning.

Then ingest all sheets:

```powershell
python -m src.ingest
```

Expected: `data\processed\01_ingested.csv`; the console reports row count, sheets, and canonical columns. The script adds trace identifiers but does not deduplicate.

## 5. Audit, clean, and test

Run each stage in order:

```powershell
python -m src.validate
python -m src.clean
python -m pytest -q
python -m src.statistics
```

Acceptance checks:

- Ingestion schema gate passes.
- `01_ingested.csv` row count equals the sum of rows read from all workbook sheets.
- `fact_sales_lines.csv` has the same number of rows as the ingested source; cleaning drops zero rows.
- `line_value` reconciles to `quantity * unit_price` for valid numeric pairs.
- `data_quality_audit.csv` records counts and percentages for missing values, duplicate candidates, negative quantities, cancellation-prefixed invoices, invalid timestamps/prices/quantities, and outlier flags.
- `python -m pytest -q` passes the isolated synthetic tests. These tests do not validate the official dataset itself.

## 6. PostgreSQL

Create a local database and login in your PostgreSQL installation (choose your own secure password). For example, from `psql` as an administrator:

```sql
CREATE DATABASE retailsignal;
CREATE USER retailsignal_user WITH PASSWORD 'replace_with_a_local_secret';
GRANT CONNECT ON DATABASE retailsignal TO retailsignal_user;
```

Then either copy `.env.example` to `.env` and edit the local connection string (the loader reads `.env` without overriding an already-set environment variable), or set the connection for the current PowerShell session:

```powershell
Copy-Item .env.example .env
# Edit .env locally with your own password; never commit .env.
# Alternative for the current PowerShell session:
$env:DATABASE_URL = "postgresql+psycopg://retailsignal_user:replace_with_a_local_secret@localhost:5432/retailsignal"
python -m src.load_postgres --init-schema
python -m src.run_sql --file sql/02_transformations.sql
python -m src.run_sql --file sql/07_data_quality_checks.sql
```

Run a query file the same way, for example:

```powershell
python -m src.run_sql --file sql/03_sales_analysis.sql
python -m src.run_sql --file sql/04_customer_analysis.sql
python -m src.run_sql --file sql/05_cohort_analysis.sql
python -m src.run_sql --file sql/06_product_and_country_analysis.sql
```

`src/run_sql.py` executes the SQL statements and prints up to 20 result rows per result set by default. Use `--preview-rows 50` to see a longer preview. For full result export, run the SQL in pgAdmin/psql or use PostgreSQL `\copy`/a client that can export results. Never put a real password in a committed file.

**Database acceptance criteria:** stage row count equals the cleaned CSV row count; transformed fact row count equals stage row count; signed sum of `quantity * unit_price` matches the fact `line_value` sum within database numeric precision; foreign-key creation succeeds; invoice metadata variations are reported, not silently hidden.

## 7. Notebooks

From the active virtual environment:

```powershell
jupyter notebook
```

Run in order: `01_data_quality_audit.ipynb`, `02_exploratory_analysis.ipynb`, `03_customer_analytics.ipynb`. Save notebook outputs only after they have been generated from the real workbook. Do not check raw source records or personal/customer-level exports into Git.

## 8. Power BI Desktop

Follow `powerbi/README.md`. Use CSV marts under `data\processed\` and `data\marts\`, or PostgreSQL tables if you prefer a direct database connection. Validate DAX totals against the Python/SQL output before sharing screenshots.

## Troubleshooting

- **Workbook not found:** the default exact path is `data\raw\online_retail_II.xlsx`; check `Get-ChildItem data\raw -Recurse`.
- **Schema gate failed:** list actual headers and sheet names; don't bypass the failure or guess field semantics.
- **Out of memory:** read each sheet separately, close other heavy applications, and preserve the one-time CSV checkpoint; don't sample rows for the final reported results.
- **Date parse failures:** review example source values from the audit; preserve those rows and keep them out of time-dependent analyses.
- **PostgreSQL connection failure:** verify service status, database, user, host, port, and current PowerShell `DATABASE_URL` value without posting the password.
- **Foreign-key insert failure:** confirm dimension inserts were run before line facts and inspect blank or inconsistent identifiers.
- **Power BI totals differ:** check filter context, relationships, duplicated many-to-many joins, currency, and whether negative lines are added twice.

## GitHub repository and future updates

The public repository is already available at [github.com/sinanaghdi/retailsignal](https://github.com/sinanaghdi/retailsignal). Clone it to get the canonical history:

```powershell
git clone https://github.com/sinanaghdi/retailsignal.git
Set-Location retailsignal
git status
```

For future work, edit files in that clone, run the relevant tests, check that the raw workbook, generated outputs, and `.env` are absent from the staged changes, and publish a normal commit:

```powershell
git status --short
git add src tests sql docs reports notebooks powerbi presentation README.md
git status --short
git commit -m "Describe the verified change"
git push
```

Do not initialize a separate repository and force-push it over the existing project history. The archive's `scripts/publish_to_github.ps1` helper now explicitly refuses to create a parallel history and points to this clone-first workflow.
