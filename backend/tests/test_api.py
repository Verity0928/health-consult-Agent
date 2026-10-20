import logging

import httpx
from fastapi.testclient import TestClient
import main


def test_health_check():
    client = TestClient(main.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_endpoint_rejects_malformed_body():
    client = TestClient(main.app)
    resp = client.post("/api/chat", json={"session_id": "x"})  # missing message, llm_config
    assert resp.status_code == 422


def test_chat_endpoint_passes_base_url_and_embedding_model_to_run_turn(monkeypatch):
    # The red-flag short-circuit never reaches run_turn's retrieval code, so
    # it can't prove the two new kwargs are actually wired through main.py.
    # Capture what main.py calls run_turn with instead.
    client = TestClient(main.app)
    captured = {}

    def fake_run_turn(session, message, llm, kb_entries, **kwargs):
        captured.update(kwargs)
        from app.schemas import PipelineDebugInfo, PipelineResult
        return PipelineResult(reply="ok", status="answered", debug=PipelineDebugInfo())

    monkeypatch.setattr(main, "run_turn", fake_run_turn)
    resp = client.post("/api/chat", json={
        "session_id": "s5", "message": "随便问点什么",
        "llm_config": {
            "base_url": "http://unused.invalid", "api_key": "x", "model": "x",
            "embedding_model": "text-embedding-3-small",
        },
    })
    assert resp.status_code == 200
    assert captured["base_url"] == "http://unused.invalid"
    assert captured["embedding_model"] == "text-embedding-3-small"


def test_chat_endpoint_red_flag_short_circuits_without_calling_llm(monkeypatch):
    client = TestClient(main.app)
    # LLMClient would fail on a real network call; red-flag path must never reach it
    resp = client.post("/api/chat", json={
        "session_id": "s1", "message": "我现在呼吸困难",
        "llm_config": {"base_url": "http://unused.invalid", "api_key": "x", "model": "x"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "handoff"
    assert body["debug"]["handoff_reason"] == "red_flag"


def test_chat_endpoint_returns_502_on_llm_transport_error(monkeypatch):
    client = TestClient(main.app)

    class ExplodingLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        def complete_json(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

        def complete_text(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(main, "LLMClient", ExplodingLLMClient)
    resp = client.post("/api/chat", json={
        "session_id": "s2", "message": "哪些食物富含钾",
        "llm_config": {"base_url": "http://unused.invalid", "api_key": "secret-key", "model": "x"},
    })
    assert resp.status_code == 502
    assert "secret-key" not in resp.text


def test_chat_endpoint_logs_the_real_llm_error_server_side(monkeypatch, caplog):
    client = TestClient(main.app)

    class ExplodingLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        def complete_json(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

        def complete_text(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(main, "LLMClient", ExplodingLLMClient)
    with caplog.at_level(logging.ERROR, logger="main"):
        resp = client.post("/api/chat", json={
            "session_id": "s3", "message": "哪些食物富含钾",
            "llm_config": {"base_url": "http://unused.invalid", "api_key": "secret-key", "model": "x"},
        })

    assert resp.status_code == 502
    assert "secret-key" not in resp.text
    # The client never sees the real cause, but the server log must have it.
    assert "ConnectError" in caplog.text
    assert "boom" in caplog.text


def test_chat_endpoint_logs_provider_status_and_body_on_http_error(monkeypatch, caplog):
    client = TestClient(main.app)

    def raise_status_error(*args, **kwargs):
        request = httpx.Request("POST", "http://unused.invalid/chat/completions")
        response = httpx.Response(401, text='{"error":"invalid api key for model x"}', request=request)
        raise httpx.HTTPStatusError("401 Unauthorized", request=request, response=response)

    class ExplodingLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        def complete_json(self, *args, **kwargs):
            raise_status_error()

        def complete_text(self, *args, **kwargs):
            raise_status_error()

    monkeypatch.setattr(main, "LLMClient", ExplodingLLMClient)
    with caplog.at_level(logging.ERROR, logger="main"):
        resp = client.post("/api/chat", json={
            "session_id": "s4", "message": "哪些食物富含钾",
            "llm_config": {"base_url": "http://unused.invalid", "api_key": "secret-key", "model": "x"},
        })

    assert resp.status_code == 502
    assert "secret-key" not in resp.text
    assert "401" in caplog.text
    assert "invalid api key for model x" in caplog.text
