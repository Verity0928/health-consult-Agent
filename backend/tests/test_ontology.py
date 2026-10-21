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
