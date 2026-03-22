import pytest
from unittest.mock import AsyncMock, patch
from app.engine.guardian import GuardianEngine, ComplianceResult, ComplianceError

COMPLIANT_JSON = '{"compliant": true, "reason": null, "article": null, "confidence": 0.98}'
NON_COMPLIANT_JSON = '{"compliant": false, "reason": "promotes illegal discrimination", "article": "Art. 5(1)(a)", "confidence": 0.95}'


@pytest.fixture
def guardian(test_settings):
    return GuardianEngine(
        base_url=test_settings.vllm_base_url,
        model=test_settings.vllm_guardian_model,
        max_retries=test_settings.guardian_max_retries,
    )


@pytest.mark.asyncio
async def test_compliant_response_passes(guardian):
    with patch.object(guardian, "_judge_call", new=AsyncMock(return_value=COMPLIANT_JSON)):
        result = await guardian.check("some prompt", "some response")
    assert result.compliant is True
    assert result.retries == 0


@pytest.mark.asyncio
async def test_noncompliant_raises_after_max_retries(guardian):
    with patch.object(guardian, "_judge_call", new=AsyncMock(return_value=NON_COMPLIANT_JSON)):
        with patch.object(guardian, "_correct_call", new=AsyncMock(return_value="")):
            with pytest.raises(ComplianceError) as exc_info:
                await guardian.check("some prompt", "bad response")
    assert "Art. 5(1)(a)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_self_correction_succeeds_on_first_correction(guardian):
    # Judge says non-compliant → correction call returns non-empty text → accepted
    with patch.object(guardian, "_judge_call", new=AsyncMock(return_value=NON_COMPLIANT_JSON)):
        with patch.object(guardian, "_correct_call", new=AsyncMock(return_value="better neutral response")):
            result = await guardian.check("prompt", "first response")
    assert result.compliant is True
    assert result.retries == 1


@pytest.mark.asyncio
async def test_malformed_judge_json_treated_as_noncompliant(guardian):
    with patch.object(guardian, "_judge_call", new=AsyncMock(return_value="not json at all")):
        with patch.object(guardian, "_correct_call", new=AsyncMock(return_value="")):
            with pytest.raises(ComplianceError):
                await guardian.check("prompt", "response")


@pytest.mark.asyncio
async def test_compliance_error_contains_article_ref(guardian):
    with patch.object(guardian, "_judge_call", new=AsyncMock(return_value=NON_COMPLIANT_JSON)):
        with patch.object(guardian, "_correct_call", new=AsyncMock(return_value="")):
            try:
                await guardian.check("prompt", "bad response")
            except ComplianceError as e:
                assert e.article == "Art. 5(1)(a)"
                assert "discrimination" in e.reason
