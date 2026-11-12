"""Streamlit frontend for the AI Analytics Assistant.

Run the API first (uvicorn api:app --port 8000), then: streamlit run app.py
"""
import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# API_URL=inprocess runs the FastAPI app inside Streamlit (one process, used for free hosting).
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

EXAMPLES = [
    ("What are our total sales, total profit and profit margin?", ":material/payments:"),
    ("Show total sales by category as a bar chart", ":material/bar_chart:"),
    ("How many VIP customers do we have, and how much did they spend in total?", ":material/workspace_premium:"),
    ("How many orders were late, and what percentage of all orders is that?", ":material/local_shipping:"),
    ("Show total sales by year as a line chart", ":material/show_chart:"),
    ("Which sub-categories lose money?", ":material/trending_down:"),
]

st.set_page_config(page_title="AI Analytics Assistant", page_icon=":material/insights:", layout="wide")


# ---------- API calls ----------

@st.cache_resource(show_spinner="Loading the assistant...")
def in_process_client():
    from fastapi.testclient import TestClient

    import api
    return TestClient(api.app)


def call_api(method, path, timeout, **kwargs):
    if API_URL == "inprocess":
        try:
            return getattr(in_process_client(), method)(path, **kwargs)
        except Exception as e:  # keep the same error handling as the HTTP path
            raise requests.ConnectionError(str(e)) from e
    return getattr(requests, method)(f"{API_URL}{path}", timeout=timeout, **kwargs)


@st.cache_data(ttl=600, show_spinner=False)
def get_kpis():
    resp = call_api("get", "/kpis", 15)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30, show_spinner=False)
def get_health():
    try:
        return call_api("get", "/health", 5).json()
    except requests.RequestException:
        return None


def ask_api(question, fresh):
    try:
        resp = call_api("post", "/ask", 180, json={"question": question, "fresh": fresh})
    except requests.RequestException:
        return {"error": "Can't reach the API. Is `uvicorn api:app --port 8000` running?"}
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        return {"error": f"{detail}"}
    return resp.json()


# ---------- formatting ----------

def money(value, compact=False):
    if compact and abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if compact and abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.2f}"


def md_safe(text):
    # Streamlit reads $...$ as LaTeX, so escape dollar signs in answers.
    return text.replace("$", "\\$")


def nice(name):
    return name.replace("_", " ").capitalize()


def make_figure(chart):
    x, y = nice(chart["x_label"]), nice(chart["y_label"])
    data = pd.DataFrame({x: chart["x"], y: chart["y"]})
    if chart["chart_type"] == "line":
        fig = px.line(data, x=x, y=y, title=chart["title"], markers=True)
    else:
        fig = px.bar(data, x=x, y=y, title=chart["title"], text_auto=",.0f")
        fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(margin=dict(t=50, l=10, r=10, b=10), xaxis_title=None, xaxis_type="category")
    fig.update_yaxes(tickformat=",.0f")
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>")
    return fig


def auto_chart(table):
    """If the agent didn't draw a chart but the result is label + number, offer a quick one."""
    if not table or len(table["columns"]) != 2 or not 2 <= len(table["rows"]) <= 40:
        return None
    try:
        y = [float(r[1]) for r in table["rows"]]
    except (TypeError, ValueError):
        return None
    label = table["columns"][0].lower()
    kind = "line" if any(w in label for w in ("year", "month", "date", "quarter")) else "bar"
    return {"chart_type": kind, "title": "", "x_label": table["columns"][0],
            "y_label": table["columns"][1], "x": [str(r[0]) for r in table["rows"]], "y": y}


# ---------- one answer ----------

def show_answer(result, idx):
    if "error" in result:
        st.error(result["error"], title="Couldn't answer that", icon=":material/error:")
        return

    st.markdown(md_safe(result["answer"]))

    with st.container(horizontal=True, gap="small"):
        if result.get("cached"):
            st.badge("Saved answer, 0 Gemini requests", icon=":material/bolt:", color="green")
        else:
            st.badge(f"{result['gemini_requests']} Gemini requests", icon=":material/smart_toy:", color="blue")
            st.badge(f"{result['seconds']} s", icon=":material/timer:", color="gray")
        if result.get("rule"):
            st.badge(f"Rule: {result['rule']['heading']}", icon=":material/menu_book:", color="violet")
        if result.get("sql"):
            st.badge("Read-only SQL", icon=":material/lock:", color="gray")
        if result.get("hit_cap"):
            st.badge("Stopped at step cap", icon=":material/warning:", color="orange")

    table = result.get("table")
    chart = result.get("chart") or auto_chart(table)
    tabs = []
    if chart:
        tabs.append("Chart")
    if table:
        tabs.append("Data")
    if result.get("sql"):
        tabs.append("SQL")
    if result.get("notes"):
        tabs.append("Business rule")
    tabs.append("Agent steps")

    for name, tab in zip(tabs, st.tabs(tabs, key=f"tabs_{idx}")):
        with tab:
            if name == "Chart":
                if not result.get("chart"):
                    st.caption("Quick chart of the result table.")
                st.plotly_chart(make_figure(chart), key=f"chart_{idx}",
                                alt=chart["title"] or "Chart of the query result")
            elif name == "Data":
                df = pd.DataFrame(table["rows"], columns=table["columns"])
                st.dataframe(df, hide_index=True, alt="Query result",
                             column_config={c: st.column_config.NumberColumn(format="localized")
                                            for c in df.select_dtypes("number").columns})
                if table["truncated"]:
                    st.caption("Showing the first 100 rows.")
            elif name == "SQL":
                st.caption("The exact query the agent ran, as the read-only `ai_reader` database user.")
                st.code(result["sql"], language="sql", wrap_lines=True)
            elif name == "Business rule":
                rule = result["rule"]
                st.markdown(f"**{rule['heading']}**")
                st.markdown(md_safe(rule["content"]))
                others = result["notes"][1:]
                if others:
                    st.caption("Also retrieved: " + ", ".join(n["heading"] for n in others))
            elif name == "Agent steps":
                if result.get("model"):
                    st.caption(f"Model: {result['model']}")
                for i, step in enumerate(result["steps"], 1):
                    st.markdown(f"**{i}. `{step['tool']}`**")
                    args = step["args"]
                    if "sql" in args:
                        st.code(args["sql"], language="sql", wrap_lines=True)
                    other = {k: v for k, v in args.items() if k != "sql"}
                    if other:
                        st.json(other, expanded=True)
                if not result["steps"]:
                    st.caption("The agent answered without calling a tool.")


# ---------- state ----------

if "history" not in st.session_state:
    st.session_state.history = []  # list of (question, result)
if "pending" not in st.session_state:
    st.session_state.pending = None


def queue(question):
    st.session_state.pending = question


# ---------- sidebar ----------

with st.sidebar:
    st.header(":material/insights: AI Analytics Assistant")
    health = get_health()
    if health and health.get("database") == "ok":
        st.badge("API and database online", icon=":material/check_circle:", color="green")
    elif health:
        st.badge(f"Database: {health.get('database')}", icon=":material/error:", color="red")
    else:
        st.badge("API offline", icon=":material/error:", color="red")

    st.subheader("Try a question")
    for i, (q, icon) in enumerate(EXAMPLES):
        st.button(q, icon=icon, key=f"ex_{i}", on_click=queue, args=(q,), width="stretch", type="tertiary")

    st.divider()
    reuse = st.toggle("Reuse saved answers", value=True,
                      help="Questions asked before come back instantly and cost 0 Gemini requests.")
    if st.button("Clear conversation", icon=":material/delete_sweep:", width="stretch"):
        st.session_state.history = []
        st.rerun()

    with st.expander("How it works", icon=":material/info:"):
        st.markdown(
            "1. **Gemini** reads your question and picks tools in a loop (LangGraph agent).\n"
            "2. **search_docs** finds company definitions (VIP, late order, AOV) in the business "
            "notes with pgvector.\n"
            "3. **run_sql** runs a SELECT on PostgreSQL as a read-only user, with a 5 s timeout "
            "and a row limit.\n"
            "4. **make_chart** draws the chart.\n\n"
            "Every number comes from SQL, and every answer shows the query behind it."
        )


# ---------- header ----------

st.title("Sales analytics assistant")
st.caption("Ask questions about 4 years of US office-supplies sales (2014 to 2017) in plain English. "
           "Every answer shows the SQL and the business rule behind it.")

try:
    k = get_kpis()
    with st.grid(5, gap="small", min_column_width=170):
        st.metric("Total sales", money(k["total_sales"], compact=True), border=True, height="stretch",
                  chart_data=k["sales_by_year"], chart_type="area", help="Sales by year, 2014 to 2017")
        st.metric("Total profit", money(k["total_profit"], compact=True), border=True, height="stretch",
                  chart_data=k["profit_by_year"], chart_type="area", help="Profit by year, 2014 to 2017")
        st.metric("Profit margin", f"{k['margin_pct']:.2f}%", border=True, height="stretch",
                  help="Total profit / total sales")
        st.metric("Orders", f"{k['orders']:,}", border=True, height="stretch",
                  chart_data=k["orders_by_year"], chart_type="area", help="Orders by year, 2014 to 2017")
        st.metric("Avg order value", money(k["aov"]), border=True, height="stretch",
                  help=f"Total sales / distinct orders, across {k['customers']:,} customers")
except Exception:  # API down (HTTP) or database down (in-process)
    st.warning("Start the API to see the headline numbers: `uvicorn api:app --port 8000`",
               title="API offline", icon=":material/cloud_off:")


# ---------- conversation ----------

for idx, (question, result) in enumerate(st.session_state.history):
    with st.chat_message("user"):
        st.markdown(md_safe(question))
    with st.chat_message("assistant"):
        show_answer(result, idx)

if not st.session_state.history and not st.session_state.pending:
    st.info("Pick a question in the sidebar, or type your own below.",
            title="Ask anything about the sales data", icon=":material/lightbulb:")

typed = st.chat_input("Ask about sales, profit, customers, shipping...", max_chars=500)
question = typed or st.session_state.pending
st.session_state.pending = None

if question:
    with st.chat_message("user"):
        st.markdown(md_safe(question))
    with st.chat_message("assistant"):
        with st.spinner("Thinking: searching the business notes, writing SQL, checking the numbers..."):
            result = ask_api(question, fresh=not reuse)
        show_answer(result, len(st.session_state.history))
    st.session_state.history.append((question, result))
