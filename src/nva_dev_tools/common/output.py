import sys
from collections.abc import Callable

from rich.console import Console
from rich.table import Table
from rich.text import Text

STYLES = {
    "prune": "green",
    "pruned": "bold green",
    "skip": "yellow",
    "failed": "bold red",
    "review": "cyan",
    "stale": "red",
    "-": "dim",
}
"""Colours for action and state cells. Rich drops them when stdout is not a terminal."""


def console() -> Console:
    # A fixed huge width: rich must never squeeze or drop columns to fit the window, like column -t
    return Console(width=10_000)


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def error(message: str) -> None:
    print(message, file=sys.stderr)


def print_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    styled_column: int | None = None,
    row_style: Callable[[list[str]], str | None] | None = None,
) -> None:
    """A borderless table. styled_column colours that cell by its value (see STYLES); row_style colours whole rows."""
    table = Table(box=None, show_edge=False, pad_edge=False, header_style="bold")
    for header in headers:
        table.add_column(header, no_wrap=True)
    for row in rows:
        cells: list[str | Text] = list(row)
        if styled_column is not None:
            cells[styled_column] = Text(row[styled_column], style=STYLES.get(row[styled_column], ""))
        table.add_row(*cells, style=row_style(row) if row_style else None)
    console().print(table)
