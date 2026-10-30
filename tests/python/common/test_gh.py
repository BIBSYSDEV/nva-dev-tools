import shutil
from pathlib import Path

import pytest

from nva_dev_tools.common.gh import PullRequest, latest_pull_requests, parse_pull_requests, pull_request_query

requires_gh = pytest.mark.skipif(shutil.which("gh") is None, reason="gh is not installed")


@requires_gh
def test_unauthenticated_gh_is_reported_and_leaves_the_state_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "empty-gh-config"))
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert latest_pull_requests(["topic"], tmp_path) is None
    assert "PR state not checked" in capsys.readouterr().err


def test_missing_gh_is_reported_and_leaves_the_state_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    assert latest_pull_requests(["topic"], tmp_path) is None
    assert "PR state not checked" in capsys.readouterr().err


def test_no_branches_means_no_request() -> None:
    assert latest_pull_requests([], Path("/nonexistent")) == {}


def test_query_declares_one_variable_and_one_field_per_branch() -> None:
    query = pull_request_query(2)
    assert "$branch0: String!" in query and "$branch1: String!" in query
    assert query.count("pullRequests(headRefName: $branch") == 2
    assert "headRepository { nameWithOwner }" in query


def own(number: int, state: str = "MERGED", repository: str | None = "BIBSYSDEV/nva-nvi") -> dict:
    head_repository = {"nameWithOwner": repository} if repository else None
    return {"number": number, "state": state, "headRefOid": f"sha{number}", "headRepository": head_repository}


def test_parse_maps_aliases_back_to_branches_and_lowercases_state() -> None:
    response = {
        "data": {
            "repository": {
                "nameWithOwner": "BIBSYSDEV/nva-nvi",
                "branch0": {"nodes": [own(42)]},
                "branch1": {"nodes": []},
            }
        }
    }
    assert parse_pull_requests(["topic", "other"], response) == {
        "topic": PullRequest(number=42, state="merged", head_sha="sha42"),
        "other": None,
    }


def test_parse_skips_pull_requests_from_forks_and_deleted_forks() -> None:
    response = {
        "data": {
            "repository": {
                "nameWithOwner": "BIBSYSDEV/nva-nvi",
                "branch0": {"nodes": [own(9, repository="someone/nva-nvi"), own(8, repository=None), own(7, "OPEN")]},
                "branch1": {"nodes": [own(6, repository="someone/nva-nvi")]},
            }
        }
    }
    assert parse_pull_requests(["topic", "other"], response) == {
        "topic": PullRequest(number=7, state="open", head_sha="sha7"),
        "other": None,
    }
