# Drug & Symptom Normalization Ontology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LLM's unverifiable, inconsistent guess at a drug's generic name with a deterministic, auditable alias lookup, and add the same mechanism for symptom phrasing — so "芬必得" and "布洛芬", or "头疼" and "头痛", are recognized as the same concept every time, not only when the model happens to know it this turn.

**Architecture:** A new `backend/app/ontology.py` module holds two plain Python dicts (`DRUG_ALIASES`, `SYMPTOM_ALIASES`: common patient-facing term → canonical term) and two lookup functions (`normalize_drug_name`, `normalize_symptom`). This is deliberately *not* a formal OWL/RDF ontology — no reasoner, no class hierarchy — just a deterministic alias table, which is the right scope for this demo's KB size and gives the real benefits a heavier ontology would (determinism, auditability, zero extra LLM call) without the engineering cost of one a reasoner would need.

Integration has two parts, both additive and fail-open (an unrecognized term behaves exactly as it does today):
1. `semantic_parser.py` calls these lookups right after the LLM returns `SemanticTags`, and **overwrites** `drug_name_normalized` / sets the new `symptom_or_condition_normalized` field only when the raw term is found in the table. A term outside the table leaves the LLM's own guess (for drugs) or `None` (for symptoms, which have no prior normalized field) exactly as before — the ontology only ever makes a known term *more* reliable, never removes information the LLM already produced.
2. `pipeline.py` appends whichever canonical term(s) were recognized to `retrieval_query` before calling either retrieval path, so a brand name or colloquial phrasing that isn't in a KB entry's keyword list (but whose canonical form is) now has a chance to match. `pipeline.py`'s `_core_entity()` (used for topic-switch detection) is updated to prefer `symptom_or_condition_normalized` over `_raw`, matching the priority `drug_name_normalized` already has — so "头疼" then "头痛" about the same ongoing complaint is recognized as the same topic instead of resetting the topic-turn counter.

**Tech Stack:** Same as the existing backend (Python 3.12, FastAPI, Pydantic v2, pytest). No new dependency — plain dicts, no ontology/graph library.

**Spec:** No separate spec document. Requirements were worked out in conversation with the product owner (a medical AI PM) after discussing whether the knowledge base should be restructured as a formal ontology. Agreed scope, which this plan treats as binding:
- A lightweight alias table, not a formal OWL/RDF ontology with a reasoner — out of proportion to this demo's KB size.
- Covers two kinds of normalization requested, in this order: (1) drug names, (2) symptom phrasing.
- Alias coverage only needs to span what the demo KB already references (see `backend/app/knowledge_base/data/drug_contraindication.json`, `drug_usage_factual.json`, `department_triage.json`) — this is a pipeline-mechanism change, not a content-expansion pass (same scope boundary the semantic-retrieval plan drew for itself).
- Must not weaken anything the LLM already gets right: the ontology only *overrides* when it has an entry, never blanks a field it doesn't recognize.

## Global Constraints

- No new Python dependency.
- `ExtractedEntities.symptom_or_condition_normalized` is a new `Optional[str] = None` field — additive, so every existing `ExtractedEntities(...)` construction across the test suite (which doesn't pass it) keeps working unmodified.
- `normalize_drug_name`/`normalize_symptom` must never raise on `None` or empty-string input — callers pass `Optional[str]` fields straight through.
- Alias matching is exact-after-`.strip()` only (no fuzzy/substring matching) — brand and colloquial names are discrete, enumerable strings, unlike free-text KB questions, so the brittleness that motivated semantic retrieval does not apply here.
- The ontology only ever *adds* information to `retrieval_query` (appends canonical terms) — never removes or rewrites the original message text, so the existing keyword/semantic retrieval paths keep working on unrecognized input exactly as before.

## Review Focus

- A drug or symptom alias padded with whitespace (`"  芬必得  "`) must still normalize — `.strip()` happens before lookup, not just on exact dict keys as typed in the source. (Task 1, Task 2)
- A term the LLM extracted but that isn't in either alias table must leave `drug_name_normalized` exactly as the LLM produced it (not blanked to `None`) and `symptom_or_condition_normalized` as `None` — the ontology degrades to current behavior, never regresses it. (Task 1, Task 2)
- `_core_entity()`'s existing priority (drug over symptom over exam) must still hold after adding `symptom_or_condition_normalized` to the chain — a turn with both a recognized drug and a recognized symptom must still key off the drug. (Task 2)
- Appending a canonical term to `retrieval_query` when the canonical term is *already* the literal text the patient used (not a brand/colloquial alias) must not break or duplicate-match anything — this is the common case and must stay a no-op in effect. (Task 1)
- Two different colloquial phrasings of the same symptom across turns ("头疼" then "头痛") must resolve to the same `_core_entity()` value, so `is_topic_switch` does not fire between them — this is the concrete behavioral bug the symptom half of this plan exists to fix. (Task 2)

---

### Task 1: Drug name ontology

**Files:**
- Create: `backend/app/ontology.py`
- Modify: `backend/app/semantic_parser.py`
- Modify: `backend/app/pipeline.py`
- Test: `backend/tests/test_ontology.py`
- Test: `backend/tests/test_semantic_parser.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: `DRUG_ALIASES: dict[str, str]` (alias → canonical, see Step 3 for the exact seed set); `normalize_drug_name(raw: Optional[str]) -> Optional[str]` (returns `None` for `None`/empty/unrecognized input, the canonical name otherwise). `semantic_parser.parse_semantics` now overwrites `tags.extracted_entities.drug_name_normalized` with `normalize_drug_name(tags.extracted_entities.drug_name_raw)` whenever that call returns non-`None`. `pipeline.run_turn`'s `retrieval_query` construction appends `tags.extracted_entities.drug_name_normalized` (if set) as a separate word before calling retrieval.

- [ ] **Step 1: Write the failing tests for `normalize_drug_name`**

```python
# backend/tests/test_ontology.py
from app.ontology import normalize_drug_name


def test_normalizes_a_known_brand_name_to_its_generic_name():
    assert normalize_drug_name("芬必得") == "布洛芬"


def test_strips_whitespace_before_matching():
    assert normalize_drug_name("  芬必得  ") == "布洛芬"


def test_returns_none_for_an_unrecognized_name():
    assert normalize_drug_name("某种没听过的药") is None


def test_returns_none_for_none_input():
    assert normalize_drug_name(None) is None


def test_returns_none_for_empty_string():
    assert normalize_drug_name("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_ontology.py -v`
Expected: FAIL — `app.ontology` does not exist (`ModuleNotFoundError`).

- [ ] **Step 3: Create `backend/app/ontology.py` with the drug alias table**

```python
from typing import Optional

# Common brand/colloquial names a patient might actually type -> the
# generic name this KB's entries are written against (see
# backend/app/knowledge_base/data/drug_contraindication.json and
# drug_usage_factual.json). Deliberately not exhaustive -- this covers
# what the demo KB references, not a general drug database.
DRUG_ALIASES: dict[str, str] = {
    "芬必得": "布洛芬",
    "芬克": "布洛芬",
    "布洛芬缓释胶囊": "布洛芬",
    "开瑞坦": "氯雷他定",
    "开瑞坦糖浆": "氯雷他定",
    "拜阿司匹林": "阿司匹林",
    "巴米尔": "阿司匹林",
    "泰诺林": "对乙酰氨基酚",
    "百服宁": "对乙酰氨基酚",
    "必理通": "对乙酰氨基酚",
    "扑热息痛": "对乙酰氨基酚",
    "洛赛克": "奥美拉唑",
    "奥西康": "奥美拉唑",
    "可迈丁": "华法林",
    "格华止": "二甲双胍",
    "君力达": "二甲双胍",
    "优甲乐": "左甲状腺素",
    "优甲乐片": "左甲状腺素",
}


def normalize_drug_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return DRUG_ALIASES.get(raw.strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: same command as Step 2.
Expected: PASS, all 5 tests.

- [ ] **Step 5: Write the failing test for `semantic_parser` wiring**

```python
# backend/tests/test_semantic_parser.py — add
def test_parse_semantics_normalizes_a_recognized_drug_brand_name():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "drug_contraindication",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"drug_name_raw": "芬必得", "drug_name_normalized": None},
    })
    tags = parse_semantics("芬必得能和阿司匹林一起吃吗", [], llm)
    assert tags.extracted_entities.drug_name_normalized == "布洛芬"


def test_parse_semantics_keeps_the_llms_guess_for_an_unrecognized_drug_name():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "drug_contraindication",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"drug_name_raw": "某种没听过的药",
                                "drug_name_normalized": "模型自己猜的名字"},
    })
    tags = parse_semantics("某种没听过的药怎么吃", [], llm)
    assert tags.extracted_entities.drug_name_normalized == "模型自己猜的名字"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_semantic_parser.py -v`
Expected: FAIL — `parse_semantics` doesn't call `normalize_drug_name` yet, so the first new test gets the LLM's raw `None` back instead of `"布洛芬"`; the second test currently happens to pass already (nothing overwrites it) — note that in your run but don't treat it as satisfying the step, since Step 2's own test must also be driving the implementation.

- [ ] **Step 7: Wire `normalize_drug_name` into `parse_semantics`**

In `backend/app/semantic_parser.py`, import `normalize_drug_name` from `app.ontology`. After `tags = llm.complete_json(...)` inside `parse_semantics` (before the `return`), add:

```python
canonical_drug = normalize_drug_name(tags.extracted_entities.drug_name_raw)
if canonical_drug is not None:
    tags.extracted_entities.drug_name_normalized = canonical_drug
```

- [ ] **Step 8: Run tests to verify they pass**

Run: same command as Step 6.
Expected: PASS, both new tests, plus the file's 3 pre-existing tests still pass.

- [ ] **Step 9: Write the failing test for retrieval-query augmentation**

```python
# backend/tests/test_pipeline.py — add
def test_run_turn_appends_the_normalized_drug_name_to_the_retrieval_query(monkeypatch):
    import app.retrieval as retrieval_mod
    captured = {}
    orig_search = retrieval_mod.search_knowledge_base

    def capturing_search(sub_type, query, entries):
        captured["query"] = query
        return orig_search(sub_type, query, entries)

    retrieval_mod.search_knowledge_base = capturing_search
    try:
        llm = FakeLLMClient()
        llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                         "population_status": "unknown", "special_population_flags": [],
                         "extracted_entities": {"drug_name_raw": "芬必得"}})
        llm.queue_text("芬必得和阿司匹林一起吃要小心胃肠道刺激。")
        llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                         "disclaimer_pass": True, "format_pass": True,
                         "overall_pass": True, "violations": []})
        kb = [KBEntry(id="a", sub_type="drug_contraindication", question_topic="阿司匹林和布洛芬能一起吃吗",
                      keywords=["阿司匹林", "布洛芬"], answer_body="x", source_note="演示数据")]
        session = SessionState(session_id="x")
        run_turn(session, "芬必得能和阿司匹林一起吃吗", llm, kb)
        assert "布洛芬" in captured["query"]
    finally:
        retrieval_mod.search_knowledge_base = orig_search


def test_run_turn_still_answers_when_patient_already_used_the_canonical_drug_name():
    # drug_name_raw == the canonical name itself isn't a key in
    # DRUG_ALIASES (only brand/colloquial names are keys), so
    # normalize_drug_name returns None here and drug_name_normalized
    # stays whatever the LLM's own extraction produced -- typically the
    # same canonical text, trivially. Appending it to retrieval_query is
    # then a harmless duplicate; this proves it doesn't break matching.
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "drug_contraindication",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {"drug_name_raw": "布洛芬", "drug_name_normalized": "布洛芬"}})
    llm.queue_text("布洛芬和阿司匹林一起吃要小心胃肠道刺激。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    kb = [KBEntry(id="a", sub_type="drug_contraindication", question_topic="阿司匹林和布洛芬能一起吃吗",
                  keywords=["阿司匹林", "布洛芬"], answer_body="x", source_note="演示数据")]
    session = SessionState(session_id="x")
    result = run_turn(session, "布洛芬和阿司匹林一起吃可以吗", llm, kb)
    assert result.status == "answered"
    assert result.debug.hit_status == "hit"
```

Follow this file's existing pattern (see the `special_population` test around line 90) for monkeypatching `retrieval_mod.search_knowledge_base` via direct attribute reassignment with a `try/finally` restore — that is this file's established convention, not `monkeypatch.setattr`.

- [ ] **Step 10: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -k "appends_the_normalized_drug_name or already_used_the_canonical" -v`
Expected: `test_run_turn_appends_the_normalized_drug_name_to_the_retrieval_query` FAILS (`captured["query"]` is `"芬必得能和阿司匹林一起吃吗"`, which does not contain `"布洛芬"`). `test_run_turn_still_answers_when_patient_already_used_the_canonical_drug_name` already PASSES at this point — the keyword matcher finds `"布洛芬"`/`"阿司匹林"` directly in the unmodified message text, with or without the Step 11 change. That's fine: it's a regression-proof for Step 11, not a test Step 11 is required to turn green — keep it and re-run it in Step 12 to confirm Step 11 didn't break it.

- [ ] **Step 11: Append the canonical drug name to `retrieval_query`**

In `backend/app/pipeline.py`, after the existing `retrieval_query` is set (both branches — fresh topic and fact-followup) and before the `if tags.sub_type is not None:` retrieval block, add:

```python
if tags.extracted_entities.drug_name_normalized:
    retrieval_query = f"{retrieval_query} {tags.extracted_entities.drug_name_normalized}"
```

- [ ] **Step 12: Run tests to verify they pass, then run the whole file**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS, all tests including every pre-existing one.

- [ ] **Step 13: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: All tests pass.

- [ ] **Step 14: Commit**

```bash
git add backend/app/ontology.py backend/app/semantic_parser.py backend/app/pipeline.py backend/tests/test_ontology.py backend/tests/test_semantic_parser.py backend/tests/test_pipeline.py
git commit -m "feat(backend): deterministic drug-name normalization via alias ontology"
```

---

### Task 2: Symptom synonym ontology

**Files:**
- Modify: `backend/app/ontology.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/semantic_parser.py`
- Modify: `backend/app/pipeline.py`
- Test: `backend/tests/test_ontology.py`
- Test: `backend/tests/test_semantic_parser.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `normalize_drug_name`'s module (Task 1) — this task adds alongside it in the same file.
- Produces: `SYMPTOM_ALIASES: dict[str, str]` (see Step 3 for the seed set); `normalize_symptom(raw: Optional[str]) -> Optional[str]` (same `None`/empty/unrecognized → `None` contract as `normalize_drug_name`); `ExtractedEntities.symptom_or_condition_normalized: Optional[str] = None` (new field, additive); `parse_semantics` sets it the same way it overwrites `drug_name_normalized`; `pipeline._core_entity()` tries `symptom_or_condition_normalized` between `drug_name_normalized` and `symptom_or_condition_raw`; `retrieval_query` also gets the normalized symptom appended, same mechanism as Task 1's drug append.

- [ ] **Step 1: Write the failing tests for `normalize_symptom`**

```python
# backend/tests/test_ontology.py — add
from app.ontology import normalize_symptom


def test_normalizes_a_colloquial_symptom_phrase_to_its_canonical_term():
    assert normalize_symptom("头疼") == "头痛"


def test_normalize_symptom_strips_whitespace_before_matching():
    assert normalize_symptom("  头疼  ") == "头痛"


def test_normalize_symptom_returns_none_for_an_unrecognized_phrase():
    assert normalize_symptom("一种没见过的说法") is None


def test_normalize_symptom_returns_none_for_none_input():
    assert normalize_symptom(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_ontology.py -v`
Expected: FAIL — `normalize_symptom` does not exist yet (`ImportError`).

- [ ] **Step 3: Add the symptom alias table and lookup function**

In `backend/app/ontology.py`, add (same file as Task 1's `DRUG_ALIASES`/`normalize_drug_name`):

```python
# Colloquial phrasings a patient might type -> the canonical term this
# KB's department_triage/lifestyle_education entries are written
# against (see backend/app/knowledge_base/data/department_triage.json).
SYMPTOM_ALIASES: dict[str, str] = {
    "头疼": "头痛",
    "脑袋疼": "头痛",
    "脑仁疼": "头痛",
    "头昏": "头晕",
    "晕眩": "头晕",
    "眩晕": "头晕",
    "肚子疼": "腹痛",
    "肚子痛": "腹痛",
    "肚疼": "腹痛",
    "干咳": "咳嗽",
    "咳痰": "咳嗽",
    "起疹子": "皮疹",
    "长疹子": "皮疹",
    "红疙瘩": "皮疹",
    "关节酸痛": "关节疼",
    "骨头疼": "关节疼",
    "发热": "发烧",
    "高烧": "发烧",
    "大姨妈不准": "月经不调",
    "例假不规律": "月经不调",
}


def normalize_symptom(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return SYMPTOM_ALIASES.get(raw.strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: same command as Step 2.
Expected: PASS, all tests in the file (Task 1's 5 plus this task's 4).

- [ ] **Step 5: Write the failing test for the new schema field**

```python
# backend/tests/test_schemas.py — add
from app.schemas import ExtractedEntities

def test_extracted_entities_symptom_or_condition_normalized_defaults_to_none():
    entities = ExtractedEntities()
    assert entities.symptom_or_condition_normalized is None
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schemas.py -v`
Expected: FAIL — `AttributeError`, the field doesn't exist.

- [ ] **Step 7: Add the field**

In `backend/app/schemas.py`, add `symptom_or_condition_normalized: Optional[str] = None` to `ExtractedEntities`, directly after `symptom_or_condition_raw`.

- [ ] **Step 8: Run test to verify it passes**

Run: same as Step 6.
Expected: PASS.

- [ ] **Step 9: Write the failing test for `semantic_parser` wiring**

```python
# backend/tests/test_semantic_parser.py — add
def test_parse_semantics_normalizes_a_recognized_symptom_phrase():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "department_triage",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"symptom_or_condition_raw": "头疼"},
    })
    tags = parse_semantics("我头疼，挂什么科", [], llm)
    assert tags.extracted_entities.symptom_or_condition_normalized == "头痛"


def test_parse_semantics_leaves_normalized_symptom_none_when_unrecognized():
    llm = FakeLLMClient()
    llm.queue_json({
        "route_scope": "in_scope", "sub_type": "department_triage",
        "population_status": "unknown", "special_population_flags": [],
        "extracted_entities": {"symptom_or_condition_raw": "一种没见过的说法"},
    })
    tags = parse_semantics("一种没见过的说法，挂什么科", [], llm)
    assert tags.extracted_entities.symptom_or_condition_normalized is None
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_semantic_parser.py -k symptom -v`
Expected: FAIL — `parse_semantics` doesn't call `normalize_symptom` yet, so `symptom_or_condition_normalized` stays `None` for both (the first test fails; the second happens to already pass, same caveat as Task 1 Step 6 — don't treat that as the step's completion).

- [ ] **Step 11: Wire `normalize_symptom` into `parse_semantics`**

In `backend/app/semantic_parser.py`, import `normalize_symptom` alongside `normalize_drug_name`. In the same block added in Task 1 Step 7, add:

```python
canonical_symptom = normalize_symptom(tags.extracted_entities.symptom_or_condition_raw)
if canonical_symptom is not None:
    tags.extracted_entities.symptom_or_condition_normalized = canonical_symptom
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_semantic_parser.py -v`
Expected: PASS, all tests in the file.

- [ ] **Step 13: Write the failing test for `_core_entity` priority and topic-switch consistency**

```python
# backend/tests/test_pipeline.py — add
def test_core_entity_prefers_normalized_symptom_over_raw():
    from app.pipeline import _core_entity
    from app.schemas import SemanticTags, ExtractedEntities
    tags = SemanticTags(
        route_scope="in_scope", sub_type="department_triage", population_status="unknown",
        extracted_entities=ExtractedEntities(
            symptom_or_condition_raw="头疼", symptom_or_condition_normalized="头痛",
        ),
    )
    assert _core_entity(tags) == "头痛"


def test_core_entity_still_prefers_drug_name_over_symptom():
    from app.pipeline import _core_entity
    from app.schemas import SemanticTags, ExtractedEntities
    tags = SemanticTags(
        route_scope="in_scope", sub_type="drug_contraindication", population_status="unknown",
        extracted_entities=ExtractedEntities(
            drug_name_normalized="布洛芬",
            symptom_or_condition_raw="头疼", symptom_or_condition_normalized="头痛",
        ),
    )
    assert _core_entity(tags) == "布洛芬"


def test_different_phrasings_of_the_same_symptom_do_not_reset_topic_turns():
    llm = FakeLLMClient()
    llm.queue_json({"route_scope": "in_scope", "sub_type": "department_triage",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {"symptom_or_condition_raw": "头疼"}})
    llm.queue_text("反复头痛建议先挂神经内科看看。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    # Keywords on the canonical term "头痛", not the colloquial "头疼" the
    # patient actually typed -- turn 1 only hits because retrieval_query
    # gets "头痛" appended (Task 2's second change below); turn 2 hits
    # because "头痛" already appears literally in what the patient typed.
    kb = [KBEntry(id="a", sub_type="department_triage", question_topic="头痛反复发作挂什么科",
                  keywords=["头痛"], answer_body="x", source_note="演示数据")]
    session = SessionState(session_id="x")
    result1 = run_turn(session, "我头疼，该挂什么科", llm, kb)
    assert result1.status == "answered"
    assert session.topic_turns == 1

    llm.queue_json({"route_scope": "in_scope", "sub_type": "department_triage",
                     "population_status": "unknown", "special_population_flags": [],
                     "extracted_entities": {"symptom_or_condition_raw": "头痛"}})
    llm.queue_text("如果吃了止痛药还是没缓解，建议尽快就医。")
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    result2 = run_turn(session, "吃了止痛药头痛还是没好", llm, kb)
    assert result2.status == "answered"
    # "头疼" then "头痛" are the same symptom once normalized -> same
    # topic, so this is turn 2 on the same topic, not a reset to 1.
    assert session.topic_turns == 2
```

- [ ] **Step 14: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -k "core_entity or same_symptom" -v`
Expected: FAIL on all three. `_core_entity` doesn't check `symptom_or_condition_normalized` yet, so the first two tests assert the wrong return value. The topic-turns test fails for a compound reason at this point in the sequence (Step 15 hasn't run yet either): turn 1's `retrieval_query` doesn't yet have `"头痛"` appended, so it misses the `keywords=["头痛"]` entry entirely and the turn short-circuits to a handoff instead of reaching `"answered"` — both `result1.status == "answered"` and the final `topic_turns` assertion fail. That's expected; Step 15 fixes both at once.

- [ ] **Step 15: Update `_core_entity` and append the normalized symptom to `retrieval_query`**

In `backend/app/pipeline.py`'s `_core_entity`, insert `symptom_or_condition_normalized` between the existing `drug_name_normalized` and `symptom_or_condition_raw` terms:

```python
def _core_entity(tags: SemanticTags) -> Optional[str]:
    return (
        tags.extracted_entities.drug_name_normalized
        or tags.extracted_entities.symptom_or_condition_normalized
        or tags.extracted_entities.symptom_or_condition_raw
        or tags.extracted_entities.exam_item_raw
    )
```

In the `retrieval_query` augmentation block added in Task 1 Step 11, add the symptom alongside the drug:

```python
if tags.extracted_entities.drug_name_normalized:
    retrieval_query = f"{retrieval_query} {tags.extracted_entities.drug_name_normalized}"
if tags.extracted_entities.symptom_or_condition_normalized:
    retrieval_query = f"{retrieval_query} {tags.extracted_entities.symptom_or_condition_normalized}"
```

- [ ] **Step 16: Run tests to verify they pass, then run the whole file**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS, all tests including every pre-existing one.

- [ ] **Step 17: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: All tests pass.

- [ ] **Step 18: Commit**

```bash
git add backend/app/ontology.py backend/app/schemas.py backend/app/semantic_parser.py backend/app/pipeline.py backend/tests/test_ontology.py backend/tests/test_schemas.py backend/tests/test_semantic_parser.py backend/tests/test_pipeline.py
git commit -m "feat(backend): deterministic symptom-phrasing normalization via alias ontology"
```
