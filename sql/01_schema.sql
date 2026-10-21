-- RetailSignal PostgreSQL schema. Run from psql or `python -m src.run_sql --file sql/01_schema.sql`.
CREATE SCHEMA IF NOT EXISTS retailsignal;

CREATE TABLE IF NOT EXISTS retailsignal.stg_online_retail (
    source_row_id BIGINT PRIMARY KEY,
    invoice_no TEXT,
    stock_code TEXT,
    description TEXT,
    quantity NUMERIC(14, 4),
    invoice_date TIMESTAMP NULL,
    unit_price NUMERIC(14, 4),
    customer_id TEXT,
    country TEXT,
    source_sheet TEXT,
    is_exact_duplicate_extra_row BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS retailsignal.dim_customer (
    customer_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS retailsignal.dim_product (
    stock_code TEXT PRIMARY KEY,
    description TEXT,
    source_line_count BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS retailsignal.dim_country (
    country TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS retailsignal.dim_invoice (
    invoice_no TEXT PRIMARY KEY,
    invoice_date TIMESTAMP NULL,
    customer_id TEXT NULL REFERENCES retailsignal.dim_customer(customer_id),
    country TEXT NULL REFERENCES retailsignal.dim_country(country),
    is_cancellation_invoice BOOLEAN NOT NULL,
    source_line_count BIGINT NOT NULL,
    date_variants BIGINT NOT NULL,
    customer_variants BIGINT NOT NULL,
    country_variants BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS retailsignal.fact_sales_line (
    source_row_id BIGINT PRIMARY KEY,
    invoice_no TEXT NULL REFERENCES retailsignal.dim_invoice(invoice_no),
    stock_code TEXT NULL REFERENCES retailsignal.dim_product(stock_code),
    customer_id TEXT NULL REFERENCES retailsignal.dim_customer(customer_id),
    country TEXT NULL REFERENCES retailsignal.dim_country(country),
    invoice_date TIMESTAMP NULL,
    quantity NUMERIC(14, 4),
    unit_price NUMERIC(14, 4),
    line_value NUMERIC(20, 4),
    is_cancellation_invoice BOOLEAN NOT NULL,
    is_negative_quantity BOOLEAN NOT NULL,
    is_negative_line_value BOOLEAN NOT NULL,
    is_positive_sales_line BOOLEAN NOT NULL,
    is_customer_analytics_eligible BOOLEAN NOT NULL,
    is_exact_duplicate_extra_row BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_stg_invoice_date ON retailsignal.stg_online_retail(invoice_date);
CREATE INDEX IF NOT EXISTS ix_fact_invoice_date ON retailsignal.fact_sales_line(invoice_date);
CREATE INDEX IF NOT EXISTS ix_fact_customer ON retailsignal.fact_sales_line(customer_id);
CREATE INDEX IF NOT EXISTS ix_fact_product ON retailsignal.fact_sales_line(stock_code);
CREATE INDEX IF NOT EXISTS ix_fact_country ON retailsignal.fact_sales_line(country);
