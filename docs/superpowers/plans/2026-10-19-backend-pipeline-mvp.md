# Backend Pipeline MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend that implements the full health-consult-agent decision pipeline (safety guard → semantic parsing → retrieval → dispatch → generation → self-check), callable via a single HTTP endpoint and exercised end-to-end with fake LLM responses (no real API key required to run the test suite).

**Architecture:** A workflow-orchestrated pipeline (not an autonomous agent loop). Each stage is a small, independently testable Python module with a narrow pure-ish function signature; an orchestrator (`pipeline.py`) wires them together in a fixed sequence and owns the self-check retry loop. All LLM calls go through a single `LLMClientProtocol` so every module can be tested with a deterministic fake instead of a real API key.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest. No database — session state is in-memory (demo scope, single process). No vector DB — retrieval uses deterministic keyword-overlap scoring (see Task 5).

**Spec:** [docs/PRD-健康咨询Agent开源Demo设计文档.md](../../PRD-健康咨询Agent开源Demo设计文档.md) — sections 4, 5, 7 define the pipeline this plan implements; section 2.3 defines the API-key handling constraint.

## Global Constraints

- Backend is Python + FastAPI; module layout mirrors the architecture diagram in spec §4.1 (one file per stage: safety_guard, semantic_parser, retrieval, dispatcher, generator, self_check).
- API key arrives per-request in the HTTP body and is never written to disk or to logs (spec §2.3). No module may persist it beyond the lifetime of a single request.
- `route_scope` ∈ {`in_scope`, `clinical_prescription_intent`, `out_of_scope_disease_consult`}; `sub_type` ∈ {`drug_contraindication`, `drug_usage_factual`, `drug_efficacy_evaluation`, `lifestyle_education`, `department_triage`, `pre_exam_instructions`, `health_checkup_explanation`} or `null`; `population_status` ∈ {`identified_special`, `identified_general`, `unknown`} (spec §5.2).
- `hit_status` ∈ {`hit`, `partial`, `miss`}; `route_decision` ∈ {`ANSWER`, `ASK_ONCE`, `HANDOFF`} (spec §5.4).
- `topic_turns > 2` forces `HANDOFF`; `ask_round >= 2` forbids further `ASK_ONCE` and forces `HANDOFF` (spec §5.4).
- Self-check has exactly 4 dimensions (`compliance_pass`, `grounding_pass`, `disclaimer_pass`, `format_pass`); on failure, regenerate once with the violation list as feedback; on second failure, `HANDOFF` with `handoff_reason="self_check_failed"` (spec §5.6).
- ANSWER replies target 250–300 Chinese characters; ASK_ONCE replies target ≤60 characters (spec §7.2/7.3) — self-check's `format_pass` enforces an upper bound of 320/80 chars respectively to leave LLM margin.
- Every knowledge-base entry carries `source_note` stating it is demo data, not medical authority (spec §2.1, §10).

## Review Focus

- **Red flag mid-conversation, not just turn one:** a red-flag keyword appearing in message 3 of an ongoing session must still force immediate `HANDOFF` before any LLM call — the L0 check must run on every turn, not only on session start. Covered in Task 2 and re-exercised in Task 10's end-to-end test.
- **ASK_ONCE answer reveals a special population:** when the user answers an `ASK_ONCE` follow-up and that answer resolves `population_status` to `identified_special`, the pipeline must re-route to `HANDOFF` (`special_population`), not fall through to `ANSWER`. Covered in Task 10.
- **Malformed LLM JSON from semantic_parser:** if the LLM's structured-output call returns invalid JSON or a value outside the enums, the module must not raise an uncaught exception — it must surface a typed error that the pipeline turns into `HANDOFF` with `handoff_reason="parse_error"`. Covered in Task 4 and Task 10.
- **Self-check fails twice in a row:** the retry loop must terminate after exactly one retry (never loop indefinitely) and hand off with `self_check_failed`, even if the regenerated reply also fails different dimensions than the first attempt. Covered in Task 10.
- **Topic switch resets counters:** `topic_turns` and `ask_round` must reset to 0 when the resolved `sub_type` (or core entity) changes between turns, not just increment forever — otherwise a legitimate multi-topic conversation gets wrongly cut off at turn 3. Covered in Task 6 and Task 10.

---

## Task 1: Core schemas and LLM client abstraction

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/llm_client.py`
- Create: `backend/tests/fakes.py`
- Create: `backend/requirements.txt`
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Produces: `ExtractedEntities`, `SemanticTags`, `KBEntry`, `RetrievalResult`, `RouteDecision` (str enum: `ANSWER`/`ASK_ONCE`/`HANDOFF`), `DispatchResult`, `SelfCheckResult`, `ChatMessage` (fields: `role: Literal["user","ai"]`, `content: str`) — all Pydantic `BaseModel`s, used by every later task.
- Produces: `LLMClientProtocol` (a `typing.Protocol`) with methods `complete_json(self, system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> BaseModel` and `complete_text(self, system_prompt: str, user_prompt: str) -> str`.
- Produces: `LLMClient(base_url: str, api_key: str, model: str)` implementing `LLMClientProtocol` — real implementation calling an OpenAI-compatible `/chat/completions` endpoint.
- Produces: `LLMParseError(Exception)` raised by `LLMClient.complete_json` when the response is not valid JSON or fails schema validation.
- Produces (test double, in `tests/fakes.py`): `FakeLLMClient` implementing `LLMClientProtocol`, with `queue_json(response: dict) -> None` and `queue_text(response: str) -> None` to enqueue canned responses popped in FIFO order by `complete_json`/`complete_text`; raises `AssertionError` if called with an empty queue; `complete_json` raises `LLMParseError` if the queued dict fails `schema.model_validate`.

- [ ] **Step 1: Write `backend/requirements.txt`**

Pin: `fastapi`, `uvicorn`, `pydantic>=2`, `httpx`, `pytest`.

- [ ] **Step 2: Write the failing test for `FakeLLMClient` and schema validation**

```python
# backend/tests/test_llm_client.py
from app.schemas import SemanticTags
from tests.fakes import FakeLLMClient
from app.llm_client import LLMParseError

def test_fake_llm_client_returns_queued_json_as_schema():
    client = FakeLLMClient()
    client.queue_json({
        "route_scope": "in_scope", "sub_type": "lifestyle_education",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {},
    })
    result = client.complete_json("sys", "user", SemanticTags)
    assert result.route_scope == "in_scope"
    assert isinstance(result, SemanticTags)

def test_fake_llm_client_raises_on_invalid_schema():
    client = FakeLLMClient()
    client.queue_json({"route_scope": "not_a_valid_enum_value"})
    with pytest.raises(LLMParseError):
        client.complete_json("sys", "user", SemanticTags)

def test_fake_llm_client_text_returns_queued_text():
    client = FakeLLMClient()
    client.queue_text("hello")
    assert client.complete_text("sys", "user") == "hello"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest backend/tests/test_llm_client.py -v`
Expected: FAIL (import errors — `app.schemas`, `app.llm_client`, `tests.fakes` don't exist yet)

- [ ] **Step 4: Implement `backend/app/schemas.py`**

Define all Pydantic models listed in Interfaces above, using exact enum values from Global Constraints. `ExtractedEntities` fields all `Optional[str] = None`. `SemanticTags.special_population_flags: list[str] = []`. `KBEntry` fields: `id: str`, `sub_type: str`, `question_topic: str`, `keywords: list[str]`, `answer_body: str`, `caution_population: str = ""`, `risk_warning: str = ""`, `source_note: str`. `RetrievalResult`: `hit_status: Literal["hit","partial","miss"]`, `matched_entry: Optional[KBEntry] = None`. `DispatchResult`: `route_decision: RouteDecision`, `handoff_reason: Optional[str] = None`, `ask_missing_fact_type: list[str] = []`. `SelfCheckResult`: the 4 bool fields + `overall_pass: bool` + `violations: list[str] = []`.

- [ ] **Step 5: Implement `backend/app/llm_client.py`**

`LLMParseError(Exception)`. `LLMClientProtocol` as a `typing.Protocol` with the two methods. `LLMClient` dataclass/class storing `base_url`/`api_key`/`model`; `complete_text` POSTs `{model, messages: [{role:"system",content:system_prompt},{role:"user",content:user_prompt}]}` to `f"{base_url}/chat/completions"` with `Authorization: Bearer {api_key}` via `httpx.Client`, returns `choices[0].message.content`; `complete_json` calls `complete_text`, `json.loads`s the result (stripping markdown code fences if present), then `schema.model_validate(...)`, raising `LLMParseError` wrapping any `json.JSONDecodeError` or `pydantic.ValidationError`.

- [ ] **Step 6: Implement `backend/tests/fakes.py`**

`FakeLLMClient` with `_json_queue: list[dict]`, `_text_queue: list[str]`; `queue_json`/`queue_text` append; `complete_json` pops index 0 (raise `AssertionError("no queued json response")` if empty), validates via `schema.model_validate`, re-raising `pydantic.ValidationError` as `LLMParseError`; `complete_text` pops index 0 similarly.

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest backend/tests/test_llm_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/llm_client.py backend/tests/fakes.py backend/tests/test_llm_client.py backend/requirements.txt
git commit -m "feat(backend): core schemas and LLM client abstraction with fake for testing"
```

---

## Task 2: Safety guard (L0 + L1)

**Files:**
- Create: `backend/app/safety_guard.py`
- Test: `backend/tests/test_safety_guard.py`

**Interfaces:**
- Consumes: `SemanticTags` (Task 1).
- Produces: `RED_FLAG_KEYWORDS: list[str]` (module-level constant, ≥10 entries covering: 过敏性休克, 呼吸困难, 意识不清, 大出血, 自杀, 自伤, 精神心理危机 and 2–3 colloquial variants of each theme).
- Produces: `check_l0(message: str) -> bool` — `True` if any keyword is a substring of the lowercased/stripped message.
- Produces: `check_l1(tags: SemanticTags) -> Optional[str]` — returns a `handoff_reason` string (`"clinical_prescription_intent"`, `"special_population"`, or `"out_of_scope_disease_consult"`) per Global Constraints' route_scope/population_status rules, or `None` if nothing is blocked. Priority order when multiple could apply: `clinical_prescription_intent` first, then `identified_special`, then `out_of_scope_disease_consult` (checked in that order, first match wins).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_safety_guard.py
from app.safety_guard import check_l0, check_l1
from app.schemas import SemanticTags

def test_l0_blocks_red_flag_keyword():
    assert check_l0("我现在呼吸困难，喘不上气") is True

def test_l0_passes_normal_message():
    assert check_l0("哪些食物富含钾") is False

def test_l1_blocks_clinical_prescription_intent():
    tags = SemanticTags(route_scope="clinical_prescription_intent", sub_type=None,
                         population_status="unknown", extracted_entities={})
    assert check_l1(tags) == "clinical_prescription_intent"

def test_l1_blocks_identified_special_population():
    tags = SemanticTags(route_scope="in_scope", sub_type="drug_contraindication",
                         population_status="identified_special",
                         special_population_flags=["pregnant"], extracted_entities={})
    assert check_l1(tags) == "special_population"

def test_l1_routes_out_of_scope_disease_consult():
    tags = SemanticTags(route_scope="out_of_scope_disease_consult", sub_type=None,
                         population_status="unknown", extracted_entities={})
    assert check_l1(tags) == "out_of_scope_disease_consult"

def test_l1_passes_clean_in_scope_message():
    tags = SemanticTags(route_scope="in_scope", sub_type="lifestyle_education",
                         population_status="unknown", extracted_entities={})
    assert check_l1(tags) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_safety_guard.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `backend/app/safety_guard.py`**

As specified in Interfaces.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_safety_guard.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/safety_guard.py backend/tests/test_safety_guard.py
git commit -m "feat(backend): L0 red-flag and L1 post-filter safety guard"
```

---

## Task 3: Knowledge base loader and seed data

**Files:**
- Create: `backend/app/knowledge_base/__init__.py`
- Create: `backend/app/knowledge_base/loader.py`
- Create: `backend/app/knowledge_base/data/lifestyle_education.json`
- Create: `backend/app/knowledge_base/data/drug_contraindication.json`
- Create: `backend/app/knowledge_base/data/drug_usage_factual.json`
- Create: `backend/app/knowledge_base/data/department_triage.json`
- Create: `backend/app/knowledge_base/data/pre_exam_instructions.json`
- Create: `backend/app/knowledge_base/data/health_checkup_explanation.json`
- Test: `backend/tests/test_knowledge_base.py`

**Interfaces:**
- Consumes: `KBEntry` (Task 1).
- Produces: `load_knowledge_base(data_dir: Path) -> list[KBEntry]` — reads every `*.json` file in `data_dir`, each file is a JSON array of entry objects matching `KBEntry` fields, returns the concatenated, validated list. Raises `ValueError` with the filename if a file fails validation.
- Produces: `DEFAULT_KB_DATA_DIR: Path` constant pointing at `backend/app/knowledge_base/data/`.

Each data file holds 5–8 entries for its `sub_type`. Content is real public health-science knowledge (common, uncontroversial facts — diet/mineral content, drug-label usage facts, standard pre-exam fasting rules, department-triage heuristics), rewritten in the implementer's own words, not copied verbatim from any single source. Every entry's `source_note` is exactly: `"整理自公开医学科普资料，仅供技术演示参考，非医疗依据"`. `drug_contraindication` and `drug_usage_factual` entries must have a non-empty `caution_population`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_knowledge_base.py
from app.knowledge_base.loader import load_knowledge_base, DEFAULT_KB_DATA_DIR

def test_loads_all_seed_entries_with_required_fields():
    entries = load_knowledge_base(DEFAULT_KB_DATA_DIR)
    assert len(entries) >= 30  # 6 sub_types x >=5 entries
    sub_types = {e.sub_type for e in entries}
    assert sub_types == {
        "lifestyle_education", "drug_contraindication", "drug_usage_factual",
        "department_triage", "pre_exam_instructions", "health_checkup_explanation",
    }
    for e in entries:
        assert e.source_note == "整理自公开医学科普资料，仅供技术演示参考，非医疗依据"
        assert e.keywords, f"{e.id} has no keywords"

def test_drug_entries_have_caution_population():
    entries = load_knowledge_base(DEFAULT_KB_DATA_DIR)
    drug_entries = [e for e in entries if e.sub_type in ("drug_contraindication", "drug_usage_factual")]
    assert all(e.caution_population for e in drug_entries)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_knowledge_base.py -v`
Expected: FAIL (module/data not found)

- [ ] **Step 3: Write the 6 JSON data files**

Each entry: `{"id": "<sub_type_prefix>_NNN", "sub_type": "...", "question_topic": "...", "keywords": [...], "answer_body": "...", "caution_population": "...", "risk_warning": "...", "source_note": "整理自公开医学科普资料，仅供技术演示参考，非医疗依据"}`. Example (`lifestyle_education.json`, one entry):

```json
{
  "id": "lifestyle_001",
  "sub_type": "lifestyle_education",
  "question_topic": "哪些食物富含钾",
  "keywords": ["钾", "补钾", "富钾食物"],
  "answer_body": "香蕉、橙子等水果；菠菜、土豆、红薯等蔬菜；豆类、坚果、深海鱼都富含钾，日常饮食搭配着吃就能补上。",
  "caution_population": "慢性肾病、肾功能不全者需限钾，不宜自行增加富钾食物摄入",
  "risk_warning": "",
  "source_note": "整理自公开医学科普资料，仅供技术演示参考，非医疗依据"
}
```

Write 5–8 such entries per file covering distinct, common questions for that sub_type.

- [ ] **Step 4: Implement `backend/app/knowledge_base/loader.py`**

As specified in Interfaces; iterate `data_dir.glob("*.json")`, `json.load` each (array of objects), `KBEntry.model_validate` each object, collect into one list, wrap validation errors in `ValueError(f"{path.name}: {e}")`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_knowledge_base.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/knowledge_base/ backend/tests/test_knowledge_base.py
git commit -m "feat(backend): knowledge base loader and seed demo data for 6 sub-types"
```

---

## Task 4: Semantic parser module

**Files:**
- Create: `backend/app/semantic_parser.py`
- Test: `backend/tests/test_semantic_parser.py`

**Interfaces:**
- Consumes: `SemanticTags`, `ChatMessage`, `LLMClientProtocol`, `LLMParseError` (Task 1).
- Produces: `SEMANTIC_PARSER_SYSTEM_PROMPT: str` (module constant — the prompt from spec §7.1, instructing the model to output only the `SemanticTags` JSON shape, no prose).
- Produces: `ParseError(Exception)` — raised when the LLM output fails validation; carries a `.handoff_reason = "parse_error"` attribute.
- Produces: `parse_semantics(message: str, history: list[ChatMessage], llm: LLMClientProtocol) -> SemanticTags` — builds the user prompt by rendering `message` and the last 5 `history` entries as `[turn_no] role: content` lines (spec §7 appendix format), calls `llm.complete_json(SEMANTIC_PARSER_SYSTEM_PROMPT, user_prompt, SemanticTags)`, re-raises any `LLMParseError` as `ParseError`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_semantic_parser.py
import pytest
from app.semantic_parser import parse_semantics, ParseError
from app.schemas import ChatMessage
from tests.fakes import FakeLLMClient

def test_parse_semantics_returns_tags_from_llm():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "lifestyle_education",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {},
    })
    tags = parse_semantics("哪些食物富含钾", [], llm)
    assert tags.sub_type == "lifestyle_education"

def test_parse_semantics_raises_parse_error_on_bad_llm_output():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "garbage"})
    with pytest.raises(ParseError) as exc_info:
        parse_semantics("随便说点什么", [], llm)
    assert exc_info.value.handoff_reason == "parse_error"

def test_parse_semantics_includes_history_in_prompt():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "drug_contraindication",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"coreference_resolved_query": "氯雷他定"},
    })
    history = [ChatMessage(role="user", content="吃了抗过敏药还能喝酒吗"),
               ChatMessage(role="ai", content="您方便说下具体是哪种抗过敏药吗？")]
    tags = parse_semantics("氯雷他定", history, llm)
    assert tags.extracted_entities.coreference_resolved_query == "氯雷他定"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_semantic_parser.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `backend/app/semantic_parser.py`**

As specified in Interfaces. `SEMANTIC_PARSER_SYSTEM_PROMPT` adapted from spec §7.1 (route_scope/sub_type/population_status/special_population_flags/extracted_entities task instructions, enum values copied verbatim from Global Constraints).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_semantic_parser.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/semantic_parser.py backend/tests/test_semantic_parser.py
git commit -m "feat(backend): semantic parser module with LLM-backed structured tagging"
```

---

## Task 5: Retrieval module

**Files:**
- Create: `backend/app/retrieval.py`
- Test: `backend/tests/test_retrieval.py`

**Interfaces:**
- Consumes: `KBEntry`, `RetrievalResult` (Task 1); `list[KBEntry]` from `load_knowledge_base` (Task 3).
- Produces: `search_knowledge_base(sub_type: str, query: str, entries: list[KBEntry]) -> RetrievalResult`.

Matching algorithm (deterministic, no embeddings — demo-scope keyword overlap per spec §5.3):
1. Filter `entries` to those with matching `sub_type`. If empty, return `RetrievalResult(hit_status="miss", matched_entry=None)`.
2. For each candidate, `score = (number of its keywords that appear as a substring of the lowercased query) / len(keywords)`.
3. Sort descending by score. Let `best = scores[0]`, `second = scores[1] if len(scores) > 1 else 0.0`.
4. If `best >= 0.6` and `best - second >= 0.1`: `hit_status="hit"`, `matched_entry=` that candidate.
5. Elif `best >= 0.3`: `hit_status="partial"`, `matched_entry=` that candidate (still returned for potential ASK_ONCE context, per spec §5.4's "部分命中" allowing an ASK_ONCE path).
6. Else: `hit_status="miss"`, `matched_entry=None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_retrieval.py
from app.retrieval import search_knowledge_base
from app.schemas import KBEntry

def _entry(id_, sub_type, keywords):
    return KBEntry(id=id_, sub_type=sub_type, question_topic=id_, keywords=keywords,
                    answer_body="x", source_note="演示数据")

def test_hit_when_query_clearly_matches_one_entry():
    entries = [_entry("a", "lifestyle_education", ["钾", "补钾"]),
               _entry("b", "lifestyle_education", ["血糖", "监测"])]
    result = search_knowledge_base("lifestyle_education", "哪些食物富含钾可以补钾", entries)
    assert result.hit_status == "hit"
    assert result.matched_entry.id == "a"

def test_miss_when_no_entry_for_sub_type():
    result = search_knowledge_base("department_triage", "随便问点什么", [])
    assert result.hit_status == "miss"
    assert result.matched_entry is None

def test_partial_when_weak_overlap():
    entries = [_entry("a", "drug_usage_factual", ["优甲乐", "空腹", "饭前", "饭后"])]
    result = search_knowledge_base("drug_usage_factual", "优甲乐", entries)
    assert result.hit_status == "partial"

def test_miss_when_wrong_sub_type_only_available():
    entries = [_entry("a", "lifestyle_education", ["钾"])]
    result = search_knowledge_base("department_triage", "钾", entries)
    assert result.hit_status == "miss"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_retrieval.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `backend/app/retrieval.py`**

As specified in Interfaces.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_retrieval.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval.py backend/tests/test_retrieval.py
git commit -m "feat(backend): keyword-overlap retrieval against the knowledge base"
```

---

## Task 6: Session state store

**Files:**
- Create: `backend/app/session_state.py`
- Test: `backend/tests/test_session_state.py`

**Interfaces:**
- Consumes: `ChatMessage` (Task 1).
- Produces: `SessionState` (Pydantic model or plain dataclass): `session_id: str`, `history: list[ChatMessage] = []`, `topic_turns: int = 0`, `ask_round: int = 0`, `current_sub_type: Optional[str] = None`, `current_core_entity: Optional[str] = None`, `handoff_source: Optional[str] = None`, `closed: bool = False`.
- Produces: `SessionStore` class with `get_or_create(session_id: str) -> SessionState` and `save(session: SessionState) -> None`, backed by an in-memory `dict[str, SessionState]`.
- Produces: `update_topic_counters(session: SessionState, sub_type: Optional[str], core_entity: Optional[str], is_ask_once: bool) -> None` — mutates `session` in place: if `sub_type != session.current_sub_type or core_entity != session.current_core_entity` (and `sub_type is not None`), reset `topic_turns = 0`, `ask_round = 0`, update `current_sub_type`/`current_core_entity`; else increment `topic_turns += 1`, and if `is_ask_once`, also `ask_round += 1`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_session_state.py
from app.session_state import SessionStore, SessionState, update_topic_counters

def test_store_creates_new_session_on_first_access():
    store = SessionStore()
    s = store.get_or_create("abc")
    assert s.session_id == "abc"
    assert s.topic_turns == 0

def test_store_returns_same_session_on_second_access():
    store = SessionStore()
    s1 = store.get_or_create("abc")
    s1.topic_turns = 5
    store.save(s1)
    s2 = store.get_or_create("abc")
    assert s2.topic_turns == 5

def test_update_topic_counters_increments_on_same_topic():
    s = SessionState(session_id="x", current_sub_type="lifestyle_education", current_core_entity=None)
    update_topic_counters(s, "lifestyle_education", None, is_ask_once=False)
    assert s.topic_turns == 1
    assert s.ask_round == 0

def test_update_topic_counters_resets_on_topic_switch():
    s = SessionState(session_id="x", current_sub_type="lifestyle_education",
                      current_core_entity=None, topic_turns=3, ask_round=1)
    update_topic_counters(s, "drug_contraindication", "氯雷他定", is_ask_once=False)
    assert s.topic_turns == 0
    assert s.ask_round == 0
    assert s.current_sub_type == "drug_contraindication"

def test_update_topic_counters_increments_ask_round_on_ask_once():
    s = SessionState(session_id="x", current_sub_type="drug_contraindication", current_core_entity="氯雷他定")
    update_topic_counters(s, "drug_contraindication", "氯雷他定", is_ask_once=True)
    assert s.ask_round == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_session_state.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `backend/app/session_state.py`**

As specified in Interfaces.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_session_state.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/session_state.py backend/tests/test_session_state.py
git commit -m "feat(backend): in-memory session state with topic/ask-round counters"
```

---

## Task 7: Dispatcher module

**Files:**
- Create: `backend/app/dispatcher.py`
- Test: `backend/tests/test_dispatcher.py`

**Interfaces:**
- Consumes: `SemanticTags`, `RetrievalResult`, `DispatchResult`, `RouteDecision`, `SessionState` (Tasks 1, 6).
- Produces: `decide_route(tags: SemanticTags, retrieval: RetrievalResult, session: SessionState) -> DispatchResult`.

Decision logic, in order:
1. If `session.topic_turns > 2`: return `HANDOFF`, `handoff_reason="topic_turns_exceeded"`.
2. If `session.ask_round >= 2`: return `HANDOFF`, `handoff_reason="escalate_after_ask"`.
3. If `tags.sub_type == "drug_efficacy_evaluation"`: return `HANDOFF`, `handoff_reason="drug_efficacy_evaluation"` (the "伪健康咨询" case, spec §5.4).
4. If `retrieval.hit_status == "miss"`: return `HANDOFF`, `handoff_reason="hit_status_miss"`.
5. If `retrieval.hit_status == "partial"`: return `ASK_ONCE`, `ask_missing_fact_type=["clarify_query"]` if `session.ask_round == 0`, else `HANDOFF` with `handoff_reason="hit_status_partial"`.
6. If `retrieval.hit_status == "hit"`:
   - If `tags.sub_type in ("drug_contraindication", "drug_usage_factual")` and `tags.population_status == "unknown"`: return `ASK_ONCE`, `ask_missing_fact_type=["patient_identity"]` (+ `["drug_name"]` if `tags.extracted_entities.drug_name_normalized is None`) — the population-confirmation rule from spec §5.4.
   - Else (including `population_status == "unknown"` for non-drug sub_types, which spec §5.4 treats as `identified_general`): return `ANSWER`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_dispatcher.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_dispatcher.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `backend/app/dispatcher.py`**

As specified in Interfaces.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_dispatcher.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/dispatcher.py backend/tests/test_dispatcher.py
git commit -m "feat(backend): dispatcher module implementing route_decision layering"
```

---

## Task 8: Generator module

**Files:**
- Create: `backend/app/generator.py`
- Test: `backend/tests/test_generator.py`

**Interfaces:**
- Consumes: `SemanticTags`, `RetrievalResult`, `KBEntry`, `LLMClientProtocol` (Task 1).
- Produces: `ANSWER_SYSTEM_PROMPT: str`, `ASK_ONCE_SYSTEM_PROMPT: str` (module constants, adapted from spec §7.2/§7.3).
- Produces: `generate_answer(tags: SemanticTags, entry: KBEntry, llm: LLMClientProtocol, feedback: Optional[list[str]] = None) -> str` — renders a user prompt embedding `entry.answer_body`, `entry.caution_population`, `entry.risk_warning`, and (if `feedback`) a `"上一次回答有以下问题，请修正：{feedback}"` block; calls `llm.complete_text(ANSWER_SYSTEM_PROMPT, user_prompt)`.
- Produces: `generate_ask_once(tags: SemanticTags, missing_fact_type: list[str], ask_round: int, user_query: str, llm: LLMClientProtocol) -> str` — renders `{ask_round}`, `{missing_fact_type}`, `{user_query}` into the ASK_ONCE prompt; calls `llm.complete_text(ASK_ONCE_SYSTEM_PROMPT, user_prompt)`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_generator.py
from app.generator import generate_answer, generate_ask_once
from app.schemas import SemanticTags, KBEntry, ExtractedEntities
from tests.fakes import FakeLLMClient

def test_generate_answer_returns_llm_text():
    llm = FakeLLMClient()
    llm.queue_text("含钾比较丰富的有香蕉、橙子...")
    entry = KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                     keywords=["钾"], answer_body="香蕉橙子菠菜富含钾",
                     source_note="演示数据")
    tags = SemanticTags(route_scope="in_scope", sub_type="lifestyle_education",
                         population_status="unknown", extracted_entities=ExtractedEntities())
    reply = generate_answer(tags, entry, llm)
    assert reply == "含钾比较丰富的有香蕉、橙子..."

def test_generate_answer_includes_feedback_in_prompt(monkeypatch):
    captured = {}
    llm = FakeLLMClient()
    llm.queue_text("修正后的回答")
    original_complete_text = llm.complete_text
    def spy(system_prompt, user_prompt):
        captured["user_prompt"] = user_prompt
        return original_complete_text(system_prompt, user_prompt)
    llm.complete_text = spy
    entry = KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                     keywords=["钾"], answer_body="x", source_note="演示数据")
    tags = SemanticTags(route_scope="in_scope", sub_type="lifestyle_education",
                         population_status="unknown", extracted_entities=ExtractedEntities())
    generate_answer(tags, entry, llm, feedback=["回答超出了条目范围"])
    assert "回答超出了条目范围" in captured["user_prompt"]

def test_generate_ask_once_returns_llm_text():
    llm = FakeLLMClient()
    llm.queue_text("您方便说下具体是哪种抗过敏药吗？")
    tags = SemanticTags(route_scope="in_scope", sub_type="drug_contraindication",
                         population_status="unknown", extracted_entities=ExtractedEntities())
    reply = generate_ask_once(tags, ["drug_name", "patient_identity"], 1, "醉酒后吃抗过敏药会有什么影响", llm)
    assert reply == "您方便说下具体是哪种抗过敏药吗？"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_generator.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `backend/app/generator.py`**

As specified in Interfaces; prompts adapted from spec §7.2 (ANSWER: medical/口语化 tone, 250–300字, no mechanical disclaimer template) and §7.3 (ASK_ONCE: only ask, no conclusions, ≤60字, one question per message).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_generator.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/generator.py backend/tests/test_generator.py
git commit -m "feat(backend): generator module for ANSWER and ASK_ONCE replies"
```

---

## Task 9: Self-check module

**Files:**
- Create: `backend/app/self_check.py`
- Test: `backend/tests/test_self_check.py`

**Interfaces:**
- Consumes: `SelfCheckResult`, `KBEntry`, `LLMClientProtocol` (Task 1).
- Produces: `SELF_CHECK_SYSTEM_PROMPT: str` (module constant, the prompt drafted in spec §7.3 "质检 Prompt").
- Produces: `run_self_check(reply: str, entry: KBEntry, sub_type: Optional[str], llm: LLMClientProtocol) -> SelfCheckResult` — renders `{retrieved_entry}` (entry's `answer_body`/`caution_population`/`risk_warning`), `{generated_reply}`, `{sub_type}` into the prompt; calls `llm.complete_json(SELF_CHECK_SYSTEM_PROMPT, user_prompt, SelfCheckResult)`; additionally enforces the length rule from Global Constraints in code (not trusting the LLM alone): if `len(reply) > 320`, force `format_pass = False` and append `"回复超过320字"` to `violations` before computing `overall_pass = all four bools`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_self_check.py
from app.self_check import run_self_check
from app.schemas import KBEntry
from tests.fakes import FakeLLMClient

def _entry():
    return KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                    keywords=["钾"], answer_body="香蕉橙子菠菜富含钾", source_note="演示数据")

def test_run_self_check_passes_when_llm_says_all_pass():
    llm = FakeLLMClient()
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    result = run_self_check("含钾食物有香蕉橙子", _entry(), "lifestyle_education", llm)
    assert result.overall_pass is True

def test_run_self_check_fails_when_llm_flags_grounding():
    llm = FakeLLMClient()
    llm.queue_json({"compliance_pass": True, "grounding_pass": False,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": False, "violations": ["提到的具体数值在条目中找不到依据"]})
    result = run_self_check("每天应补钾3500mg", _entry(), "lifestyle_education", llm)
    assert result.overall_pass is False
    assert result.grounding_pass is False
    assert result.violations

def test_run_self_check_forces_format_fail_on_overlong_reply():
    llm = FakeLLMClient()
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    long_reply = "香蕉橙子富含钾。" * 60  # far over 320 chars
    result = run_self_check(long_reply, _entry(), "lifestyle_education", llm)
    assert result.format_pass is False
    assert result.overall_pass is False
    assert any("320" in v for v in result.violations)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_self_check.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `backend/app/self_check.py`**

As specified in Interfaces; `SELF_CHECK_SYSTEM_PROMPT` copied from spec §7.3's 质检 Prompt block.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_self_check.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/self_check.py backend/tests/test_self_check.py
git commit -m "feat(backend): self-check module (compliance/grounding/disclaimer/format)"
```

---

## Task 10: Pipeline orchestrator

**Files:**
- Create: `backend/app/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything from Tasks 1–9 (`check_l0`, `check_l1`, `load_knowledge_base`, `search_knowledge_base`, `parse_semantics`/`ParseError`, `decide_route`, `generate_answer`/`generate_ask_once`, `run_self_check`, `SessionStore`/`update_topic_counters`).
- Produces: `PipelineDebugInfo` (Pydantic model in `app/schemas.py` — add in this task): `route_scope: Optional[str] = None`, `sub_type: Optional[str] = None`, `population_status: Optional[str] = None`, `hit_status: Optional[str] = None`, `route_decision: Optional[str] = None`, `handoff_reason: Optional[str] = None`, `self_check: Optional[SelfCheckResult] = None`, `retry_count: int = 0` — every field defaults so `PipelineDebugInfo()` is valid (used by the L0 short-circuit path, which reaches no later stage).
- Produces: `PipelineResult` (Pydantic model in `app/schemas.py`): `reply: str`, `status: Literal["answered","asked","handoff","closed"]`, `debug: PipelineDebugInfo`.
- Produces: `run_turn(session: SessionState, message: str, llm: LLMClientProtocol, kb_entries: list[KBEntry]) -> PipelineResult`.

Orchestration sequence (a helper `_handoff(session, reason, debug) -> PipelineResult` builds the common handoff return — appends `ChatMessage(role="user", content=message)` to `session.history` plus `ChatMessage(role="ai", content=HANDOFF_REPLY_TEXT)`, and returns `PipelineResult(reply=HANDOFF_REPLY_TEXT, status="handoff", debug=debug)`; a handoff never sets `session.closed` — the spec treats it as leaving the AI pipeline, not ending the conversation):

1. If `check_l0(message)`: return `_handoff(session, "red_flag", PipelineDebugInfo(handoff_reason="red_flag"))` immediately — no LLM calls made.
2. Else call `parse_semantics(message, session.history, llm)`. If it raises `ParseError`: return `_handoff(session, "parse_error", PipelineDebugInfo(handoff_reason="parse_error"))`.
3. Call `check_l1(tags)`. If it returns a reason: return `_handoff(session, reason, PipelineDebugInfo(route_scope=tags.route_scope, sub_type=tags.sub_type, population_status=tags.population_status, handoff_reason=reason))`.
4. Call `update_topic_counters(session, tags.sub_type, tags.extracted_entities.coreference_resolved_query or tags.extracted_entities.drug_name_normalized, is_ask_once=False)` (pre-dispatch, so `decide_route` next reads up-to-date `topic_turns`/`ask_round`).
5. Call `search_knowledge_base(tags.sub_type, message, kb_entries)` only if `tags.sub_type is not None`; else synthesize `RetrievalResult(hit_status="miss")`.
6. Call `decide_route(tags, retrieval, session)`. Build the running `debug = PipelineDebugInfo(route_scope=tags.route_scope, sub_type=tags.sub_type, population_status=tags.population_status, hit_status=retrieval.hit_status, route_decision=dispatch.route_decision.value)` — reused and extended in the branches below.
7. If `HANDOFF`: return `_handoff(session, dispatch.handoff_reason, debug)` (with `debug.handoff_reason` set).
8. If `ASK_ONCE`: call `reply = generate_ask_once(tags, dispatch.ask_missing_fact_type, session.ask_round + 1, message, llm)`, call `update_topic_counters(session, tags.sub_type, ..., is_ask_once=True)`, append `ChatMessage(role="user", content=message)` and `ChatMessage(role="ai", content=reply)` to `session.history`, return `PipelineResult(reply=reply, status="asked", debug=debug)`.
9. If `ANSWER`: call `reply = generate_answer(tags, retrieval.matched_entry, llm)`, then `check = run_self_check(reply, retrieval.matched_entry, tags.sub_type, llm)`.
   - If `check.overall_pass`: append `ChatMessage(role="user", content=message)` and `ChatMessage(role="ai", content=reply)` to `session.history`, `debug.self_check = check`, `debug.retry_count = 0`, return `PipelineResult(reply=reply, status="answered", debug=debug)`.
   - Else: call `reply = generate_answer(tags, retrieval.matched_entry, llm, feedback=check.violations)`, `check = run_self_check(reply, retrieval.matched_entry, tags.sub_type, llm)` again.
     - If this second `check.overall_pass`: same as above but `debug.retry_count = 1`.
     - Else: `debug.self_check = check`, `debug.retry_count = 1`, `debug.handoff_reason = "self_check_failed"`, return `_handoff(session, "self_check_failed", debug)`.

`HANDOFF_REPLY_TEXT` is a module constant: `"您描述的情况需要医生进一步介入，已为您转接人工，请稍候。"`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_pipeline.py
from app.pipeline import run_turn
from app.session_state import SessionState
from app.schemas import KBEntry
from tests.fakes import FakeLLMClient

def _kb():
    return [KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                     keywords=["钾", "补钾"], answer_body="香蕉橙子富含钾",
                     source_note="演示数据")]

def test_red_flag_short_circuits_before_any_llm_call():
    llm = FakeLLMClient()  # no queued responses at all
    session = SessionState(session_id="x")
    result = run_turn(session, "我现在呼吸困难", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "red_flag"

def test_red_flag_mid_conversation_still_short_circuits():
    llm = FakeLLMClient()
    session = SessionState(session_id="x", topic_turns=1)
    session.history = [__import__("app.schemas", fromlist=["ChatMessage"]).ChatMessage(role="user", content="哪些食物富含钾")]
    result = run_turn(session, "我现在意识不清了", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "red_flag"

def test_happy_path_answer_with_passing_self_check():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="x")
    result = run_turn(session, "哪些食物富含钾", llm, _kb())
    assert result.status == "answered"
    assert result.debug.retry_count == 0
    assert result.debug.route_decision == "ANSWER"

def test_self_check_fails_twice_then_handoff():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("第一次回答")
    llm.queue_json({"compliance_pass": True, "grounding_pass": False,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": False, "violations": ["编造了条目外的数值"]})
    llm.queue_text("第二次回答")
    llm.queue_json({"compliance_pass": True, "grounding_pass": False,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": False, "violations": ["仍然编造了数值"]})
    session = SessionState(session_id="x")
    result = run_turn(session, "哪些食物富含钾", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "self_check_failed"
    assert result.debug.retry_count == 1

def test_parse_error_from_semantic_parser_becomes_handoff():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "not_valid"})
    session = SessionState(session_id="x")
    result = run_turn(session, "随便说点什么", llm, _kb())
    assert result.status == "handoff"
    assert result.debug.handoff_reason == "parse_error"

def test_ask_once_answer_revealing_special_population_forces_handoff():
    llm = FakeLLMClient()
    # Turn 1: ASK_ONCE because population_status unknown on a drug sub_type
    llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {"drug_name_normalized": "氯雷他定"}})
    kb = [KBEntry(id="d", sub_type="drug_contraindication", question_topic="氯雷他定",
                   keywords=["氯雷他定"], answer_body="x", caution_population="孕妇慎用",
                   source_note="演示数据")]
    session = SessionState(session_id="x")
    import app.retrieval as retrieval_mod
    orig_search = retrieval_mod.search_knowledge_base
    # force a hit so dispatcher reaches the population-unknown ASK_ONCE branch
    retrieval_mod.search_knowledge_base = lambda sub_type, query, entries: __import__(
        "app.schemas", fromlist=["RetrievalResult"]).RetrievalResult(hit_status="hit", matched_entry=entries[0])
    try:
        llm.queue_text("您方便说下是否孕期吗？")
        run_turn(session, "吃氯雷他定会有什么影响", llm, kb)
        # Turn 2: answer reveals special population
        llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                         "population_status": "identified_special",
                         "special_population_flags": ["pregnant"],
                         "extracted_entities": {"drug_name_normalized": "氯雷他定"}})
        result = run_turn(session, "我现在怀孕了", llm, kb)
        assert result.status == "handoff"
        assert result.debug.handoff_reason == "special_population"
    finally:
        retrieval_mod.search_knowledge_base = orig_search
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_pipeline.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Add `PipelineDebugInfo` and `PipelineResult` to `backend/app/schemas.py`**

As specified in Interfaces.

- [ ] **Step 4: Implement `backend/app/pipeline.py`**

Following the orchestration sequence above exactly; `HANDOFF_REPLY_TEXT = "您描述的情况需要医生进一步介入，已为您转接人工，请稍候。"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_pipeline.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(backend): pipeline orchestrator wiring all stages with self-check retry loop"
```

---

## Task 11: Closing-probe dialogue completion

**Files:**
- Create: `backend/app/closing_probe.py`
- Modify: `backend/app/session_state.py` — add field to `SessionState`
- Modify: `backend/app/pipeline.py` — insert pre-check and post-ANSWER hook into `run_turn`
- Test: `backend/tests/test_closing_probe.py`
- Test: `backend/tests/test_pipeline.py` — add closing-probe cases (append to existing file)

This task closes the gap spec §2.5/§6 describe: after an `ANSWER` is delivered (directly, or after an `ASK_ONCE` round resolves into one), the dispatcher appends a closing probe and the *next* user message is first checked against three outcomes before falling through to normal routing — explicit decline (→ close the session), anything else (→ let it flow through the normal pipeline unchanged, which already naturally handles "new question" via re-classification and "new symptom" via `out_of_scope_disease_consult` routing). The fourth spec outcome, "no response within a timeout", has no meaning in a synchronous request/response API — it belongs to the frontend's idle-timer, out of scope here.

**Interfaces:**
- Consumes: `PipelineResult`, `SessionState` (Tasks 1, 6, 10).
- Produces (in `closing_probe.py`): `CLOSING_PROBE_POOL: list[str]` — the 4 fixed phrases from spec §2.5 (a/b/c/d, verbatim). `pick_closing_probe(rng: random.Random | None = None) -> str` — returns `(rng or random.Random()).choice(CLOSING_PROBE_POOL)`. `EXPLICIT_DECLINE_KEYWORDS: list[str]` — `["没有了", "没有", "谢谢", "好的", "就是问问", "不用了", "就这样", "不用", "没事了"]`. `is_explicit_decline(message: str) -> bool` — `True` iff `len(message.strip()) <= 10` and any keyword is a substring of the stripped message. `CLOSING_FAREWELL_TEXT: str = "好的，祝您身体健康，有需要随时再来问我～"`.
- Modifies `SessionState` (Task 6): add field `awaiting_closing_response: bool = False`.
- Modifies `run_turn` (Task 10): insert, immediately after the L0 check and before `parse_semantics` is called — if `session.awaiting_closing_response` is `True`: set it back to `False`; if `is_explicit_decline(message)`, set `session.closed = True` and return `PipelineResult(reply=CLOSING_FAREWELL_TEXT, status="closed", debug=PipelineDebugInfo())` without calling the LLM or any later stage; otherwise fall through to the rest of the existing sequence unchanged (the message is processed as a normal new turn). Additionally, at every point in `run_turn` where a `PipelineResult` with `status="answered"` is about to be returned (both the first-try-passes and retry-passes branches from Task 10 Step 9), append `"\n\n" + pick_closing_probe()` to `reply` and set `session.awaiting_closing_response = True` before returning.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_closing_probe.py
from app.closing_probe import is_explicit_decline, pick_closing_probe, CLOSING_PROBE_POOL
import random

def test_explicit_decline_detected_on_short_thanks():
    assert is_explicit_decline("谢谢") is True
    assert is_explicit_decline("没有了") is True

def test_explicit_decline_not_triggered_on_longer_message_containing_keyword():
    assert is_explicit_decline("谢谢，不过我还想问问血压怎么自测") is False

def test_pick_closing_probe_returns_pool_member_deterministically():
    rng = random.Random(0)
    result = pick_closing_probe(rng)
    assert result in CLOSING_PROBE_POOL
```

```python
# append to backend/tests/test_pipeline.py
from app.closing_probe import CLOSING_PROBE_POOL, CLOSING_FAREWELL_TEXT

def test_answered_reply_appends_closing_probe_and_sets_awaiting_flag():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("含钾比较丰富的有香蕉、橙子等水果。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="x")
    result = run_turn(session, "哪些食物富含钾", llm, _kb())
    assert any(p in result.reply for p in CLOSING_PROBE_POOL)
    assert session.awaiting_closing_response is True

def test_explicit_decline_after_closing_probe_closes_session_without_llm_call():
    llm = FakeLLMClient()  # nothing queued — must not be called
    session = SessionState(session_id="x", awaiting_closing_response=True)
    result = run_turn(session, "没有了，谢谢", llm, _kb())
    assert result.status == "closed"
    assert result.reply == CLOSING_FAREWELL_TEXT
    assert session.closed is True
    assert session.awaiting_closing_response is False

def test_new_question_after_closing_probe_flows_through_normal_pipeline():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "lifestyle_education",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {}})
    llm.queue_text("血糖可以在家用血糖仪监测。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    session = SessionState(session_id="x", awaiting_closing_response=True)
    result = run_turn(session, "血糖怎么监测", llm, _kb())
    assert result.status == "answered"
    assert session.awaiting_closing_response is True  # re-armed by the new ANSWER
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_closing_probe.py backend/tests/test_pipeline.py -v`
Expected: FAIL (`app.closing_probe` not found; new pipeline assertions fail against current behavior)

- [ ] **Step 3: Implement `backend/app/closing_probe.py`**

As specified in Interfaces.

- [ ] **Step 4: Add `awaiting_closing_response: bool = False` to `SessionState` in `backend/app/session_state.py`**

- [ ] **Step 5: Modify `backend/app/pipeline.py`**

Insert the pre-check and the post-ANSWER hook exactly as described in Interfaces above.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest backend/tests/test_closing_probe.py backend/tests/test_pipeline.py -v`
Expected: PASS (all tests in both files, including the 6 pre-existing `test_pipeline.py` cases from Task 10)

- [ ] **Step 7: Commit**

```bash
git add backend/app/closing_probe.py backend/app/session_state.py backend/app/pipeline.py backend/tests/test_closing_probe.py backend/tests/test_pipeline.py
git commit -m "feat(backend): closing-probe dialogue completion after ANSWER turns"
```

---

## Task 12: FastAPI endpoint

**Files:**
- Create: `backend/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `SessionStore`, `run_turn`, `load_knowledge_base`, `DEFAULT_KB_DATA_DIR`, `LLMClient` (Tasks 1, 3, 6, 10, 11).
- Produces: `app: FastAPI` instance in `backend/main.py`.
- Produces: `POST /api/chat` accepting JSON body `{"session_id": str, "message": str, "llm_config": {"base_url": str, "api_key": str, "model": str}}`, returning the `PipelineResult` JSON (`reply`, `status`, `debug`). Constructs an `LLMClient` from `llm_config` fresh per request (never cached/stored), loads the KB once at module import time into a module-level list, uses a module-level `SessionStore` singleton.
- Produces: `GET /api/health` returning `{"status": "ok"}` (no auth, no LLM call — basic liveness check).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_api.py
from fastapi.testclient import TestClient
import main

def test_health_check():
    client = TestClient(main.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_chat_endpoint_rejects_malformed_body():
    client = TestClient(main.app)
    resp = client.post("/api/chat", json={"session_id": "x"})  # missing message, llm_config
    assert resp.status_code == 422

def test_chat_endpoint_red_flag_short_circuits_without_calling_llm(monkeypatch):
    client = TestClient(main.app)
    # LLMClient would fail on a real network call; red-flag path must never reach it
    resp = client.post("/api/chat", json={
        "session_id": "s1", "message": "我现在呼吸困难",
        "llm_config": {"base_url": "http://unused.invalid", "api_key": "x", "model": "x"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "handoff"
    assert body["debug"]["handoff_reason"] == "red_flag"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_api.py -v`
Expected: FAIL (`main` module not found)

- [ ] **Step 3: Implement `backend/main.py`**

FastAPI app with the two routes as specified; request/response Pydantic models reuse `PipelineResult` and a new `ChatTurnRequest` (add to `schemas.py`: `session_id: str`, `message: str`, `llm_config: LLMConfig` where `LLMConfig` is `{base_url: str, api_key: str, model: str}`, also added to `schemas.py` in this step).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_api.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full backend test suite**

Run: `pytest backend/ -v`
Expected: all tests across Tasks 1–12 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/app/schemas.py backend/tests/test_api.py
git commit -m "feat(backend): FastAPI chat endpoint wiring the full pipeline"
```
