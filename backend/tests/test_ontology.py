from app.ontology import normalize_drug_name, normalize_symptom


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


def test_normalizes_a_colloquial_symptom_phrase_to_its_canonical_term():
    assert normalize_symptom("头疼") == "头痛"


def test_normalize_symptom_strips_whitespace_before_matching():
    assert normalize_symptom("  头疼  ") == "头痛"


def test_normalize_symptom_returns_none_for_an_unrecognized_phrase():
    assert normalize_symptom("一种没见过的说法") is None


def test_normalize_symptom_returns_none_for_none_input():
    assert normalize_symptom(None) is None


def test_bone_pain_is_not_merged_into_joint_pain():
    # Final review (opus) caught this: 骨头疼 (bone pain -- differential
    # includes fracture, osteoporosis, bone metastasis, osteomyelitis;
    # triaged to orthopedics/hematology) is NOT the same clinical concept
    # as 关节疼 (joint pain -- triaged to orthopedics/rheumatology via a
    # different KB entry). Conflating them flipped a safe clarifying
    # question into a confident wrong answer in a live KB probe.
    assert normalize_symptom("骨头疼") is None


def test_canonical_drug_names_normalize_to_themselves():
    # A patient who already says the generic name must be recognized just
    # as deterministically as one who uses a brand name -- not silently
    # left to whatever the LLM's own (unverified) extraction produced.
    assert normalize_drug_name("布洛芬") == "布洛芬"
    assert normalize_drug_name("氯雷他定") == "氯雷他定"


def test_canonical_symptom_terms_normalize_to_themselves():
    assert normalize_symptom("头痛") == "头痛"
    assert normalize_symptom("头晕") == "头晕"
