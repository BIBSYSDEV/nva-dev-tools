from datetime import date
from pathlib import Path

import pytest
from conftest import Repo, fake_pull_requests

from nva_dev_tools.common import git
from nva_dev_tools.common.gh import PullRequest
from nva_dev_tools.common.run import Refusal
from nva_dev_tools.worktrees import actions
from nva_dev_tools.worktrees.actions import PruneOutcome


def prune_outcomes(repo: Repo, *, apply: bool, force: bool = False, cwd: Path | None = None) -> dict[str, PruneOutcome]:
    plan = actions.plan_prune(repo.classify(), force=force, original_cwd=cwd or repo.main)
    if apply:
        actions.apply_prune(repo.root, plan)
    return {outcome.worktree.name: outcome for outcome in plan}


def prune_actions(repo: Repo, *, apply: bool, force: bool = False) -> dict[str, str]:
    return {name: outcome.action for name, outcome in prune_outcomes(repo, apply=apply, force=force).items()}


def remove(repo: Repo, branch: str, *, force: bool = False, keep_branch: bool = False, **kwargs) -> None:
    """actions.remove() from the main worktree, which is where the tests stand."""
    actions.remove(repo.root, branch, force=force, keep_branch=keep_branch, original_cwd=repo.main, **kwargs)


def stale_setup(repo: Repo) -> None:
    """clean (stale, deletable), dirty (stale, dirty), squashed (stale, own commits), fresh (review)."""
    repo.checkout_from_origin("clean")
    (repo.checkout_from_origin("dirty") / "x.txt").write_text("x")
    repo.commit_in(repo.checkout_from_origin("squashed"))
    for branch in ("clean", "dirty", "squashed"):
        repo.origin_delete_branch(branch)
    repo.add("fresh")


def test_prune_dry_run_touches_nothing(repo: Repo) -> None:
    stale_setup(repo)
    assert prune_actions(repo, apply=False) == {
        "clean": "prune",
        "dirty": "skip",
        "squashed": "skip",
        "fresh": "review",
        "main": "-",
    }
    assert repo.local_branches() == {"main", "clean", "dirty", "squashed", "fresh"}


def test_prune_removes_worktree_and_branch_together(repo: Repo) -> None:
    stale_setup(repo)
    assert prune_actions(repo, apply=True) == {
        "clean": "pruned",
        "dirty": "skip",
        "squashed": "skip",
        "fresh": "review",
        "main": "-",
    }
    assert not (repo.root / "clean").exists()
    assert repo.local_branches() == {"main", "dirty", "squashed", "fresh"}


def test_prune_force_takes_dirty_and_unmerged_but_never_review(repo: Repo) -> None:
    stale_setup(repo)
    expected = {"clean": "pruned", "dirty": "pruned", "squashed": "pruned", "fresh": "review", "main": "-"}
    assert prune_actions(repo, apply=True, force=True) == expected
    assert repo.local_branches() == {"main", "fresh"}


def test_prune_skips_the_worktree_holding_the_current_directory(repo: Repo) -> None:
    stale_setup(repo)
    inside = repo.root / "clean" / "sub"
    inside.mkdir()
    clean = prune_outcomes(repo, apply=True, cwd=inside)["clean"]
    assert clean.action == "skip" and "current directory" in clean.notes
    assert (repo.root / "clean").exists()


def test_prune_reports_a_locked_worktree_as_failed_and_continues(repo: Repo) -> None:
    stale_setup(repo)
    repo.lock_worktree(repo.root / "clean")
    repo.checkout_from_origin("other")
    repo.origin_delete_branch("other")
    taken = prune_actions(repo, apply=True)
    assert taken["clean"] == "failed" and taken["other"] == "pruned"


def test_prune_reports_a_branch_it_could_not_delete_as_failed(repo: Repo) -> None:
    stale_setup(repo)
    repo.lock_branch_ref("clean")
    clean = prune_outcomes(repo, apply=True)["clean"]
    assert clean.action == "failed" and "worktree removed, could not delete branch" in clean.notes
    assert not (repo.root / "clean").exists() and "clean" in repo.local_branches()


def test_prune_handles_a_missing_folder(repo: Repo, tmp_path: Path) -> None:
    repo.checkout_from_origin("missing").rename(tmp_path / "moved")
    repo.origin_delete_branch("missing")
    assert prune_actions(repo, apply=True) == {"missing": "pruned", "main": "-"}
    assert "missing" not in repo.local_branches()
    assert "missing" not in repo.worktree_branches()


def test_prune_of_one_missing_folder_keeps_the_bookkeeping_of_the_others(repo: Repo, tmp_path: Path) -> None:
    repo.checkout_from_origin("clean").rename(tmp_path / "clean-moved")
    squashed = repo.checkout_from_origin("squashed")
    repo.commit_in(squashed)
    squashed.rename(tmp_path / "squashed-moved")
    for branch in ("clean", "squashed"):
        repo.origin_delete_branch(branch)
    assert prune_actions(repo, apply=True) == {"clean": "pruned", "squashed": "skip", "main": "-"}
    assert repo.worktree_branches() == {"main", "squashed"}


def test_remove_merged_and_clean(repo: Repo) -> None:
    repo.checkout_from_origin("done")
    remove(repo, "done")
    assert not (repo.root / "done").exists() and "done" not in repo.local_branches()


def test_remove_squash_merged_via_pull_request_lookup(repo: Repo) -> None:
    repo.commit_in(repo.checkout_from_origin("squashed"))
    repo.origin_delete_branch("squashed")
    with pytest.raises(Refusal, match="not verifiably merged"):
        remove(repo, "squashed", pull_requests=fake_pull_requests())
    merged = fake_pull_requests(squashed=PullRequest(number=1, state="merged", head_sha=repo.tip("squashed")))
    remove(repo, "squashed", pull_requests=merged)
    assert "squashed" not in repo.local_branches()


def test_remove_squash_merged_branch_that_was_pushed_without_upstream(repo: Repo) -> None:
    stacked = repo.add("stacked")
    repo.commit_in(stacked)
    repo.push(stacked)
    repo.origin_delete_branch("stacked")
    with pytest.raises(Refusal, match="not verifiably merged"):
        remove(repo, "stacked", pull_requests=fake_pull_requests())
    merged = fake_pull_requests(stacked=PullRequest(number=1, state="merged", head_sha=repo.tip("stacked")))
    remove(repo, "stacked", pull_requests=merged)
    assert "stacked" not in repo.local_branches()


def test_remove_refuses_unmerged_and_dirty_unless_forced(repo: Repo) -> None:
    repo.commit_in(repo.add("wip"))
    with pytest.raises(Refusal, match="not verifiably merged"):
        remove(repo, "wip")
    (repo.checkout_from_origin("done") / "x.txt").write_text("x")
    with pytest.raises(Refusal, match="uncommitted changes"):
        remove(repo, "done")
    remove(repo, "wip", force=True)
    assert "wip" not in repo.local_branches()


def test_remove_refuses_the_default_branch_even_when_forced(repo: Repo) -> None:
    with pytest.raises(Refusal, match="default branch"):
        remove(repo, "main", force=True)
    assert repo.main.is_dir() and "main" in repo.local_branches()


def test_remove_refuses_the_worktree_holding_the_current_directory_even_when_forced(repo: Repo) -> None:
    inside = repo.checkout_from_origin("done") / "sub"
    inside.mkdir()
    for cwd in (repo.root / "done", inside):
        with pytest.raises(Refusal, match="current directory"):
            actions.remove(repo.root, "done", force=True, keep_branch=False, original_cwd=cwd)
    assert (repo.root / "done").is_dir()


def test_current_directory_is_recognised_through_a_symlink(repo: Repo, tmp_path: Path) -> None:
    stale_setup(repo)
    link = tmp_path / "link-to-repo"
    link.symlink_to(repo.root)
    with pytest.raises(Refusal, match="current directory"):
        actions.remove(repo.root, "clean", force=True, keep_branch=False, original_cwd=link / "clean")
    clean = prune_outcomes(repo, apply=True, cwd=link / "clean")["clean"]
    assert clean.action == "skip" and "current directory" in clean.notes
    assert (repo.root / "clean").is_dir()


def test_remove_finds_the_worktree_by_branch_not_by_folder_name(repo: Repo) -> None:
    repo.origin_branch("done")
    repo.fetch()
    other_path = repo.checkout("done", folder="some-other-folder")
    remove(repo, "done")
    assert not other_path.exists() and "done" not in repo.local_branches()


def test_remove_keep_branch_refuses_a_dirty_or_absent_worktree(repo: Repo) -> None:
    (repo.add("wip") / "x.txt").write_text("x")
    with pytest.raises(Refusal, match="uncommitted changes"):
        remove(repo, "wip", keep_branch=True)
    remove(repo, "wip", force=True, keep_branch=True)
    with pytest.raises(Refusal, match="has no worktree"):
        remove(repo, "wip", keep_branch=True)


def test_remove_keep_branch_and_orphaned_branch(repo: Repo) -> None:
    path = repo.add("wip")
    repo.commit_in(path)
    remove(repo, "wip", keep_branch=True)
    assert not path.exists() and "wip" in repo.local_branches()
    remove(repo, "wip", force=True)
    assert "wip" not in repo.local_branches()
    with pytest.raises(Refusal, match="No local branch"):
        remove(repo, "wip", force=True)


def test_remove_consults_pull_requests_only_after_the_local_checks(repo: Repo) -> None:
    def never_called(branch: str) -> PullRequest | None:
        raise AssertionError("gh must not be asked before a local refusal")

    (repo.checkout_from_origin("done") / "x.txt").write_text("x")
    with pytest.raises(Refusal, match="uncommitted changes"):
        remove(repo, "done", pull_requests=never_called)
    remove(repo, "done", force=True, pull_requests=never_called)


def test_add_defaults_and_refusals(repo: Repo) -> None:
    path = actions.add(repo.root, None, None)
    assert path.name == date.today().isoformat()
    with pytest.raises(Refusal, match="already exists:"):
        actions.add(repo.root, path.name, None)
    repo.origin_branch("theirs")
    with pytest.raises(Refusal, match="exists on origin"):
        actions.add(repo.root, "theirs", None)
    remove(repo, path.name, force=True, keep_branch=True)
    with pytest.raises(Refusal, match="exists locally"):
        actions.add(repo.root, path.name, None)


def test_add_starts_from_fresh_origin_head_and_slashes_become_dashes(repo: Repo) -> None:
    repo.origin_commit("newer main")
    path = actions.add(repo.root, "feature/thing", None)
    assert path.name == "feature-thing"
    assert repo.tip("feature/thing") == repo.tip("origin/main")


def test_checkout_remote_branch_tracks_and_is_idempotent(repo: Repo) -> None:
    repo.origin_branch("theirs")
    path, existed = actions.checkout(repo.root, "theirs")
    assert not existed and path.is_dir()
    assert git.git("rev-parse", "--abbrev-ref", "theirs@{upstream}", cwd=repo.root) == "origin/theirs"
    again, existed_now = actions.checkout(repo.root, "theirs")
    assert existed_now and again == path


def test_ensure_worktree_returns_checks_out_or_creates(repo: Repo) -> None:
    mine = repo.add("mine")
    assert actions.ensure_worktree(repo.root, "mine") == mine
    repo.origin_branch("theirs")
    theirs = actions.ensure_worktree(repo.root, "theirs")
    assert theirs == repo.root / "theirs" and theirs.is_dir()
    brand_new = actions.ensure_worktree(repo.root, "brand-new")
    assert brand_new.is_dir() and "brand-new" in repo.local_branches()
    assert actions.ensure_worktree(repo.root, None).name == date.today().isoformat()


def test_checkout_refusals(repo: Repo) -> None:
    with pytest.raises(Refusal, match="No branch 'np-9999'"):
        actions.checkout(repo.root, "np-9999")
    assert not (repo.root / "np-9999").exists()
    (repo.root / "stray").mkdir()
    with pytest.raises(Refusal, match="not a worktree"):
        actions.checkout(repo.root, "stray")
    repo.origin_branch("elsewhere")
    repo.fetch()
    other_path = repo.checkout("elsewhere", folder="some-other-folder")
    with pytest.raises(Refusal, match=f"already checked out at {other_path}"):
        actions.checkout(repo.root, "elsewhere")
