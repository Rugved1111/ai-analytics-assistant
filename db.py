"""Run SQL on Postgres as the read-only ai_reader user, with a row limit."""
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

MAX_ROWS = 100


def run_sql(sql: str, max_rows: int = MAX_ROWS) -> dict:
    """Run one query; return its columns, rows, and whether rows were cut off."""
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["AI_DB_USER"],
        password=os.environ["AI_DB_PASSWORD"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [col.name for col in cur.description]
            rows = cur.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    return {"columns": columns, "rows": rows[:max_rows], "truncated": truncated}


if __name__ == "__main__":
    result = run_sql("SELECT customer_name, segment FROM customers ORDER BY customer_name", max_rows=5)
    print(result["columns"])
    for row in result["rows"]:
        print(row)
    print("truncated:", result["truncated"])