import hashlib
import pytest
from app.engine.shield import ShieldEngine


@pytest.fixture
def shield(tmp_path):
    # Write a minimal synonym pairs file for testing
    import json
    pairs_file = tmp_path / "pairs.json"
    pairs_file.write_text(json.dumps({"pairs": [
        ["however", "nevertheless"], ["utilize", "use"], ["obtain", "get"],
        ["therefore", "thus"], ["additionally", "furthermore"],
        ["significant", "important"], ["demonstrate", "show"],
        ["regarding", "concerning"], ["approximately", "about"],
        ["indicates", "shows"], ["requires", "needs"], ["provides", "offers"],
        ["ensures", "guarantees"], ["implement", "apply"], ["sufficient", "enough"],
        ["prior to", "before"], ["subsequent to", "after"], ["in order to", "to"],
        ["in addition", "also"], ["as a result", "consequently"],
        ["due to", "because of"], ["with respect to", "about"],
        ["in the event that", "if"], ["at this point", "now"],
        ["make use of", "use"], ["take into account", "consider"],
        ["carry out", "perform"], ["in spite of", "despite"],
        ["as well as", "and"], ["a number of", "several"],
        ["a large number of", "many"], ["in many cases", "often"],
        ["at the present time", "currently"], ["for the purpose of", "to"],
        ["in the near future", "soon"], ["on the other hand", "conversely"],
        ["in contrast", "but"], ["in particular", "specifically"],
        ["with regard to", "on"], ["in terms of", "regarding"],
        ["a great deal of", "much"], ["on a regular basis", "regularly"],
        ["in the majority of", "most"], ["in the absence of", "without"],
        ["in conjunction with", "with"], ["in accordance with", "per"],
        ["in the context of", "within"], ["as opposed to", "rather than"],
        ["in light of", "given"], ["be aware of", "know"],
        ["make sure", "ensure"], ["find out", "discover"],
        ["set up", "establish"], ["look into", "investigate"]
    ]}))
    return ShieldEngine(synonym_pairs_path=str(pairs_file))


def test_mask_detects_person_name(shield):
    text = "Please help Max Mustermann with his account."
    result = shield.mask(text)
    assert "Max Mustermann" not in result.masked_text
    assert "PERSON_" in result.masked_text


def test_mask_detects_email(shield):
    text = "Contact us at max@example.com for support."
    result = shield.mask(text)
    assert "max@example.com" not in result.masked_text


def test_deanonymize_restores_original(shield):
    text = "Max Mustermann has IBAN DE89370400440532013000"
    result = shield.mask(text)
    restored = shield.deanonymize(result.masked_text, result.mapping)
    assert "Max Mustermann" in restored


def test_mask_returns_empty_mapping_when_no_pii(shield):
    text = "The weather is nice today."
    result = shield.mask(text)
    assert result.mapping == {}


def test_watermark_is_deterministic_for_same_seed(shield):
    text = "We should utilize this approach. However the results indicate significant improvement."
    result1 = shield.watermark(text, request_id="req-abc")
    result2 = shield.watermark(text, request_id="req-abc")
    assert result1 == result2


def test_watermark_returns_string(shield):
    result = shield.watermark("Short text.", request_id="req-xyz")
    assert isinstance(result, str)
    assert len(result) > 0


def test_watermark_seed_from_request_id():
    seed = int(hashlib.sha256("req-abc".encode()).hexdigest()[:8], 16)
    assert seed > 0


def test_mask_two_persons_get_different_pseudonyms(shield):
    text = "Alice called Bob about the contract."
    result = shield.mask(text)
    assert "Alice" not in result.masked_text
    assert "Bob" not in result.masked_text
    # Both should be masked with different pseudonyms
    assert len(result.mapping) == 2
    pseudonyms = list(result.mapping.keys())
    assert pseudonyms[0] != pseudonyms[1]


def test_mask_email_gets_email_pseudonym(shield):
    text = "Contact max@example.com for support."
    result = shield.mask(text)
    assert "max@example.com" not in result.masked_text
    assert any("EMAIL_" in k for k in result.mapping.keys())
