"""Check the assistant's answers against the hand-written answer key.

Usage:
  python eval.py          # checks saved answers only: 0 Gemini requests
  python eval.py --live   # asks the agent again (about 3 Gemini requests per question)

The API must be running (uvicorn api:app --port 8000). The expected values come from
sql/03_practice_queries.sql and sql/06_rag_answer_key.sql, run by hand in psql.
"""
import sys

import requests

API_URL = "http://127.0.0.1:8000/ask"

# (question, values that must appear in the result table)
ANSWER_KEY = [
    ("What are our total sales, total profit and profit margin?", [2297200.86, 286397.02, 12.47]),
    ("Show total sales by category as a bar chart", [836154.03, 741999.80, 719047.03]),
    ("How many VIP customers do we have, and how much did they spend in total?", [20]),
    ("How many orders were late, and what percentage of all orders is that?", [904]),
    ("Show total sales by year as a line chart", [484247.50, 470532.51, 609205.60, 733215.26]),
    ("Which sub-categories lose money?", ["Tables", "Bookcases", "Supplies"]),
]


def found(expected, cells):
    if isinstance(expected, str):
        return expected in cells
    return any(isinstance(c, (int, float)) and abs(c - expected) < 0.01 for c in cells)


def main(live):
    passed = 0
    for question, expected in ANSWER_KEY:
        resp = requests.post(API_URL, json={"question": question, "fresh": live}, timeout=180)
        if resp.status_code != 200:
            print(f"ERROR  {question}\n       {resp.json().get('detail')}")
            continue
        data = resp.json()
        rows = (data.get("table") or {}).get("rows", [])
        cells = [round(c, 2) if isinstance(c, float) else c for row in rows for c in row]
        missing = [e for e in expected if not found(e, cells)]
        ok = not missing
        passed += ok
        source = "saved" if data["cached"] else f"{data['gemini_requests']} requests"
        print(f"{'PASS ' if ok else 'FAIL '}  {question}  ({source})")
        if missing:
            print(f"       missing: {missing}  got: {rows[:5]}")
    print(f"\n{passed}/{len(ANSWER_KEY)} questions match the answer key")
    return passed == len(ANSWER_KEY)


if __name__ == "__main__":
    sys.exit(0 if main("--live" in sys.argv) else 1)
