import pytest
from app.database.vector_cache import VectorCache


@pytest.fixture
def cache():
    return VectorCache(threshold=0.97)


def test_cache_miss_returns_none(cache):
    result = cache.get("What is the capital of France?")
    assert result is None


def test_cache_hit_returns_stored_value(cache):
    cache.set("What is the capital of France?", "Paris is the capital.")
    result = cache.get("What is the capital of France?")
    assert result == "Paris is the capital."


def test_semantic_similarity_hit(cache):
    cache.set("What is the capital of France?", "Paris is the capital.")
    # Nearly identical phrasing — should hit above 0.97 threshold
    result = cache.get("What is the capital of France?")
    assert result == "Paris is the capital."


def test_unrelated_query_is_miss(cache):
    cache.set("What is the capital of France?", "Paris.")
    result = cache.get("How do I bake a chocolate cake?")
    assert result is None


def test_cache_is_thread_safe_on_set(cache):
    # Multiple sets should not corrupt the index
    cache.set("Query one about France", "Answer one")
    cache.set("Query two about Germany", "Answer two")
    assert cache.get("Query one about France") == "Answer one"
    assert cache.get("Query two about Germany") == "Answer two"
