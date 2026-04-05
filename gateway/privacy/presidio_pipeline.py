from __future__ import annotations

import json
import uuid
from typing import Any

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


_SUPPORTED_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "URL",
    "LOCATION",
    "DATE_TIME",
    "NRP",
    "MEDICAL_LICENSE",
    "US_SSN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "UK_NHS",
    "CRYPTO",
    "US_BANK_NUMBER",
    "AU_ABN",
    "AU_ACN",
    "AU_TFN",
    "AU_MEDICARE",
]


class PrivacyPipeline:
    def __init__(self) -> None:
        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()

    def redact(self, text: str) -> tuple[str, dict[str, str]]:
        results = self._analyzer.analyze(
            text=text,
            entities=_SUPPORTED_ENTITIES,
            language="en",
        )

        entity_map: dict[str, str] = {}
        operators: dict[str, OperatorConfig] = {}

        for result in results:
            short_id = uuid.uuid4().hex[:8]
            placeholder = f"[{result.entity_type}_{short_id}]"
            original = text[result.start:result.end]
            entity_map[placeholder] = original
            operators[result.entity_type] = OperatorConfig(
                "replace", {"new_value": placeholder}
            )

        if not results:
            return text, {}

        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        return anonymized.text, entity_map

    def restore(self, text: str, entity_map: dict[str, str]) -> str:
        for placeholder, original in entity_map.items():
            text = text.replace(placeholder, original)
        return text

    def redact_json(self, body: bytes) -> tuple[bytes, dict[str, str]]:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            redacted_text, entity_map = self.redact(body.decode("utf-8", errors="replace"))
            return redacted_text.encode("utf-8"), entity_map

        combined_map: dict[str, str] = {}

        def _process(node: Any) -> Any:
            if isinstance(node, str):
                redacted, partial_map = self.redact(node)
                combined_map.update(partial_map)
                return redacted
            if isinstance(node, dict):
                return {k: _process(v) for k, v in node.items()}
            if isinstance(node, list):
                return [_process(item) for item in node]
            return node

        redacted_payload = _process(payload)
        return json.dumps(redacted_payload).encode("utf-8"), combined_map
