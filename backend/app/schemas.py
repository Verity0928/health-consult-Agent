from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


class ExtractedEntities(BaseModel):
    drug_name_raw: Optional[str] = None
    drug_name_normalized: Optional[str] = None
    coreference_resolved_query: Optional[str] = None
    symptom_or_condition_raw: Optional[str] = None
    exam_item_raw: Optional[str] = None


class SemanticTags(BaseModel):
    route_scope: Literal["in_scope", "clinical_prescription_intent", "out_of_scope_disease_consult"]
    sub_type: Optional[Literal[
        "drug_contraindication", "drug_usage_factual", "drug_efficacy_evaluation",
        "lifestyle_education", "department_triage", "pre_exam_instructions",
        "health_checkup_explanation",
    ]] = None
    population_status: Literal["identified_special", "identified_general", "unknown"]
    special_population_flags: list[str] = []
    extracted_entities: ExtractedEntities = ExtractedEntities()


class KBEntry(BaseModel):
    id: str
    sub_type: str
    question_topic: str
    keywords: list[str] = []
    answer_body: str
    caution_population: str = ""
    risk_warning: str = ""
    source_note: str = ""


class RetrievalResult(BaseModel):
    hit_status: Literal["hit", "partial", "miss"]
    matched_entry: Optional[KBEntry] = None


class RouteDecision(str, Enum):
    ANSWER = "ANSWER"
    ASK_ONCE = "ASK_ONCE"
    HANDOFF = "HANDOFF"


class DispatchResult(BaseModel):
    route_decision: RouteDecision
    handoff_reason: Optional[str] = None
    ask_missing_fact_type: list[str] = []


class SelfCheckResult(BaseModel):
    compliance_pass: bool
    grounding_pass: bool
    disclaimer_pass: bool
    format_pass: bool
    overall_pass: bool
    violations: list[str] = []


class ChatMessage(BaseModel):
    role: Literal["user", "ai"]
    content: str
