import pytest

from app.semantic_parser import parse_semantics, ParseError
from app.schemas import ChatMessage
from tests.fakes import FakeLLMClient


def test_parse_semantics_returns_tags_from_llm():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "lifestyle_education",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {},
    })
    tags = parse_semantics("哪些食物富含钾", [], llm)
    assert tags.sub_type == "lifestyle_education"


def test_parse_semantics_raises_parse_error_on_bad_llm_output():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "garbage"})
    with pytest.raises(ParseError) as exc_info:
        parse_semantics("随便说点什么", [], llm)
    assert exc_info.value.handoff_reason == "parse_error"


def test_parse_semantics_includes_history_in_prompt():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "drug_contraindication",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"coreference_resolved_query": "氯雷他定"},
    })
    history = [ChatMessage(role="user", content="吃了抗过敏药还能喝酒吗"),
               ChatMessage(role="ai", content="您方便说下具体是哪种抗过敏药吗？")]
    tags = parse_semantics("氯雷他定", history, llm)
    assert tags.extracted_entities.coreference_resolved_query == "氯雷他定"
