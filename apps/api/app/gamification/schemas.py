"""Gamification response models (docs/spec/05 §5.1, §5.7)."""

from datetime import date, datetime

from pydantic import BaseModel


class XpAwardOut(BaseModel):
    reason: str
    amount: int


class XpSummaryOut(BaseModel):
    today: int
    goal: int
    total: int
    daily_goal_reached_now: bool


class StreakOut(BaseModel):
    current: int
    longest: int
    freezes_available: int
    done_today: bool
    at_risk: bool


class AchievementOut(BaseModel):
    code: str
    title: str
    description: str
    earned_at: datetime | None


class AchievementsOut(BaseModel):
    items: list[AchievementOut]


class LessonCountsOut(BaseModel):
    total: int
    started: int
    completed: int
    by_stage: dict[str, int]


class TopicProgressOut(BaseModel):
    slug: str
    title: str
    total: int
    completed: int


class XpTotalsOut(BaseModel):
    total: int
    today: int
    goal: int


class AccuracyOut(BaseModel):
    correct: int
    total: int


class ReviewTotalsOut(BaseModel):
    due_count: int
    next_due_on: date | None


class ProgressOut(BaseModel):
    lessons: LessonCountsOut
    by_topic: list[TopicProgressOut]
    xp: XpTotalsOut
    streak: StreakOut
    recall_accuracy: AccuracyOut
    reviews: ReviewTotalsOut
