import pytest

from nva_dev_tools.common.run import CommandError, run


def test_missing_executable_is_a_command_error_even_without_check() -> None:
    with pytest.raises(CommandError, match="not installed or not on PATH"):
        run(["nva-dev-tools-no-such-command"], check=False)


def test_non_zero_exit_is_a_command_error_only_with_check() -> None:
    assert run(["false"], check=False).returncode != 0
    with pytest.raises(CommandError, match="exit code"):
        run(["false"])
