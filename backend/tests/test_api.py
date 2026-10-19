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
