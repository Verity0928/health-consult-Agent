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


def test_parse_semantics_normalizes_a_recognized_drug_brand_name():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "drug_contraindication",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"drug_name_raw": "芬必得", "drug_name_normalized": None},
    })
    tags = parse_semantics("芬必得能和阿司匹林一起吃吗", [], llm)
    assert tags.extracted_entities.drug_name_normalized == "布洛芬"


def test_parse_semantics_keeps_the_llms_guess_for_an_unrecognized_drug_name():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "drug_contraindication",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"drug_name_raw": "某种没听过的药",
                                "drug_name_normalized": "模型自己猜的名字"},
    })
    tags = parse_semantics("某种没听过的药怎么吃", [], llm)
    assert tags.extracted_entities.drug_name_normalized == "模型自己猜的名字"


def test_parse_semantics_normalizes_a_recognized_symptom_phrase():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "department_triage",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"symptom_or_condition_raw": "头疼"},
    })
    tags = parse_semantics("我头疼，挂什么科", [], llm)
    assert tags.extracted_entities.symptom_or_condition_normalized == "头痛"


def test_parse_semantics_leaves_normalized_symptom_none_when_unrecognized():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "department_triage",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"symptom_or_condition_raw": "一种没见过的说法"},
    })
    tags = parse_semantics("一种没见过的说法，挂什么科", [], llm)
    assert tags.extracted_entities.symptom_or_condition_normalized is None
