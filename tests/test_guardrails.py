"""The SQL guardrail and the read-only database role. No Gemini requests."""
import psycopg
import pytest

from agent_tools import check_select, run_sql as run_sql_tool
from db import run_sql


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select count(*) from orders;",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
    "SELECT * FROM products WHERE product_name ILIKE '%update set%'",
    "SELECT SUM(sales) FROM order_lines OFFSET 0",
])
def test_allows_plain_selects(sql):
    assert check_select(sql) is None


@pytest.mark.parametrize("sql", [
    "DROP TABLE orders",
    "DELETE FROM orders",
    "UPDATE order_lines SET sales = 0",
    "INSERT INTO customers VALUES ('x', 'y', 'z')",
    "SELECT 1; DELETE FROM orders",
    "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d",
    "SELECT pg_sleep(30)",
    "TRUNCATE orders",
    "GRANT ALL ON orders TO public",
])
def test_blocks_everything_else(sql):
    assert check_select(sql) is not None


def test_tool_returns_guardrail_message_not_exception():
    assert run_sql_tool.invoke({"sql": "DROP TABLE orders"}).startswith("Guardrail")


def test_tool_returns_sql_error_as_text():
    assert run_sql_tool.invoke({"sql": "SELECT nope FROM orders"}).startswith("SQL error")


def test_database_role_is_read_only():
    # Even if the guardrail were bypassed, ai_reader cannot write.
    with pytest.raises(psycopg.Error):
        run_sql("DELETE FROM orders WHERE false RETURNING 1")


def test_database_role_has_statement_timeout():
    with pytest.raises(psycopg.Error):
        run_sql("SELECT pg_sleep(6)")


def test_row_limit():
    result = run_sql("SELECT row_id FROM order_lines", max_rows=10)
    assert len(result["rows"]) == 10 and result["truncated"]
