import pytest

from nva_dev_tools.common.output import Cell, print_table, status_cell


def test_table_is_plain_and_aligned_when_not_a_terminal(capsys: pytest.CaptureFixture[str]) -> None:
    print_table(["A", "LONG"], [[status_cell("prune"), "y"], [Cell("longer", "yellow"), ""]])
    lines = capsys.readouterr().out.splitlines()
    assert [line.split() for line in lines] == [["A", "LONG"], ["prune", "y"], ["longer"]]
    assert "\x1b[" not in "\n".join(lines), "no ANSI colour codes when stdout is not a terminal"
    assert lines[1].index("y") == lines[0].index("LONG")


def test_cell_text_is_never_read_as_markup(capsys: pytest.CaptureFixture[str]) -> None:
    print_table(["DETAIL"], [["! [rejected] main (fetch first)"], [Cell("[bold]x[/bold]", "red")]])
    rows = [line.rstrip() for line in capsys.readouterr().out.splitlines()[1:]]
    assert rows == ["! [rejected] main (fetch first)", "[bold]x[/bold]"]
