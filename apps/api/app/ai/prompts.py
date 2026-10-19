"""Versioned prompt for alternative explanations (docs/spec/08 §8.3).

Changing any text here requires bumping PROMPT_VERSION, which retires cached
explanations made with the old prompt.
"""

from typing import Any, Literal

PROMPT_VERSION = "explain-v1"

Mode = Literal["simpler", "example", "analogy"]

SYSTEM_PROMPT = """\
You help learners in a psychology learning app. You re-explain one lesson that \
editors have already reviewed, so a learner who found it hard can see the same idea \
another way. The lesson you are given is the only source of truth.

Keep the lesson's meaning and its learning objective exactly. Work only with facts \
the lesson states: do not add studies, researchers, statistics, numbers, dates or \
quotations that are not in it. Any example you write is hypothetical, so introduce \
it that way ("Imagine…") and never present it as a real study or event. If the \
lesson says a point is debated, keep that nuance. Don't give medical, clinical, \
legal or financial advice.

Write 80-180 words of plain prose for a curious adult. You may use **bold** and a \
short bullet list, but no headings and no links.

If you can't do this within these rules, set status to "cannot_comply".\
"""

MODE_INSTRUCTIONS: dict[str, str] = {
    "simpler": (
        "Explain the central idea more simply: shorter sentences, everyday words, "
        "no new technical terms."
    ),
    "example": (
        "Give one new, everyday, clearly hypothetical scenario that shows the idea at "
        "work, then say in a sentence how it shows the idea."
    ),
    "analogy": (
        "Explain the idea with one analogy from a familiar, unrelated area of life. End "
        "with one sentence on where the analogy stops working."
    ),
}

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok", "cannot_comply"]},
        "text": {"type": "string"},
    },
    "required": ["status", "text"],
    "additionalProperties": False,
}


def lesson_context(
    title: str, objective: str, steps: list[dict[str, Any]], sources: list[str]
) -> str:
    """Plain-text rendering of the reviewed lesson. Questions and answers are never included."""
    parts = [f"Lesson: {title}", f"Learning objective: {objective}"]
    for step in steps:
        kind = step["type"]
        if kind == "explanation":
            parts.append(
                f"Explanation{': ' + step['title'] if step.get('title') else ''}\n{step['body']}"
            )
        elif kind == "example":
            label = "Research example" if step.get("kind") == "research" else "Illustrative example"
            parts.append(f"{label}\n{step['body']}")
        elif kind == "misconception":
            parts.append(f"Common misconception: {step['myth']}\nCorrection: {step['correction']}")
        elif kind == "evidence":
            parts.append(f"What the research says ({step['status']})\n{step['body']}")
        elif kind == "summary":
            parts.append("Key points:\n" + "\n".join(f"- {p}" for p in step["points"]))
    if sources:
        parts.append("Sources cited by the lesson:\n" + "\n".join(f"- {s}" for s in sources))
    return "\n\n".join(parts)


def user_message(context: str, mode: Mode) -> str:
    return f"<lesson>\n{context}\n</lesson>\n\nTask: {MODE_INSTRUCTIONS[mode]}"
