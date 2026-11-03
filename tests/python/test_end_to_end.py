"""The installed console script, run the way the mise shims run it."""

import subprocess
from pathlib import Path

from conftest import Repo

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def nva_dev(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    command = ["uv", "run", "--quiet", "--project", str(PROJECT_ROOT), "nva-dev", *args]
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def test_console_script_lists_and_refuses(repo: Repo) -> None:
    repo.commit_in(repo.add("wip"))
    listed = nva_dev("wt", "list", "--no-pr", cwd=repo.main)
    assert listed.returncode == 0, listed.stderr
    assert listed.stdout.splitlines()[0].split() == ["STATUS", "WORKTREE", "BRANCH", "NOTES"]
    refused = nva_dev("wt", "remove", "wip", "--no-pr", cwd=repo.main)
    assert refused.returncode == 1
    assert "not verifiably merged" in refused.stderr


def test_console_script_help_and_usage_error(repo: Repo) -> None:
    assert "Show the worktrees as wt:list does" in nva_dev("wt", "prune", "--help", cwd=repo.main).stdout
    assert nva_dev("wt", "remove", cwd=repo.main).returncode == 2
