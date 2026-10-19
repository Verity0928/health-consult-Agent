from typing import Optional

from pydantic import BaseModel

from app.schemas import ChatMessage


class SessionState(BaseModel):
    session_id: str
    history: list[ChatMessage] = []
    topic_turns: int = 0
    ask_round: int = 0
    current_sub_type: Optional[str] = None
    current_core_entity: Optional[str] = None
    handoff_source: Optional[str] = None
    closed: bool = False
    handed_off: bool = False
    awaiting_closing_response: bool = False
    awaiting_fact_answer: bool = False
    topic_query: Optional[str] = None


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def save(self, session: SessionState) -> None:
        self._sessions[session.session_id] = session


def is_topic_switch(session: SessionState, sub_type: Optional[str], core_entity: Optional[str]) -> bool:
    return sub_type is not None and (
        sub_type != session.current_sub_type or core_entity != session.current_core_entity
    )


def update_topic_counters(
    session: SessionState,
    sub_type: Optional[str],
    core_entity: Optional[str],
) -> None:
    """Call exactly once per turn, before dispatch, so decide_route reads
    up-to-date counters. ask_round is bumped separately by increment_ask_round
    only when the dispatcher actually issues another ASK_ONCE."""
    if is_topic_switch(session, sub_type, core_entity):
        # The message that starts a topic is itself the first message under
        # it (spec: topic_turns counts every patient message on the topic).
        session.topic_turns = 1
        session.ask_round = 0
        session.current_sub_type = sub_type
        session.current_core_entity = core_entity
    else:
        session.topic_turns += 1


def increment_ask_round(session: SessionState) -> None:
    session.ask_round += 1
