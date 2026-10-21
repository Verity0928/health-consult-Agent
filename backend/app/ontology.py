from typing import Optional

# Common brand/colloquial names a patient might actually type -> the
# generic name this KB's entries are written against (see
# backend/app/knowledge_base/data/drug_contraindication.json and
# drug_usage_factual.json). Deliberately not exhaustive -- this covers
# what the demo KB references, not a general drug database.
DRUG_ALIASES: dict[str, str] = {
    "芬必得": "布洛芬",
    "芬克": "布洛芬",
    "布洛芬缓释胶囊": "布洛芬",
    "开瑞坦": "氯雷他定",
    "开瑞坦糖浆": "氯雷他定",
    "拜阿司匹林": "阿司匹林",
    "巴米尔": "阿司匹林",
    "泰诺林": "对乙酰氨基酚",
    "百服宁": "对乙酰氨基酚",
    "必理通": "对乙酰氨基酚",
    "扑热息痛": "对乙酰氨基酚",
    "洛赛克": "奥美拉唑",
    "奥西康": "奥美拉唑",
    "可迈丁": "华法林",
    "格华止": "二甲双胍",
    "君力达": "二甲双胍",
    "优甲乐": "左甲状腺素",
    "优甲乐片": "左甲状腺素",
}


def normalize_drug_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return DRUG_ALIASES.get(raw.strip())


# Colloquial phrasings a patient might type -> the canonical term this
# KB's department_triage/lifestyle_education entries are written
# against (see backend/app/knowledge_base/data/department_triage.json).
SYMPTOM_ALIASES: dict[str, str] = {
    "头疼": "头痛",
    "脑袋疼": "头痛",
    "脑仁疼": "头痛",
    "头昏": "头晕",
    "晕眩": "头晕",
    "眩晕": "头晕",
    "肚子疼": "腹痛",
    "肚子痛": "腹痛",
    "肚疼": "腹痛",
    "干咳": "咳嗽",
    "咳痰": "咳嗽",
    "起疹子": "皮疹",
    "长疹子": "皮疹",
    "红疙瘩": "皮疹",
    "关节酸痛": "关节疼",
    "骨头疼": "关节疼",
    "发热": "发烧",
    "高烧": "发烧",
    "大姨妈不准": "月经不调",
    "例假不规律": "月经不调",
}


def normalize_symptom(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return SYMPTOM_ALIASES.get(raw.strip())
