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
