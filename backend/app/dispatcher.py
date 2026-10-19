from app.schemas import DispatchResult, RetrievalResult, RouteDecision, SemanticTags
from app.session_state import SessionState

POPULATION_CONFIRMATION_SUB_TYPES = ("drug_contraindication", "drug_usage_factual")


def decide_route(tags: SemanticTags, retrieval: RetrievalResult, session: SessionState) -> DispatchResult:
    if session.topic_turns > 2:
        return DispatchResult(route_decision=RouteDecision.HANDOFF, handoff_reason="topic_turns_exceeded")

    if session.ask_round >= 2:
        return DispatchResult(route_decision=RouteDecision.HANDOFF, handoff_reason="escalate_after_ask")

    if tags.sub_type == "drug_efficacy_evaluation":
        return DispatchResult(route_decision=RouteDecision.HANDOFF, handoff_reason="drug_efficacy_evaluation")

    if retrieval.hit_status == "miss":
        return DispatchResult(route_decision=RouteDecision.HANDOFF, handoff_reason="hit_status_miss")

    if retrieval.hit_status == "partial":
        if session.ask_round == 0:
            return DispatchResult(route_decision=RouteDecision.ASK_ONCE, ask_missing_fact_type=["clarify_query"])
        return DispatchResult(route_decision=RouteDecision.HANDOFF, handoff_reason="hit_status_partial")

    # retrieval.hit_status == "hit"
    if tags.sub_type in POPULATION_CONFIRMATION_SUB_TYPES and tags.population_status == "unknown":
        missing = ["patient_identity"]
        if tags.extracted_entities.drug_name_normalized is None:
            missing.append("drug_name")
        return DispatchResult(route_decision=RouteDecision.ASK_ONCE, ask_missing_fact_type=missing)

    return DispatchResult(route_decision=RouteDecision.ANSWER)
