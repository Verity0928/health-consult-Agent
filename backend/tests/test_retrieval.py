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


def test_hit_resolves_specific_entry_over_generic_keyword_collision():
    # A long, specific keyword list sharing one generic term with a short,
    # unrelated entry must not get diluted below the entry that actually
    # matches more of the query (uncapped matched/len(keywords) ties these
    # at 0.5/0.5 and arbitrarily returns the wrong one).
    entries = [
        _entry("generic", "department_triage", ["挂什么科", "咳嗽"]),
        _entry("specific", "department_triage", ["挂什么科", "孩子发烧", "小孩发烧", "儿童发烧"]),
    ]
    result = search_knowledge_base("department_triage", "孩子发烧挂什么科", entries)
    assert result.hit_status == "hit"
    assert result.matched_entry.id == "specific"
