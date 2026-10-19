import random
from typing import Optional

CLOSING_PROBE_POOL: list[str] = [
    "您自己身体最近有什么不舒服的地方吗？没有的话咱们这次咨询就先到这儿啦～",
    "还有别的想问的吗？或者身体上有哪儿不舒服？没有的话就先这样，祝您身体健康～",
    "您这边还有其他问题，或者身体上有什么不舒服吗？没有的话这次咨询就先到这里啦～",
    "先说到这儿哈～您自己身体上要是有哪儿不舒服，随时跟我说。",
]

EXPLICIT_DECLINE_KEYWORDS: list[str] = [
    "没有了", "没有", "谢谢", "好的", "就是问问", "不用了", "就这样", "不用", "没事了",
]

# Any of these appearing means the message is itself a question, not a
# decline — a short reply that happens to contain a decline-sounding word
# (e.g. "好的，孕妇能吃吗") must not be swallowed as "the patient is done".
QUESTION_MARKERS: list[str] = [
    "吗", "呢", "？", "?", "怎么", "能不能", "能否", "为什么", "多少", "哪", "什么",
]

CLOSING_FAREWELL_TEXT = "好的，祝您身体健康，有需要随时再来问我～"


def pick_closing_probe(rng: Optional[random.Random] = None) -> str:
    return (rng or random.Random()).choice(CLOSING_PROBE_POOL)


def is_explicit_decline(message: str) -> bool:
    stripped = message.strip()
    if len(stripped) > 10:
        return False
    if any(marker in stripped for marker in QUESTION_MARKERS):
        return False
    return any(keyword in stripped for keyword in EXPLICIT_DECLINE_KEYWORDS)
