from app.knowledge_base.loader import load_knowledge_base, DEFAULT_KB_DATA_DIR
from app.retrieval import search_knowledge_base


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


def test_every_entry_hits_on_its_own_question_topic():
    # Regression guard: an entry whose own representative question doesn't
    # resolve to a hit against the real KB (not an isolated test fixture)
    # means the scoring algorithm and this entry's keywords are out of sync
    # with each other — exactly the gap that let the real flagship example
    # from the design doc silently score "partial" instead of "hit".
    entries = load_knowledge_base(DEFAULT_KB_DATA_DIR)
    by_subtype: dict[str, list] = {}
    for e in entries:
        by_subtype.setdefault(e.sub_type, []).append(e)

    failures = []
    for e in entries:
        result = search_knowledge_base(e.sub_type, e.question_topic, by_subtype[e.sub_type])
        if result.hit_status != "hit" or result.matched_entry.id != e.id:
            failures.append((e.id, e.question_topic, result.hit_status))

    assert not failures, f"entries failing to self-match: {failures}"
