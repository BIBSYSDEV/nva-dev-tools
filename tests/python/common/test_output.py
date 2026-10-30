import pytest

from nva_dev_tools.common.output import print_table


def test_table_is_plain_and_aligned_when_not_a_terminal(capsys: pytest.CaptureFixture[str]) -> None:
    print_table(["A", "LONG"], [["x", "y"], ["longer", ""]], styled_column=0)
    lines = capsys.readouterr().out.splitlines()
    assert [line.split() for line in lines] == [["A", "LONG"], ["x", "y"], ["longer"]]
    assert "\x1b[" not in "\n".join(lines), "no ANSI colour codes when stdout is not a terminal"
    assert lines[1].index("y") == lines[0].index("LONG")
