# Semantic Retrieval Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the brittle exact-keyword-overlap knowledge base matching with embedding-based semantic matching (so "血压高能吃甜的吗" matches the same entry as "高血压能吃蛋糕吗"), while keeping every downstream safety/grounding guarantee identical and never requiring a second API key from the user.

**Architecture:** Add a new semantic retrieval path (`backend/app/semantic_retrieval.py`) that embeds the user's query and the candidate KB entries' `question_topic` text via the same OpenAI-compatible provider the user already configured, scores candidates by cosine similarity, and returns the exact same `RetrievalResult` shape the existing keyword path returns. `pipeline.py`'s single retrieval call site tries semantic first (only when the user filled in an `embedding_model`) and falls back to the existing keyword-overlap `retrieval.search_knowledge_base` on any failure — a missing field, an unsupported `/embeddings` endpoint, a malformed response, or a transport error. `dispatcher.py`, `generator.py`, and `self_check.py` are untouched: they only ever see a `RetrievalResult`, never how it was produced, so the grounding/safety story (self_check's `grounding_pass` checks the answer against `matched_entry.answer_body`, same as today) does not change at all.

**Tech Stack:** Same as the existing backend (Python 3.12, FastAPI, Pydantic v2, httpx, pytest). No new dependency: cosine similarity is implemented in pure Python (corpus is a few dozen entries; no need for numpy/a vector DB).

**Spec:** This plan has no separate spec document — the requirements were worked out in conversation with the product owner (a medical AI PM) after a live demo surfaced that the 42-entry keyword-matched KB was too brittle (`高血压能吃蛋糕吗` → `无糖的` → `handoff_reason: hit_status_partial`, see commit history around 2026-10-20). The agreed decisions, which this plan treats as binding:
- Do **not** add live open-web search — it would contradict this project's own "workflow pipeline, not ReAct" architecture story and break the auditable-grounding guarantee (self_check validates against a known KB entry, not an arbitrary webpage).
- Semantic retrieval reuses the user's own already-configured OpenAI-compatible `base_url`/`api_key` — no second API key, no new external service.
- If the configured provider doesn't support `/embeddings` (very plausible — many "OpenAI-compatible" proxies only implement chat completions), retrieval must fall back to the existing keyword matching silently — the user still gets an answer, never a 502.
- Scope for this pass is **pipeline validation**, not content expansion: prove semantic retrieval works end-to-end against the existing 42-entry KB. Growing the KB's content volume is a separate, later piece of work.
- The Settings modal gets a 4th, optional field ("Embedding Model") with a hint explaining it's optional and what happens if the provider doesn't support it.

## Global Constraints

- No new Python dependency (pure-Python cosine similarity; httpx is already a dependency).
- `LLMConfig.embedding_model` is optional and defaults to `""` on both backend (Pydantic) and frontend (TS) — every existing caller/test that doesn't know about this field keeps working unmodified.
- `run_turn`'s new parameters (`base_url`, `embedding_model`) are trailing, defaulted kwargs — zero changes to the ~30 existing `run_turn(...)` call sites across the test suite.
- The semantic path must never raise an exception that reaches `main.py`'s `/api/chat` handler uncaught when a classic-keyword-equivalent answer is still obtainable — any semantic-path failure degrades to the keyword path, not to a 502.
- Corpus embeddings are cached in-process, keyed by `(base_url, embedding_model)`, never keyed by or containing the API key (matches this project's existing privacy guarantee: the key is forwarded per-request and never retained).
- Thresholds (`SEMANTIC_HIT_THRESHOLD` etc.) are a reasoned starting point calibrated against synthetic test vectors, not a real embeddings provider (none is available to call from this environment without spending the user's own key). Flag this plainly in the module as needing real-world recalibration once exercised against a live provider.

## Review Focus

- A configured provider's `base_url` serves chat completions but returns 404 or an error body for `/embeddings` (common for "OpenAI-compatible" proxies that don't implement the full API surface) — the turn must still complete with a real answer via the keyword fallback, not a 502. (Task 3)
- `embedding_model` left blank (the common case — it's optional) must produce byte-for-byte identical behavior to today: the semantic path must never be attempted, `llm.embed()` must never be called. (Task 3)
- The embeddings response has an unexpected JSON shape (missing `data` key, empty `data` list) — must raise a caught, fallback-triggering error, not an unhandled `KeyError`/`IndexError` that escapes to the client. (Task 1, Task 3)
- The very first request for a given `(base_url, embedding_model)` pair (cold corpus cache) must still return a correct result, not an empty/partial one while "warming up". (Task 2)
- A `sub_type` with zero matching KB entries under the semantic path must return `miss` without ever calling `embed()` on an empty list (some providers reject empty `input` arrays). (Task 2)

---

### Task 1: `LLMConfig.embedding_model` + `LLMClient.embed()`

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/llm_client.py`
- Modify: `backend/tests/fakes.py`
- Test: `backend/tests/test_llm_client_transport.py`
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: `LLMConfig.embedding_model: str = ""` (schemas.py); `LLMClientProtocol.embed(self, texts: list[str], model: str) -> list[list[float]]`; `LLMClient.embed(...)` implementation (POSTs `{base_url}/embeddings` with `{"model": model, "input": texts}`, returns `[d["embedding"] for d in response.json()["data"]]`, raises `httpx.HTTPStatusError` on non-2xx via `response.raise_for_status()`, raises `KeyError` on unexpected shape — same error-handling shape as `complete_text`); `FakeLLMClient.queue_embeddings(vectors: list[list[float]])` and `FakeLLMClient.embed(texts, model) -> list[list[float]]` (pops one queued batch per call, raises `AssertionError` if the queue is empty, same style as `queue_text`/`queue_json`) plus a `FakeLLMClient.embed_calls: list[tuple[list[str], str]]` call log later tasks' tests can assert against (append `(texts, model)` on every call).

- [ ] **Step 1: Write the failing test for `LLMConfig.embedding_model` defaulting**

```python
# backend/tests/test_schemas.py (create if it doesn't exist, else add to it)
from app.schemas import LLMConfig

def test_llm_config_embedding_model_defaults_to_empty_string():
    config = LLMConfig(base_url="https://api.openai.com/v1", api_key="k", model="gpt-4o-mini")
    assert config.embedding_model == ""
```

Check first whether `backend/tests/test_schemas.py` already exists; if so add this test to it instead of creating a new file.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schemas.py -v` (or the file you added it to)
Expected: FAIL — `embedding_model` is not a field on `LLMConfig` (`ValidationError` or `AttributeError`, depending on Pydantic's extra-field handling).

- [ ] **Step 3: Add the field**

In `backend/app/schemas.py`, add `embedding_model: str = ""` to `LLMConfig`.

- [ ] **Step 4: Run test to verify it passes**

Run: same command as Step 2.
Expected: PASS.

- [ ] **Step 5: Write the failing test for `LLMClient.embed()`'s wire format**

```python
# backend/tests/test_llm_client_transport.py — add alongside the existing tests
def test_embed_posts_input_and_returns_vectors():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})

    client = _client(handler)
    result = client.embed(["foo", "bar"], model="text-embedding-3-small")
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "https://fake.test/v1/embeddings"


def test_embed_raises_http_status_error_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = _client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.embed(["foo"], model="text-embedding-3-small")
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_llm_client_transport.py -v`
Expected: FAIL — `LLMClient` has no `embed` method (`AttributeError`).

- [ ] **Step 7: Implement `LLMClient.embed`**

In `backend/app/llm_client.py`: add `embed(self, texts: list[str], model: str) -> list[list[float]]` to `LLMClient`, following `complete_text`'s exact pattern (`httpx.Client(timeout=60, transport=self._transport)`, POST to `f"{self.base_url}/embeddings"`, same `Authorization` header, body `{"model": model, "input": texts}`, `response.raise_for_status()`, return `[d["embedding"] for d in response.json()["data"]]`). Add the matching method signature to `LLMClientProtocol`.

- [ ] **Step 8: Run tests to verify they pass**

Run: same command as Step 6.
Expected: PASS.

- [ ] **Step 9: Extend `FakeLLMClient` with `embed`/`queue_embeddings`**

In `backend/tests/fakes.py`, following the exact style of `queue_text`/`complete_text`: add `self._embed_queue: list[list[list[float]]] = []` and `self.embed_calls: list[tuple[list[str], str]] = []` to `__init__`; add `queue_embeddings(self, vectors: list[list[float]]) -> None` (appends to the queue); add `embed(self, texts: list[str], model: str) -> list[list[float]]` (append `(texts, model)` to `embed_calls`, pop and return the next queued batch, raise `AssertionError("no queued embeddings")` if empty — same shape as `complete_text`'s empty-queue behavior).

- [ ] **Step 10: Write the failing test for the fake**

```python
# backend/tests/test_llm_client.py — add
def test_fake_llm_client_embed_returns_queued_vectors_and_logs_the_call():
    client = FakeLLMClient()
    client.queue_embeddings([[1.0, 0.0], [0.0, 1.0]])
    result = client.embed(["a", "b"], model="m")
    assert result == [[1.0, 0.0], [0.0, 1.0]]
    assert client.embed_calls == [(["a", "b"], "m")]
```

- [ ] **Step 11: Run test to verify it fails, then implement, then verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_llm_client.py -v` before and after Step 9's implementation.
Expected: FAIL (no `embed` method) then PASS.

- [ ] **Step 12: Commit**

```bash
git add backend/app/schemas.py backend/app/llm_client.py backend/tests/fakes.py backend/tests/test_llm_client_transport.py backend/tests/test_llm_client.py backend/tests/test_schemas.py
git commit -m "feat(backend): add embedding_model config field and LLMClient.embed()"
```

---

### Task 2: `semantic_retrieval.py`

**Files:**
- Create: `backend/app/semantic_retrieval.py`
- Test: `backend/tests/test_semantic_retrieval.py`

**Interfaces:**
- Consumes: `LLMClientProtocol.embed` (Task 1); `KBEntry`, `RetrievalResult` (existing, `app/schemas.py`); `FakeLLMClient` (Task 1, for tests).
- Produces: `search_knowledge_base_semantic(sub_type: str, query: str, entries: list[KBEntry], llm: LLMClientProtocol, base_url: str, embedding_model: str) -> RetrievalResult` — same return shape as `retrieval.search_knowledge_base`, so Task 3 can call either interchangeably. Raises whatever `llm.embed()` raises (does not catch — Task 3's call site is responsible for the try/fallback).

- [ ] **Step 1: Write the failing tests for cosine similarity and the empty-candidates case**

```python
# backend/tests/test_semantic_retrieval.py
from app.semantic_retrieval import search_knowledge_base_semantic
from app.schemas import KBEntry
from tests.fakes import FakeLLMClient


def _entry(id_, sub_type, topic):
    return KBEntry(id=id_, sub_type=sub_type, question_topic=topic, answer_body="x", source_note="演示数据")


def test_miss_when_no_entries_for_sub_type_never_calls_embed():
    llm = FakeLLMClient()
    result = search_knowledge_base_semantic("department_triage", "随便问点什么", [], llm, "https://fake.test/v1", "m")
    assert result.hit_status == "miss"
    assert result.matched_entry is None
    assert llm.embed_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_semantic_retrieval.py -v`
Expected: FAIL — `app.semantic_retrieval` does not exist yet (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the module skeleton and the empty-candidates short-circuit**

Create `backend/app/semantic_retrieval.py` with the constants (`SEMANTIC_HIT_THRESHOLD = 0.75`, `SEMANTIC_HIT_MARGIN = 0.05`, `SEMANTIC_PARTIAL_THRESHOLD = 0.5` — comment: "starting point calibrated against synthetic test vectors; needs recalibration against a real embeddings provider"), a module-level `_CORPUS_CACHE: dict[tuple[str, str], dict[str, list[float]]] = {}`, and `search_knowledge_base_semantic` with the `candidates = [e for e in entries if e.sub_type == sub_type]` / `if not candidates: return RetrievalResult(hit_status="miss", matched_entry=None)` short-circuit from `retrieval.py`, nothing else yet (the rest of the body raises `NotImplementedError` for now so Step 4 only proves this one case).

- [ ] **Step 4: Run test to verify it passes**

Run: same as Step 2.
Expected: PASS.

- [ ] **Step 5: Write the failing test for cosine similarity scoring (hit/partial/miss) and corpus caching**

```python
def test_hit_when_query_vector_closely_matches_one_candidate():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0], [0.0, 1.0]])  # corpus: entry a, entry b
    llm.queue_embeddings([[0.99, 0.01]])             # query — nearly identical to entry a
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾"),
               _entry("b", "lifestyle_education", "血糖日常怎么监测")]
    result = search_knowledge_base_semantic("lifestyle_education", "钾元素从哪里补", entries, llm, "https://fake.test/v1", "m")
    assert result.hit_status == "hit"
    assert result.matched_entry.id == "a"


def test_partial_when_query_vector_is_only_loosely_related():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0]])
    llm.queue_embeddings([[0.6, 0.8]])  # cosine sim ≈ 0.6 — above PARTIAL, below HIT
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾")]
    result = search_knowledge_base_semantic("lifestyle_education", "随便问点别的", entries, llm, "https://fake.test/v1", "m")
    assert result.hit_status == "partial"


def test_miss_when_query_vector_is_unrelated_to_every_candidate():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0]])
    llm.queue_embeddings([[0.0, 1.0]])  # orthogonal — cosine sim 0
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾")]
    result = search_knowledge_base_semantic("lifestyle_education", "完全不相关的问题", entries, llm, "https://fake.test/v1", "m")
    assert result.hit_status == "miss"


def test_corpus_embeddings_are_cached_across_calls_with_the_same_base_url_and_model():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0]])   # corpus — only computed once, on the first call
    llm.queue_embeddings([[1.0, 0.0]])   # call 1's query
    llm.queue_embeddings([[1.0, 0.0]])   # call 2's query (no second corpus batch queued — proves it's not refetched)
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾")]
    search_knowledge_base_semantic("lifestyle_education", "第一次提问", entries, llm, "https://fake.test/v1", "m")
    search_knowledge_base_semantic("lifestyle_education", "第二次提问", entries, llm, "https://fake.test/v1", "m")
    # Without caching this would be 4 calls (corpus + query, twice over).
    # With caching: 1 corpus call (first search only) + 1 query call per search = 3.
    assert len(llm.embed_calls) == 3
```

Note for the implementer: the exact call-count assertion in the last test depends on your batching choice in Step 7 — adjust the queued-vector counts/assertion to match whatever shape you implement, as long as the test still proves "the corpus is embedded once, not once per search call."

- [ ] **Step 6: Run tests to verify they fail**

Run: same command as Step 2.
Expected: FAIL (`NotImplementedError` from Step 3's stub).

- [ ] **Step 7: Implement scoring and caching**

Add a pure-Python `_cosine_similarity(a: list[float], b: list[float]) -> float` (`dot / (norm_a * norm_b)`, guard against zero norms by returning `0.0`). Add `_get_corpus_embeddings(candidates, llm, base_url, embedding_model) -> dict[str, list[float]]`: look up `_CORPUS_CACHE[(base_url, embedding_model)]` (create empty dict if absent), find candidates whose `id` isn't yet cached, call `llm.embed([e.question_topic for e in missing], embedding_model)` once for all of them (batched), store each by `id`. In `search_knowledge_base_semantic`, after the empty-candidates short-circuit: get corpus embeddings, embed the query (`llm.embed([query], embedding_model)[0]`), score every candidate by cosine similarity against the query vector, sort descending, apply the same hit/margin/partial logic as `retrieval.py`'s `search_knowledge_base` (`best_score >= SEMANTIC_HIT_THRESHOLD and (best_score - second_score) >= SEMANTIC_HIT_MARGIN` → hit; `best_score >= SEMANTIC_PARTIAL_THRESHOLD` → partial; else miss).

- [ ] **Step 8: Run tests to verify they pass**

Run: same command as Step 2.
Expected: PASS, all tests in the file.

- [ ] **Step 9: Commit**

```bash
git add backend/app/semantic_retrieval.py backend/tests/test_semantic_retrieval.py
git commit -m "feat(backend): add embedding-based semantic retrieval with in-process corpus cache"
```

---

### Task 3: Wire into `pipeline.py` and `main.py` with fallback

**Files:**
- Modify: `backend/app/pipeline.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_pipeline.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `search_knowledge_base_semantic` (Task 2); `retrieval.search_knowledge_base` (existing); `LLMConfig.embedding_model` (Task 1).
- Produces: `run_turn(session, message, llm, kb_entries, base_url: str = "", embedding_model: Optional[str] = None) -> PipelineResult` — same return type as today; the two new params are trailing and defaulted, so every existing call site needs no change.

- [ ] **Step 1: Write the failing test — semantic path used and its result wins when configured**

```python
# backend/tests/test_pipeline.py — add, following this file's existing fixture/style conventions (check _kb() and how other tests set up `llm` first)
def test_run_turn_uses_semantic_retrieval_result_when_embedding_model_configured(monkeypatch):
    import app.pipeline as pipeline_module

    def fake_semantic(sub_type, query, entries, llm, base_url, embedding_model):
        from app.schemas import RetrievalResult
        return RetrievalResult(hit_status="hit", matched_entry=entries[0])

    monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", fake_semantic)
    session = SessionState(session_id="s1")
    llm = FakeLLMClient()
    # queue whatever parse_semantics/generate_answer/self_check need to reach "answered" —
    # follow the exact setup an existing "answered" test in this file already uses.
    result = run_turn(session, "哪些食物富含钾", llm, _kb(), base_url="https://fake.test/v1", embedding_model="m")
    assert result.status == "answered"
```

Adapt the exact queued responses to whatever `_kb()`/existing "reaches ANSWER" tests in this file already set up — don't invent a new fixture shape if one exists.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -k semantic -v`
Expected: FAIL — `run_turn` doesn't accept `base_url`/`embedding_model` kwargs yet (`TypeError`), and `pipeline` doesn't import `search_knowledge_base_semantic` to monkeypatch.

- [ ] **Step 3: Write the failing test — falls back to keyword retrieval when the semantic path raises**

```python
def test_run_turn_falls_back_to_keyword_retrieval_when_semantic_path_raises(monkeypatch):
    import app.pipeline as pipeline_module
    import httpx

    def fake_semantic(sub_type, query, entries, llm, base_url, embedding_model):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", fake_semantic)
    session = SessionState(session_id="s2")
    llm = FakeLLMClient()
    # same queued setup as an existing test that reaches "answered" via the real keyword path
    result = run_turn(session, "哪些食物富含钾", llm, _kb(), base_url="https://fake.test/v1", embedding_model="m")
    assert result.status == "answered"  # keyword path still finds the "钾" entry and answers normally
```

- [ ] **Step 4: Write the failing test — blank `embedding_model` never attempts the semantic path**

```python
def test_run_turn_never_calls_semantic_retrieval_when_embedding_model_is_blank(monkeypatch):
    import app.pipeline as pipeline_module

    called = []

    def fake_semantic(*args, **kwargs):
        called.append(True)
        raise AssertionError("should not be called")

    monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", fake_semantic)
    session = SessionState(session_id="s3")
    llm = FakeLLMClient()
    # same queued setup as the existing default-path "answered" test
    run_turn(session, "哪些食物富含钾", llm, _kb())  # no base_url/embedding_model passed — defaults
    assert called == []
```

- [ ] **Step 5: Run tests to verify all three fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -k "semantic or fall_back or blank" -v`
Expected: FAIL for all three (signature mismatch / import error).

- [ ] **Step 6: Implement**

In `backend/app/pipeline.py`: add `from app.semantic_retrieval import search_knowledge_base_semantic` at module level (so tests can `monkeypatch.setattr(pipeline_module, "search_knowledge_base_semantic", ...)`); change `run_turn`'s signature to add `base_url: str = "", embedding_model: Optional[str] = None` (after `kb_entries`); replace the retrieval call site (currently `if tags.sub_type is not None: retrieval_result = retrieval.search_knowledge_base(...)`) with:

```python
if tags.sub_type is not None:
    if embedding_model:
        try:
            retrieval_result = search_knowledge_base_semantic(
                tags.sub_type, retrieval_query, kb_entries, llm, base_url, embedding_model
            )
        except (httpx.HTTPError, KeyError):
            retrieval_result = retrieval.search_knowledge_base(tags.sub_type, retrieval_query, kb_entries)
    else:
        retrieval_result = retrieval.search_knowledge_base(tags.sub_type, retrieval_query, kb_entries)
else:
    retrieval_result = RetrievalResult(hit_status="miss")
```

Add `import httpx` to `pipeline.py` if not already present.

- [ ] **Step 7: Run tests to verify they pass, then run the whole file**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS, all tests (including every pre-existing one — this proves the defaulted kwargs didn't regress anything).

- [ ] **Step 8: Wire `main.py` to pass the new fields through**

In `backend/main.py`'s `chat()` handler, change the `run_turn(session, request.message, llm, _kb_entries)` call to `run_turn(session, request.message, llm, _kb_entries, base_url=request.llm_config.base_url, embedding_model=request.llm_config.embedding_model)`.

- [ ] **Step 9: Write the failing test confirming the API accepts the new field**

```python
# backend/tests/test_api.py — add
def test_chat_endpoint_accepts_embedding_model_field(monkeypatch):
    client = TestClient(main.app)
    resp = client.post("/api/chat", json={
        "session_id": "s5", "message": "我现在呼吸困难",  # red-flag path — short-circuits before any LLM call
        "llm_config": {"base_url": "http://unused.invalid", "api_key": "x", "model": "x", "embedding_model": "text-embedding-3-small"},
    })
    assert resp.status_code == 200
```

- [ ] **Step 10: Run test, confirm it already passes (Pydantic accepts unknown-to-old-schema extra field once Task 1 added it)**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_api.py -v`
Expected: PASS (this step is a regression-proof, not expected to need new production code — if it fails, something in Task 1/3's wiring is wrong; investigate rather than add a special case).

- [ ] **Step 11: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: All tests pass (68 existing + this plan's new ones).

- [ ] **Step 12: Commit**

```bash
git add backend/app/pipeline.py backend/main.py backend/tests/test_pipeline.py backend/tests/test_api.py
git commit -m "feat(backend): wire semantic retrieval into the pipeline with keyword fallback"
```

---

### Task 4: Frontend — `embedding_model` field in Settings

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/SettingsModal/SettingsModal.tsx`
- Modify: `frontend/src/components/SettingsModal/SettingsModal.css` (only if the new field needs a style rule beyond what `.hc-modal-field` already provides — check first)
- Test: `frontend/src/components/SettingsModal/SettingsModal.test.tsx`

**Interfaces:**
- Consumes: nothing from earlier tasks (frontend only needs to produce the right JSON shape; Task 3 already made the backend accept it).
- Produces: `LLMConfig.embedding_model?: string` (optional, so the four existing object literals in `settingsStore.test.ts` that omit it keep compiling/working — do not make it required).

- [ ] **Step 1: Write the failing test for the new field**

```tsx
// frontend/src/components/SettingsModal/SettingsModal.test.tsx — add
it('renders an optional Embedding Model field with a hint about the keyword fallback', () => {
  render(<SettingsModal open={true} onClose={() => {}} />);
  expect(screen.getByText('Embedding Model')).toBeInTheDocument();
  expect(screen.getByText(/回退到关键词检索/)).toBeInTheDocument();
});

it('includes embedding_model when saving', async () => {
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={() => {}} />);
  await user.type(screen.getByPlaceholderText('text-embedding-3-small'), 'my-embed-model');
  await user.click(screen.getByRole('button', { name: '保存' }));
  const saved = JSON.parse(sessionStorage.getItem('health-consult-llm-config') ?? '{}');
  expect(saved.embedding_model).toBe('my-embed-model');
});
```

Check the exact placeholder text you pick in Step 3 and keep this test's `getByPlaceholderText` argument in sync with it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- SettingsModal`
Expected: FAIL — the field doesn't exist yet.

- [ ] **Step 3: Add the field**

In `frontend/src/types.ts`, add `embedding_model?: string;` to `LLMConfig`. In `SettingsModal.tsx`: add `embedding_model: ''` to `EMPTY_CONFIG`; add a 4th `<label className="hc-modal-field">` block (same shape as the existing Model field) with text `Embedding Model`, `placeholder="text-embedding-3-small"`, bound to `config.embedding_model` / `setConfig({ ...config, embedding_model: e.target.value })`; add a `<p className="hc-modal-hint">` below it: "填写后将启用语义检索，问法更灵活、命中率更高；若所选服务商不支持 Embeddings 接口，会自动回退到关键词检索，不影响正常使用。"

- [ ] **Step 4: Run tests to verify they pass**

Run: same as Step 2.
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: All tests pass (44 existing + this task's new ones).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/components/SettingsModal/SettingsModal.tsx frontend/src/components/SettingsModal/SettingsModal.test.tsx
git commit -m "feat(frontend): optional Embedding Model field in settings"
```
