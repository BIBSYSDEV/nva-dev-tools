from collections.abc import Callable

import pytest
from conftest import Repo, fake_pull_requests

from nva_dev_tools.common.gh import PullRequest
from nva_dev_tools.worktrees.classify import PullRequestLookup, parse_porcelain
from nva_dev_tools.worktrees.model import Worktree

PORCELAIN = """\
worktree /repos/nva-nvi/.bare
bare

worktree /repos/nva-nvi/main
HEAD 967b07b0000000000000000000000000000000000
branch refs/heads/main

worktree /repos/nva-nvi/old
HEAD 3ff584c0000000000000000000000000000000000
branch refs/heads/feature/old
prunable gitdir file points to non-existent location

worktree /repos/nva-nvi/loose
HEAD 0fee41990000000000000000000000000000000000
detached
"""


def test_parse_porcelain_reads_every_record_kind() -> None:
    entries = parse_porcelain(PORCELAIN)
    assert [entry.path.name for entry in entries] == [".bare", "main", "old", "loose"]
    assert entries[0].bare
    assert entries[1].branch == "main"
    assert entries[2].branch == "feature/old" and entries[2].prunable
    assert entries[3].branch is None


def test_default_branch_and_bare_entry(repo: Repo) -> None:
    worktrees = repo.classify(fetch=False)
    assert [worktree.name for worktree in worktrees] == ["main"]
    assert worktrees[0].notes == ["default branch"]
    assert not (worktrees[0].status.stale or worktrees[0].status.review)


# --- The classification matrix. Each scenario prepares a branch called "topic" and states what to expect.

Scenario = Callable[[Repo], PullRequestLookup | None]


def fresh_at_tip(repo: Repo) -> None:
    repo.add("topic")


def fresh_main_moved_past(repo: Repo) -> None:
    repo.add("topic")
    repo.origin_commit()


def never_pushed_with_own_commits(repo: Repo) -> None:
    repo.commit_in(repo.add("topic"))


def never_pushed_with_own_commits_and_a_tag_of_the_same_name(repo: Repo) -> None:
    repo.commit_in(repo.add("topic"))
    repo.tag("topic")


def pushed_and_merged_fast_forward(repo: Repo) -> None:
    repo.checkout_from_origin("topic")


def pushed_and_merged_via_later_commit_on_main(repo: Repo) -> None:
    repo.checkout_from_origin("topic")
    repo.origin_commit("someone merged something else")


def gone_from_origin_without_own_commits(repo: Repo) -> None:
    repo.checkout_from_origin("topic")
    repo.origin_delete_branch("topic")


def gone_from_origin_with_own_commits(repo: Repo) -> None:
    repo.commit_in(repo.checkout_from_origin("topic"), "feature work")
    repo.origin_delete_branch("topic")


def squash_merged_pull_request(repo: Repo) -> PullRequestLookup:
    gone_from_origin_with_own_commits(repo)
    return fake_pull_requests(topic=PullRequest(number=42, state="merged", head_sha=repo.tip("topic")))


def squash_merged_then_more_local_commits(repo: Repo) -> PullRequestLookup:
    gone_from_origin_with_own_commits(repo)
    merged_tip = repo.tip("topic")
    repo.commit_in(repo.root / "topic", "forgot something")
    return fake_pull_requests(topic=PullRequest(number=42, state="merged", head_sha=merged_tip))


def squash_merged_after_reviewer_pushed_more(repo: Repo) -> PullRequestLookup:
    """The merged head is a commit the local clone never fetched, since the branch was gone before the next fetch."""
    repo.commit_in(repo.checkout_from_origin("topic"), "feature work")
    repo.push(repo.root / "topic")
    merged_tip = repo.origin_commit_on("topic", "reviewer fixup")
    repo.origin_pull_request_head(42, merged_tip)
    repo.origin_delete_branch("topic")
    assert not repo.commit_exists(merged_tip)
    return fake_pull_requests(topic=PullRequest(number=42, state="merged", head_sha=merged_tip))


def squash_merged_with_a_head_that_cannot_be_fetched(repo: Repo) -> PullRequestLookup:
    gone_from_origin_with_own_commits(repo)
    return fake_pull_requests(topic=PullRequest(number=42, state="merged", head_sha="0" * 40))


def pushed_without_upstream_then_squash_merged(repo: Repo) -> PullRequestLookup:
    """Pushed without -u, as stacked branches often are, so only the pull request shows it was ever pushed."""
    path = repo.add("topic")
    repo.commit_in(path, "feature work")
    repo.push(path)
    repo.origin_delete_branch("topic")
    return fake_pull_requests(topic=PullRequest(number=42, state="merged", head_sha=repo.tip("topic")))


def pushed_without_upstream_squash_merged_then_more_local_commits(repo: Repo) -> PullRequestLookup:
    pull_requests = pushed_without_upstream_then_squash_merged(repo)
    repo.commit_in(repo.root / "topic", "forgot something")
    return pull_requests


def never_pushed_sharing_its_name_with_a_merged_pull_request(repo: Repo) -> PullRequestLookup:
    """Someone else's pull request from a branch of the same name, with no commits beyond main in common."""
    repo.origin_branch("theirs")
    their_head = repo.origin_commit_on("theirs", "their work")
    repo.commit_in(repo.add("topic"))
    return fake_pull_requests(topic=PullRequest(number=42, state="merged", head_sha=their_head))


def fresh_sharing_its_name_with_a_merged_pull_request(repo: Repo) -> PullRequestLookup:
    repo.origin_branch("theirs")
    their_head = repo.origin_commit_on("theirs", "their work")
    repo.add("topic")
    return fake_pull_requests(topic=PullRequest(number=42, state="merged", head_sha=their_head))


def open_pull_request(repo: Repo) -> PullRequestLookup:
    repo.commit_in(repo.checkout_from_origin("topic"))
    return fake_pull_requests(topic=PullRequest(number=7, state="open", head_sha=repo.tip("topic")))


def pushed_without_pull_request(repo: Repo) -> PullRequestLookup:
    repo.commit_in(repo.checkout_from_origin("topic"))
    return fake_pull_requests()


def merged_but_dirty(repo: Repo) -> None:
    (repo.checkout_from_origin("topic") / "x.txt").write_text("x")


def merged_folder_deleted_by_hand(repo: Repo) -> None:
    repo.checkout_from_origin("topic").rename(repo.root.parent / "moved-away")


def locked_and_folder_deleted_by_hand(repo: Repo) -> None:
    path = repo.checkout_from_origin("topic")
    repo.lock_worktree(path)
    path.rename(repo.root.parent / "moved-away")


def ahead_of_origin(repo: Repo) -> None:
    repo.commit_in(repo.checkout_from_origin("topic"))


MATRIX: list[tuple[Scenario, dict[str, bool], list[str]]] = [
    (fresh_at_tip, {"review": True, "deletable": True}, ["no own commits", "never pushed"]),
    (fresh_main_moved_past, {"review": True, "deletable": True}, ["no own commits", "never pushed"]),
    (never_pushed_with_own_commits, {}, ["never pushed"]),
    (never_pushed_with_own_commits_and_a_tag_of_the_same_name, {}, ["never pushed"]),
    (pushed_and_merged_fast_forward, {"stale": True, "deletable": True}, ["no own commits"]),
    (pushed_and_merged_via_later_commit_on_main, {"stale": True, "deletable": True}, ["no own commits"]),
    (gone_from_origin_without_own_commits, {"stale": True, "deletable": True}, ["no own commits", "gone from origin"]),
    (gone_from_origin_with_own_commits, {"stale": True}, ["gone from origin"]),
    (squash_merged_pull_request, {"stale": True, "deletable": True}, ["gone from origin", "PR #42 merged"]),
    (
        squash_merged_then_more_local_commits,
        {"stale": True},
        ["gone from origin", "PR #42 merged", "unmerged local commits"],
    ),
    (
        squash_merged_after_reviewer_pushed_more,
        {"stale": True, "deletable": True},
        ["gone from origin", "PR #42 merged"],
    ),
    (
        squash_merged_with_a_head_that_cannot_be_fetched,
        {"stale": True},
        ["gone from origin", "PR #42 merged", "merged head not fetched"],
    ),
    (
        pushed_without_upstream_then_squash_merged,
        {"stale": True, "deletable": True},
        ["gone from origin", "PR #42 merged"],
    ),
    (
        pushed_without_upstream_squash_merged_then_more_local_commits,
        {"stale": True},
        ["gone from origin", "PR #42 merged", "unmerged local commits"],
    ),
    (never_pushed_sharing_its_name_with_a_merged_pull_request, {}, ["never pushed"]),
    (
        fresh_sharing_its_name_with_a_merged_pull_request,
        {"review": True, "deletable": True},
        ["no own commits", "never pushed"],
    ),
    (open_pull_request, {}, ["1 unpushed", "PR #7 open"]),
    (pushed_without_pull_request, {}, ["1 unpushed", "no PR"]),
    (merged_but_dirty, {"stale": True, "deletable": True, "dirty": True}, ["no own commits", "dirty"]),
    (
        merged_folder_deleted_by_hand,
        {"stale": True, "deletable": True, "missing": True},
        ["no own commits", "folder missing"],
    ),
    (
        locked_and_folder_deleted_by_hand,
        {"stale": True, "deletable": True, "missing": True, "locked": True},
        ["no own commits", "folder missing", "locked"],
    ),
    (ahead_of_origin, {}, ["1 unpushed"]),
]

BRANCH_FLAGS = ("stale", "review", "deletable")
WORKTREE_FLAGS = ("dirty", "missing", "locked")


@pytest.mark.parametrize(
    ("scenario", "expected_flags", "expected_notes"), MATRIX, ids=lambda value: getattr(value, "__name__", "")
)
def test_classification_matrix(
    repo: Repo, scenario: Scenario, expected_flags: dict[str, bool], expected_notes: list[str]
) -> None:
    pull_requests = scenario(repo)
    worktrees = repo.classify(pull_requests=pull_requests)
    topic = next(worktree for worktree in worktrees if worktree.branch == "topic")
    assert flags_of(topic) == {flag: expected_flags.get(flag, False) for flag in BRANCH_FLAGS + WORKTREE_FLAGS}
    assert topic.notes == expected_notes


def flags_of(worktree: Worktree) -> dict[str, bool]:
    branch_flags = {flag: getattr(worktree.status, flag) for flag in BRANCH_FLAGS}
    return branch_flags | {flag: getattr(worktree, flag) for flag in WORKTREE_FLAGS}
