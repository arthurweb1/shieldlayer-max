from __future__ import annotations

import json
from dataclasses import dataclass, field

import spacy

from gateway.guardian.eu_ai_act import EU_AI_ACT_RULES, ComplianceRule


@dataclass
class ComplianceResult:
    compliant: bool
    violations: list[dict] = field(default_factory=list)
    risk_score: float = 0.0


_SEVERITY_WEIGHTS: dict[str, float] = {
    "block": 1.0,
    "warn": 0.4,
    "log": 0.1,
}

_COMPLIANCE_NOTICE_CHUNK = (
    b"data: {\"choices\":[{\"delta\":{\"content\":\"[RESPONSE BLOCKED: EU AI Act compliance violation]\"},"
    b"\"finish_reason\":null}]}\n\n"
)


class GuardianJudge:
    def __init__(self) -> None:
        self._rules: list[ComplianceRule] = EU_AI_ACT_RULES
        try:
            self._nlp = spacy.load("en_core_web_lg")
        except OSError:
            self._nlp = spacy.blank("en")

    async def evaluate(self, body: bytes) -> ComplianceResult:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        violations: list[dict] = []
        for rule in self._rules:
            try:
                triggered = rule.check(payload)
            except Exception:
                triggered = False

            if triggered:
                violations.append(
                    {
                        "article": rule.article,
                        "description": rule.description,
                        "severity": rule.severity,
                    }
                )

        risk_score = self._score_risk(violations)
        has_block = any(v["severity"] == "block" for v in violations)

        return ComplianceResult(
            compliant=not has_block,
            violations=violations,
            risk_score=risk_score,
        )

    async def filter_chunk(self, chunk: bytes) -> bytes:
        if not chunk.startswith(b"data:"):
            return chunk

        payload_bytes = chunk[len(b"data:"):].strip()
        if payload_bytes in (b"[DONE]", b""):
            return chunk

        try:
            payload = json.loads(payload_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return chunk

        for rule in self._rules:
            if rule.severity != "block":
                continue
            try:
                triggered = rule.check(payload)
            except Exception:
                triggered = False

            if triggered:
                return _COMPLIANCE_NOTICE_CHUNK

        return chunk

    def _score_risk(self, violations: list[dict]) -> float:
        raw = sum(_SEVERITY_WEIGHTS.get(v["severity"], 0.0) for v in violations)
        return min(1.0, max(0.0, raw))
