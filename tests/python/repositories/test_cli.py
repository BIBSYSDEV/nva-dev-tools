import json
from datetime import date, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import Repo, bare_clone, commit_files, make_origin

from nva_dev_tools.cli import cli
from nva_dev_tools.common.git import git
from nva_dev_tools.repositories.cli import describe_last_commit


def clone(folder: Path, name: str, files: dict[str, str] | None = None) -> Repo:
    origin = make_origin(folder.parent / "origins" / name)
    if files:
        commit_files(origin, files)
    return bare_clone(origin, folder / name)


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


def gradle_build(gradle_version: str) -> dict[str, str]:
    return {
        "gradlew": "",
        "gradle/wrapper/gradle-wrapper.properties": f"distributionUrl=gradle-{gradle_version}-bin.zip\n",
    }


@pytest.fixture
def two_gradle_clones(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "clones"
    clone(folder, "nva-nvi", gradle_build("9.8.2"))
    clone(folder, "nva-search-api", gradle_build("9.7.0"))
    monkeypatch.setenv("NVA_REPOS_DIR", str(folder))


def versions(*args: str) -> Result:
    return CliRunner().invoke(cli, ["repos", "versions", *args])


@pytest.mark.usefixtures("two_gradle_clones")
def test_versions_table_marks_what_is_older_than_the_newest() -> None:
    result = versions()
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0].split() == ["REPOSITORY", "LAST", "COMMIT", "JAVA", "GRADLE", "NVA-COMMONS", "NVA-GRADLE-PLUGINS"]
    assert "9.8.2" in lines[1] and "⚠" not in lines[1]
    assert "9.7.0 ⚠" in lines[2]
    assert lines[-1] == "⚠ = older than the newest version used in any repository (Gradle 9.8.2)"


@pytest.mark.usefixtures("two_gradle_clones")
def test_versions_as_markdown() -> None:
    lines = versions("--format", "markdown").stdout.splitlines()
    assert lines[0] == "| Repository | Last commit | Java | Gradle | nva-commons | nva-gradle-plugins |"
    assert lines[3].startswith("| nva-search-api | ") and lines[3].endswith(" | - | 9.7.0 ⚠ | - | - |")


@pytest.mark.usefixtures("two_gradle_clones")
def test_versions_as_json() -> None:
    report = json.loads(versions("--format", "json", "nva-search-api").stdout)
    assert report["newest"] == {"gradle": "9.7.0"}
    [repository] = report["repositories"]
    assert repository["name"] == "nva-search-api" and repository["problem"] is None
    assert repository["gradle"] == {"version": "9.7.0", "note": None, "outdated": False}


def test_last_commit_age_counts_calendar_days() -> None:
    late_yesterday = datetime(2026, 11, 9, 23, 30).astimezone()
    assert describe_last_commit(late_yesterday, today=date(2026, 11, 10)) == "2026-11-09 (1d ago)"
    assert describe_last_commit(late_yesterday, today=date(2026, 11, 9)) == "2026-11-09 (today)"
    assert describe_last_commit(None) == "-"
