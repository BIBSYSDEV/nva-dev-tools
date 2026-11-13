"""Root command group. Each family registers its own click.Group here."""

import sys

import click

from nva_dev_tools.common.output import error
from nva_dev_tools.common.run import CommandError, Refusal
from nva_dev_tools.repositories.cli import repos
from nva_dev_tools.worktrees.cli import wt

EXIT_REFUSED = 1
EXIT_COMMAND_FAILED = 2


@click.group()
def cli() -> None:
    """Local development workflow for NVA."""


cli.add_command(repos)
cli.add_command(wt)


def main() -> None:
    """Entry point: Click handles its own exceptions and exit codes; this maps the two domain exceptions."""
    try:
        cli()
    except Refusal as refusal:
        error(str(refusal))
        sys.exit(EXIT_REFUSED)
    except CommandError as failure:
        error(str(failure))
        sys.exit(EXIT_COMMAND_FAILED)
