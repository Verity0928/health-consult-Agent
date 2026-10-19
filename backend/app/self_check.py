from typing import Optional

from app.llm_client import LLMClientProtocol
from app.schemas import KBEntry, SelfCheckResult

MAX_REPLY_LENGTH = 320

SELF_CHECK_SYSTEM_PROMPT = """\
你是健康咨询回复的质检员，负责在回复发送给患者之前做最后一道把关。

【审核维度，逐项给出 true/false 和理由】
1. compliance_pass：回复中是否存在确定性诊断结论、具体剂量调整、"建议停药/加量"等个体化诊疗决策表述？
   （不存在=true）
2. grounding_pass：回复中的每一条医学结论，是否都能在"命中的知识库条目原文"中找到依据？
   （全部可溯源=true）
3. disclaimer_pass：若 sub_type 属于用药类(drug_contraindication/drug_usage_factual)，回复是否携带了
   人群限定尾句？（非用药类此项默认true）
4. format_pass：回复字数是否在300字以内，且没有混入"还有其他问题吗"一类的收尾话术？（符合=true）

严格按 SelfCheckResult 的 JSON 结构输出：
compliance_pass, grounding_pass, disclaimer_pass, format_pass, overall_pass（四项全部true才为true）,
violations（具体违规点描述，用于反馈给生成模块重试）
"""


def run_self_check(
    reply: str,
    entry: Optional[KBEntry],
    sub_type: Optional[str],
    llm: LLMClientProtocol,
) -> SelfCheckResult:
    retrieved_entry = ""
    if entry is not None:
        retrieved_entry = (
            f"answer_body: {entry.answer_body}\n"
            f"caution_population: {entry.caution_population}\n"
            f"risk_warning: {entry.risk_warning}"
        )
    user_prompt = (
        f"【命中的知识库条目原文】：\n{retrieved_entry}\n\n"
        f"【待审核的AI生成回复】：\n{reply}\n\n"
        f"【本轮 sub_type】：{sub_type}"
    )
    result = llm.complete_json(SELF_CHECK_SYSTEM_PROMPT, user_prompt, SelfCheckResult)

    if len(reply) > MAX_REPLY_LENGTH:
        result = result.model_copy(update={
            "format_pass": False,
            "violations": [*result.violations, f"回复超过{MAX_REPLY_LENGTH}字"],
        })

    result = result.model_copy(update={
        "overall_pass": (
            result.compliance_pass
            and result.grounding_pass
            and result.disclaimer_pass
            and result.format_pass
        ),
    })
    return result
