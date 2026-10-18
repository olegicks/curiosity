import time
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.config import AppEnv, parse_version
from app.core.clock import FixedClock, local_date, resolve_timezone
from app.core.ids import uuid7
from tests.conftest import make_settings

# --- ids -----------------------------------------------------------------------------


def test_uuid7_has_version_and_variant() -> None:
    value = uuid7()
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_uuid7_embeds_current_millisecond_timestamp() -> None:
    before = time.time_ns() // 1_000_000
    value = uuid7()
    after = time.time_ns() // 1_000_000
    assert before <= value.int >> 80 <= after + 1  # +1: counter overflow may borrow a ms


def test_uuid7_is_monotonic_and_unique() -> None:
    ids = [uuid7() for _ in range(10_000)]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


# --- clock ---------------------------------------------------------------------------


def test_fixed_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 11, 2, 12, 0))  # noqa: DTZ001


def test_fixed_clock_advance() -> None:
    clock = FixedClock(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))
    clock.advance(timedelta(days=1, hours=1))
    assert clock.now() == datetime(2026, 11, 3, 13, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("timezone", "expected"),
    [
        ("UTC", date(2026, 11, 2)),
        ("Pacific/Auckland", date(2026, 11, 3)),  # UTC+13 in November
        ("America/Los_Angeles", date(2026, 11, 2)),
        ("Not/AZone", date(2026, 11, 2)),  # unknown → UTC
        (None, date(2026, 11, 2)),
    ],
)
def test_local_date_uses_user_timezone(timezone: str | None, expected: date) -> None:
    clock = FixedClock(datetime(2026, 11, 2, 23, 30, tzinfo=UTC))
    assert local_date(clock, timezone) == expected


def test_resolve_timezone_rejects_path_like_names() -> None:
    assert resolve_timezone("../etc/passwd").key == "UTC"


# --- config --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"), [("1.0.0", (1, 0, 0)), ("10.20.30", (10, 20, 30)), (" 2.1.0 ", (2, 1, 0))]
)
def test_parse_version_valid(raw: str, expected: tuple[int, int, int]) -> None:
    assert parse_version(raw) == expected


@pytest.mark.parametrize("raw", ["1.0", "1.0.0.0", "v1.0.0", "1.x.0", "", "1.0.-1"])
def test_parse_version_invalid(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid version"):
        parse_version(raw)


def test_settings_reject_invalid_min_app_version() -> None:
    with pytest.raises(ValidationError):
        make_settings(min_app_version="latest")


def test_openapi_disabled_by_default_in_production_only() -> None:
    assert make_settings(app_env=AppEnv.STAGING).openapi_enabled
    assert not make_settings(app_env=AppEnv.PRODUCTION).openapi_enabled
    assert make_settings(app_env=AppEnv.PRODUCTION, expose_openapi=True).openapi_enabled
