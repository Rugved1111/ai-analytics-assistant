"""API behaviour without spending Gemini requests (saved answers and plain SQL only)."""
import json

import pytest
from fastapi.testclient import TestClient

import api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "CACHE_FILE", tmp_path / "answers.json")
    return TestClient(api.app)


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"


def test_kpis_match_answer_key(client):
    k = client.get("/kpis").json()
    assert k["total_sales"] == pytest.approx(2297200.86)
    assert k["total_profit"] == pytest.approx(286397.02)
    assert k["margin_pct"] == pytest.approx(12.47)
    assert k["orders"] == 5009
    assert k["aov"] == pytest.approx(458.61)
    assert k["years"] == [2014, 2015, 2016, 2017]


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_rejects_bad_questions(client, question):
    assert client.post("/ask", json={"question": question}).status_code == 400


def test_cache_only_without_saved_answer_is_404(client):
    assert client.post("/ask", json={"question": "anything", "cache_only": True}).status_code == 404


def test_saved_answer_is_returned_without_gemini(client):
    saved = {"question": "How many VIP customers?", "answer": "20.", "gemini_requests": 3}
    api.CACHE_FILE.write_text(json.dumps({api.cache_key("How many VIP customers?"): saved}))
    body = client.post("/ask", json={"question": "how many VIP customers", "cache_only": True}).json()
    assert body["cached"] is True and body["answer"] == "20."


def test_parse_notes():
    text = "## VIP (distance 0.31)\nA VIP has sales of 10,000.\n\n## Shipping (distance 0.52)\nLate means > 5 days."
    notes = api.parse_notes(text)
    assert [n.heading for n in notes] == ["VIP", "Shipping"]
    assert notes[0].distance == pytest.approx(0.31)


def test_build_chart_from_make_chart_args():
    chart = api.build_chart({"sql": "SELECT region, SUM(sales) FROM orders JOIN order_lines USING (order_id) "
                                     "GROUP BY region ORDER BY region",
                             "chart_type": "bar", "title": "Sales by region"})
    assert chart.x == ["Central", "East", "South", "West"] and len(chart.y) == 4


def test_build_table_refuses_non_select():
    assert api.build_table("DELETE FROM orders") is None


def fake_agent(failures, monkeypatch):
    """Replace the agent: raise the given errors in order, then return an empty conversation."""
    calls = []

    def run_agent(question, model):
        calls.append(model)
        if failures:
            raise RuntimeError(failures.pop(0))
        return [], False

    monkeypatch.setattr(api, "run_agent", run_agent)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    return calls


def test_busy_model_is_retried_then_next_model(client, monkeypatch):
    calls = fake_agent(["503 UNAVAILABLE", "503 UNAVAILABLE"], monkeypatch)
    assert client.post("/ask", json={"question": "q"}).status_code == 200
    assert calls == [api.MODELS[0], api.MODELS[0], api.MODELS[1]]


def test_quota_error_skips_to_next_model(client, monkeypatch):
    calls = fake_agent(["429 RESOURCE_EXHAUSTED"], monkeypatch)
    assert client.post("/ask", json={"question": "q"}).status_code == 200
    assert calls == [api.MODELS[0], api.MODELS[1]]


def test_all_models_out_of_quota_is_429(client, monkeypatch):
    fake_agent(["429 RESOURCE_EXHAUSTED"] * 4, monkeypatch)
    assert client.post("/ask", json={"question": "q"}).status_code == 429
