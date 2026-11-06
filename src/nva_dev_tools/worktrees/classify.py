from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nva_dev_tools.common import git
from nva_dev_tools.common.gh import PullRequest
from nva_dev_tools.worktrees.model import BranchStatus, Worktree

PullRequestLookup = Callable[[str], PullRequest | None]
"""Given a branch name, the latest pull request for it or None. Injected so tests can stub gh."""


@dataclass(frozen=True)
class PorcelainEntry:
    path: Path
    branch: str | None
    """None for a detached HEAD and for the bare entry."""
    bare: bool = False
    prunable: bool = False
    locked: bool = False


def parse_porcelain(text: str) -> list[PorcelainEntry]:
    """Parse `git worktree list --porcelain`: blank-line separated records of `key [value]` lines."""
    entries: list[PorcelainEntry] = []
    for record in text.strip().split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in record.splitlines() if line)
        if "worktree" not in fields:
            continue
        branch = fields.get("branch", "").removeprefix("refs/heads/")
        entries.append(
            PorcelainEntry(
                path=Path(fields["worktree"]),
                branch=branch or None,
                bare="bare" in fields,
                prunable="prunable" in fields,
                locked="locked" in fields,
            )
        )
    return entries


def list_worktrees(root: Path) -> list[PorcelainEntry]:
    return parse_porcelain(git.git("worktree", "list", "--porcelain", cwd=root))


def find_worktree(root: Path, branch: str) -> PorcelainEntry | None:
    """The worktree that has the branch checked out, whatever its folder is called."""
    return next((entry for entry in list_worktrees(root) if entry.branch == branch), None)


def classify_branch(
    branch: str, root: Path, default_ref: str, *, pull_requests: PullRequestLookup | None
) -> BranchStatus:
    """The one place that decides whether a branch is stale, up for review or safe to delete."""
    pull_request = pull_requests(branch) if pull_requests is not None else None
    on_origin = git.remote_branch_exists(branch, root)
    pushed = (
        on_origin
        or git.tracks_its_own_remote_branch(branch, root)
        or (pull_request is not None and _opened_from(branch, pull_request, root, default_ref))
    )
    in_default = git.is_ancestor(git.local_ref(branch), default_ref, root)
    status = BranchStatus(stale=in_default and pushed, review=in_default and not pushed, deletable=in_default)
    if in_default:
        status.notes.append("no own commits")

    if on_origin:
        ahead, behind = git.ahead_behind(git.local_ref(branch), git.remote_ref(branch), root)
        if ahead:
            status.notes.append(f"{ahead} unpushed")
        if behind:
            status.notes.append(f"{behind} behind")
    elif pushed:
        status.stale = True
        status.notes.append("gone from origin")
    else:
        status.notes.append("never pushed")

    if pull_requests is not None and pushed:
        if pull_request is None:
            status.notes.append("no PR")
        else:
            status.notes.append(f"PR #{pull_request.number} {pull_request.state}")
            if pull_request.state == "merged":
                status.stale = True
                contained, note = _merged_head_contains(branch, pull_request, root)
                status.deletable = status.deletable or contained
                if note is not None:
                    status.notes.append(note)
    return status


def _opened_from(branch: str, pull_request: PullRequest, root: Path, default_ref: str) -> bool:
    """True when the pull request shares a commit with the local branch that is not on the default branch.

    That proves a push git itself keeps no trace of: a branch pushed without setting its upstream, as stacked
    branches often are, is gone from origin once its pull request is merged. Comparing history rather than
    trusting the name keeps a never-pushed branch that merely shares its name with a pull request out of it.
    """
    if not _head_available(pull_request, root):
        return False
    shared = git.merge_base(git.local_ref(branch), pull_request.head_sha, root)
    return shared is not None and not git.is_ancestor(shared, default_ref, root)


def _head_available(pull_request: PullRequest, root: Path) -> bool:
    """Whether the pull request head is in the object store, fetching it first when it is not.

    That head is past the local tip when a reviewer pushed the last commits, and then usually not fetched
    either, since the branch is deleted on origin by the time the merge is noticed. GitHub keeps the pull
    request head under refs/pull/<number>/head, so it is fetched from there.
    """
    if not git.commit_exists(pull_request.head_sha, root):
        git.fetch_pull_request_head(pull_request.number, root)
    return git.commit_exists(pull_request.head_sha, root)


def _merged_head_contains(branch: str, pull_request: PullRequest, root: Path) -> tuple[bool, str | None]:
    """Whether every local commit is in the head that was merged, with a note when it is not."""
    if not _head_available(pull_request, root):
        return False, "merged head not fetched"
    if git.is_ancestor(git.local_ref(branch), pull_request.head_sha, root):
        return True, None
    return False, "unmerged local commits"


@dataclass(frozen=True)
class Listing:
    """The worktrees of a repository and the ref they are measured against, listed once per command."""

    root: Path
    entries: list[PorcelainEntry]
    """Every worktree except the bare entry."""
    default_ref: str

    @property
    def default_branch(self) -> str:
        return self.default_ref.removeprefix("origin/")

    @property
    def branches(self) -> list[str]:
        """The branches that get classified: every checked-out branch except the default one."""
        return [
            entry.branch for entry in self.entries if entry.branch is not None and entry.branch != self.default_branch
        ]


def list_repository(root: Path, *, fetch: bool) -> Listing:
    if fetch:
        git.fetch(root)
    entries = [entry for entry in list_worktrees(root) if not entry.bare]
    return Listing(root=root, entries=entries, default_ref=git.default_ref(root))


def classify(
    listing: Listing,
    *,
    pull_requests: PullRequestLookup | None = None,
    progress: Callable[[PorcelainEntry], None] | None = None,
) -> list[Worktree]:
    """Classify every worktree of the listing.

    pull_requests is consulted for every branch when given; None means no PR state is used.
    progress, if given, is called after each worktree, for a progress bar.
    """
    worktrees: list[Worktree] = []
    for entry in listing.entries:
        worktrees.append(classify_entry(entry, listing, pull_requests=pull_requests))
        if progress is not None:
            progress(entry)
    return worktrees


def classify_entry(entry: PorcelainEntry, listing: Listing, *, pull_requests: PullRequestLookup | None) -> Worktree:
    if entry.branch is None:
        status = BranchStatus(notes=["detached HEAD"])
    elif entry.branch == listing.default_branch:
        status = BranchStatus(notes=["default branch"])
    else:
        status = classify_branch(entry.branch, listing.root, listing.default_ref, pull_requests=pull_requests)

    worktree = Worktree(
        path=entry.path, name=_relative_name(entry.path, listing.root), branch=entry.branch, status=status
    )
    # git reports a locked worktree whose folder is gone as locked, not prunable, so look at the folder itself
    worktree.missing = entry.prunable or not entry.path.is_dir()
    worktree.dirty = not worktree.missing and git.is_dirty(entry.path)
    worktree.locked = entry.locked
    return worktree


def _relative_name(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
