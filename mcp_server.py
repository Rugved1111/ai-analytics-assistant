"""Phase 7: an MCP server that exposes the analytics tools to any MCP client
(Claude Desktop, Claude Code, Cursor, the MCP Inspector, ...).

The client's own model does the reasoning; this server only provides the tools, so it uses
0 Gemini requests. The same guardrails apply: SELECT-only check, read-only database role,
5 second timeout and a row limit.

Run over stdio (what desktop clients use):   python mcp_server.py
Run over HTTP:                                 python mcp_server.py --http   (http://localhost:8001/mcp)
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)  # desktop clients may start the server from another folder
load_dotenv(ROOT / ".env")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from agent_tools import check_select  # noqa: E402
from db import run_sql as query_db  # noqa: E402
from rag_answer import SCHEMA  # noqa: E402
from search_docs import search_docs as find_chunks  # noqa: E402

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

server = MCPServer(
    name="sales-analytics",
    title="Sales analytics",
    version="1.0",
    instructions=(
        "Tools for a US office-supplies retailer's sales database (orders 2014-2017). "
        "If a question uses a company term (VIP, late order, AOV, active customer, heavy discount, margin), "
        "call search_docs first and follow the definition it returns. Get every number from run_sql "
        "(PostgreSQL, SELECT only). Read the schema resource before writing SQL.\n\n" + SCHEMA
    ),
)


def plain(value):
    """Database values (Decimal, date) to JSON-friendly values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


@server.tool(annotations=READ_ONLY)
def search_docs(question: str, k: int = 3) -> list[dict]:
    """Search the company's business notes for definitions and rules (VIP, late order,
    heavy discount, AOV, active customer, profit margin...). Call this before writing SQL
    for any question that uses a company term. Returns the closest sections first."""
    return find_chunks(question, k=max(1, min(k, 5)))


@server.tool(annotations=READ_ONLY)
def run_sql(sql: str, max_rows: int = 50) -> dict:
    """Run one read-only PostgreSQL SELECT on the sales database.
    Tables: customers, products, orders, order_lines (see the schema in the server instructions).
    Returns the column names, up to max_rows rows (100 at most), and whether rows were cut off."""
    problem = check_select(sql)
    if problem:
        return {"error": problem}
    try:
        result = query_db(sql, max_rows=max(1, min(max_rows, 100)))
    except Exception as e:
        return {"error": f"SQL error: {e}"}
    rows = [[plain(v) for v in row] for row in result["rows"]]
    return {"columns": result["columns"], "rows": rows, "truncated": result["truncated"]}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
def make_chart(sql: str, chart_type: str = "bar", title: str = "Chart") -> dict:
    """Draw a bar or line chart from a SELECT that returns exactly 2 columns
    (label, number). Saves an interactive HTML file under charts/ and returns its path and the data."""
    if chart_type not in ("bar", "line"):
        return {"error": "chart_type must be 'bar' or 'line'."}
    problem = check_select(sql)
    if problem:
        return {"error": problem}
    try:
        result = query_db(sql, max_rows=100)
    except Exception as e:
        return {"error": f"SQL error: {e}"}
    if len(result["columns"]) != 2:
        return {"error": f"The query must return 2 columns, it returned {len(result['columns'])}."}
    import plotly.graph_objects as go

    x = [str(r[0]) for r in result["rows"]]
    y = [float(r[1]) for r in result["rows"]]
    trace = go.Bar(x=x, y=y) if chart_type == "bar" else go.Scatter(x=x, y=y, mode="lines+markers")
    fig = go.Figure(trace)
    fig.update_layout(title=title, xaxis_title=result["columns"][0], yaxis_title=result["columns"][1])
    os.makedirs("charts", exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "chart"
    path = ROOT / "charts" / f"{slug}.html"
    fig.write_html(path, include_plotlyjs="cdn")
    return {"path": str(path), "x": x, "y": y, "x_label": result["columns"][0], "y_label": result["columns"][1]}


@server.resource("analytics://schema", name="schema", description="Database schema", mime_type="text/plain")
def schema() -> str:
    return SCHEMA


@server.resource("analytics://business-notes", name="business-notes",
                 description="The company's business definitions and rules", mime_type="text/markdown")
def business_notes() -> str:
    return (ROOT / "docs" / "business_notes.md").read_text()


@server.prompt(name="analyst", description="Answer a business question with the sales tools")
def analyst(question: str) -> str:
    return (f"Answer this business question with the sales-analytics tools: {question}\n"
            "Look up company terms with search_docs first, get every number from run_sql, "
            "then answer in 1-4 sentences and show the SQL you ran.")


if __name__ == "__main__":
    if "--http" in sys.argv:
        server.run(transport="streamable-http", port=8001)
    else:
        server.run()
