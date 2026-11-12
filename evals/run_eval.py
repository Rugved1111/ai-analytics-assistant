"""Phase 6: run the 30-question evaluation against the API.

Usage (the API must be running: uvicorn api:app --port 8000):
  python -m evals.run_eval                 # saved answers only: 0 Gemini requests
  python -m evals.run_eval --live          # ask Gemini for questions without a saved answer
  python -m evals.run_eval --live --limit 5
  python -m evals.run_eval --grade         # also let an LLM grade the answer text

How a question is scored
  1. Execution accuracy (automatic, no LLM): run the hand-written key SQL and check that every
     value it returns appears in the agent's result table (numbers within rounding).
  2. Chart check: for "chart" questions the agent must also return a chart.
  3. Optional LLM grader: Gemini reads the question, the key result and the agent's written
     answer, and scores whether the text states the right numbers (1-5) without inventing any.

Answers are saved by the API, so a --live run that stops on the daily free quota can simply be
run again the next day: questions answered before are not asked again.
Results are written to evals/results/latest.json and evals/results/latest.md.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import run_sql  # noqa: E402
from evals.questions import QUESTIONS  # noqa: E402

load_dotenv()

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
RESULTS = Path(__file__).parent / "results"
GRADER_MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest"]


# ---------- execution accuracy ----------

def as_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("%", ""))
    except ValueError:
        return None


def close(a, b):
    # Allows rounding differences such as 18.0 vs 18.05 and 12.47 vs 12.4672.
    return abs(a - b) <= 0.051 or abs(a - b) <= abs(b) * 0.001


def value_found(expected, cells):
    num = as_number(expected)
    if num is not None:
        return any((c := as_number(cell)) is not None and close(c, num) for cell in cells)
    return any(str(expected).strip().lower() == str(cell).strip().lower() for cell in cells)


def expected_values(sql):
    result = run_sql(sql, max_rows=100)
    return [v for row in result["rows"] for v in row], result["rows"]


def score_table(question, answer):
    expected, key_rows = expected_values(question["sql"])
    rows = (answer.get("table") or {}).get("rows", [])
    cells = [c for row in rows for c in row]
    missing = [v for v in expected if not value_found(v, cells)]
    return {"correct": not missing, "missing": [str(m) for m in missing][:8],
            "key_rows": [[str(v) for v in r] for r in key_rows][:20]}


# ---------- optional LLM grader ----------

def grade_answer(question, key_rows, agent_rows, answer_text):
    """Ask Gemini to grade the written answer. Costs 1 request per question."""
    from google import genai
    from google.genai import types
    from pydantic import BaseModel

    class Grade(BaseModel):
        score: int        # 1 (wrong) to 5 (fully correct and clear)
        invented_numbers: bool
        reason: str

    prompt = f"""You grade answers from a data assistant. Be strict.
QUESTION: {question}
ANSWER KEY (rows from the hand-written SQL): {key_rows}
DATA THE ASSISTANT RETRIEVED (its own query result): {agent_rows}
ASSISTANT ANSWER: {answer_text}

Score 1-5: 5 = agrees with the answer key (rounding is fine) and answers the question;
3 = partly correct or missing a key number; 1 = wrong.
Extra supporting numbers are fine when they appear in the retrieved data.
invented_numbers = true only if the answer states a number found in neither the answer key
nor the retrieved data (allow rounding and simple formatting such as $ and %)."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    import time

    last = None
    for model in [m for m in GRADER_MODELS for _ in (1, 2)]:  # each model gets a second try
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json",
                                                   response_schema=Grade))
            return {**resp.parsed.model_dump(), "grader_model": model}
        except Exception as e:  # busy or out of quota: wait, then retry or try the next free model
            last = e
            time.sleep(3)
    return {"error": f"{type(last).__name__}: {str(last)[:120]}"}


# ---------- runner ----------

def ask(question, live):
    resp = requests.post(f"{API_URL}/ask", json={"question": question, "cache_only": not live}, timeout=300)
    if resp.status_code == 200:
        return resp.json(), None
    try:
        detail = resp.json().get("detail")
    except ValueError:
        detail = resp.text
    return None, (resp.status_code, detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="ask Gemini for questions without a saved answer")
    parser.add_argument("--grade", action="store_true", help="LLM-grade the answer text (1 request each)")
    parser.add_argument("--limit", type=int, help="ask at most this many new questions with --live")
    parser.add_argument("--only", nargs="*", help="question ids to run, e.g. q01 q17")
    args = parser.parse_args()

    questions = [q for q in QUESTIONS if not args.only or q["id"] in args.only]
    results, new_asked, quota_out = [], 0, False
    for q in questions:
        live = args.live and not quota_out and (args.limit is None or new_asked < args.limit)
        answer, error = ask(q["question"], live)
        row = {"id": q["id"], "kind": q["kind"], "question": q["question"]}
        if error:
            status, detail = error
            row["status"] = "not run" if status == 404 else "error"
            row["detail"] = detail
            if status == 429:
                quota_out = True
            print(f"{row['status'].upper():8} {q['id']} {q['question']}")
            results.append(row)
            continue
        if not answer["cached"]:
            new_asked += 1
        score = score_table(q, answer)
        chart_ok = q["kind"] != "chart" or answer.get("chart") is not None
        row.update({
            "status": "pass" if score["correct"] and chart_ok else "fail",
            "correct_numbers": score["correct"], "chart_ok": chart_ok, "missing": score["missing"],
            "answer": answer["answer"], "sql": answer.get("sql"), "rule": (answer.get("rule") or {}).get("heading"),
            "gemini_requests": answer["gemini_requests"], "seconds": answer["seconds"], "cached": answer["cached"],
        })
        if args.grade:
            agent_rows = (answer.get("table") or {}).get("rows", [])[:30]
            row["grade"] = grade_answer(q["question"], score["key_rows"], agent_rows, answer["answer"])
        flag = "PASS" if row["status"] == "pass" else "FAIL"
        extra = f"  missing {score['missing']}" if score["missing"] else ""
        extra += "" if chart_ok else "  (no chart)"
        print(f"{flag:8} {q['id']} {q['question']}{extra}")
        results.append(row)

    write_report(results, args)


def write_report(results, args):
    ran = [r for r in results if r["status"] in ("pass", "fail")]
    passed = [r for r in ran if r["status"] == "pass"]
    by_kind = {}
    for r in ran:
        k = by_kind.setdefault(r["kind"], [0, 0])
        k[0] += r["status"] == "pass"
        k[1] += 1
    grades = [r["grade"]["score"] for r in ran if isinstance(r.get("grade"), dict) and "score" in r["grade"]]
    invented = sum(1 for r in ran if isinstance(r.get("grade"), dict) and r["grade"].get("invented_numbers"))
    live = [r for r in ran if not r["cached"]]

    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "questions": len(results), "answered": len(ran), "passed": len(passed),
        "accuracy_pct": round(100 * len(passed) / len(ran), 1) if ran else None,
        "by_kind": {k: f"{p}/{n}" for k, (p, n) in by_kind.items()},
        "avg_gemini_requests": round(sum(r["gemini_requests"] for r in ran) / len(ran), 1) if ran else None,
        "avg_seconds_live": round(sum(r["seconds"] for r in live) / len(live), 1) if live else None,
        "llm_grade_avg": round(sum(grades) / len(grades), 2) if grades else None,
        "answers_with_invented_numbers": invented if grades else None,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "latest.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2, default=str))

    lines = ["# Evaluation results", "", f"Run at {summary['run_at']}.", "",
             f"**{len(passed)}/{len(ran)} answered questions correct** "
             f"({len(ran)} of {len(results)} answered so far).", "",
             "| Kind | Passed |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary["by_kind"].items()]
    if summary["avg_gemini_requests"] is not None:
        lines += ["", f"Average Gemini requests per question: {summary['avg_gemini_requests']}."]
    if grades:
        lines += [f"LLM grader average: {summary['llm_grade_avg']} / 5; "
                  f"answers with invented numbers: {invented}."]
    lines += ["", "| Id | Kind | Question | Result |", "|---|---|---|---|"]
    for r in results:
        status = r["status"]
        if r.get("missing"):
            status += f" (missing {', '.join(r['missing'][:3])})"
        lines.append(f"| {r['id']} | {r['kind']} | {r['question']} | {status} |")
    (RESULTS / "latest.md").write_text("\n".join(lines) + "\n")

    print(f"\n{len(passed)}/{len(ran)} correct, {len(results) - len(ran)} not run yet. "
          f"By kind: {summary['by_kind']}")
    print(f"Report: {RESULTS / 'latest.md'}")


if __name__ == "__main__":
    main()
