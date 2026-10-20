import httpx
import pytest
from pydantic import BaseModel

from app.llm_client import LLMClient, LLMParseError


class _Tiny(BaseModel):
    a: int


def _client(handler):
    return LLMClient(base_url="https://fake.test/v1", api_key="k", model="m",
                      transport=httpx.MockTransport(handler))


def test_complete_text_returns_message_content_and_sends_auth_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好"}}]})

    client = _client(handler)
    assert client.complete_text("sys", "user") == "你好"
    assert captured["authorization"] == "Bearer k"
    assert captured["url"] == "https://fake.test/v1/chat/completions"


def test_complete_json_strips_markdown_code_fences():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]})

    client = _client(handler)
    result = client.complete_json("sys", "user", _Tiny)
    assert result.a == 1


def test_complete_json_raises_llm_parse_error_on_non_json_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "这不是JSON，抱歉"}}]})

    client = _client(handler)
    with pytest.raises(LLMParseError):
        client.complete_json("sys", "user", _Tiny)


def test_complete_text_raises_on_http_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    client = _client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.complete_text("sys", "user")


def test_embed_posts_input_and_returns_vectors():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})

    client = _client(handler)
    result = client.embed(["foo", "bar"], model="text-embedding-3-small")
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "https://fake.test/v1/embeddings"


def test_embed_raises_http_status_error_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = _client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.embed(["foo"], model="text-embedding-3-small")
