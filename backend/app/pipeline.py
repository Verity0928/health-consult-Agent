import app.retrieval as retrieval
from app.dispatcher import decide_route
from app.generator import generate_answer, generate_ask_once
from app.llm_client import LLMClientProtocol
from app.safety_guard import check_l0, check_l1
from app.schemas import ChatMessage, KBEntry, PipelineDebugInfo, PipelineResult, RetrievalResult
from app.self_check import run_self_check
from app.semantic_parser import ParseError, parse_semantics
from app.session_state import SessionState, update_topic_counters

HANDOFF_REPLY_TEXT = "您描述的情况需要医生进一步介入，已为您转接人工，请稍候。"


def _handoff(session: SessionState, reason: str, debug: PipelineDebugInfo, message: str) -> PipelineResult:
    debug.handoff_reason = reason
    session.history.append(ChatMessage(role="user", content=message))
    session.history.append(ChatMessage(role="ai", content=HANDOFF_REPLY_TEXT))
    return PipelineResult(reply=HANDOFF_REPLY_TEXT, status="handoff", debug=debug)


def run_turn(
    session: SessionState,
    message: str,
    llm: LLMClientProtocol,
    kb_entries: list[KBEntry],
) -> PipelineResult:
    if check_l0(message):
        return _handoff(session, "red_flag", PipelineDebugInfo(), message)

    try:
        tags = parse_semantics(message, session.history, llm)
    except ParseError:
        return _handoff(session, "parse_error", PipelineDebugInfo(), message)

    l1_reason = check_l1(tags)
    if l1_reason is not None:
        debug = PipelineDebugInfo(
            route_scope=tags.route_scope,
            sub_type=tags.sub_type,
            population_status=tags.population_status,
        )
        return _handoff(session, l1_reason, debug, message)

    core_entity = tags.extracted_entities.coreference_resolved_query or tags.extracted_entities.drug_name_normalized
    update_topic_counters(session, tags.sub_type, core_entity, is_ask_once=False)

    if tags.sub_type is not None:
        retrieval_result = retrieval.search_knowledge_base(tags.sub_type, message, kb_entries)
    else:
        retrieval_result = RetrievalResult(hit_status="miss")

    dispatch = decide_route(tags, retrieval_result, session)
    debug = PipelineDebugInfo(
        route_scope=tags.route_scope,
        sub_type=tags.sub_type,
        population_status=tags.population_status,
        hit_status=retrieval_result.hit_status,
        route_decision=dispatch.route_decision.value,
    )

    if dispatch.route_decision.value == "HANDOFF":
        return _handoff(session, dispatch.handoff_reason, debug, message)

    if dispatch.route_decision.value == "ASK_ONCE":
        reply = generate_ask_once(tags, dispatch.ask_missing_fact_type, session.ask_round + 1, message, llm)
        update_topic_counters(session, tags.sub_type, core_entity, is_ask_once=True)
        session.history.append(ChatMessage(role="user", content=message))
        session.history.append(ChatMessage(role="ai", content=reply))
        return PipelineResult(reply=reply, status="asked", debug=debug)

    # ANSWER
    reply = generate_answer(tags, retrieval_result.matched_entry, llm)
    check = run_self_check(reply, retrieval_result.matched_entry, tags.sub_type, llm)

    if not check.overall_pass:
        reply = generate_answer(tags, retrieval_result.matched_entry, llm, feedback=check.violations)
        check = run_self_check(reply, retrieval_result.matched_entry, tags.sub_type, llm)
        debug.retry_count = 1
        if not check.overall_pass:
            debug.self_check = check
            return _handoff(session, "self_check_failed", debug, message)

    debug.self_check = check
    session.history.append(ChatMessage(role="user", content=message))
    session.history.append(ChatMessage(role="ai", content=reply))
    return PipelineResult(reply=reply, status="answered", debug=debug)
