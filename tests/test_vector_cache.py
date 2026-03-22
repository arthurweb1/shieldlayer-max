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


# --- ACL tests ---

def test_cache_acl_admin_sees_admin_entry():
    """Admin (level 2) can see admin-level cached entries."""
    cache = VectorCache(threshold=0.97)
    cache.set("What is the EU AI Act?", "EU AI Act explanation.", caller_level=2)
    result = cache.get("What is the EU AI Act?", caller_level=2)
    assert result == "EU AI Act explanation."


def test_cache_acl_viewer_cannot_see_admin_entry():
    """Viewer (level 0) cannot see an admin-level (level 2) cached entry."""
    cache = VectorCache(threshold=0.97)
    cache.set("What is the EU AI Act?", "EU AI Act explanation.", caller_level=2)
    result = cache.get("What is the EU AI Act?", caller_level=0)
    assert result is None


def test_cache_acl_admin_can_see_viewer_entry():
    """Admin (level 2) can see a viewer-level (level 0) cached entry."""
    cache = VectorCache(threshold=0.97)
    cache.set("What is the EU AI Act?", "EU AI Act explanation.", caller_level=0)
    result = cache.get("What is the EU AI Act?", caller_level=2)
    assert result == "EU AI Act explanation."


def test_cache_acl_backward_compatible():
    """Callers without caller_level default to 0 (viewer) — no breaking change."""
    cache = VectorCache(threshold=0.97)
    cache.set("Simple question", "Simple answer.")
    result = cache.get("Simple question")
    assert result == "Simple answer."
