"""`curiosity` command-line tool for privileged operations (no admin HTTP endpoints)."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy.orm import Session

from app.ai import admin as ai_admin
from app.ai.provider import build_provider
from app.config import get_settings
from app.content.importer import ContentImportError, import_content
from app.content.loader import ContentSet, load_content
from app.core.clock import SystemClock
from app.core.db import create_db_engine, create_session_factory

app = typer.Typer(no_args_is_help=True, help="Curiosity maintenance commands.")
content_app = typer.Typer(no_args_is_help=True, help="Validate and import lesson content.")
app.add_typer(content_app, name="content")
feedback_app = typer.Typer(no_args_is_help=True, help="Triage 'report a problem' submissions.")
content_app.add_typer(feedback_app, name="feedback")
ai_app = typer.Typer(no_args_is_help=True, help="Pre-generate and review AI explanations.")
app.add_typer(ai_app, name="ai")


@app.command("openapi")
def export_openapi(
    out: Annotated[Path, typer.Option(help="Where to write the OpenAPI JSON document")],
) -> None:
    """Write the API's OpenAPI document (no database or server needed)."""
    import json
    import secrets

    from app.config import AppEnv, Settings
    from app.main import create_app

    settings = Settings(  # placeholders: the schema does not depend on them
        _env_file=None,
        app_env=AppEnv.TEST,
        database_url="postgresql+psycopg://unused@localhost/unused",
        jwt_secret=secrets.token_urlsafe(32),  # throwaway; nothing is signed
        expose_openapi=True,
    )
    schema = create_app(settings).openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    typer.echo(f"wrote {out}")


@contextmanager
def _session() -> Iterator[Session]:
    """A database session from DATABASE_URL (tests replace this)."""
    engine = create_db_engine(get_settings())
    try:
        with create_session_factory(engine)() as db:
            yield db
    finally:
        engine.dispose()


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


# --- content feedback ------------------------------------------------------------------------


@feedback_app.command("list")
def feedback_list(
    status: Annotated[str, typer.Option(help="open, resolved, dismissed or all")] = "open",
) -> None:
    """List content reports, oldest first."""
    from app.learning import feedback

    with _session() as db:
        rows = feedback.list_feedback(db, status=None if status == "all" else status)
        for row, slug in rows:
            message = " ".join((row.message or "").split())
            day = f"{row.created_at:%Y-%m-%d}"
            typer.echo(f"{row.id}  {day}  {row.status:<9} {slug}  {row.kind}  {message}")
        typer.echo(f"{len(rows)} report(s)")


@feedback_app.command("resolve")
def feedback_resolve(
    feedback_id: uuid.UUID,
    note: Annotated[str | None, typer.Option(help="What was done, e.g. a commit hash")] = None,
    dismiss: Annotated[bool, typer.Option(help="Close without a content change")] = False,
) -> None:
    """Mark a report as resolved (or dismissed)."""
    from app.learning import feedback

    with _session() as db:
        try:
            feedback.resolve_feedback(
                db, feedback_id, dismiss=dismiss, note=note, now=SystemClock().now()
            )
        except LookupError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1) from None
    typer.echo("dismissed" if dismiss else "resolved")


# --- AI explanations ---------------------------------------------------------------------------


@ai_app.command("pregenerate")
def ai_pregenerate(
    max_cost_micros: Annotated[
        int, typer.Option(help="Stop once this much has been spent (micro-USD)")
    ] = 2_000_000,
) -> None:
    """Create variant 1 for every published lesson and mode that has none yet."""
    settings = get_settings()
    provider = build_provider(settings)
    with _session() as db:
        summary = ai_admin.pregenerate(
            db, settings=settings, provider=provider, max_cost_micros=max_cost_micros
        )
    typer.echo(
        f"created {len(summary.created)}, skipped {summary.skipped}, "
        f"failed {len(summary.failed)}, cost {summary.cost_micros} micro-USD"
    )
    for label in summary.failed:
        typer.echo(f"failed: {label}", err=True)
    if summary.stopped_by_budget:
        typer.echo("stopped: cost limit reached", err=True)


@ai_app.command("list")
def ai_list(
    status: Annotated[str | None, typer.Option(help="Filter by status")] = None,
    flagged: Annotated[bool, typer.Option(help="Only flagged or hidden explanations")] = False,
) -> None:
    """List explanations with their review status."""
    with _session() as db:
        rows = ai_admin.list_explanations(db, status=status, flagged=flagged)
        for row in rows:
            typer.echo(
                f"{row.id}  {row.lesson_slug}/{row.mode} v{row.variant}  {row.status}"
                f"  flags={row.flag_count}"
            )
        typer.echo(f"{len(rows)} explanation(s)")


@ai_app.command("set-status")
def ai_set_status(explanation_id: uuid.UUID, status: str) -> None:
    """Set an explanation's status: approved, rejected, hidden or generated."""
    with _session() as db:
        try:
            ai_admin.set_status(db, explanation_id, status, SystemClock().now())
        except (ValueError, LookupError) as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1) from None
    typer.echo(f"{explanation_id}: {status}")


@ai_app.command("review")
def ai_review(
    flagged: Annotated[bool, typer.Option(help="Review flagged or hidden explanations")] = False,
) -> None:
    """Walk through unreviewed (or flagged) explanations: approve, reject, skip or quit."""
    choices = {"a": "approved", "r": "rejected"}
    with _session() as db:
        rows = (
            ai_admin.list_explanations(db, flagged=True)
            if flagged
            else ai_admin.list_explanations(db, status="generated")
        )
        reviewed = 0
        for row in rows:
            typer.echo("")
            typer.echo(f"{row.lesson_slug} / {row.mode} (v{row.variant}, flags={row.flag_count})")
            typer.echo(row.content)
            answer = typer.prompt("[a]pprove, [r]eject, [s]kip, [q]uit", default="s").lower()
            if answer == "q":
                break
            if answer in choices:
                ai_admin.set_status(db, row.id, choices[answer], SystemClock().now())
                reviewed += 1
        typer.echo(f"reviewed {reviewed} of {len(rows)}")
