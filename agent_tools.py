"""Phase 4: the three tools the agent can choose from.

The tool decorator turns a normal Python function into something an LLM can call.
The function name becomes the tool name, the docstring becomes the
description Gemini reads, and the type hints become the argument schema.
"""

import os
import re
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

import plotly.graph_objects as go
from langchain_core.tools import tool

from rag_answer import run_sql as query_db
from search_docs import search_docs as find_chunks

CHART_DIR = "charts"


# Words that change data or the server. The database role is read-only anyway;
# this check refuses them before the query ever reaches Postgres.
BLOCKED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|vacuum|pg_sleep|pg_terminate_backend)\b",
    re.IGNORECASE,
)


def check_select(sql):
    """Return an error message if the SQL is not one plain SELECT, else None."""
    # Ignore text inside quotes, so a filter like name = 'Update Desk' is fine.
    body = re.sub(r"'(?:[^']|'')*'", "''", sql).strip().rstrip(";").strip()
    if ";" in body:
        return "Guardrail: only one statement is allowed."
    if not re.match(r"(?is)^(select|with)\b", body):
        return "Guardrail: only SELECT queries are allowed."
    found = BLOCKED.search(body)
    if found:
        return f"Guardrail: the keyword '{found.group(1)}' is not allowed."
    return None


def format_rows(columns, rows):
    lines = [" | ".join(columns)]
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    return "\n".join(lines)


@tool
def search_docs(question: str) -> str:
    """Search the company's business notes for definitions and rules.
    Use this FIRST whenever a question uses a company term such as VIP,
    late order, heavy discount or AOV, before writing any SQL."""
    chunks = find_chunks(question, k=3)
    parts = []
    for c in chunks:
        parts.append(f"## {c['heading']} (distance {c['distance']:.2f})\n{c['content']}")
    return "\n\n".join(parts)


@tool
def run_sql(sql: str) -> str:
    """Run one read-only PostgreSQL SELECT query on the sales database
    and return the result as text (at most 20 rows).
    Tables: customers, products, orders, order_lines."""
    problem = check_select(sql)
    if problem:
        return problem
    try:
        columns, rows = query_db(sql)
    except Exception as e:
        return f"SQL error: {e}"
    return format_rows(columns, rows)


@tool
def make_chart(sql: str, chart_type: Literal["bar", "line"], title: str) -> str:
    """Draw a chart from a SELECT query that returns exactly 2 columns:
    the first column is the label (x axis), the second is the number (y axis).
    Saves an HTML file and returns its path."""
    problem = check_select(sql)
    if problem:
        return problem
    try:
        columns, rows = query_db(sql, max_rows=100)
    except Exception as e:
        return f"SQL error: {e}"
    if len(columns) != 2:
        return f"Chart error: the query must return 2 columns, it returned {len(columns)}."
    x = [str(r[0]) for r in rows]
    y = [float(r[1]) for r in rows]
    if chart_type == "bar":
        trace = go.Bar(x=x, y=y)
    else:
        trace = go.Scatter(x=x, y=y, mode="lines+markers")
    fig = go.Figure(trace)
    fig.update_layout(title=title, xaxis_title=columns[0], yaxis_title=columns[1])
    os.makedirs(CHART_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "chart"
    path = os.path.join(CHART_DIR, f"{slug}.html")
    fig.write_html(path, include_plotlyjs="cdn")
    return f"Chart saved to {path} ({len(rows)} points)."


TOOLS = [search_docs, run_sql, make_chart]


if __name__ == "__main__":
    # Test every tool by hand. No Gemini calls, so this costs 0 requests.
    for t in TOOLS:
        print(f"--- {t.name}: what Gemini will see ---")
        print(t.description)
        print(t.args)
        print()

    print("=== 1. search_docs ===")
    print(search_docs.invoke({"question": "Who counts as a VIP customer?"}))

    print("\n=== 2. run_sql (VIP count, expect 20) ===")
    print(run_sql.invoke({"sql": """
        SELECT COUNT(*) AS vip_customers FROM (
            SELECT o.customer_id
            FROM orders o JOIN order_lines ol USING (order_id)
            GROUP BY o.customer_id
            HAVING SUM(ol.sales) >= 10000
        ) v
    """}))

    print("\n=== 3. run_sql with a broken query (expect 'SQL error', not a crash) ===")
    print(run_sql.invoke({"sql": "SELECT nope FROM orders"}))

    print("\n=== 4. make_chart (expect 4 points) ===")
    print(make_chart.invoke({
        "sql": """
            SELECT o.region, ROUND(SUM(ol.sales), 2) AS sales
            FROM orders o JOIN order_lines ol USING (order_id)
            GROUP BY o.region ORDER BY sales DESC
        """,
        "chart_type": "bar",
        "title": "Sales by region",
    }))