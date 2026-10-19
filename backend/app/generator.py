from typing import Optional

from app.llm_client import LLMClientProtocol
from app.schemas import KBEntry, SemanticTags

ANSWER_SYSTEM_PROMPT = """\
你是健康咨询助手，基于给定的知识库条目回答患者的问题。

要求：
1. 只能基于【条目内容】生成回答，不允许脱离条目自由发挥、编造条目之外的具体数值或结论
2. 语气像医生随口解答，口语化、亲和自然，不使用机械的免责声明模板
3. 回答整体控制在250-300字以内
4. 如果条目带有【人群限定提醒】，用自然口语的方式带出，而不是生硬罗列
5. 如果条目带有【风险提示】，在必要时体现
6. 不做任何形式的诊断、不对病情做推断判断、不提供个体化治疗方案
"""

ASK_ONCE_SYSTEM_PROMPT = """\
你是健康咨询助手，当前需要向患者追问一个事实性信息才能继续回答。

要求：
1. 只能提出缩小范围/确认具体信息的问题，不得包含任何结论、判断或建议
2. 一次只问一个话题（如果需要确认用药人身份，可以和药名确认合并在同一条消息内）
3. 语气自然亲和，像医生随口确认，不要让患者感觉在走流程
4. 单条消息控制在60字以内
5. 不要解释你为什么要问这么多，简短带过原因即可
"""


def generate_answer(
    tags: SemanticTags,
    entry: KBEntry,
    llm: LLMClientProtocol,
    feedback: Optional[list[str]] = None,
) -> str:
    parts = [
        f"【条目内容】：{entry.answer_body}",
    ]
    if entry.caution_population:
        parts.append(f"【人群限定提醒】：{entry.caution_population}")
    if entry.risk_warning:
        parts.append(f"【风险提示】：{entry.risk_warning}")
    if feedback:
        parts.append(f"上一次回答有以下问题，请修正：{feedback}")
    user_prompt = "\n".join(parts)
    return llm.complete_text(ANSWER_SYSTEM_PROMPT, user_prompt)


def generate_ask_once(
    tags: SemanticTags,
    missing_fact_type: list[str],
    ask_round: int,
    user_query: str,
    llm: LLMClientProtocol,
) -> str:
    user_prompt = (
        f"【当前追问轮次 ask_round】：{ask_round}\n"
        f"【需要确认的信息类型 missing_fact_type】：{missing_fact_type}\n"
        f"【患者原始问题】：{user_query}"
    )
    return llm.complete_text(ASK_ONCE_SYSTEM_PROMPT, user_prompt)
