from app.pipeline import run_turn
from app.session_state import SessionState
from app.schemas import KBEntry, ChatMessage, RetrievalResult
from app.closing_probe import CLOSING_PROBE_POOL, CLOSING_FAREWELL_TEXT
from tests.fakes import FakeLLMClient


def _kb():
    # single keyword per entry so fixture queries score a clean 1.0 (hit), not a partial match
    return [
        KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                keywords=["钾"], answer_body="香蕉橙子富含钾",
                source_note="演示数据"),
        KBEntry(id="b", sub_type="lifestyle_education", question_topic="血糖监测",
                keywords=["血糖", "监测"], answer_body="血糖可以在家用血糖仪监测",
                source_note="演示数据"),
    ]


def test_red_flag_short_circuits_before_any_llm_call():
    llm = FakeLLMClient()  # no queued responses at all
    session = SessionState(session_id="x")
    result = run_turn(session, "我现在呼吸困难", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "red_flag"


def test_red_flag_mid_conversation_still_short_circuits():
    llm = FakeLLMClient()
    session = SessionState(session_id="x", topic_turns=1)
    session.history = [ChatMessage(role="user", content="哪些食物富含钾")]
    result = run_turn(session, "我现在意识不清了", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "red_flag"


def test_happy_path_answer_with_passing_self_check():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="x")
    result = run_turn(session, "哪些食物富含钾", llm, _kb())
    assert result.status == "answered"
    assert result.debug.retry_count == 0
    assert result.debug.route_decision == "ANSWER"


def test_self_check_fails_twice_then_handoff():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("第一次回答")
    llm.queue_json({"compliance_pass": True, "grounding_pass": False,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": False, "violations": ["编造了条目外的数值"]})
    llm.queue_text("第二次回答")
    llm.queue_json({"compliance_pass": True, "grounding_pass": False,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": False, "violations": ["仍然编造了数值"]})
    session = SessionState(session_id="x")
    result = run_turn(session, "哪些食物富含钾", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "self_check_failed"
    assert result.debug.retry_count == 1


def test_parse_error_from_semantic_parser_becomes_handoff():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "not_valid"})
    session = SessionState(session_id="x")
    result = run_turn(session, "随便说点什么", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "parse_error"


def test_ask_once_answer_revealing_special_population_forces_handoff():
    llm = FakeLLMClient()
    # Turn 1: ASK_ONCE because population_status unknown on a drug sub_type
    llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {"drug_name_normalized": "氯雷他定"}})
    kb = [KBEntry(id="d", sub_type="drug_contraindication", question_topic="氯雷他定",
                   keywords=["氯雷他定"], answer_body="x", caution_population="孕妇慎用",
                   source_note="演示数据")]
    session = SessionState(session_id="x")
    import app.retrieval as retrieval_mod
    orig_search = retrieval_mod.search_knowledge_base
    # force a hit so dispatcher reaches the population-unknown ASK_ONCE branch
    retrieval_mod.search_knowledge_base = lambda sub_type, query, entries: RetrievalResult(
        hit_status="hit", matched_entry=entries[0])
    try:
        llm.queue_text("您方便说下是否孕期吗？")
        run_turn(session, "吃氯雷他定会有什么影响", llm, kb)
        # Turn 2: answer reveals special population
        llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                         "population_status": "identified_special",
                         "special_population_flags": ["pregnant"],
                         "extracted_entities": {"drug_name_normalized": "氯雷他定"}})
        result = run_turn(session, "我现在怀孕了", llm, kb)
        assert result.status == "handoff"
        assert result.debug.handoff_reason == "special_population"
    finally:
        retrieval_mod.search_knowledge_base = orig_search


def test_answered_reply_appends_closing_probe_and_sets_awaiting_flag():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="x")
    result = run_turn(session, "哪些食物富含钾", llm, _kb())
    assert any(p in result.reply for p in CLOSING_PROBE_POOL)
    assert session.awaiting_closing_response is True


def test_explicit_decline_after_closing_probe_closes_session_without_llm_call():
    llm = FakeLLMClient()  # nothing queued — must not be called
    session = SessionState(session_id="x", awaiting_closing_response=True)
    result = run_turn(session, "没有了，谢谢", llm, _kb())
    assert result.status == "closed"
    assert result.reply == CLOSING_FAREWELL_TEXT
    assert session.closed is True
    assert session.awaiting_closing_response is False


def test_new_question_after_closing_probe_flows_through_normal_pipeline():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("血糖可以在家用血糖仪监测。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="x", awaiting_closing_response=True)
    result = run_turn(session, "血糖怎么监测", llm, _kb())
    assert result.status == "answered"
    assert session.awaiting_closing_response is True  # re-armed by the new ANSWER
