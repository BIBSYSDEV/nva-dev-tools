from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import Repo, bare_clone, make_origin

from nva_dev_tools.cli import cli
from nva_dev_tools.common.git import git


def clone(folder: Path, name: str) -> Repo:
    return bare_clone(make_origin(folder.parent / "origins" / name), folder / name)


def pull(*args: str) -> Result:
    return CliRunner().invoke(cli, ["repos", "pull", *args])


def rows(result: Result) -> list[str]:
    """The table lines below the header, without the blank line and summary under the table."""
    return result.stdout.split("\n\n")[0].splitlines()[1:]


def test_pull_prints_a_table_and_a_summary_and_fails_when_one_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "clones"
    clone(folder, "nva-commons").origin_commit()
    broken = clone(folder, "nva-nvi")
    git("remote", "set-url", "origin", str(tmp_path / "gone"), cwd=broken.root)
    clone(folder, "nva-search-api")
    monkeypatch.setenv("NVA_REPOS_DIR", str(folder))

    result = pull()

    assert result.exit_code == 1, result.output
    assert result.stdout.splitlines()[0].split() == ["STATUS", "REPOSITORY", "DETAIL"]
    assert [row.split()[:2] for row in rows(result)] == [
        ["updated", "nva-commons"],
        ["failed", "nva-nvi"],
        ["up", "to"],
    ]
    assert result.stdout.strip().endswith("1 updated, 1 up to date, 1 failed")


def test_pull_only_the_named_repositories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "clones"
    clone(folder, "nva-commons")
    clone(folder, "nva-nvi")
    monkeypatch.setenv("NVA_REPOS_DIR", str(folder))
    result = pull("nva-nvi")
    assert result.exit_code == 0, result.output
    assert [row.split()[-2] for row in rows(result)] == ["nva-nvi"]


def test_pull_expands_a_tilde_in_nva_repos_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clone(tmp_path / "home" / "nva", "nva-nvi")
    monkeypatch.setenv("NVA_REPOS_DIR", "~/nva")
    result = pull()
    assert result.exit_code == 0, result.output
    assert "1 up to date" in result.stdout


def test_pull_without_nva_repos_dir_uses_the_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "clones"
    clone(folder, "nva-nvi")
    monkeypatch.chdir(folder)
    assert pull().exit_code == 0
    monkeypatch.chdir(tmp_path / "home")
    refused = pull()
    assert refused.exit_code == 1
    assert "set NVA_REPOS_DIR" in str(refused.exception)
