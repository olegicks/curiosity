from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.config import get_settings
from tests.conftest import TEST_JWT_SECRET, UNREACHABLE_DATABASE_URL
from tests.content_factory import standard_lessons, write_content

runner = CliRunner()


@pytest.fixture(autouse=True)
def cli_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DATABASE_URL)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_validate_reports_ok(tmp_path: Path) -> None:
    root = write_content(tmp_path, standard_lessons())
    result = runner.invoke(app, ["content", "validate", "--dir", str(root)])
    assert result.exit_code == 0, result.output
    assert "ok: 5 lessons (3 published)" in result.output


def test_validate_fails_with_errors(tmp_path: Path) -> None:
    lessons = standard_lessons()
    lessons[0]["related"] = ["ghost"]
    root = write_content(tmp_path, lessons)
    result = runner.invoke(app, ["content", "validate", "--dir", str(root)])
    assert result.exit_code == 1
    assert "unknown related lesson 'ghost'" in result.output


def test_import_refuses_invalid_content_before_touching_the_database(tmp_path: Path) -> None:
    result = runner.invoke(app, ["content", "import", "--dir", str(tmp_path / "missing")])
    assert result.exit_code == 1
    assert "import aborted" in result.output
