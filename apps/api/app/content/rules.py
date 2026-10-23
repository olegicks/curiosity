"""Per-lesson rules that span fields (docs/spec/03 §3.2-3.3). Pure functions."""

from collections import Counter
from datetime import date, timedelta

from app.content.schema import (
    EvidenceStatus,
    EvidenceStep,
    ExampleStep,
    ExplanationStep,
    HookStep,
    LessonFile,
    LessonStatus,
    MisconceptionStep,
    QuestionIn,
    QuestionRole,
    QuestionStep,
    QuestionType,
    SummaryStep,
    word_count,
)

HOOK_MAX_WORDS = 80
EXPLANATION_MAX_WORDS = 220
SUMMARY_POINT_MAX_WORDS = 25
READING_WORDS_RANGE = (350, 1100)
REVIEW_STALE_AFTER = timedelta(days=365)


def _estimate_problems(q: QuestionIn) -> list[str]:
    e = q.estimate
    if e is None:
        return [f"question {q.key}: estimate needs an estimate block"]
    problems: list[str] = []
    if q.options:
        problems.append(f"question {q.key}: estimate questions have no options")
    if q.role is not QuestionRole.LESSON:
        problems.append(f"question {q.key}: estimate questions are lesson questions only")
    if not e.min < e.max:
        problems.append(f"question {q.key}: estimate min must be below max")
    if not e.min <= e.answer <= e.max:
        problems.append(f"question {q.key}: estimate answer must be within min-max")
    if e.anchor is not None and not e.min <= e.anchor <= e.max:
        problems.append(f"question {q.key}: estimate anchor must be within min-max")
    if e.step > e.max - e.min or e.tolerance >= e.max - e.min:
        problems.append(f"question {q.key}: estimate step and tolerance must fit the range")
    return problems


def question_problems(q: QuestionIn) -> list[str]:
    if q.type is QuestionType.ESTIMATE:
        return _estimate_problems(q)
    problems: list[str] = []
    if q.estimate is not None:
        problems.append(f"question {q.key}: only estimate questions take an estimate block")
    if len(q.options) < 2:
        problems.append(f"question {q.key}: needs at least 2 options")
    keys = [o.key for o in q.options]
    if len(set(keys)) != len(keys):
        problems.append(f"question {q.key}: duplicate option keys")
    correct = sum(o.correct for o in q.options)
    n = len(q.options)
    if q.type is QuestionType.SINGLE_CHOICE:
        if not 3 <= n <= 5:
            problems.append(f"question {q.key}: single_choice needs 3-5 options, has {n}")
        if correct != 1:
            problems.append(f"question {q.key}: single_choice needs exactly 1 correct option")
    elif q.type is QuestionType.MULTI_SELECT:
        if not 4 <= n <= 6:
            problems.append(f"question {q.key}: multi_select needs 4-6 options, has {n}")
        if correct < 2:
            problems.append(f"question {q.key}: multi_select needs at least 2 correct options")
        if correct == n:
            problems.append(f"question {q.key}: multi_select cannot have every option correct")
    elif q.type is QuestionType.TRUE_FALSE:
        if sorted(keys) != ["false", "true"]:
            problems.append(f"question {q.key}: true_false options must be keyed true/false")
        if correct != 1:
            problems.append(f"question {q.key}: true_false needs exactly 1 correct option")
    return problems


def lesson_problems(lesson: LessonFile) -> list[str]:
    """Structural rules; editorial requirements apply only to published lessons."""
    p: list[str] = []
    steps = lesson.steps
    by_type = Counter(s.type for s in steps)

    # step ordering and counts
    if not isinstance(steps[0], HookStep) or by_type["hook"] != 1:
        p.append("exactly one hook step is required and it must be first")
    if not isinstance(steps[-1], SummaryStep) or by_type["summary"] != 1:
        p.append("exactly one summary step is required and it must be last")
    if not 1 <= by_type["explanation"] <= 3:
        p.append("1-3 explanation steps are required")
    if not 1 <= by_type["example"] <= 3:
        p.append("1-3 example steps are required")
    if by_type["misconception"] < 1:
        p.append("at least one misconception step is required")
    if lesson.evidence_status is not EvidenceStatus.ESTABLISHED and by_type["evidence"] < 1:
        p.append("an evidence step is required when evidence_status is not 'established'")

    # word limits
    for step in steps:
        if isinstance(step, HookStep) and word_count(step.body) > HOOK_MAX_WORDS:
            p.append(f"hook exceeds {HOOK_MAX_WORDS} words")
        if isinstance(step, ExplanationStep) and word_count(step.body) > EXPLANATION_MAX_WORDS:
            p.append(f"explanation step exceeds {EXPLANATION_MAX_WORDS} words")
        if isinstance(step, SummaryStep):
            for point in step.points:
                if word_count(point) > SUMMARY_POINT_MAX_WORDS:
                    p.append(f"summary point exceeds {SUMMARY_POINT_MAX_WORDS} words")

    # sources referenced by steps must be listed on the lesson
    lesson_sources = {s.key for s in lesson.sources}
    if len(lesson_sources) != len(lesson.sources):
        p.append("duplicate source keys")
    for step in steps:
        if isinstance(step, ExampleStep):
            if step.kind == "research" and not step.source_key:
                p.append("research examples need a source_key")
            if step.source_key and step.source_key not in lesson_sources:
                p.append(f"example source {step.source_key!r} is not listed in sources")
        if isinstance(step, EvidenceStep):
            for key in step.source_keys:
                if key not in lesson_sources:
                    p.append(f"evidence source {key!r} is not listed in sources")

    # questions
    keys = [q.key for q in lesson.questions]
    if len(set(keys)) != len(keys):
        p.append("duplicate question keys")
    questions = {q.key: q for q in lesson.questions}
    for q in lesson.questions:
        p.extend(question_problems(q))

    lesson_qs = [q for q in lesson.questions if q.role is QuestionRole.LESSON]
    recall_qs = [q for q in lesson.questions if q.role is QuestionRole.RECALL]
    if not 2 <= len(lesson_qs) <= 4:
        p.append(f"2-4 lesson questions are required, found {len(lesson_qs)}")
    if len(recall_qs) < 4:
        p.append(f"at least 4 recall questions are required, found {len(recall_qs)}")
    for role, group in ((QuestionRole.LESSON, lesson_qs), (QuestionRole.RECALL, recall_qs)):
        if sum(q.type is QuestionType.TRUE_FALSE for q in group) > 1:
            p.append(f"at most one true_false question per role ({role.value})")
    lesson_prompts = {q.prompt.casefold() for q in lesson_qs}
    for q in recall_qs:
        if q.prompt.casefold() in lesson_prompts:
            p.append(f"recall question {q.key} duplicates a lesson question prompt")

    referenced = [s.question_key for s in steps if isinstance(s, QuestionStep)]
    for key, count in Counter(referenced).items():
        question = questions.get(key)
        if question is None:
            p.append(f"question step references unknown question {key!r}")
        elif question.role is not QuestionRole.LESSON:
            p.append(f"question step {key!r} must reference a lesson-role question")
        if count > 1:
            p.append(f"question {key!r} appears in more than one step")
    for q in lesson_qs:
        if q.key not in referenced:
            p.append(f"lesson question {q.key!r} is not placed in any step")

    if lesson.slug in lesson.related or lesson.slug in lesson.prerequisites:
        p.append("a lesson cannot reference itself")

    # editorial requirements for published lessons
    if lesson.status is LessonStatus.PUBLISHED:
        if lesson.last_reviewed_on is None:
            p.append("published lessons need last_reviewed_on")
        if len({r.casefold() for r in lesson.reviewers}) < 2:
            p.append("published lessons need an author and an independent reviewer")
        if not 1 <= len(lesson.related) <= 4:
            p.append("published lessons need 1-4 related lessons")
        if len(lesson.sources) < 2:
            p.append("published lessons need at least 2 sources")
    return p


def lesson_warnings(lesson: LessonFile, today: date) -> list[str]:
    w: list[str] = []
    if lesson.last_reviewed_on and today - lesson.last_reviewed_on > REVIEW_STALE_AFTER:
        w.append("last reviewed more than 12 months ago")
    recall = sum(q.role is QuestionRole.RECALL for q in lesson.questions)
    if recall < 5:
        w.append(f"only {recall} recall questions (target 5-6)")
    words = 0
    for step in lesson.steps:
        if isinstance(step, HookStep | ExplanationStep | ExampleStep):
            words += word_count(step.body)
        elif isinstance(step, MisconceptionStep):
            words += word_count(step.myth) + word_count(step.correction)
        elif isinstance(step, EvidenceStep):
            words += word_count(step.body)
        elif isinstance(step, SummaryStep):
            words += sum(word_count(point) for point in step.points)
    low, high = READING_WORDS_RANGE
    if not low <= words <= high:
        w.append(f"reading length {words} words is outside {low}-{high}")
    return w
