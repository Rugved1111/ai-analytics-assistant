import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from db import run_sql

load_dotenv()  # reads GEMINI_API_KEY from .env
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# What Gemini needs to know about OUR database
SCHEMA = """
customers(customer_id text PK, customer_name text, segment text)
products(product_key int PK, product_id text, product_name text, category text, sub_category text)
orders(order_id text PK, customer_id text FK -> customers, order_date date, ship_date date,
       ship_mode text, country text, city text, state text, postal_code text, region text)
order_lines(row_id int PK, order_id text FK -> orders, product_key int FK -> products,
            sales numeric, quantity int, discount numeric, profit numeric)

Notes:
- One row in order_lines = one product on one order. Sales and profit live here, in USD.
- To count orders use count(DISTINCT order_id).
- Profit margin = SUM(profit) / SUM(sales) * 100, shown as a percentage rounded to 2 decimals.
- Data covers 2014-01-03 to 2017-12-30.
"""

SYSTEM_PROMPT = f"""You are an expert PostgreSQL analyst.
Write ONE PostgreSQL SELECT query that answers the user's question using only this schema:
{SCHEMA}
Rules:
- Only SELECT. Never INSERT, UPDATE, DELETE, DROP or ALTER.
- Round money to 2 decimals.
- explanation: one plain-English sentence for a business user saying what the query calculates.
- chart_type: "bar" for comparing groups, "line" for trends over time, "table" for anything else.
"""


# The exact shape we want back: Gemini must fill these 3 fields
class SqlAnswer(BaseModel):
    sql: str
    explanation: str
    chart_type: str


def call_gemini(question: str):
    """Ask Gemini for SQL. If its servers are busy (5xx error), wait and try again."""
    for attempt in range(1, 4):
        try:
            return client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=question,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=SqlAnswer,
                ),
            )
        except errors.ServerError:
            if attempt == 3:
                raise  # still busy after 3 tries: give up and let the caller see the error
            wait = 5 * attempt  # 5s, then 10s
            print(f"  Gemini is busy, retrying in {wait}s (attempt {attempt} of 3)...")
            time.sleep(wait)


def ask(question: str) -> tuple[SqlAnswer, dict]:
    """Turn a question into SQL with Gemini, run it, and return both."""
    response = call_gemini(question)
    answer = response.parsed
    result = run_sql(answer.sql)
    return answer, result


# Business questions we already know the answers to (Phase 1 answer key)
QUESTIONS = [
    "What are our total sales, total profit and profit margin?",
    "Who are our top 5 customers by sales?",
    "How many orders did we get each year?",
    "Which sub-categories lose money?",
    "What is the profit margin by region?",
]

if __name__ == "__main__":
    for question in QUESTIONS:
        print("=" * 60)
        print("QUESTION:", question)
        try:
            answer, result = ask(question)
        except Exception as error:
            print("FAILED:", error)
            continue
        print("SQL:", answer.sql)
        print("CHART:", answer.chart_type)
        print("RESULT:", result["columns"])
        for row in result["rows"]:
            print(row)