from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal


@dataclass
class ComplianceRule:
    article: str
    description: str
    check: Callable[[dict], bool]
    severity: Literal["block", "warn", "log"]


def _get_text_corpus(payload: dict) -> str:
    """Flatten relevant text fields from a request payload into a single lowercase string."""
    parts: list[str] = []
    messages = payload.get("messages", [])
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and isinstance(block.get("text"), str):
                            parts.append(block["text"])
    system = payload.get("system", "")
    if isinstance(system, str):
        parts.append(system)
    prompt = payload.get("prompt", "")
    if isinstance(prompt, str):
        parts.append(prompt)
    return " ".join(parts).lower()


_SUBLIMINAL_PATTERNS = re.compile(
    r"(subliminal|below conscious|unconscious(ly)?|without (their |the user.s )?awareness"
    r"|imperceptib(le|ly)|hidden suggestion|covert (persuasion|influence|manipulat))",
    re.IGNORECASE,
)

_VULNERABILITY_PATTERNS = re.compile(
    r"(target(ing)?\s+(children|minors|elderly|disabled|low.income|vulnerable|impoverished)"
    r"|exploit(ing)?\s+(age|disability|mental|cognitive|financial\s+vulnerability)"
    r"|manipulat\w+\s+(due\s+to\s+)?(age|disability|poverty|mental illness))",
    re.IGNORECASE,
)

_SOCIAL_SCORING_PATTERNS = re.compile(
    r"(social\s+scor(e|ing)|citizen\s+score|rank\s+individuals?\s+by"
    r"|government.+score|public\s+authorit\w+.+(rank|score|rate)\s+people"
    r"|state.backed\s+(scoring|ranking)|civic\s+credit\s+score)",
    re.IGNORECASE,
)

_BIOMETRIC_PATTERNS = re.compile(
    r"(unverified\s+biometric|raw\s+biometric|biometric\s+data\s+(without|lacking)"
    r"|facial\s+recognition\s+data\s+from|fingerprint\s+dataset\s+(unverified|unlabeled))",
    re.IGNORECASE,
)


def _check_subliminal(payload: dict) -> bool:
    return bool(_SUBLIMINAL_PATTERNS.search(_get_text_corpus(payload)))


def _check_vulnerability_exploitation(payload: dict) -> bool:
    return bool(_VULNERABILITY_PATTERNS.search(_get_text_corpus(payload)))


def _check_social_scoring(payload: dict) -> bool:
    corpus = _get_text_corpus(payload)
    if not _SOCIAL_SCORING_PATTERNS.search(corpus):
        return False
    authority_markers = re.search(
        r"(government|municipal|federal|state|public\s+authorit|ministry|agency|council)",
        corpus,
        re.IGNORECASE,
    )
    return bool(authority_markers)


def _check_biometric_data_quality(payload: dict) -> bool:
    return bool(_BIOMETRIC_PATTERNS.search(_get_text_corpus(payload)))


def _check_audit_metadata(payload: dict) -> bool:
    # Audit metadata enforcement is handled externally by ForensicAudit;
    # this rule always passes at the request level.
    return False


EU_AI_ACT_RULES: list[ComplianceRule] = [
    ComplianceRule(
        article="Art 5.1(a)",
        description=(
            "Prohibition on AI systems that deploy subliminal techniques beyond a person's "
            "consciousness to materially distort behaviour in a manner causing harm."
        ),
        check=_check_subliminal,
        severity="block",
    ),
    ComplianceRule(
        article="Art 5.1(b)",
        description=(
            "Prohibition on AI systems that exploit vulnerabilities of specific groups due to "
            "age, disability, or socioeconomic circumstances to distort behaviour."
        ),
        check=_check_vulnerability_exploitation,
        severity="block",
    ),
    ComplianceRule(
        article="Art 5.1(c)",
        description=(
            "Prohibition on AI systems used by public authorities for social scoring of natural "
            "persons that leads to detrimental treatment."
        ),
        check=_check_social_scoring,
        severity="block",
    ),
    ComplianceRule(
        article="Art 10.2",
        description=(
            "Training data quality requirements — flag requests that reference processing of "
            "unverified biometric datasets without documented provenance."
        ),
        check=_check_biometric_data_quality,
        severity="warn",
    ),
    ComplianceRule(
        article="Art 12.1",
        description=(
            "Record-keeping obligation — audit metadata must accompany all high-risk AI "
            "system interactions. Enforced externally by ForensicAudit."
        ),
        check=_check_audit_metadata,
        severity="log",
    ),
]
