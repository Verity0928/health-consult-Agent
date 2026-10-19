from app.generator import generate_answer, generate_ask_once
from app.schemas import SemanticTags, KBEntry, ExtractedEntities
from tests.fakes import FakeLLMClient


def test_generate_answer_returns_llm_text():
    llm = FakeLLMClient()
    llm.queue_text("含钾比较丰富的有香蕉、橙子...")
    entry = KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                     keywords=["钾"], answer_body="香蕉橙子菠菜富含钾",
                     source_note="演示数据")
    tags = SemanticTags(route_scope="in_scope", sub_type="lifestyle_education",
                         population_status="unknown", extracted_entities=ExtractedEntities())
    reply = generate_answer(tags, entry, llm)
    assert reply == "含钾比较丰富的有香蕉、橙子..."


def test_generate_answer_includes_feedback_in_prompt(monkeypatch):
    captured = {}
    llm = FakeLLMClient()
    llm.queue_text("修正后的回答")
    original_complete_text = llm.complete_text

    def spy(system_prompt, user_prompt):
        captured["user_prompt"] = user_prompt
        return original_complete_text(system_prompt, user_prompt)

    llm.complete_text = spy
    entry = KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                     keywords=["钾"], answer_body="x", source_note="演示数据")
    tags = SemanticTags(route_scope="in_scope", sub_type="lifestyle_education",
                         population_status="unknown", extracted_entities=ExtractedEntities())
    generate_answer(tags, entry, llm, feedback=["回答超出了条目范围"])
    assert "回答超出了条目范围" in captured["user_prompt"]


def test_generate_ask_once_returns_llm_text():
    llm = FakeLLMClient()
    llm.queue_text("您方便说下具体是哪种抗过敏药吗？")
    tags = SemanticTags(route_scope="in_scope", sub_type="drug_contraindication",
                         population_status="unknown", extracted_entities=ExtractedEntities())
    reply = generate_ask_once(tags, ["drug_name", "patient_identity"], 1, "醉酒后吃抗过敏药会有什么影响", llm)
    assert reply == "您方便说下具体是哪种抗过敏药吗？"
