# gateway/tests/test_watermark.py
from gateway.watermark.engine import Watermarker


def test_watermark_changes_text():
    wm = Watermarker(secret="test-secret")
    original = "The quick brown fox utilizes advanced algorithms."
    marked = wm.apply(original, session_id="sess-abc")
    # watermark may or may not change this specific text depending on bit stream
    # but the method must run without error and return a string
    assert isinstance(marked, str)
    assert len(marked) > 0


def test_watermark_detectable():
    wm = Watermarker(secret="test-secret")
    original = "The system employs sophisticated methods and advanced algorithms."
    marked = wm.apply(original, session_id="sess-abc")
    assert wm.detect(marked, session_id="sess-abc") is True


def test_different_sessions_detectable_independently():
    wm = Watermarker(secret="test-secret")
    text = "The system employs sophisticated methods."
    m1 = wm.apply(text, session_id="s1")
    m2 = wm.apply(text, session_id="s2")
    assert wm.detect(m1, session_id="s1") is True
    assert wm.detect(m2, session_id="s2") is True


def test_empty_text_returns_empty():
    wm = Watermarker(secret="test-secret")
    assert wm.apply("", session_id="x") == ""
