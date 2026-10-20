import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.knowledge_base.loader import DEFAULT_KB_DATA_DIR, load_knowledge_base
from app.llm_client import LLMClient
from app.pipeline import run_turn
from app.schemas import ChatTurnRequest, LLMConfig, PipelineResult
from app.session_state import SessionStore

logger = logging.getLogger(__name__)

app = FastAPI(title="健康咨询 Agent Demo")

_kb_entries = load_knowledge_base(DEFAULT_KB_DATA_DIR)
_session_store = SessionStore()


def _log_llm_failure(context: str, exc: Exception) -> None:
    # The real cause (status code, provider's own error body) only ever
    # goes to the server log, never to the client — the client gets a
    # fixed, actionable message instead (never the raw exception text,
    # which can carry request details).
    if isinstance(exc, httpx.HTTPStatusError):
        logger.error("%s: status=%s body=%s", context, exc.response.status_code, exc.response.text[:500])
    else:
        logger.error("%s: %r", context, exc)


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
        result = run_turn(
            session, request.message, llm, _kb_entries,
            base_url=request.llm_config.base_url, embedding_model=request.llm_config.embedding_model,
        )
    except (httpx.HTTPError, KeyError) as exc:
        _log_llm_failure(f"LLM call failed for session {request.session_id}", exc)
        raise HTTPException(
            status_code=502,
            detail="LLM 调用失败，请检查 API 配置（base_url / api_key / model）是否正确",
        ) from exc
    _session_store.save(session)
    return result


@app.post("/api/test-connection")
def test_connection(llm_config: LLMConfig) -> dict:
    # A single, minimal completion call — never touches session state or
    # the chat pipeline (no semantic parsing, retrieval, or self-check) —
    # this only needs to prove base_url/api_key/model actually work.
    llm = LLMClient(base_url=llm_config.base_url, api_key=llm_config.api_key, model=llm_config.model)
    try:
        llm.complete_text("你是连接测试助手。", "请只回复“ok”两个字，不要加任何其他内容。")
    except (httpx.HTTPError, KeyError) as exc:
        _log_llm_failure("Test connection failed", exc)
        raise HTTPException(
            status_code=502,
            detail="LLM 调用失败，请检查 API 配置（base_url / api_key / model）是否正确",
        ) from exc
    return {"status": "ok"}


# Serve the built frontend, if it exists. Guarded so a machine/CI run that
# hasn't built the frontend yet doesn't break backend import (and therefore
# every backend test that imports this module).
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
