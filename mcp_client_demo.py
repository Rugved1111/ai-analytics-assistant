"""Phase 7: talk to mcp_server.py the way Claude Desktop would (over stdio). 0 Gemini requests.

Usage: python mcp_client_demo.py
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parent


def show(result):
    data = result.structured_content if result.structured_content is not None else \
        [c.text for c in result.content if hasattr(c, "text")]
    text = json.dumps(data, default=str)
    print(text[:400] + (" ..." if len(text) > 400 else ""))


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], cwd=str(ROOT))
    async with Client(params) as client:
        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools.tools])
        resources = await client.list_resources()
        print("Resources:", [str(r.uri) for r in resources.resources])

        print("\n1. search_docs('Who counts as a VIP customer?')")
        show(await client.call_tool("search_docs", {"question": "Who counts as a VIP customer?", "k": 1}))

        print("\n2. run_sql: VIP count (expect 20)")
        show(await client.call_tool("run_sql", {"sql": """
            SELECT COUNT(*) AS vip_customers FROM (
                SELECT o.customer_id FROM orders o JOIN order_lines l USING (order_id)
                GROUP BY 1 HAVING SUM(l.sales) >= 10000) v"""}))

        print("\n3. run_sql: DROP TABLE (expect the guardrail to refuse)")
        show(await client.call_tool("run_sql", {"sql": "DROP TABLE orders"}))

        print("\n4. make_chart: sales by region")
        show(await client.call_tool("make_chart", {
            "sql": "SELECT region, ROUND(SUM(sales), 2) FROM orders JOIN order_lines USING (order_id) "
                   "GROUP BY region ORDER BY 2 DESC",
            "chart_type": "bar", "title": "Sales by region"}))


if __name__ == "__main__":
    asyncio.run(main())
