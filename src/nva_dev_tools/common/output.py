import sys
from collections.abc import Sequence
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table
from rich.text import Text

STYLES = {
    "prune": "green",
    "pruned": "bold green",
    "skip": "yellow",
    "failed": "bold red",
    "review": "cyan",
    "-": "dim",
    "updated": "green",
    "up to date": "dim",
    "skipped": "yellow",
}
"""Colours for status cells, see status_cell(). Rich drops them when stdout is not a terminal."""


def console() -> Console:
    # A fixed huge width: rich must never squeeze or drop columns to fit the window, like column -t
    return Console(width=10_000)


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def error(message: str) -> None:
    print(message, file=sys.stderr)


@dataclass(frozen=True)
class Cell:
    """One table cell: text and an optional style such as "yellow".

    The text is printed as it is, never read as Rich markup, so a git message with [brackets] stays intact.
    """

    text: str
    style: str = ""


def status_cell(status: str) -> Cell:
    """A status such as prune, failed or up to date, coloured from STYLES."""
    return Cell(status, STYLES.get(status, ""))


def print_table(headers: list[str], rows: Sequence[Sequence[str | Cell]]) -> None:
    """A borderless table. A str is a cell without a style."""
    table = Table(box=None, show_edge=False, pad_edge=False, header_style="bold")
    for header in headers:
        table.add_column(header, no_wrap=True)
    for row in rows:
        cells = [Cell(cell) if isinstance(cell, str) else cell for cell in row]
        table.add_row(*(Text(cell.text, style=cell.style) for cell in cells))
    console().print(table)
