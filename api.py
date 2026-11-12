"""FastAPI backend for the AI Analytics Assistant.

Endpoints
  GET  /health  -> API and database status
  GET  /kpis    -> headline numbers for the dashboard header (plain SQL, no Gemini)
  POST /ask     -> runs the LangGraph agent and returns the answer, the SQL it ran,
                   the result rows, the business rule it used and chart data

Answers are saved in cache/answers.json. Asking the same question again returns the
saved answer instantly and costs 0 Gemini requests (send "fresh": true to skip it).
"""
import json
import re
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from agent import FALLBACK_MODELS, MAX_STEPS, MODEL, build_agent
from agent_tools import check_select
from db import run_sql

app = FastAPI(title="AI Analytics Assistant", version="1.0")

MODELS = [MODEL, *FALLBACK_MODELS]
_agents = {}  # model name -> agent, built on first use

CACHE_FILE = Path("cache/answers.json")


# ---------- response shapes ----------

class Question(BaseModel):
    question: str
    fresh: bool = False  # True = ignore the saved answer and ask Gemini again
    cache_only: bool = False  # True = only return a saved answer, never call Gemini (for evals)


class Step(BaseModel):
    tool: str
    args: dict


class Note(BaseModel):
    heading: str
    content: str
    distance: float


class Chart(BaseModel):
    chart_type: str
    title: str
    x_label: str
    y_label: str
    x: list[str]
    y: list[float]


class Table(BaseModel):
    columns: list[str]
    rows: list[list]
    truncated: bool


class Answer(BaseModel):
    question: str
    answer: str
    sql: str | None = None
    table: Table | None = None
    rule: Note | None = None
    notes: list[Note] = []
    chart: Chart | None = None
    steps: list[Step] = []
    gemini_requests: int = 0
    model: str | None = None
    seconds: float = 0.0
    hit_cap: bool = False
    cached: bool = False


# ---------- helpers ----------

def text_of(msg):
    # .text is a str-like property in newer langchain-core, a method in older ones
    t = msg.text
    return str(t) if isinstance(t, str) else t()


def to_json(value):
    """Make database values JSON-friendly."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def is_quota_error(err):
    text = str(err)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


def is_busy_error(err):
    """Gemini's servers are overloaded for a moment (503); worth retrying."""
    text = str(err)
    return "503" in text or "UNAVAILABLE" in text or "overloaded" in text.lower()


def cache_key(question):
    return re.sub(r"[^a-z0-9 ]", "", question.lower()).strip()


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_to_cache(answer: Answer):
    cache = load_cache()
    cache[cache_key(answer.question)] = answer.model_dump()
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def parse_notes(text):
    """search_docs returns '## Heading (distance 0.31)\\ncontent' blocks."""
    notes = []
    for block in re.split(r"\n\n(?=## )", text.strip()):
        found = re.match(r"## (.+?) \(distance ([\d.]+)\)\n(.*)", block, re.S)
        if found:
            notes.append(Note(heading=found.group(1), content=found.group(3).strip(),
                              distance=float(found.group(2))))
    return notes


def build_table(sql):
    """Re-run the agent's final query (read-only role, guarded) to get clean rows for the UI."""
    if not sql or check_select(sql):
        return None
    try:
        result = run_sql(sql, max_rows=100)
    except Exception:
        return None
    rows = [[to_json(v) for v in row] for row in result["rows"]]
    return Table(columns=result["columns"], rows=rows, truncated=result["truncated"])


def build_chart(args):
    """Turn the agent's make_chart call into chart data the UI draws with Plotly."""
    table = build_table(args.get("sql"))
    if not table or len(table.columns) != 2:
        return None
    try:
        y = [float(r[1]) for r in table.rows]
    except (TypeError, ValueError):
        return None
    return Chart(chart_type=args.get("chart_type", "bar"), title=args.get("title", ""),
                 x_label=table.columns[0], y_label=table.columns[1],
                 x=[str(r[0]) for r in table.rows], y=y)


# ---------- the agent ----------

def run_agent(question, model):
    if model not in _agents:
        _agents[model] = build_agent(model)
    state, hit_cap = None, False
    try:
        for state in _agents[model].stream(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": MAX_STEPS},
            stream_mode="values",
        ):
            pass
    except GraphRecursionError:
        hit_cap = True
    return (state["messages"] if state else []), hit_cap


def summarise(question, messages, hit_cap, model, seconds):
    steps, sql, answer, requests, notes, chart_args = [], None, "", 0, [], None
    for msg in messages:
        if msg.type == "ai":
            requests += 1
            for call in msg.tool_calls:
                steps.append(Step(tool=call["name"], args=call["args"]))
                if call["name"] == "run_sql":
                    sql = call["args"].get("sql", sql)
                elif call["name"] == "make_chart":
                    chart_args = call["args"]
                    sql = call["args"].get("sql", sql)
            if not msg.tool_calls:
                answer = text_of(msg)
        elif msg.type == "tool" and msg.name == "search_docs":
            notes = parse_notes(text_of(msg))
    if hit_cap and not answer:
        answer = f"I stopped after {MAX_STEPS} steps without a final answer. Try rephrasing the question."
    return Answer(
        question=question, answer=answer, sql=sql, table=build_table(sql),
        rule=notes[0] if notes else None, notes=notes,
        chart=build_chart(chart_args) if chart_args else None,
        steps=steps, gemini_requests=requests, model=model,
        seconds=round(seconds, 1), hit_cap=hit_cap,
    )


# ---------- endpoints ----------

@app.get("/health")
def health():
    try:
        run_sql("SELECT 1")
        db = "ok"
    except Exception as e:
        db = f"error: {type(e).__name__}"
    return {"status": "ok", "database": db, "model": MODEL}


@app.get("/kpis")
def kpis():
    totals = run_sql("""
        SELECT ROUND(SUM(ol.sales), 2), ROUND(SUM(ol.profit), 2),
               ROUND(100 * SUM(ol.profit) / SUM(ol.sales), 2),
               COUNT(DISTINCT o.order_id), COUNT(DISTINCT o.customer_id),
               ROUND(SUM(ol.sales) / COUNT(DISTINCT o.order_id), 2)
        FROM orders o JOIN order_lines ol USING (order_id)
    """)["rows"][0]
    yearly = run_sql("""
        SELECT EXTRACT(YEAR FROM o.order_date)::int, ROUND(SUM(ol.sales), 2),
               ROUND(SUM(ol.profit), 2), COUNT(DISTINCT o.order_id)
        FROM orders o JOIN order_lines ol USING (order_id)
        GROUP BY 1 ORDER BY 1
    """)["rows"]
    sales, profit, margin, orders, customers, aov = (to_json(v) for v in totals)
    return {
        "total_sales": sales, "total_profit": profit, "margin_pct": margin,
        "orders": orders, "customers": customers, "aov": aov,
        "years": [r[0] for r in yearly],
        "sales_by_year": [to_json(r[1]) for r in yearly],
        "profit_by_year": [to_json(r[2]) for r in yearly],
        "orders_by_year": [r[3] for r in yearly],
    }


@app.post("/ask", response_model=Answer)
def ask(q: Question):
    question = q.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty.")
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="Question is too long (500 characters max).")

    saved = load_cache().get(cache_key(question))
    if saved and not q.fresh:
        return Answer(**{**saved, "cached": True})
    if q.cache_only:
        raise HTTPException(status_code=404, detail="No saved answer for this question.")

    # Try each free model in turn. A busy model (503) gets one more try after a short pause;
    # a model whose daily quota is used up (429) is skipped.
    last_error = None
    attempts = [(m, wait) for m in MODELS for wait in (0, 3)]
    for model, wait in attempts:
        if last_error is not None and is_quota_error(last_error) and wait:
            continue
        time.sleep(wait)
        start = time.time()
        try:
            messages, hit_cap = run_agent(question, model)
        except Exception as e:
            last_error = e
            if is_quota_error(e) or is_busy_error(e):
                continue
            raise HTTPException(status_code=502, detail=f"Agent failed: {type(e).__name__}: {e}")
        result = summarise(question, messages, hit_cap, model, time.time() - start)
        if result.answer and not hit_cap:
            save_to_cache(result)
        return result

    # Every model is busy or out of quota. A saved answer is better than an error.
    if saved:
        return Answer(**{**saved, "cached": True})
    if is_quota_error(last_error):
        raise HTTPException(status_code=429, detail="The free Gemini quota is used up for today. "
                            "Try a question that was asked before, or try again tomorrow.")
    raise HTTPException(status_code=503, detail="Gemini is very busy right now. "
                        "Please try again in a minute, or pick one of the saved example questions.")
