# gateway/watermark/engine.py
import hashlib
import re

# Synonym pairs: (form_a, form_b)
# Each word appears at most once across all pairs to avoid substitution conflicts.
# apply() uses bit=1 to substitute form_a->form_b, bit=0 leaves text unchanged.
_SYNONYM_MAP: list[tuple[str, str]] = [
    ("uses", "utilizes"),
    ("employs", "applies"),
    ("shows", "demonstrates"),
    ("gets", "obtains"),
    ("helps", "assists"),
    ("makes", "creates"),
    ("fast", "rapid"),
    ("big", "large"),
    ("important", "significant"),
    ("advanced", "sophisticated"),
    ("method", "approach"),
    ("algorithm", "procedure"),
    ("needs", "requires"),
    ("starts", "initiates"),
    ("ends", "terminates"),
    ("changes", "modifies"),
    ("builds", "constructs"),
    ("checks", "verifies"),
    ("sends", "transmits"),
    ("stores", "persists"),
    ("reads", "retrieves"),
    ("runs", "executes"),
    ("stops", "halts"),
]


class Watermarker:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def _bit_stream(self, session_id: str, length: int) -> list[int]:
        """Deterministic pseudo-random bit stream keyed on secret + session_id."""
        seed = hashlib.sha256(f"{self._secret}:{session_id}".encode()).digest()
        bits: list[int] = []
        block = seed
        while len(bits) < length:
            bits.extend((b >> i) & 1 for b in block for i in range(8))
            block = hashlib.sha256(block).digest()
        return bits[:length]

    def apply(self, text: str, session_id: str) -> str:
        """Apply deterministic synonym substitution watermark."""
        if not text:
            return text
        bits = self._bit_stream(session_id, len(_SYNONYM_MAP))
        result = text
        for idx, (original, replacement) in enumerate(_SYNONYM_MAP):
            if bits[idx]:
                result = re.sub(
                    rf"\b{re.escape(original)}\b",
                    replacement,
                    result,
                    flags=re.IGNORECASE,
                )
        return result

    def detect(self, text: str, session_id: str) -> bool:
        """Return True if text carries the watermark signature for session_id."""
        bits = self._bit_stream(session_id, len(_SYNONYM_MAP))
        hits = 0
        checks = 0
        for idx, (form_a, form_b) in enumerate(_SYNONYM_MAP):
            a_present = bool(re.search(rf"\b{re.escape(form_a)}\b", text, re.IGNORECASE))
            b_present = bool(re.search(rf"\b{re.escape(form_b)}\b", text, re.IGNORECASE))
            if not a_present and not b_present:
                continue  # pair not relevant to this text
            checks += 1
            # bit=1 means form_a was replaced by form_b in apply(); expect form_b present
            # bit=0 means no substitution; expect form_a present (or neither changed)
            expected = form_b if bits[idx] else form_a
            if re.search(rf"\b{re.escape(expected)}\b", text, re.IGNORECASE):
                hits += 1

        if checks == 0:
            return True  # No applicable synonyms — trivially consistent
        return (hits / checks) >= 0.5
