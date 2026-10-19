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
