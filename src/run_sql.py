"""Execute a project SQL script against PostgreSQL and print compact result previews."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from src.config import PROJECT_ROOT
from dotenv import load_dotenv


def database_dsn() -> str:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is not set. See docs/setup.md and .env.example.")
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def split_sql_statements(sql_text: str) -> list[str]:
    """Split this project's SQL files on statement semicolons outside quotes/comments."""
    statements: list[str] = []
    buffer: list[str] = []
    i, state = 0, "normal"
    while i < len(sql_text):
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < len(sql_text) else ""
        if state == "single":
            buffer.append(ch)
            if ch == "'":
                if nxt == "'":
                    buffer.append(nxt)
                    i += 1
                else:
                    state = "normal"
        elif state == "double":
            buffer.append(ch)
            if ch == '"':
                if nxt == '"':
                    buffer.append(nxt)
                    i += 1
                else:
                    state = "normal"
        elif state == "line_comment":
            buffer.append(ch)
            if ch == "\n":
                state = "normal"
        elif state == "block_comment":
            buffer.append(ch)
            if ch == "*" and nxt == "/":
                buffer.append(nxt)
                i += 1
                state = "normal"
        else:
            if ch == "'":
                buffer.append(ch)
                state = "single"
            elif ch == '"':
                buffer.append(ch)
                state = "double"
            elif ch == "-" and nxt == "-":
                buffer.extend([ch, nxt])
                i += 1
                state = "line_comment"
            elif ch == "/" and nxt == "*":
                buffer.extend([ch, nxt])
                i += 1
                state = "block_comment"
            elif ch == ";":
                statement = "".join(buffer).strip()
                if statement and statement not in {"--", "/* */"}:
                    statements.append(statement)
                buffer = []
            else:
                buffer.append(ch)
        i += 1
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return [s for s in statements if s and not all(line.strip().startswith("--") or not line.strip() for line in s.splitlines())]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--preview-rows", type=int, default=20, help="Maximum result rows printed for each SELECT")
    args = parser.parse_args()
    sql_path = args.file if args.file.is_absolute() else PROJECT_ROOT / args.file
    if not sql_path.exists():
        raise FileNotFoundError(sql_path)
    statements = split_sql_statements(sql_path.read_text(encoding="utf-8"))
    if not statements:
        raise ValueError(f"No SQL statements found in {sql_path}")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("PostgreSQL execution requires psycopg. Install dependencies with: python -m pip install -r requirements.txt") from exc
    with psycopg.connect(database_dsn(), autocommit=True) as conn:
        for number, statement in enumerate(statements, start=1):
            cursor = conn.execute(statement, prepare=False)
            if cursor.description:
                columns = [column.name for column in cursor.description]
                rows = cursor.fetchmany(max(1, args.preview_rows) + 1)
                has_more = len(rows) > args.preview_rows
                shown = rows[:args.preview_rows]
                print(f"\nStatement {number}/{len(statements)} — {len(columns)} column(s){' (preview)' if has_more else ''}")
                print(" | ".join(columns))
                for row in shown:
                    print(" | ".join("NULL" if value is None else str(value) for value in row))
                if has_more:
                    print(f"... additional rows omitted (showing {args.preview_rows})")
            else:
                print(f"Statement {number}/{len(statements)} executed; rowcount={cursor.rowcount}.")
    print(f"\nExecuted {len(statements)} statement(s) from {sql_path}")

if __name__ == "__main__":
    main()
