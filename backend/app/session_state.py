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


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def save(self, session: SessionState) -> None:
        self._sessions[session.session_id] = session


def update_topic_counters(
    session: SessionState,
    sub_type: Optional[str],
    core_entity: Optional[str],
    is_ask_once: bool,
) -> None:
    topic_switched = (
        sub_type is not None
        and (sub_type != session.current_sub_type or core_entity != session.current_core_entity)
    )
    if topic_switched:
        session.topic_turns = 0
        session.ask_round = 0
        session.current_sub_type = sub_type
        session.current_core_entity = core_entity
    else:
        session.topic_turns += 1
        if is_ask_once:
            session.ask_round += 1
