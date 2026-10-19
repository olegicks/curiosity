"""Heuristic checks on generated explanations (docs/spec/08 §8.4). Pure functions.

This is a safety net, not proof of accuracy; labels and user flags back it up.
"""

import re

MIN_WORDS = 40
MAX_WORDS = 250

_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_MARKUP = re.compile(r"^\s{0,3}#|!?\[[^\]]*\]\([^)]*\)|</?[a-zA-Z][^>]*>", re.MULTILINE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*%?")
_CITATION_PHRASES = (
    "et al",
    "researchers found",
    "a study",
    "studies show",
    "according to",
    "research shows",
)
_BLOCKED_PHRASES = (
    "as an ai",
    "i cannot",
    "i can't",
    "diagnos",
    "medical advice",
    "financial advice",
    "legal advice",
    "see a doctor",
)


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def output_problem(text: str, lesson_text: str) -> str | None:
    """Return why ``text`` must not be shown, or None if it passes."""
    words = word_count(text)
    if words < MIN_WORDS:
        return "too_short"
    if words > MAX_WORDS:
        return "too_long"
    if _URL.search(text) or _EMAIL.search(text):
        return "link"
    if _MARKUP.search(text):
        return "markup"
    lesson_numbers = set(_NUMBER.findall(lesson_text))
    if any(n not in lesson_numbers for n in _NUMBER.findall(text)):
        return "unsupported_number"
    lowered, lesson_lowered = text.lower(), lesson_text.lower()
    for phrase in _CITATION_PHRASES:
        if phrase in lowered and phrase not in lesson_lowered:
            return "unsupported_citation"
    for phrase in _BLOCKED_PHRASES:
        if phrase in lowered:
            return "blocked_phrase"
    return None
