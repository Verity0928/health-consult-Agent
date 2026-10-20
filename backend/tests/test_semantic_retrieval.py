import pytest

import app.semantic_retrieval as semantic_retrieval
from app.semantic_retrieval import search_knowledge_base_semantic
from app.schemas import KBEntry
from tests.fakes import FakeLLMClient


@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    # The corpus cache is process-global by design (it survives across
    # requests in the real server). Clear it between tests so one test's
    # cached corpus doesn't silently satisfy another test's "first call"
    # assumption.
    semantic_retrieval._CORPUS_CACHE.clear()


def _entry(id_, sub_type, topic):
    return KBEntry(id=id_, sub_type=sub_type, question_topic=topic, answer_body="x", source_note="演示数据")


def test_miss_when_no_entries_for_sub_type_never_calls_embed():
    llm = FakeLLMClient()
    result = search_knowledge_base_semantic("department_triage", "随便问点什么", [], llm, "https://fake.test/v1", "m")
    assert result.hit_status == "miss"
    assert result.matched_entry is None
    assert llm.embed_calls == []


def test_hit_when_query_vector_closely_matches_one_candidate():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0], [0.0, 1.0]])  # corpus: entry a, entry b
    llm.queue_embeddings([[0.99, 0.01]])             # query — nearly identical to entry a
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾"),
               _entry("b", "lifestyle_education", "血糖日常怎么监测")]
    result = search_knowledge_base_semantic("lifestyle_education", "钾元素从哪里补", entries, llm, "https://fake.test/v1", "m")
    assert result.hit_status == "hit"
    assert result.matched_entry.id == "a"


def test_partial_when_query_vector_is_only_loosely_related():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0]])
    llm.queue_embeddings([[0.6, 0.8]])  # cosine sim ≈ 0.6 — above PARTIAL, below HIT
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾")]
    result = search_knowledge_base_semantic("lifestyle_education", "随便问点别的", entries, llm, "https://fake.test/v1", "m")
    assert result.hit_status == "partial"


def test_miss_when_query_vector_is_unrelated_to_every_candidate():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0]])
    llm.queue_embeddings([[0.0, 1.0]])  # orthogonal — cosine sim 0
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾")]
    result = search_knowledge_base_semantic("lifestyle_education", "完全不相关的问题", entries, llm, "https://fake.test/v1", "m")
    assert result.hit_status == "miss"


def test_corpus_embeddings_are_cached_across_calls_with_the_same_base_url_and_model():
    llm = FakeLLMClient()
    llm.queue_embeddings([[1.0, 0.0]])   # corpus — only computed once, on the first call
    llm.queue_embeddings([[1.0, 0.0]])   # call 1's query
    llm.queue_embeddings([[1.0, 0.0]])   # call 2's query (no second corpus batch queued — proves it's not refetched)
    entries = [_entry("a", "lifestyle_education", "哪些食物富含钾")]
    search_knowledge_base_semantic("lifestyle_education", "第一次提问", entries, llm, "https://fake.test/v1", "m")
    search_knowledge_base_semantic("lifestyle_education", "第二次提问", entries, llm, "https://fake.test/v1", "m")
    # Without caching this would be 4 calls (corpus + query, twice over).
    # With caching: 1 corpus call (first search only) + 1 query call per search = 3.
    assert len(llm.embed_calls) == 3
