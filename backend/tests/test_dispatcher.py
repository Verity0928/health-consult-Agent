from app.dispatcher import decide_route
from app.schemas import SemanticTags, RetrievalResult, RouteDecision, ExtractedEntities
from app.session_state import SessionState


def _tags(**kw):
    defaults = dict(route_scope="in_scope", sub_type="lifestyle_education",
                     population_status="unknown", extracted_entities=ExtractedEntities())
    defaults.update(kw)
    return SemanticTags(**defaults)


def test_handoff_when_topic_turns_exceeded():
    session = SessionState(session_id="x", topic_turns=3)
    result = decide_route(_tags(), RetrievalResult(hit_status="hit"), session)
    assert result.route_decision == RouteDecision.HANDOFF
    assert result.handoff_reason == "topic_turns_exceeded"


def test_handoff_on_drug_efficacy_evaluation():
    session = SessionState(session_id="x")
    result = decide_route(_tags(sub_type="drug_efficacy_evaluation"), RetrievalResult(hit_status="hit"), session)
    assert result.route_decision == RouteDecision.HANDOFF
    assert result.handoff_reason == "drug_efficacy_evaluation"


def test_answer_when_hit_and_non_drug_subtype_population_unknown():
    session = SessionState(session_id="x")
    result = decide_route(_tags(sub_type="lifestyle_education", population_status="unknown"),
                           RetrievalResult(hit_status="hit"), session)
    assert result.route_decision == RouteDecision.ANSWER


def test_ask_once_when_hit_drug_subtype_population_unknown():
    session = SessionState(session_id="x")
    result = decide_route(_tags(sub_type="drug_contraindication", population_status="unknown"),
                           RetrievalResult(hit_status="hit"), session)
    assert result.route_decision == RouteDecision.ASK_ONCE
    assert "patient_identity" in result.ask_missing_fact_type


def test_handoff_when_miss():
    session = SessionState(session_id="x")
    result = decide_route(_tags(), RetrievalResult(hit_status="miss"), session)
    assert result.route_decision == RouteDecision.HANDOFF
    assert result.handoff_reason == "hit_status_miss"


def test_handoff_when_partial_and_already_asked_once():
    session = SessionState(session_id="x", ask_round=1)
    result = decide_route(_tags(), RetrievalResult(hit_status="partial"), session)
    assert result.route_decision == RouteDecision.HANDOFF
    assert result.handoff_reason == "hit_status_partial"
