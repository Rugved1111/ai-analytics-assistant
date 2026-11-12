"""The MCP server, connected in-process (no subprocess, no Gemini)."""
import asyncio
import json

from mcp import Client

from mcp_server import server


def call(name, args):
    async def go():
        async with Client(server) as client:
            result = await client.call_tool(name, args)
            if result.structured_content is not None:
                return result.structured_content
            return json.loads(result.content[0].text)
    return asyncio.run(go())


def test_lists_three_tools():
    async def go():
        async with Client(server) as client:
            return sorted(t.name for t in (await client.list_tools()).tools)
    assert asyncio.run(go()) == ["make_chart", "run_sql", "search_docs"]


def test_run_sql_vip_count():
    out = call("run_sql", {"sql": "SELECT COUNT(*) FROM (SELECT o.customer_id FROM orders o "
                                  "JOIN order_lines l USING (order_id) GROUP BY 1 HAVING SUM(l.sales) >= 10000) v"})
    assert out["rows"] == [[20]]


def test_run_sql_guardrail():
    assert "Guardrail" in call("run_sql", {"sql": "DELETE FROM orders"})["error"]


def test_search_docs_finds_vip_rule():
    out = call("search_docs", {"question": "Who is a VIP customer?", "k": 1})
    chunks = out["result"] if isinstance(out, dict) else out
    assert "VIP" in chunks[0]["content"]
