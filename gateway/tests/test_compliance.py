# gateway/tests/test_compliance.py
import pytest
from gateway.compliance.judge import GuardianJudge, ComplianceResult


@pytest.fixture
def judge():
    return GuardianJudge(max_rewrites=3)


def test_compliant_text_passes(judge):
    result = judge.check("Here is a summary of your financial report.")
    assert result.compliant is True
    assert result.violations == []


def test_art5_subliminal_flagged(judge):
    result = judge.check("This subliminal technique will manipulate your subconscious.")
    assert result.compliant is False
    assert any("Art.5" in v for v in result.violations)


def test_art5_social_scoring_flagged(judge):
    result = judge.check("Citizens with low social credit scores are restricted.")
    assert result.compliant is False


def test_art12_no_disclosure_flagged(judge):
    result = judge.check("I am a human advisor, not an AI system.")
    assert result.compliant is False
    assert any("Art.12" in v for v in result.violations)


@pytest.mark.asyncio
async def test_rewrite_called_on_violation(judge):
    async def fake_rewrite(text, violations):
        return "Compliant rewritten text."
    judge._rewrite = fake_rewrite
    output, rewrites = await judge.enforce("Manipulate users subliminally.")
    assert rewrites >= 1
    assert output == "Compliant rewritten text."
