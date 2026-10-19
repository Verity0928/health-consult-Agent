from fastapi import FastAPI

from app.knowledge_base.loader import DEFAULT_KB_DATA_DIR, load_knowledge_base
from app.llm_client import LLMClient
from app.pipeline import run_turn
from app.schemas import ChatTurnRequest, PipelineResult
from app.session_state import SessionStore

app = FastAPI(title="健康咨询 Agent Demo")

_kb_entries = load_knowledge_base(DEFAULT_KB_DATA_DIR)
_session_store = SessionStore()


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=PipelineResult)
def chat(request: ChatTurnRequest) -> PipelineResult:
    session = _session_store.get_or_create(request.session_id)
    llm = LLMClient(
        base_url=request.llm_config.base_url,
        api_key=request.llm_config.api_key,
        model=request.llm_config.model,
    )
    result = run_turn(session, request.message, llm, _kb_entries)
    _session_store.save(session)
    return result
