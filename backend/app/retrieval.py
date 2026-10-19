from app.schemas import KBEntry, RetrievalResult

HIT_THRESHOLD = 0.6
HIT_MARGIN = 0.1
PARTIAL_THRESHOLD = 0.2
# Cap the scoring denominator: a long keyword list (synonyms, qualifiers)
# shouldn't dilute a strong match down below a short, less-specific entry
# that happens to share one generic keyword. Two matched keywords is
# already a confident signal for a short demo KB.
MAX_SCORE_DENOMINATOR = 2


def _score(query: str, entry: KBEntry) -> float:
    if not entry.keywords:
        return 0.0
    query_lower = query.lower()
    matched = sum(1 for kw in entry.keywords if kw.lower() in query_lower)
    denominator = min(len(entry.keywords), MAX_SCORE_DENOMINATOR)
    return min(matched, denominator) / denominator


def search_knowledge_base(sub_type: str, query: str, entries: list[KBEntry]) -> RetrievalResult:
    candidates = [e for e in entries if e.sub_type == sub_type]
    if not candidates:
        return RetrievalResult(hit_status="miss", matched_entry=None)

    scored = sorted(
        ((_score(query, e), e) for e in candidates),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best_score, best_entry = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0

    if best_score >= HIT_THRESHOLD and (best_score - second_score) >= HIT_MARGIN:
        return RetrievalResult(hit_status="hit", matched_entry=best_entry)
    if best_score >= PARTIAL_THRESHOLD:
        return RetrievalResult(hit_status="partial", matched_entry=best_entry)
    return RetrievalResult(hit_status="miss", matched_entry=None)
