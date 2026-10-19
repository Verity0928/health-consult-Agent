from app.session_state import SessionStore, SessionState, update_topic_counters


def test_store_creates_new_session_on_first_access():
    store = SessionStore()
    s = store.get_or_create("abc")
    assert s.session_id == "abc"
    assert s.topic_turns == 0


def test_store_returns_same_session_on_second_access():
    store = SessionStore()
    s1 = store.get_or_create("abc")
    s1.topic_turns = 5
    store.save(s1)
    s2 = store.get_or_create("abc")
    assert s2.topic_turns == 5


def test_update_topic_counters_increments_on_same_topic():
    s = SessionState(session_id="x", current_sub_type="lifestyle_education", current_core_entity=None)
    update_topic_counters(s, "lifestyle_education", None, is_ask_once=False)
    assert s.topic_turns == 1
    assert s.ask_round == 0


def test_update_topic_counters_resets_on_topic_switch():
    s = SessionState(session_id="x", current_sub_type="lifestyle_education",
                      current_core_entity=None, topic_turns=3, ask_round=1)
    update_topic_counters(s, "drug_contraindication", "氯雷他定", is_ask_once=False)
    assert s.topic_turns == 0
    assert s.ask_round == 0
    assert s.current_sub_type == "drug_contraindication"


def test_update_topic_counters_increments_ask_round_on_ask_once():
    s = SessionState(session_id="x", current_sub_type="drug_contraindication", current_core_entity="氯雷他定")
    update_topic_counters(s, "drug_contraindication", "氯雷他定", is_ask_once=True)
    assert s.ask_round == 1
