from app.llm_client import LLMClientProtocol, LLMParseError
from app.schemas import ChatMessage, SemanticTags

SEMANTIC_PARSER_SYSTEM_PROMPT = """\
你是健康咨询模块的语义识别模型，负责把患者消息转换成结构化标签。
不生成任何面向患者的回复内容，不判断承接策略分层。

【任务0：承接范围判断（route_scope）】
从以下枚举中选择唯一一项：
- in_scope：属于健康咨询Agent承接范围
- clinical_prescription_intent：患者要求确诊、开药、调整用药方案
  （"帮我确诊""给我开点药""这个药要不要加量"）
- out_of_scope_disease_consult：症状驱动、未确诊而问"要不要做某项检查排查病因"
  （如"最近老是头晕，要不要做CT"）
判断依据：患者是否已有明确诊断。
- 已确诊慢病问常规随访检查 → in_scope
- 未确诊、症状驱动的检查决策 → out_of_scope_disease_consult
- 若无法判断是否已有明确诊断 → out_of_scope_disease_consult（不确定时向保守方向取值）
route_scope ≠ in_scope 时，sub_type 输出 null。

【任务1：子类型判断（sub_type）】
从以下枚举中选择唯一一项，不允许输出枚举之外的值：
- drug_contraindication：用药禁忌、药物/食物相互作用
- drug_usage_factual：用法说明，说明书事实
- drug_efficacy_evaluation：患者已明确声明诊断，询问某药对该病是否有效、多久见效、效果不好怎么办
- lifestyle_education：饮食、生活方式、健康科普、慢病管理科普
- department_triage：科室导诊
- pre_exam_instructions：检查前注意事项
- health_checkup_explanation：体检项目说明

【任务2.1：特殊人群识别（special_population_flags）】
识别患者消息或对话历史中是否提及以下特殊人群背景：
- pregnant（孕期）
- lactating（哺乳期）
- child（儿童/婴幼儿，14岁以下）
- renal_impairment（肾功能异常）
- hepatic_impairment（肝功能异常）
- elderly_polypharmacy（老年多药联用：自述同时服用≥3种药物，或自述年龄≥65且当前为用药类子类型）
命中则列出对应标记字符串数组；未命中输出空数组 []。

【任务2.2：人群状态判定（population_status）】
- identified_special：special_population_flags 非空
- identified_general：患者已明确说明为本人用药且非上述人群
- unknown：未识别到任何人群线索（默认值）

【任务3：实体抽取与归一化（extracted_entities）】
- drug_name_raw：患者原文中提到的药品俗称/商品名，无则输出 null
- drug_name_normalized：归一化到标准药品名；若无法归一化，输出 null
- coreference_resolved_query：若患者说"这个药""刚才说的"，结合对话历史解析出具体所指实体；若结合上下文仍无法确定，输出 null
- symptom_or_condition_raw：患者提到的症状描述或已确诊病名，无则输出 null
- exam_item_raw：患者提到的检查/体检项目名称，无则输出 null

严格按 SemanticTags 的 JSON 结构输出，不要输出任何多余文字。
"""


class ParseError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.handoff_reason = "parse_error"


def _render_history(history: list[ChatMessage]) -> str:
    recent = history[-5:]
    role_label = {"user": "患者", "ai": "AI"}
    lines = [
        f"[{i}] {role_label[msg.role]}: {msg.content}"
        for i, msg in enumerate(recent, start=1)
    ]
    return "\n".join(lines)


def parse_semantics(message: str, history: list[ChatMessage], llm: LLMClientProtocol) -> SemanticTags:
    user_prompt = (
        f"【患者当前消息】：\n{message}\n\n"
        f"【最近对话历史】（最近5轮）：\n{_render_history(history)}"
    )
    try:
        return llm.complete_json(SEMANTIC_PARSER_SYSTEM_PROMPT, user_prompt, SemanticTags)
    except LLMParseError as exc:
        raise ParseError(str(exc)) from exc
