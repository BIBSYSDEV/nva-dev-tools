from pathlib import Path

import pytest
from conftest import Repo, bare_clone, make_origin

from nva_dev_tools.common.git import git
from nva_dev_tools.common.run import Refusal
from nva_dev_tools.repositories import actions
from nva_dev_tools.repositories.actions import FAILED, SKIPPED, UP_TO_DATE, UPDATED, PullResult


def clone(tmp_path: Path, name: str, default_branch: str = "main") -> Repo:
    """A clone named like a repository, in tmp_path/clones, of its own origin in tmp_path/origins."""
    return bare_clone(make_origin(tmp_path / "origins" / name, default_branch), tmp_path / "clones" / name)


def break_fetch(repo: Repo) -> None:
    git("remote", "set-url", "origin", str(repo.origin.parent / "gone"), cwd=repo.root)


def pull(repo: Repo) -> tuple[str, str]:
    result = actions.pull(repo.root)
    return result.status, result.detail


def head(worktree: Path) -> str:
    return git("rev-parse", "HEAD", cwd=worktree)


def test_pull_fast_forwards_the_default_branch_worktree(repo: Repo) -> None:
    repo.origin_commit()
    repo.origin_commit()
    status, detail = pull(repo)
    assert status == UPDATED and detail.endswith("(2 commits)")
    assert head(repo.main) == git("rev-parse", "main", cwd=repo.origin)


def test_pull_reports_up_to_date_with_the_commit(repo: Repo) -> None:
    assert pull(repo) == (UP_TO_DATE, git("rev-parse", "--short", "HEAD", cwd=repo.main))


def test_pull_finds_the_default_branch_whatever_it_and_its_folder_are_called(tmp_path: Path) -> None:
    repo = clone(tmp_path, "nva-language", default_branch="master")
    git("worktree", "move", str(repo.main), str(repo.root / "trunk"), cwd=repo.root)
    repo.origin_commit()
    assert pull(repo)[0] == UPDATED
    assert head(repo.root / "trunk") == git("rev-parse", "master", cwd=repo.origin)


def test_pull_works_on_an_ordinary_clone(tmp_path: Path) -> None:
    origin = make_origin(tmp_path / "origin")
    ordinary = tmp_path / "ordinary"
    git("clone", "-q", str(origin), str(ordinary), cwd=tmp_path)
    git("commit", "--allow-empty", "-m", "upstream change", cwd=origin)
    assert actions.pull(ordinary).status == UPDATED


def test_pull_leaves_uncommitted_changes_alone(repo: Repo) -> None:
    (repo.main / "staged.txt").write_text("work in progress")
    git("add", "staged.txt", cwd=repo.main)
    before = head(repo.main)
    repo.origin_commit()
    assert pull(repo) == (SKIPPED, "uncommitted changes")
    assert head(repo.main) == before


def test_pull_is_not_stopped_by_untracked_files(repo: Repo) -> None:
    (repo.main / "build.log").write_text("output")
    repo.origin_commit()
    assert pull(repo)[0] == UPDATED


def test_pull_leaves_local_commits_alone(repo: Repo) -> None:
    repo.commit_in(repo.main)
    before = head(repo.main)
    repo.origin_commit()
    assert pull(repo) == (SKIPPED, "1 commit not on origin/main")
    assert head(repo.main) == before


def test_pull_skips_a_clone_without_a_worktree_for_the_default_branch(repo: Repo) -> None:
    git("worktree", "remove", str(repo.main), cwd=repo.root)
    assert pull(repo) == (SKIPPED, "no worktree has main checked out")


def test_pull_reports_a_failed_fetch_with_the_reason(repo: Repo) -> None:
    break_fetch(repo)
    status, detail = pull(repo)
    assert status == FAILED and detail.startswith("fetch failed: ") and "gone" in detail


def test_pull_all_keeps_the_order_and_reports_each_as_it_ends(tmp_path: Path) -> None:
    repos = [clone(tmp_path, name) for name in ("nva-commons", "nva-nvi", "nva-search-api")]
    repos[0].origin_commit()
    break_fetch(repos[1])
    heard: list[PullResult] = []
    results = actions.pull_all([repo.root for repo in repos], progress=heard.append)
    assert [(result.repository, result.status) for result in results] == [
        ("nva-commons", UPDATED),
        ("nva-nvi", FAILED),
        ("nva-search-api", UP_TO_DATE),
    ]
    assert sorted(result.repository for result in heard) == ["nva-commons", "nva-nvi", "nva-search-api"]


def test_find_repositories_takes_clones_only_sorted_by_name(tmp_path: Path) -> None:
    for name in ("nva-nvi", "NVA-Frontend", "nva-commons"):
        clone(tmp_path, name)
    folder = tmp_path / "clones"
    (folder / "not-a-clone").mkdir()
    (folder / "notes.txt").write_text("")
    assert [path.name for path in actions.find_repositories(folder)] == ["nva-commons", "NVA-Frontend", "nva-nvi"]
    assert [path.name for path in actions.find_repositories(folder, ("nva-nvi", "nva-commons"))] == [
        "nva-nvi",
        "nva-commons",
    ]


def test_find_repositories_refuses_unknown_names_and_folders_without_clones(tmp_path: Path) -> None:
    clone(tmp_path, "nva-nvi")
    with pytest.raises(Refusal, match="No clone named nva-unknown"):
        actions.find_repositories(tmp_path / "clones", ("nva-nvi", "nva-unknown"))
    (tmp_path / "empty").mkdir()
    with pytest.raises(Refusal, match="No git clones in"):
        actions.find_repositories(tmp_path / "empty")
    with pytest.raises(Refusal, match="is not a folder"):
        actions.find_repositories(tmp_path / "missing")
