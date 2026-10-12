"""Step 3.5: RAG = retrieve business notes, then let Gemini write SQL that follows them."""
import os
import time

import psycopg
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from search_docs import search_docs

load_dotenv()

MODEL = "gemini-flash-lite-latest"
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SCHEMA = """
customers(customer_id PK, customer_name, segment)
products(product_key PK, product_id, product_name, category, sub_category)
orders(order_id PK, customer_id FK -> customers, order_date DATE, ship_date DATE,
       ship_mode, country, city, state, postal_code, region)
order_lines(row_id PK, order_id FK -> orders, product_key FK -> products,
            sales, quantity, discount, profit)
Notes: sales and profit are per order line. discount is a fraction (0.2 = 20%).
Orders run from 2014-01-03 to 2017-12-30.
"""


class RagAnswer(BaseModel):
    sql: str
    rule_used: str
    explanation: str


def build_prompt(question, chunks):
    """Schema + retrieved notes + rules + question, as one prompt."""
    notes = "\n\n".join(f"### {c['heading']}\n{c['content']}" for c in chunks)
    return f"""You are a data analyst writing PostgreSQL for a sales database.

DATABASE SCHEMA:
{SCHEMA}

BUSINESS NOTES (this company's own definitions; they override general knowledge):
{notes}

Write ONE PostgreSQL SELECT query that answers the question.
- Use only the tables and columns in the schema.
- If a note defines a term in the question, apply that definition exactly
  and quote the rule in rule_used.
- If no note defines a company-specific term, say "no rule found" in rule_used
  instead of inventing a definition.
- Round money to 2 decimals and percentages to 1 decimal.

QUESTION: {question}
"""


def call_gemini(prompt):
    """Ask Gemini for a RagAnswer. Retry only on 5xx (server busy), never on 429."""
    for wait in (5, 10, None):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=RagAnswer,
                ),
            )
            return response.parsed
        except errors.ServerError:
            if wait is None:
                raise
            print(f"  Gemini is busy (5xx), retrying in {wait}s...")
            time.sleep(wait)


def run_sql(sql, max_rows=20):
    """Run the query as the read-only ai_reader user."""
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["AI_DB_USER"],
        password=os.environ["AI_DB_PASSWORD"],
    ) as conn:
        cur = conn.execute(sql)
        columns = [d.name for d in cur.description]
        rows = cur.fetchmany(max_rows)
    return columns, rows


def rag_answer(question, k=3):
    chunks = search_docs(question, k=k)                    # 1. retrieve
    answer = call_gemini(build_prompt(question, chunks))   # 2. augment + generate
    columns, rows = run_sql(answer.sql)                    # 3. run it
    return chunks, answer, columns, rows


if __name__ == "__main__":
    # (question, answer key from sql/06_rag_answer_key.sql and Phase 2)
    tests = [
        ("How many VIP customers do we have?", "20"),
        ("How many orders were late, and what percentage of all orders is that?", "904 (18.0%)"),
        ("What was the total profit on heavily discounted order lines?", "-122615.64"),
        ("What is our average order value?", "458.61"),
    ]
    for question, expected in tests:
        print(f"\nQ: {question}")
        try:
            chunks, answer, columns, rows = rag_answer(question)
            print("  Evidence:  " + ", ".join(f"{c['heading']} ({c['distance']})" for c in chunks))
            print(f"  Rule used: {answer.rule_used}")
            print(f"  SQL:       {' '.join(answer.sql.split())}")
            print(f"  Result:    {columns} {[tuple(str(v) for v in r) for r in rows]}")
            print(f"  Expected:  {expected}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")