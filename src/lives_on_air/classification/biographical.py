from __future__ import annotations

import re


ENGLISH_PATTERNS = [
    r"\blife of\b",
    r"\blives of\b",
    r"\bbiograph(?:y|ical)\b",
    r"\bautobiograph(?:y|ical)\b",
    r"\bportrait(?: of)?\b",
    r"\bmemoir\b",
    r"\bdiar(?:y|ies)\b",
    r"\bletters(?: of)?\b",
    r"\bbased on the life\b",
]

GERMAN_PATTERNS = [
    r"\bleben\b",
    r"\bbiograph(?:ie|isch)\b",
    r"\bautobiograph(?:ie|isch)\b",
    r"\bportr[aä]t\b",
    r"\btagebuch\b",
    r"\bbriefe\b",
    r"\berinnerungen\b",
]


COMPILED_PATTERNS = [
    re.compile(pattern, flags=re.IGNORECASE) for pattern in ENGLISH_PATTERNS + GERMAN_PATTERNS
]


def biographical_score(text: str) -> int:
    return sum(1 for pattern in COMPILED_PATTERNS if pattern.search(text or ""))


def biographical_label(text: str) -> str:
    score = biographical_score(text)
    if score >= 2:
        return "high_confidence_biographical"
    if score == 1:
        return "possible_biographical"
    return "not_biographical"
