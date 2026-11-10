"""The repos command group: options and output. Logic lives in actions.py."""

import sys
from collections import Counter
from pathlib import Path

import click

from nva_dev_tools.common.output import print_table
from nva_dev_tools.repositories import actions

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


@click.group()
def repos() -> None:
    """Every clone under NVA_REPOS_DIR at once."""


def find_clones(clones_folder: Path | None, names: tuple[str, ...]) -> list[Path]:
    """The clones to work on. expanduser() because mise leaves a leading ~ in an [env] value as it is."""
    return actions.find_repositories((clones_folder or Path.cwd()).expanduser(), names)


@repos.command()
@names_argument
@clones_folder_option
@click.pass_context
def pull(context: click.Context, names: tuple[str, ...], clones_folder: Path | None) -> None:
    """Fetch origin and fast-forward the default-branch worktree of every clone, or of the named ones.

    A worktree with uncommitted changes, or with local commits that are not on origin, is left alone.
    """
    clones = find_clones(clones_folder, names)
    with click.progressbar(
        length=len(clones),
        label="Pulling",
        file=sys.stderr,
        show_eta=False,
        item_show_func=lambda result: result.repository if result is not None else None,
    ) as bar:
        results = actions.pull_all(clones, progress=lambda result: bar.update(1, result))

    rows = [[result.status, result.repository, result.detail] for result in results]
    print_table(["STATUS", "REPOSITORY", "DETAIL"], rows, styled_column=0)
    counts = Counter(result.status for result in results)
    click.echo()
    click.echo(", ".join(f"{counts[status]} {status}" for status in SUMMARY_ORDER if counts[status]))
    if counts[actions.FAILED]:
        context.exit(1)
