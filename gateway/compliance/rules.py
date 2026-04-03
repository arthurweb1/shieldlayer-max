# gateway/compliance/rules.py
import re
from dataclasses import dataclass


@dataclass
class Rule:
    article: str
    pattern: re.Pattern
    description: str


RULES: list[Rule] = [
    Rule(
        article="Art.5",
        pattern=re.compile(
            r"\b(subliminal\w*|manipulat\w*|exploit\w*\s+\w*vulnerabilit\w*|"
            r"social.?credit|biometric.?categori[sz]\w*|real.?time.?biometric\w*)",
            re.IGNORECASE,
        ),
        description="Prohibited AI practice (Art. 5 EU AI Act)",
    ),
    Rule(
        article="Art.10",
        pattern=re.compile(
            r"\b(personal.?data|training.?data\w*\s+\w*(bias\w*|discriminat\w*)|"
            r"sensitive.?categor\w*)",
            re.IGNORECASE,
        ),
        description="Data governance concern (Art. 10 EU AI Act)",
    ),
    Rule(
        article="Art.12",
        pattern=re.compile(
            r"\bI\s+am\s+a\s+(human|person|advisor|consultant|doctor|lawyer)\b",
            re.IGNORECASE,
        ),
        description="Missing AI transparency disclosure (Art. 12 EU AI Act)",
    ),
]
