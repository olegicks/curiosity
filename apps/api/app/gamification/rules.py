"""XP amounts, idempotency keys and the achievement registry (docs/spec/07 §7.4, §7.6)."""

import uuid
from dataclasses import dataclass
from enum import StrEnum


class XpReason(StrEnum):
    LESSON_COMPLETE = "lesson_complete"
    LESSON_PERFECT = "lesson_perfect"
    REVIEW_ITEM = "review_item"
    REVIEW_SESSION = "review_session"
    DAILY_GOAL = "daily_goal"


XP_LESSON_COMPLETE = 20
XP_LESSON_PERFECT = 5
XP_REVIEW_CORRECT = 5
XP_REVIEW_INCORRECT = 1
XP_REVIEW_SESSION = 10
XP_DAILY_GOAL = 10


def lesson_complete_key(lesson_id: uuid.UUID) -> str:
    return f"lesson_complete:{lesson_id}"


def lesson_perfect_key(lesson_id: uuid.UUID) -> str:
    return f"lesson_perfect:{lesson_id}"


def review_item_key(item_id: uuid.UUID) -> str:
    return f"review_item:{item_id}"


def review_session_key(session_id: uuid.UUID) -> str:
    return f"review_session:{session_id}"


def daily_goal_key(day: str) -> str:
    return f"daily_goal:{day}"


class Trigger(StrEnum):
    LESSON_COMPLETED = "lesson_completed"
    REVIEW_ANSWERED = "review_answered"
    STREAK_UPDATED = "streak_updated"
    SESSION_COMPLETED = "session_completed"


@dataclass(frozen=True)
class AchievementDef:
    code: str
    title: str
    description: str
    trigger: Trigger
    threshold: int


ACHIEVEMENTS: tuple[AchievementDef, ...] = (
    AchievementDef("first_lesson", "First step", "Complete your first lesson.",
                   Trigger.LESSON_COMPLETED, 1),
    AchievementDef("five_lessons", "Getting the picture", "Complete 5 different lessons.",
                   Trigger.LESSON_COMPLETED, 5),
    AchievementDef("topic_complete", "Topic explored", "Complete every lesson in a topic.",
                   Trigger.LESSON_COMPLETED, 1),
    AchievementDef("first_recall", "It stuck", "Recall a concept correctly in a review.",
                   Trigger.REVIEW_ANSWERED, 1),
    AchievementDef("first_understood", "Understood",
                   "Show understanding of a concept over growing intervals.",
                   Trigger.REVIEW_ANSWERED, 1),
    AchievementDef("ten_understood", "Deep understanding",
                   "Show understanding of 10 concepts.", Trigger.REVIEW_ANSWERED, 10),
    AchievementDef("streak_7", "One week", "Learn on 7 days in a row.",
                   Trigger.STREAK_UPDATED, 7),
    AchievementDef("reviews_10", "Habit of recall", "Complete 10 review sessions.",
                   Trigger.SESSION_COMPLETED, 10),
)  # fmt: skip

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS}
