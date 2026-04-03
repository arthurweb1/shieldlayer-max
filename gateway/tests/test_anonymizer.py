# gateway/tests/test_anonymizer.py
import pytest
from gateway.anonymizer.engine import AnonymizerEngine


@pytest.fixture(scope="module")
def engine():
    return AnonymizerEngine()


def test_anonymize_person_name(engine):
    result = engine.anonymize("Hi, my name is John Doe.")
    assert "John Doe" not in result.text
    assert "PERSON_" in result.text
    assert len(result.mapping) >= 1


def test_anonymize_email(engine):
    result = engine.anonymize("Contact me at alice@example.com for details.")
    assert "alice@example.com" not in result.text
    assert len(result.mapping) >= 1


def test_anonymize_phone(engine):
    result = engine.anonymize("Call me at +1-800-555-0199.")
    assert "+1-800-555-0199" not in result.text


def test_deanonymize(engine):
    result = engine.anonymize("John Doe owes Jane Smith money.")
    restored = engine.deanonymize(result.text, result.mapping)
    assert "John Doe" in restored
    assert "Jane Smith" in restored


def test_empty_text_noop(engine):
    result = engine.anonymize("")
    assert result.text == ""
    assert result.mapping == {}
