import subprocess
from pathlib import Path

import pytest
from conftest import Repo

from nva_dev_tools.common import git
from nva_dev_tools.common.run import Refusal


def test_repository_root_is_found_from_the_root_and_any_worktree(repo: Repo) -> None:
    nested = repo.add("topic") / "src" / "deep"
    nested.mkdir(parents=True)
    for cwd in (repo.root, repo.main, nested):
        assert git.repository_root(cwd) == repo.root


def test_repository_root_refuses_an_ordinary_clone(repo: Repo, tmp_path: Path) -> None:
    clone = tmp_path / "ordinary"
    subprocess.run(["git", "clone", "-q", str(repo.origin), str(clone)], check=True)
    with pytest.raises(Refusal, match="ordinary clone"):
        git.repository_root(clone)
