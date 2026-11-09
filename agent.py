"""Phase 4: the agent. Gemini in a loop, choosing from the three tools.

Usage: python agent.py "your question"
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.errors import GraphRecursionError

from agent_tools import TOOLS
from rag_answer import SCHEMA

MODEL = "gemini-flash-lite-latest"
# Every Gemini call and every tool run is one step, so 12 steps = at most 6 Gemini requests.
MAX_STEPS = 12

SYSTEM_PROMPT = f"""You are a data analyst for a US office-supplies retailer (orders from 2014 to 2017).
Answer questions with the tools. Rules:
1. If the question uses a company term (VIP, late order, AOV, active customer, heavy discount, margin),
   call search_docs FIRST and follow the definition it returns.
2. Get every number from run_sql (PostgreSQL, SELECT only, schema below). Never invent or estimate numbers.
3. If run_sql returns an SQL error, fix the query and try again.
4. Only call make_chart when the user asks for a chart, graph or plot.
5. Final answer: the answer with its key numbers, then the SQL you ran,
   then the business rule you used (if any) and the chart path (if any).

Schema:
{SCHEMA}"""


def build_agent():
    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        temperature=0,
        google_api_key=os.environ["GEMINI_API_KEY"],
        max_retries=1,
    )
    return create_agent(llm, TOOLS, system_prompt=SYSTEM_PROMPT)


def show_steps(messages):
    """Print the conversation the agent built: every tool call, result and the final answer."""
    requests = 0
    for msg in messages:
        if msg.type == "human":
            print(f"\nQUESTION: {msg.text}")
        elif msg.type == "ai":
            requests += 1
            if msg.tool_calls:
                for call in msg.tool_calls:
                    print(f"\n[Gemini request {requests}] calls {call['name']} with:")
                    for key, value in call["args"].items():
                        print(f"    {key}: {value}")
            else:
                print(f"\n[Gemini request {requests}] FINAL ANSWER:\n{msg.text}")
        elif msg.type == "tool":
            result = msg.text
            if len(result) > 400:
                result = result[:400] + " ..."
            print(f"  -> {msg.name} returned:\n{result}")
    print(f"\nGemini requests used: {requests}")


def ask(question):
    agent = build_agent()
    state = None
    hit_cap = False
    try:
        # stream_mode="values" hands back the whole conversation after every step,
        # so if the loop cap stops the agent we can still print how far it got.
        for state in agent.stream(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": MAX_STEPS},
            stream_mode="values",
        ):
            pass
    except GraphRecursionError:
        hit_cap = True
    if state:
        show_steps(state["messages"])
    if hit_cap:
        print(f"\nSTOPPED: the agent hit the {MAX_STEPS}-step loop cap.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python agent.py "your question"')
        sys.exit(1)
    ask(sys.argv[1])