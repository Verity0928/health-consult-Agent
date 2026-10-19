import pytest

from app.schemas import SemanticTags
from tests.fakes import FakeLLMClient
from app.llm_client import LLMParseError


def test_fake_llm_client_returns_queued_json_as_schema():
    client = FakeLLMClient()
    client.queue_json({
        "route_scope": "in_scope", "sub_type": "lifestyle_education",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {},
    })
    result = client.complete_json("sys", "user", SemanticTags)
    assert result.route_scope == "in_scope"
    assert isinstance(result, SemanticTags)


def test_fake_llm_client_raises_on_invalid_schema():
    client = FakeLLMClient()
    client.queue_json({"route_scope": "not_a_valid_enum_value"})
    with pytest.raises(LLMParseError):
        client.complete_json("sys", "user", SemanticTags)


def test_fake_llm_client_text_returns_queued_text():
    client = FakeLLMClient()
    client.queue_text("hello")
    assert client.complete_text("sys", "user") == "hello"
