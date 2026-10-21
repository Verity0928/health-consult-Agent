from app.pipeline import run_turn, HANDOFF_REPLY_TEXT
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


def test_run_turn_uses_semantic_retrieval_result_when_embedding_model_configured(monkeypatch):
    import app.pipeline as pipeline_module

    calls = []

    def fake_semantic(sub_type, query, entries, llm, base_url, embedding_model):
        calls.append((sub_type, query, base_url, embedding_model))
        # Return the entry keyword matching would NOT have picked for this
        # query ("b" = blood-sugar monitoring, not "a" = potassium) so the
        # test fails if the keyword path silently ran instead.
        return RetrievalResult(hit_status="hit", matched_entry=entries[1])

    monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", fake_semantic)
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="s1")
    result = run_turn(session, "哪些食物富含钾", llm, _kb(), base_url="https://fake.test/v1", embedding_model="m")
    assert result.status == "answered"
    assert calls == [("lifestyle_education", "哪些食物富含钾", "https://fake.test/v1", "m")]
    assert result.debug.hit_status == "hit"


def test_run_turn_falls_back_to_keyword_retrieval_when_semantic_path_raises(monkeypatch):
    import app.pipeline as pipeline_module
    import httpx

    def fake_semantic(sub_type, query, entries, llm, base_url, embedding_model):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", fake_semantic)
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="s2")
    result = run_turn(session, "哪些食物富含钾", llm, _kb(), base_url="https://fake.test/v1", embedding_model="m")
    assert result.status == "answered"  # keyword path still finds the "钾" entry and answers normally


def _run_turn_with_semantic_raising(monkeypatch, exc):
    import app.pipeline as pipeline_module

    def fake_semantic(sub_type, query, entries, llm, base_url, embedding_model):
        raise exc

    monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", fake_semantic)
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="s2b")
    return run_turn(session, "哪些食物富含钾", llm, _kb(), base_url="https://fake.test/v1", embedding_model="m")


def test_run_turn_falls_back_when_embeddings_response_has_empty_data_list(monkeypatch):
    # A real provider returning {"data": []} makes LLMClient.embed do
    # `[d["embedding"] for d in response.json()["data"]][0]` -> IndexError.
    result = _run_turn_with_semantic_raising(monkeypatch, IndexError("list index out of range"))
    assert result.status == "answered"


def test_run_turn_falls_back_when_embeddings_response_has_null_data(monkeypatch):
    # {"data": null} makes the list comprehension iterate None -> TypeError.
    result = _run_turn_with_semantic_raising(monkeypatch, TypeError("'NoneType' object is not iterable"))
    assert result.status == "answered"


def test_run_turn_falls_back_when_embeddings_response_is_not_json(monkeypatch):
    # A 200 response with a non-JSON body makes response.json() raise
    # json.JSONDecodeError, which is a ValueError subclass.
    result = _run_turn_with_semantic_raising(monkeypatch, ValueError("Expecting value: line 1 column 1 (char 0)"))
    assert result.status == "answered"


def test_run_turn_never_calls_semantic_retrieval_when_embedding_model_is_blank(monkeypatch):
    import app.pipeline as pipeline_module

    called = []

    def fake_semantic(*args, **kwargs):
        called.append(True)
        raise AssertionError("should not be called")

    monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", fake_semantic)
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="s3")
    run_turn(session, "哪些食物富含钾", llm, _kb())  # no base_url/embedding_model passed — defaults
    assert called == []


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


def test_ask_once_answer_without_drug_keywords_still_resolves_to_answer():
    # Regression for: retrieval on the ASK_ONCE follow-up turn must not use
    # only that turn's raw text (which legitimately has zero keyword overlap
    # with the drug entry) — it must anchor back to the topic's original query.
    llm = FakeLLMClient()
    kb = [KBEntry(id="asp", sub_type="drug_contraindication", question_topic="阿司匹林和布洛芬",
                   keywords=["阿司匹林", "布洛芬"], answer_body="一起吃可能增加胃肠道出血风险",
                   caution_population="有消化性溃疡病史者风险更高", source_note="演示数据")]
    session = SessionState(session_id="x")

    llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("您方便说下是您自己在吃吗？")
    result1 = run_turn(session, "阿司匹林和布洛芬能一起吃吗", llm, kb)
    assert result1.status == "asked"

    llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                     "population_status": "identified_general", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("一起吃可能增加胃肠道出血风险，有消化道溃疡的话更要小心。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    result2 = run_turn(session, "我自己吃的，没有其他情况", llm, kb)
    assert result2.status == "answered"


def test_distinct_lifestyle_topics_do_not_accumulate_topic_turns():
    # Regression for: topic-switch detection must distinguish genuinely
    # different subjects under the same sub_type, not just key off free-text
    # coreference resolution (which stays null for non-drug topics).
    llm = FakeLLMClient()
    session = SessionState(session_id="x")
    topics = [
        ("脂肪肝有啥症状", "脂肪肝"),
        ("最近总是便秘怎么办", "便秘"),
        ("久坐腰疼怎么预防", "腰疼"),
    ]
    for message, symptom in topics:
        llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                         "population_status": "unknown", "special_population_flags": [],
                         "extracted_entities": {"symptom_or_condition_raw": symptom}})
        run_turn(session, message, llm, [])  # empty KB: every turn misses/hands off, counters still tracked
    assert session.topic_turns == 1  # each message was its own new topic


def test_hard_handoff_reason_locks_session_for_subsequent_turns():
    llm = FakeLLMClient()
    session = SessionState(session_id="x")
    result1 = run_turn(session, "我想自杀", llm, _kb())
    assert result1.status == "handoff"
    assert session.handed_off is True

    result2 = run_turn(session, "胃镜检查要不要空腹", llm, _kb())
    assert result2.status == "handoff"
    assert result2.reply == HANDOFF_REPLY_TEXT


def test_soft_handoff_reason_does_not_lock_session():
    llm = FakeLLMClient()
    session = SessionState(session_id="x")
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    result1 = run_turn(session, "一个知识库里完全没有的问题", llm, [])  # miss -> handoff
    assert result1.status == "handoff"
    assert session.handed_off is False

    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    result2 = run_turn(session, "哪些食物富含钾", llm, _kb())
    assert result2.status == "answered"


def test_closed_session_returns_fixed_farewell_without_calling_llm():
    llm = FakeLLMClient()  # nothing queued — must not be called
    session = SessionState(session_id="x", closed=True)
    result = run_turn(session, "还有个问题", llm, _kb())
    assert result.status == "closed"
    assert result.reply == CLOSING_FAREWELL_TEXT


def test_run_turn_appends_the_normalized_drug_name_to_the_retrieval_query(monkeypatch):
    import app.retrieval as retrieval_mod
    captured = {}
    orig_search = retrieval_mod.search_knowledge_base

    def capturing_search(sub_type, query, entries):
        captured["query"] = query
        return orig_search(sub_type, query, entries)

    retrieval_mod.search_knowledge_base = capturing_search
    try:
        llm = FakeLLMClient()
        llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                         "population_status": "identified_general", "special_population_flags": [],
                         "extracted_entities": {"drug_name_raw": "芬必得"}})
        llm.queue_text("芬必得和阿司匹林一起吃要小心胃肠道刺激。")
        llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                         "disclaimer_pass": True, "format_pass": True,
                         "overall_pass": True, "violations": []})
        kb = [KBEntry(id="a", sub_type="drug_contraindication", question_topic="阿司匹林和布洛芬能一起吃吗",
                      keywords=["阿司匹林", "布洛芬"], answer_body="x", source_note="演示数据")]
        session = SessionState(session_id="x")
        run_turn(session, "芬必得能和阿司匹林一起吃吗", llm, kb)
        assert "布洛芬" in captured["query"]
    finally:
        retrieval_mod.search_knowledge_base = orig_search


def test_run_turn_still_answers_when_patient_already_used_the_canonical_drug_name():
    # drug_name_raw == the canonical name itself isn't a key in
    # DRUG_ALIASES (only brand/colloquial names are keys), so
    # normalize_drug_name returns None here and drug_name_normalized
    # stays whatever the LLM's own extraction produced -- typically the
    # same canonical text, trivially. Appending it to retrieval_query is
    # then a harmless duplicate; this proves it doesn't break matching.
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                     "population_status": "identified_general", "special_population_flags": [],
                     "extracted_entities": {"drug_name_raw": "布洛芬", "drug_name_normalized": "布洛芬"}})
    llm.queue_text("布洛芬和阿司匹林一起吃要小心胃肠道刺激。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    kb = [KBEntry(id="a", sub_type="drug_contraindication", question_topic="阿司匹林和布洛芬能一起吃吗",
                  keywords=["阿司匹林", "布洛芬"], answer_body="x", source_note="演示数据")]
    session = SessionState(session_id="x")
    result = run_turn(session, "布洛芬和阿司匹林一起吃可以吗", llm, kb)
    assert result.status == "answered"
    assert result.debug.hit_status == "hit"


def test_core_entity_prefers_normalized_symptom_over_raw():
    from app.pipeline import _core_entity
    from app.schemas import SemanticTags, ExtractedEntities
    tags = SemanticTags(
        route_scope="in_scope", sub_type="department_triage", population_status="unknown",
        extracted_entities=ExtractedEntities(
            symptom_or_condition_raw="头疼", symptom_or_condition_normalized="头痛",
        ),
    )
    assert _core_entity(tags) == "头痛"


def test_core_entity_still_prefers_drug_name_over_symptom():
    from app.pipeline import _core_entity
    from app.schemas import SemanticTags, ExtractedEntities
    tags = SemanticTags(
        route_scope="in_scope", sub_type="drug_contraindication", population_status="unknown",
        extracted_entities=ExtractedEntities(
            drug_name_normalized="布洛芬",
            symptom_or_condition_raw="头疼", symptom_or_condition_normalized="头痛",
        ),
    )
    assert _core_entity(tags) == "布洛芬"


def test_different_phrasings_of_the_same_symptom_do_not_reset_topic_turns():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "department_triage",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {"symptom_or_condition_raw": "头疼"}})
    llm.queue_text("反复头痛建议先挂神经内科看看。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    # Keywords on the canonical term "头痛", not the colloquial "头疼" the
    # patient actually typed -- turn 1 only hits because retrieval_query
    # gets "头痛" appended (Task 2's second change below); turn 2 hits
    # because "头痛" already appears literally in what the patient typed.
    kb = [KBEntry(id="a", sub_type="department_triage", question_topic="头痛反复发作挂什么科",
                  keywords=["头痛"], answer_body="x", source_note="演示数据")]
    session = SessionState(session_id="x")
    result1 = run_turn(session, "我头疼，该挂什么科", llm, kb)
    assert result1.status == "answered"
    assert session.topic_turns == 1

    llm.queue_json({"route_scope": "in_scope", "sub_type": "department_triage",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {"symptom_or_condition_raw": "头痛"}})
    llm.queue_text("如果吃了止痛药还是没缓解，建议尽快就医。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    result2 = run_turn(session, "吃了止痛药头痛还是没好", llm, kb)
    assert result2.status == "answered"
    # "头疼" then "头痛" are the same symptom once normalized -> same
    # topic, so this is turn 2 on the same topic, not a reset to 1.
    assert session.topic_turns == 2
