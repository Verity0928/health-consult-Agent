import logging
from typing import Optional

import httpx

import app.retrieval as retrieval
from app.closing_probe import CLOSING_FAREWELL_TEXT, is_explicit_decline, pick_closing_probe
from app.dispatcher import decide_route
from app.generator import generate_answer, generate_ask_once
from app.llm_client import LLMClientProtocol, LLMParseError
from app.safety_guard import check_l0, check_l1
from app.schemas import ChatMessage, KBEntry, PipelineDebugInfo, PipelineResult, RetrievalResult, SemanticTags
from app.self_check import run_self_check
from app.semantic_parser import ParseError, parse_semantics
from app.semantic_retrieval import search_knowledge_base_semantic
from app.session_state import SessionState, increment_ask_round, update_topic_counters

logger = logging.getLogger(__name__)

HANDOFF_REPLY_TEXT = "您描述的情况需要医生进一步介入，已为您转接人工，请稍候。"

# Reasons that represent a genuine safety escalation: the AI should not
# resume answering anything else in this session afterwards (spec treats
# HANDOFF as leaving the AI's scope). Routine knowledge-gap handoffs
# (hit_status miss/partial, topic_turns exceeded, self-check failure, ...)
# are "soft" — only that one question gets escalated; the patient can keep
# talking to the AI about other things.
HARD_HANDOFF_REASONS = frozenset({"red_flag", "clinical_prescription_intent", "special_population"})


def _handoff(session: SessionState, reason: str, debug: PipelineDebugInfo, message: str) -> PipelineResult:
    debug.handoff_reason = reason
    session.history.append(ChatMessage(role="user", content=message))
    session.history.append(ChatMessage(role="ai", content=HANDOFF_REPLY_TEXT))
    if reason in HARD_HANDOFF_REASONS:
        session.handed_off = True
    return PipelineResult(reply=HANDOFF_REPLY_TEXT, status="handoff", debug=debug)


def _core_entity(tags: SemanticTags) -> Optional[str]:
    return (
        tags.extracted_entities.drug_name_normalized
        or tags.extracted_entities.symptom_or_condition_normalized
        or tags.extracted_entities.symptom_or_condition_raw
        or tags.extracted_entities.exam_item_raw
    )


def run_turn(
    session: SessionState,
    message: str,
    llm: LLMClientProtocol,
    kb_entries: list[KBEntry],
    base_url: str = "",
    embedding_model: Optional[str] = None,
) -> PipelineResult:
    if session.closed:
        return PipelineResult(reply=CLOSING_FAREWELL_TEXT, status="closed", debug=PipelineDebugInfo())
    if session.handed_off:
        return PipelineResult(reply=HANDOFF_REPLY_TEXT, status="handoff", debug=PipelineDebugInfo())

    if check_l0(message):
        return _handoff(session, "red_flag", PipelineDebugInfo(), message)

    if session.awaiting_closing_response:
        session.awaiting_closing_response = False
        if is_explicit_decline(message):
            session.closed = True
            return PipelineResult(reply=CLOSING_FAREWELL_TEXT, status="closed", debug=PipelineDebugInfo())

    is_fact_followup = session.awaiting_fact_answer
    session.awaiting_fact_answer = False

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

    core_entity = _core_entity(tags)
    update_topic_counters(session, tags.sub_type, core_entity)

    # A fact-only reply to our own ASK_ONCE question (e.g. "我自己吃的")
    # often has zero keyword overlap with the entry the original question
    # pointed at. Anchor retrieval to the question that opened the topic,
    # not this turn's raw text, so the second pass can actually resolve.
    is_fresh_topic = not (is_fact_followup and session.topic_query is not None)
    retrieval_query = message if is_fresh_topic else f"{session.topic_query} {message}"

    if tags.extracted_entities.drug_name_normalized:
        retrieval_query = f"{retrieval_query} {tags.extracted_entities.drug_name_normalized}"
    if tags.extracted_entities.symptom_or_condition_normalized:
        retrieval_query = f"{retrieval_query} {tags.extracted_entities.symptom_or_condition_normalized}"

    # Save the *augmented* query as the topic anchor, not the raw message —
    # otherwise a canonical drug/symptom name recognized this turn (e.g. a
    # brand name normalized to its generic name) is lost by the time a
    # later ASK_ONCE follow-up turn re-anchors retrieval to it.
    if is_fresh_topic:
        session.topic_query = retrieval_query

    if tags.sub_type is not None:
        if embedding_model:
            try:
                retrieval_result = search_knowledge_base_semantic(
                    tags.sub_type, retrieval_query, kb_entries, llm, base_url, embedding_model
                )
            # httpx.HTTPError: transport failure / non-2xx status.
            # KeyError: response is valid JSON but missing "data".
            # IndexError: "data" is an empty list.
            # TypeError: "data" is null (iterating None).
            # ValueError: response body isn't JSON at all (json.JSONDecodeError
            # is a ValueError subclass) — covers every shape a misbehaving
            # "OpenAI-compatible" /embeddings endpoint has been seen to return.
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                logger.warning(
                    "Semantic retrieval failed for session %s, falling back to keyword matching: %r",
                    session.session_id, exc,
                )
                retrieval_result = retrieval.search_knowledge_base(tags.sub_type, retrieval_query, kb_entries)
        else:
            retrieval_result = retrieval.search_knowledge_base(tags.sub_type, retrieval_query, kb_entries)
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
        increment_ask_round(session)
        session.awaiting_fact_answer = True
        session.history.append(ChatMessage(role="user", content=message))
        session.history.append(ChatMessage(role="ai", content=reply))
        return PipelineResult(reply=reply, status="asked", debug=debug)

    # ANSWER
    try:
        reply = generate_answer(tags, retrieval_result.matched_entry, llm, user_query=message)
        check = run_self_check(reply, retrieval_result.matched_entry, tags.sub_type, message, llm)

        if not check.overall_pass:
            reply = generate_answer(
                tags, retrieval_result.matched_entry, llm, user_query=message, feedback=check.violations
            )
            check = run_self_check(reply, retrieval_result.matched_entry, tags.sub_type, message, llm)
            debug.retry_count = 1
            if not check.overall_pass:
                debug.self_check = check
                return _handoff(session, "self_check_failed", debug, message)
    except LLMParseError:
        # The self-check call itself returned malformed JSON — can't trust
        # an unreadable verdict, so treat it the same as a failed check.
        return _handoff(session, "self_check_failed", debug, message)

    debug.self_check = check
    reply = f"{reply}\n\n{pick_closing_probe()}"
    session.awaiting_closing_response = True
    session.history.append(ChatMessage(role="user", content=message))
    session.history.append(ChatMessage(role="ai", content=reply))
    return PipelineResult(reply=reply, status="answered", debug=debug)
