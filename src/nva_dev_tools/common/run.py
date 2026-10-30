import subprocess
from pathlib import Path


class CommandError(Exception):
    """A subprocess exited non-zero where that was not an expected answer."""


class Refusal(Exception):
    """A user-facing refusal: the request is understood but will not be carried out as asked."""


def run(command: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command with captured output. CommandError on a missing executable, and on non-zero exit if check."""
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as missing:
        raise CommandError(f"{command[0]} is not installed or not on PATH") from missing
    if check and completed.returncode != 0:
        raise CommandError(
            f"{' '.join(command)} failed with exit code {completed.returncode}: {completed.stderr.strip()}"
        )
    return completed
