"""The repos command group: options and output. Logic lives in actions.py and versions.py."""

import json
import sys
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import click

from nva_dev_tools.common.output import Cell, print_table, status_cell, warn
from nva_dev_tools.repositories import actions, versions
from nva_dev_tools.repositories.versions import COLUMNS, Column, DeclaredVersion, RepositoryVersions

clones_folder_option = click.option(
    "--repos-dir",
    "clones_folder",
    type=click.Path(file_okay=False, path_type=Path),
    envvar="NVA_REPOS_DIR",
    show_envvar=True,
    help="The folder that holds the clones, one folder per repository (default: the current directory).",
)
names_argument = click.argument("names", nargs=-1, metavar="[REPOSITORY]...")

SUMMARY_ORDER = (actions.UPDATED, actions.UP_TO_DATE, actions.SKIPPED, actions.FAILED)
OUTPUT_FORMATS = ("table", "markdown", "json")
OUTDATED_MARKER = "⚠"
MISSING = "-"


@click.group()
def repos() -> None:
    """Every clone under NVA_REPOS_DIR at once."""


def find_clones(clones_folder: Path | None, names: tuple[str, ...]) -> list[Path]:
    """The clones to work on. expanduser() because mise leaves a leading ~ in an [env] value as it is."""
    return actions.find_repositories((clones_folder or Path.cwd()).expanduser(), names)


def in_parallel_with_progress[Result](
    label: str, function: Callable[[Path], Result], clones: list[Path]
) -> list[Result]:
    """actions.in_parallel() with a progress bar on stderr; Click hides the bar when stderr is not a terminal."""
    with click.progressbar(
        length=len(clones),
        label=label,
        file=sys.stderr,
        show_eta=False,
        item_show_func=lambda clone: clone.name if clone is not None else None,
    ) as bar:
        return actions.in_parallel(function, clones, progress=lambda clone: bar.update(1, clone))


@repos.command()
@names_argument
@clones_folder_option
@click.pass_context
def pull(context: click.Context, names: tuple[str, ...], clones_folder: Path | None) -> None:
    """Fetch origin and fast-forward the default-branch worktree of every clone, or of the named ones.

    A worktree with uncommitted changes, or with local commits that are not on origin, is left alone.
    """
    results = in_parallel_with_progress("Pulling", actions.pull, find_clones(clones_folder, names))

    rows = [[status_cell(result.status), result.repository, result.detail] for result in results]
    print_table(["STATUS", "REPOSITORY", "DETAIL"], rows)
    counts = Counter(result.status for result in results)
    click.echo()
    click.echo(", ".join(f"{counts[status]} {status}" for status in SUMMARY_ORDER if counts[status]))
    if counts[actions.FAILED]:
        context.exit(1)


@repos.command("versions")
@names_argument
@clones_folder_option
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--no-fetch",
    "fetch",
    is_flag=True,
    default=True,
    flag_value=False,
    help="Skip git fetch first, and report origin as of the last fetch.",
)
def versions_command(names: tuple[str, ...], clones_folder: Path | None, output_format: str, fetch: bool) -> None:
    """Last commit and Java, Gradle, nva-commons and nva-gradle-plugins versions of every clone, or of the named ones.

    Read from origin's default branch, so a worktree that is behind or has another branch checked out does not
    matter. A version older than the newest one in the report is marked with ⚠. Warnings go to stderr, so
    stdout can be redirected.
    """
    reports = in_parallel_with_progress(
        "Reading versions", lambda clone: versions.read_versions(clone, fetch=fetch), find_clones(clones_folder, names)
    )
    newest_by_column = versions.mark_outdated(reports)
    for report in reports:
        if report.problem is not None:
            warn(f"{report.repository}: {report.problem}")

    if output_format == "json":
        click.echo(json.dumps(versions_as_json(reports, newest_by_column), indent=2))
        return
    if output_format == "markdown":
        print_markdown_table(reports)
    else:
        print_versions_table(reports)
    if newest_by_column:
        newest = ", ".join(f"{column.header} {version}" for column, version in newest_by_column.items())
        click.echo()
        click.echo(f"{OUTDATED_MARKER} = older than the newest version used in any repository ({newest})")


def describe(declared: DeclaredVersion) -> str:
    """'2.11.2 (self)', '9.7.0 ⚠' or '-'."""
    text = declared.version or MISSING
    if declared.note:
        text = f"{text} ({declared.note})" if declared.version else declared.note
    return f"{text} {OUTDATED_MARKER}" if declared.outdated else text


def describe_last_commit(last_commit: datetime | None, today: date | None = None) -> str:
    """'2026-11-09 (1d ago)', counting calendar days in local time, so yesterday evening is never 'today'."""
    if last_commit is None:
        return MISSING
    local_date = last_commit.astimezone().date()
    age_in_days = ((today or date.today()) - local_date).days
    age = "today" if age_in_days == 0 else f"{age_in_days}d ago"
    return f"{local_date.isoformat()} ({age})"


def versions_in_order(report: RepositoryVersions) -> list[DeclaredVersion]:
    return [report.versions[column] for column in COLUMNS]


def version_headers() -> list[str]:
    return ["Repository", "Last commit", *(column.header for column in COLUMNS)]


def print_versions_table(reports: list[RepositoryVersions]) -> None:
    rows = [
        [
            report.repository,
            describe_last_commit(report.last_commit),
            *(
                Cell(describe(declared), "yellow" if declared.outdated else "")
                for declared in versions_in_order(report)
            ),
        ]
        for report in reports
    ]
    print_table([header.upper() for header in version_headers()], rows)


def print_markdown_table(reports: list[RepositoryVersions]) -> None:
    headers = version_headers()
    click.echo("| " + " | ".join(headers) + " |")
    click.echo("| " + " | ".join("---" for _ in headers) + " |")
    for report in reports:
        cells = [report.repository, describe_last_commit(report.last_commit), *map(describe, versions_in_order(report))]
        click.echo("| " + " | ".join(cells) + " |")


def declared_as_json(declared: DeclaredVersion) -> dict[str, object]:
    return {"version": declared.version, "note": declared.note, "outdated": declared.outdated}


def versions_as_json(reports: list[RepositoryVersions], newest_by_column: dict[Column, str]) -> dict[str, object]:
    return {
        "newest": {column.key: version for column, version in newest_by_column.items()},
        "repositories": [
            {
                "name": report.repository,
                "lastCommit": report.last_commit.isoformat() if report.last_commit else None,
                **{column.key: declared_as_json(report.versions[column]) for column in COLUMNS},
                "problem": report.problem,
            }
            for report in reports
        ],
    }
