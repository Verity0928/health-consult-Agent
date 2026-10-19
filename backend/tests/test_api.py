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
