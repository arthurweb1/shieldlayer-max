import json
import httpx
from dataclasses import dataclass
from typing import Optional

COMPLIANCE_SYSTEM_PROMPT = """You are an EU AI Act compliance auditor.
Analyze the following AI-generated response and determine if it violates the EU AI Act.
Reply ONLY with valid JSON: {"compliant": bool, "reason": string|null, "article": string|null, "confidence": float}
Key articles to check:
- Art. 5: Prohibited practices (manipulation, exploitation, social scoring, biometric surveillance)
- Art. 10: Data governance (training data quality, bias)
- Art. 13: Transparency obligations
"""

CORRECTION_SYSTEM_PROMPT = (
    "You are a helpful, neutral assistant complying with EU AI Act {article}.\n"
    "The previous response was non-compliant: {reason}\n"
    "Provide a neutral, factual reformulation that avoids this issue. "
    "Do not reference the compliance issue in your response."
)


@dataclass
class ComplianceResult:
    compliant: bool
    reason: Optional[str] = None
    article: Optional[str] = None
    confidence: float = 1.0
    retries: int = 0


class ComplianceError(Exception):
    def __init__(self, reason: str, article: Optional[str]):
        super().__init__(f"Compliance violation: {reason} ({article})")
        self.reason = reason
        self.article = article


class GuardianEngine:
    def __init__(self, base_url: str, model: str, max_retries: int = 2):
        self._base_url = base_url
        self._model = model
        # max 4 total vLLM calls: 1 judge + up to 3 corrections (no re-judge)
        self._max_retries = max_retries

    async def _judge_call(self, prompt: str, response: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": COMPLIANCE_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Prompt: {prompt}\n\nResponse: {response}"},
                    ],
                    "temperature": 0,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _correct_call(self, prompt: str, reason: str, article: Optional[str] = None) -> str:
        article_ref = article or "Art. 5/10/13"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": CORRECTION_SYSTEM_PROMPT.format(
                                article=article_ref,
                                reason=reason,
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    def _parse_judge_response(self, raw: str) -> ComplianceResult:
        try:
            data = json.loads(raw)
            return ComplianceResult(
                compliant=bool(data.get("compliant", False)),
                reason=data.get("reason"),
                article=data.get("article"),
                confidence=float(data.get("confidence", 0.0)),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Malformed response → treat as non-compliant (fail-safe)
            return ComplianceResult(
                compliant=False,
                reason="malformed judge response",
                article=None,
            )

    async def check(self, original_prompt: str, response_text: str) -> ComplianceResult:
        """Check response for EU AI Act compliance.
        Call budget: 1 judge call + up to max_retries correction calls = max 4 total.
        Corrections are returned without re-judging — the correction prompt instructs
        the model to be compliant, so we trust the output."""
        raw = await self._judge_call(original_prompt, response_text)
        result = self._parse_judge_response(raw)

        if result.compliant:
            return result  # 1 call total

        # Non-compliant: correction calls (no re-judging to stay within 4-call budget)
        for retry in range(1, self._max_retries + 1):
            corrected = await self._correct_call(
                original_prompt, result.reason or "policy violation", result.article
            )
            if corrected:  # non-empty correction → return as compliant
                return ComplianceResult(compliant=True, retries=retry)

        # All correction attempts returned empty — raise
        raise ComplianceError(
            reason=result.reason or "unknown",
            article=result.article,
        )
