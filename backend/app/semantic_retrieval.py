import math

from app.llm_client import LLMClientProtocol
from app.schemas import KBEntry, RetrievalResult

# UNVALIDATED placeholder, not a calibrated value: these numbers were
# picked to make the synthetic test vectors in test_semantic_retrieval.py
# produce the hit/partial/miss result each test names — the tests were
# written to fit the thresholds, not the other way around. No real
# embeddings provider is available to call from this environment without
# spending the user's own key. Real providers can have very different
# absolute cosine-similarity ranges (e.g. OpenAI's text-embedding-3-small
# commonly scores paraphrases in the 0.5-0.75 band, which would mostly
# land as "partial" here, not "hit") — these MUST be re-measured against
# whatever provider is actually configured before trusting this path.
SEMANTIC_HIT_THRESHOLD = 0.75
SEMANTIC_HIT_MARGIN = 0.05
SEMANTIC_PARTIAL_THRESHOLD = 0.5

_CORPUS_CACHE: dict[tuple[str, str], dict[str, list[float]]] = {}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_corpus_embeddings(
    candidates: list[KBEntry], llm: LLMClientProtocol, base_url: str, embedding_model: str
) -> dict[str, list[float]]:
    cache_key = (base_url, embedding_model)
    cached = _CORPUS_CACHE.setdefault(cache_key, {})
    missing = [e for e in candidates if e.id not in cached]
    if missing:
        vectors = llm.embed([e.question_topic for e in missing], embedding_model)
        for entry, vector in zip(missing, vectors):
            cached[entry.id] = vector
    return cached


def search_knowledge_base_semantic(
    sub_type: str,
    query: str,
    entries: list[KBEntry],
    llm: LLMClientProtocol,
    base_url: str,
    embedding_model: str,
) -> RetrievalResult:
    candidates = [e for e in entries if e.sub_type == sub_type]
    if not candidates:
        return RetrievalResult(hit_status="miss", matched_entry=None)

    corpus = _get_corpus_embeddings(candidates, llm, base_url, embedding_model)
    query_vector = llm.embed([query], embedding_model)[0]

    scored = sorted(
        ((_cosine_similarity(query_vector, corpus[e.id]), e) for e in candidates),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best_score, best_entry = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0

    if best_score >= SEMANTIC_HIT_THRESHOLD and (best_score - second_score) >= SEMANTIC_HIT_MARGIN:
        return RetrievalResult(hit_status="hit", matched_entry=best_entry)
    if best_score >= SEMANTIC_PARTIAL_THRESHOLD:
        return RetrievalResult(hit_status="partial", matched_entry=best_entry)
    return RetrievalResult(hit_status="miss", matched_entry=None)
