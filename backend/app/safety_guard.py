from typing import Optional

from app.schemas import SemanticTags

RED_FLAG_KEYWORDS: list[str] = [
    "过敏性休克", "休克",
    "呼吸困难", "喘不上气", "喘不过气",
    "意识不清", "意识模糊", "昏迷",
    "大出血", "大量出血",
    "自杀", "想死", "不想活了",
    "自伤", "自残",
    "精神心理危机", "精神崩溃",
]


def check_l0(message: str) -> bool:
    normalized = message.strip().lower()
    return any(keyword.lower() in normalized for keyword in RED_FLAG_KEYWORDS)


def check_l1(tags: SemanticTags) -> Optional[str]:
    if tags.route_scope == "clinical_prescription_intent":
        return "clinical_prescription_intent"
    if tags.population_status == "identified_special":
        return "special_population"
    if tags.route_scope == "out_of_scope_disease_consult":
        return "out_of_scope_disease_consult"
    return None
