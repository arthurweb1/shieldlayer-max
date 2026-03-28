# gateway/anonymizer/engine.py
"""
PII Anonymizer Engine backed by Presidio pattern recognizers + a lightweight
person-name heuristic.

Presidio's spaCy NLP engine is not compatible with Python 3.14 (pydantic v1
forward-reference resolution is broken).  We therefore apply two minimal
monkey-patches to pydantic.v1 so that the Presidio *pattern* recognizers
(EmailRecognizer, PhoneRecognizer, etc.) can be loaded, while we substitute a
custom regex-based PERSON recognizer instead of SpacyRecognizer.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Python-3.14 / pydantic-v1 compatibility patches — applied before any import
# that transitively touches spacy.schemas (which uses forward-ref models).
# ---------------------------------------------------------------------------
import pydantic.v1.fields as _pv1f
import pydantic.v1.schema as _pv1s

_orig_prepare = _pv1f.ModelField.prepare
def _patched_prepare(self: _pv1f.ModelField) -> None:
    try:
        _orig_prepare(self)
    except Exception as exc:
        if "unable to infer type" in str(exc):
            from typing import Any
            self.type_ = Any
            self.outer_type_ = Any
            self.annotation = Any
        else:
            raise
_pv1f.ModelField.prepare = _patched_prepare

_orig_get_ann = _pv1s.get_annotation_from_field_info
def _patched_get_ann(annotation, field_info, field_name,
                     config_validate_assignment: bool = False):
    try:
        return _orig_get_ann(annotation, field_info, field_name,
                             config_validate_assignment)
    except ValueError:
        return annotation
_pv1s.get_annotation_from_field_info = _patched_get_ann
# ---------------------------------------------------------------------------

import re
from dataclasses import dataclass, field

from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    IbanRecognizer,
    IpRecognizer,
    PhoneRecognizer,
)
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer import RecognizerResult

# ---------------------------------------------------------------------------
# Entities to detect and anonymize
# ---------------------------------------------------------------------------
ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "IBAN_CODE",
    "CREDIT_CARD", "IP_ADDRESS",
]

# Module-level counters for sequential, deterministic placeholders
_ENTITY_COUNTERS: dict[str, int] = {}


def _placeholder(entity_type: str) -> str:
    """Return e.g. PERSON_001, EMAIL_002 …"""
    short = entity_type.split("_")[0]
    _ENTITY_COUNTERS[short] = _ENTITY_COUNTERS.get(short, 0) + 1
    return f"{short}_{_ENTITY_COUNTERS[short]:03d}"


# ---------------------------------------------------------------------------
# Lightweight person-name recognizer (no ML model required)
# ---------------------------------------------------------------------------
# Matches two or more consecutive Title-Case words, excluding common sentence
# starters that are not names.  Score is intentionally conservative (0.5) to
# reflect the heuristic nature of the rule.
_COMMON_NON_NAMES: frozenset[str] = frozenset({
    "The", "This", "That", "These", "Those", "My", "Your", "His", "Her",
    "Our", "Their", "Its", "We", "He", "She", "They", "You", "I",
    "Hi", "Hey", "Dear", "Hello", "Note", "Call", "Contact", "Please",
    "Thank", "Thanks", "Best", "Regards", "Sincerely", "From", "To",
    "Subject", "Re", "Fwd", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
})

_PERSON_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
)


def _detect_persons(text: str) -> list[RecognizerResult]:
    """Return RecognizerResult list for likely person names in *text*."""
    results: list[RecognizerResult] = []
    for m in _PERSON_RE.finditer(text):
        name = m.group(1)
        parts = name.split()
        # Skip if the first word is a known non-name or if any word is just one letter
        if parts[0] in _COMMON_NON_NAMES:
            continue
        if any(len(p) <= 1 for p in parts):
            continue
        results.append(
            RecognizerResult(
                entity_type="PERSON",
                start=m.start(),
                end=m.end(),
                score=0.5,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@dataclass
class AnonymizeResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original


class AnonymizerEngine:
    """
    Detect and replace PII entities with sequential placeholders.

    Uses Presidio pattern recognizers for rule-based entities and a regex
    heuristic for PERSON names.  Deanonymization reverses the mapping.
    """

    def __init__(self, spacy_model: str = "en_core_web_sm") -> None:
        # spacy_model parameter kept for API compatibility but not used here;
        # the Presidio NLP engine cannot load any spaCy model under Python 3.14.
        self._recognizers = [
            EmailRecognizer(),
            PhoneRecognizer(),
            IbanRecognizer(),
            CreditCardRecognizer(),
            IpRecognizer(),
        ]
        # Minimal stub so pattern recognizers that require nlp_artifacts work
        self._nlp_stub = NlpArtifacts(
            entities=[],
            tokens=[],
            tokens_indices=[],
            lemmas=[],
            nlp_engine=None,
            language="en",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_pattern_recognizers(self, text: str) -> list[RecognizerResult]:
        """Run all Presidio pattern recognizers and merge results."""
        entity_map = {
            EmailRecognizer: "EMAIL_ADDRESS",
            PhoneRecognizer: "PHONE_NUMBER",
            IbanRecognizer: "IBAN_CODE",
            CreditCardRecognizer: "CREDIT_CARD",
            IpRecognizer: "IP_ADDRESS",
        }
        all_results: list[RecognizerResult] = []
        for rec in self._recognizers:
            entity_type = entity_map[type(rec)]
            try:
                found = rec.analyze(
                    text,
                    entities=[entity_type],
                    nlp_artifacts=self._nlp_stub,
                )
                all_results.extend(found)
            except Exception:
                pass
        return all_results

    @staticmethod
    def _remove_overlaps(
        results: list[RecognizerResult],
    ) -> list[RecognizerResult]:
        """Keep highest-scoring non-overlapping spans; ties favour longer spans."""
        sorted_r = sorted(results, key=lambda r: (r.score, r.end - r.start), reverse=True)
        kept: list[RecognizerResult] = []
        for candidate in sorted_r:
            overlap = any(
                not (candidate.end <= k.start or candidate.start >= k.end)
                for k in kept
            )
            if not overlap:
                kept.append(candidate)
        return sorted(kept, key=lambda r: r.start)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------
    def anonymize(self, text: str, language: str = "en") -> AnonymizeResult:
        if not text.strip():
            return AnonymizeResult(text=text)

        person_results = _detect_persons(text)
        pattern_results = self._run_pattern_recognizers(text)
        all_results = self._remove_overlaps(person_results + pattern_results)

        if not all_results:
            return AnonymizeResult(text=text)

        mapping: dict[str, str] = {}
        # Replace spans from right to left to preserve indices
        out = text
        for r in sorted(all_results, key=lambda x: x.start, reverse=True):
            original = text[r.start:r.end]
            placeholder = _placeholder(r.entity_type)
            mapping[placeholder] = original
            out = out[: r.start] + placeholder + out[r.end:]

        return AnonymizeResult(text=out, mapping=mapping)

    def deanonymize(self, text: str, mapping: dict[str, str]) -> str:
        """Replace all placeholders back with their original values."""
        for placeholder, original in sorted(
            mapping.items(), key=lambda kv: len(kv[0]), reverse=True
        ):
            text = text.replace(placeholder, original)
        return text
