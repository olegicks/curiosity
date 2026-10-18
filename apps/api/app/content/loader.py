"""Load and validate a content directory (docs/spec/03 §3.1, §3.3).

Layout::

    content/subjects.yaml
    content/sources.yaml
    content/<subject>/<topic>/<slug>.yaml
    content/media/<slug>/<file>.png|webp
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.content.rules import lesson_problems, lesson_warnings
from app.content.schema import (
    ExplanationStep,
    HookStep,
    LessonFile,
    SourceIn,
    SourcesFile,
    SubjectIn,
    SubjectsFile,
)

MEDIA_MAX_BYTES = 300 * 1024


@dataclass
class ContentSet:
    root: Path
    subjects: list[SubjectIn] = field(default_factory=list)
    sources: dict[str, SourceIn] = field(default_factory=dict)
    lessons: list[LessonFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class ContentValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} content error(s)")


def content_hash(lesson: LessonFile) -> str:
    canonical = json.dumps(lesson.content_payload(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _read_yaml(path: Path, errors: list[str]) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{path}: cannot read YAML ({exc.__class__.__name__})")
        return None


def _parse[M: BaseModel](model: type[M], data: Any, where: str, errors: list[str]) -> M | None:
    try:
        return model.model_validate(data)
    except PydanticValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"])
            errors.append(f"{where}: {loc}: {err['msg']}")
        return None


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def load_content(root: Path, *, today: date) -> ContentSet:
    """Parse every file and run all rules. Never raises for content problems."""
    cs = ContentSet(root=root)
    if not root.is_dir():
        cs.errors.append(f"{root}: content directory not found")
        return cs

    subjects_file = _parse(
        SubjectsFile, _read_yaml(root / "subjects.yaml", cs.errors), "subjects.yaml", cs.errors
    )
    if subjects_file:
        cs.subjects = subjects_file.subjects
    sources_file = _parse(
        SourcesFile, _read_yaml(root / "sources.yaml", cs.errors), "sources.yaml", cs.errors
    )
    if sources_file:
        for source in sources_file.sources:
            if source.key in cs.sources:
                cs.errors.append(f"sources.yaml: duplicate source key {source.key!r}")
            cs.sources[source.key] = source

    _check_subjects(cs)
    topics = {(s.slug, t.slug) for s in cs.subjects for t in s.topics}

    for path in sorted(root.glob("*/*/*.yaml")):
        where = _rel(path, root)
        if where.startswith("media/"):
            continue
        lesson = _parse(LessonFile, _read_yaml(path, cs.errors), where, cs.errors)
        if lesson is None:
            continue
        expected = (lesson.subject, lesson.topic, lesson.slug)
        if tuple(path.relative_to(root).with_suffix("").parts) != expected:
            cs.errors.append(f"{where}: file must live at {'/'.join(expected)}.yaml")
        if (lesson.subject, lesson.topic) not in topics:
            cs.errors.append(f"{where}: unknown subject/topic {lesson.subject}/{lesson.topic}")
        for problem in lesson_problems(lesson):
            cs.errors.append(f"{where}: {problem}")
        for warning in lesson_warnings(lesson, today):
            cs.warnings.append(f"{where}: {warning}")
        for ref in lesson.sources:
            if ref.key not in cs.sources:
                cs.errors.append(f"{where}: unknown source {ref.key!r}")
        _check_media(cs, lesson, where)
        cs.lessons.append(lesson)

    _check_cross_lesson(cs)
    return cs


def _check_subjects(cs: ContentSet) -> None:
    subject_slugs = [s.slug for s in cs.subjects]
    if len(set(subject_slugs)) != len(subject_slugs):
        cs.errors.append("subjects.yaml: duplicate subject slugs")
    # Topic slugs are used alone in the API (interests, filters), so keep them globally unique.
    topic_slugs = [t.slug for s in cs.subjects for t in s.topics]
    if len(set(topic_slugs)) != len(topic_slugs):
        cs.errors.append("subjects.yaml: topic slugs must be unique across all subjects")


def _check_media(cs: ContentSet, lesson: LessonFile, where: str) -> None:
    for step in lesson.steps:
        if isinstance(step, HookStep | ExplanationStep) and step.image:
            path = cs.root / "media" / lesson.slug / step.image.file
            if not path.is_file():
                cs.errors.append(f"{where}: missing image media/{lesson.slug}/{step.image.file}")
            elif path.stat().st_size > MEDIA_MAX_BYTES:
                cs.errors.append(f"{where}: image {step.image.file} exceeds 300 KB")


def _check_cross_lesson(cs: ContentSet) -> None:
    by_slug: dict[str, LessonFile] = {}
    ids: set[str] = set()
    for lesson in cs.lessons:
        if lesson.slug in by_slug:
            cs.errors.append(f"duplicate lesson slug {lesson.slug!r}")
        if str(lesson.id) in ids:
            cs.errors.append(f"duplicate lesson id {lesson.id}")
        by_slug[lesson.slug] = lesson
        ids.add(str(lesson.id))

    for lesson in cs.lessons:
        for kind, refs in (("related", lesson.related), ("prerequisite", lesson.prerequisites)):
            for slug in refs:
                if slug not in by_slug:
                    cs.errors.append(f"{lesson.slug}: unknown {kind} lesson {slug!r}")

    # prerequisite cycles (depth-first search with colouring)
    state: dict[str, int] = {}  # 1 = visiting, 2 = done

    def visit(slug: str, trail: list[str]) -> None:
        state[slug] = 1
        for nxt in by_slug[slug].prerequisites:
            if nxt not in by_slug:
                continue
            if state.get(nxt) == 1:
                cycle = [*trail[trail.index(nxt) :], nxt] if nxt in trail else [slug, nxt]
                cs.errors.append(f"prerequisite cycle: {' -> '.join(cycle)}")
            elif state.get(nxt) is None:
                visit(nxt, [*trail, nxt])
        state[slug] = 2

    for slug in by_slug:
        if state.get(slug) is None:
            visit(slug, [slug])
