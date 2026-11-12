"""The 30-question answer key itself must be valid: every key query passes the guardrail and returns rows."""
import pytest

from agent_tools import check_select
from db import run_sql
from evals.questions import QUESTIONS
from evals.run_eval import value_found


def test_thirty_unique_questions():
    assert len(QUESTIONS) == 30
    assert len({q["id"] for q in QUESTIONS}) == 30
    assert len({q["question"] for q in QUESTIONS}) == 30


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q["id"])
def test_key_sql_runs(q):
    assert check_select(q["sql"]) is None
    assert run_sql(q["sql"])["rows"], f"{q['id']} returned no rows"


def test_known_answers():
    by_id = {q["id"]: q for q in QUESTIONS}
    assert run_sql(by_id["q17"]["sql"])["rows"][0][0] == 20          # VIP customers
    assert run_sql(by_id["q19"]["sql"])["rows"][0][0] == 904         # late orders
    assert float(run_sql(by_id["q21"]["sql"])["rows"][0][0]) == pytest.approx(-122615.64)


@pytest.mark.parametrize("expected, cells, ok", [
    (18.0, [904, 18.05], True),
    (12.47, [12.4672], True),
    (2014, ["2014"], True),
    ("Tables", ["tables"], True),
    (904, [903], False),
    (100.0, [101.0], False),
])
def test_value_matching(expected, cells, ok):
    assert value_found(expected, cells) is ok
