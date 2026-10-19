import httpx
from fastapi import FastAPI, HTTPException

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
    try:
        result = run_turn(session, request.message, llm, _kb_entries)
    except (httpx.HTTPError, KeyError) as exc:
        # Transport failure or a response shape we didn't expect (e.g. a
        # wrong base_url/model, or a provider that doesn't speak the
        # OpenAI-compatible schema). Never echo the exception text back —
        # it can carry request details — just a fixed, actionable message.
        raise HTTPException(
            status_code=502,
            detail="LLM 调用失败，请检查 API 配置（base_url / api_key / model）是否正确",
        ) from exc
    _session_store.save(session)
    return result
