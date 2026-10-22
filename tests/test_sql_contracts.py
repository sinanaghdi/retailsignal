from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_postgres_schema_has_expected_grains_and_constraints():
    sql = (ROOT / "sql" / "01_schema.sql").read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS retailsignal" in sql
    assert "stg_online_retail" in sql and "fact_sales_line" in sql
    assert "source_row_id BIGINT PRIMARY KEY" in sql
    assert "REFERENCES retailsignal.dim_invoice(invoice_no)" in sql
    assert "is_customer_analytics_eligible BOOLEAN NOT NULL" in sql


def test_transformations_preserve_staging_and_reconcile_values():
    sql = (ROOT / "sql" / "02_transformations.sql").read_text(encoding="utf-8")
    assert "TRUNCATE TABLE retailsignal.fact_sales_line" in sql
    assert "retailsignal.stg_online_retail s" in sql
    assert "s.quantity * s.unit_price" in sql
    assert "staging_signed_value_gbp" in sql and "fact_signed_value_gbp" in sql
    assert "s.duplicate_sequence > 1" in sql


def test_customer_sql_excludes_ambiguous_invoice_attribution():
    for name in ("04_customer_analysis.sql", "05_cohort_analysis.sql"):
        sql = (ROOT / "sql" / name).read_text(encoding="utf-8")
        assert "is_customer_analytics_eligible" in sql


def test_all_required_analytical_sql_files_exist():
    expected = [
        "01_schema.sql", "02_transformations.sql", "03_sales_analysis.sql",
        "04_customer_analysis.sql", "05_cohort_analysis.sql",
        "06_product_and_country_analysis.sql", "07_data_quality_checks.sql",
    ]
    for name in expected:
        path = ROOT / "sql" / name
        assert path.exists() and path.stat().st_size > 100


def test_sql_statement_splitter_respects_quotes_and_comments():
    from src.run_sql import split_sql_statements
    script = "-- semicolon ; in a comment\nSELECT 'a;b' AS label; /* comment ; */ SELECT 2;"
    statements = split_sql_statements(script)
    assert len(statements) == 2
    assert "'a;b'" in statements[0]
    assert "SELECT 2" in statements[1]


def test_product_sql_gets_description_from_dimension_not_fact():
    sql = (ROOT / "sql" / "06_product_and_country_analysis.sql").read_text(encoding="utf-8")
    product_cte = sql.split("), ranked AS", 1)[0]
    assert "retailsignal.fact_sales_line AS f" in product_cte
    assert "retailsignal.dim_product AS p" in product_cte
    assert "MAX(p.description)" in product_cte
    assert "f.description" not in product_cte
