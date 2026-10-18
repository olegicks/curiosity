"""`curiosity` command-line tool for privileged operations (no admin HTTP endpoints)."""

from pathlib import Path
from typing import Annotated

import typer

from app.config import get_settings
from app.content.importer import ContentImportError, import_content
from app.content.loader import ContentSet, load_content
from app.core.clock import SystemClock
from app.core.db import create_db_engine, create_session_factory

app = typer.Typer(no_args_is_help=True, help="Curiosity maintenance commands.")
content_app = typer.Typer(no_args_is_help=True, help="Validate and import lesson content.")
app.add_typer(content_app, name="content")

DirOption = Annotated[
    Path | None, typer.Option("--dir", help="Content directory (default: CONTENT_DIR).")
]


def _load(directory: Path | None) -> ContentSet:
    root = directory or get_settings().content_dir
    content = load_content(root, today=SystemClock().now().date())
    for warning in content.warnings:
        typer.echo(f"warning: {warning}", err=True)
    for error in content.errors:
        typer.echo(f"error: {error}", err=True)
    return content


@content_app.command("validate")
def validate(directory: DirOption = None) -> None:
    """Check every content file against the schema and editorial rules (no database)."""
    content = _load(directory)
    if not content.ok:
        typer.echo(f"{len(content.errors)} error(s)", err=True)
        raise typer.Exit(code=1)
    published = sum(lesson.status == "published" for lesson in content.lessons)
    typer.echo(f"ok: {len(content.lessons)} lessons ({published} published)")


@content_app.command("import")
def import_(directory: DirOption = None) -> None:
    """Validate, then import content into the database in one transaction."""
    settings = get_settings()
    content = _load(directory)
    if not content.ok:
        typer.echo("import aborted: content is invalid", err=True)
        raise typer.Exit(code=1)
    engine = create_db_engine(settings)
    try:
        with create_session_factory(engine)() as db:
            summary = import_content(
                db,
                content,
                now=SystemClock().now(),
                allow_draft_overwrite=settings.content_allow_draft_overwrite,
            )
    except ContentImportError as exc:
        for error in exc.errors:
            typer.echo(f"error: {error}", err=True)
        typer.echo("import aborted: nothing was written", err=True)
        raise typer.Exit(code=1) from None
    finally:
        engine.dispose()
    typer.echo(
        f"imported: {len(summary.created)} created, {len(summary.new_versions)} new versions, "
        f"{len(summary.unchanged)} unchanged, {len(summary.retired)} retired"
    )
    for slug in summary.missing_from_files:
        typer.echo(f"warning: lesson {slug!r} is in the database but has no file", err=True)
