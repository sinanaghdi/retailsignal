"""Load the cleaned line-level file into PostgreSQL staging, then run SQL transformations."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from src.config import DEFAULT_CLEANED, PROJECT_ROOT
from src.run_sql import split_sql_statements

BASE_FIELDS = ["source_row_id", "invoice_no", "stock_code", "description", "quantity", "invoice_date", "unit_price", "customer_id", "country", "source_sheet", "is_exact_duplicate_extra_row"]


def sqlalchemy_url() -> str:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is missing. Copy .env.example to .env and set local PostgreSQL credentials, then set the variable in PowerShell.")
    return value


def load_to_staging(input_path: str | Path = DEFAULT_CLEANED, init_schema: bool = False, chunk_size: int = 5_000) -> None:
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Cleaned file not found: {input_path}. Run python -m src.clean first.")
    engine = create_engine(sqlalchemy_url(), pool_pre_ping=True)
    try:
        if chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer.")
        with engine.begin() as conn:
            if init_schema:
                schema_sql = (PROJECT_ROOT / "sql" / "01_schema.sql").read_text(encoding="utf-8")
                for statement in split_sql_statements(schema_sql):
                    conn.exec_driver_sql(statement)
        frame = pd.read_csv(input_path, usecols=lambda c: c in BASE_FIELDS, low_memory=False,
                            dtype={"invoice_no": "string", "stock_code": "string", "customer_id": "string", "country": "string", "source_sheet": "string"})
        required = set(BASE_FIELDS) - set(frame.columns)
        if required:
            raise ValueError(f"Cleaned CSV lacks required staging columns: {sorted(required)}")
        frame = frame[BASE_FIELDS]
        frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="coerce", format="mixed")
        frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
        frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce")
        if frame["is_exact_duplicate_extra_row"].dtype == object:
            frame["is_exact_duplicate_extra_row"] = frame["is_exact_duplicate_extra_row"].astype(str).str.lower().map({"true": True, "false": False}).fillna(False)
        # Keep TRUNCATE, bulk insert, and reconciliation in one transaction. If insertion
        # or the row-count check fails, PostgreSQL rolls back and retains the previous staging data.
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE retailsignal.stg_online_retail"))
            frame.to_sql("stg_online_retail", conn, schema="retailsignal", if_exists="append", index=False, chunksize=chunk_size)
            result = conn.execute(text("SELECT COUNT(*) FROM retailsignal.stg_online_retail")).scalar_one()
            if result != len(frame):
                raise AssertionError(f"PostgreSQL staging count mismatch: CSV={len(frame):,}, DB={result:,}")
        print(f"Loaded and verified {len(frame):,} rows in retailsignal.stg_online_retail.")
        print("Next: python -m src.run_sql --file sql/02_transformations.sql")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_CLEANED)
    parser.add_argument("--init-schema", action="store_true", help="Create schema/table definitions before loading")
    parser.add_argument("--chunk-size", type=int, default=5_000)
    args = parser.parse_args()
    load_to_staging(args.input, args.init_schema, args.chunk_size)

if __name__ == "__main__":
    main()
