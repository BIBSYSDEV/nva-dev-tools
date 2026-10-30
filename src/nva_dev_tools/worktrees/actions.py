"""Pure worktree operations: plain arguments in, results or exceptions out. No Click, no prompts."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from nva_dev_tools.common import git
from nva_dev_tools.common.run import CommandError, Refusal
from nva_dev_tools.worktrees.classify import PullRequestLookup, classify_branch, find_worktree
from nva_dev_tools.worktrees.model import Worktree


@dataclass
class PruneOutcome:
    worktree: Worktree
    action: str
    """review, skip, prune, pruned or failed."""
    notes: list[str] = field(default_factory=list)
    """The worktree's notes plus anything prune added, such as "current directory"."""


def prune(root: Path, worktrees: list[Worktree], *, apply: bool, force: bool, original_cwd: Path) -> list[PruneOutcome]:
    """Decide, and with apply carry out, the removal of stale worktrees together with their branches.

    Runs git from root so removing a worktree never pulls the rug from under the caller's shell;
    the worktree containing original_cwd is skipped for the same reason. A failed removal is an
    outcome, not an exception.
    """
    outcomes: list[PruneOutcome] = []
    for worktree in worktrees:
        if not (worktree.status.stale or worktree.status.review):
            continue
        outcome = PruneOutcome(worktree=worktree, action="prune", notes=worktree.notes)
        outcomes.append(outcome)

        if worktree.status.review:
            outcome.action = "review"
        elif _holds(worktree.path, original_cwd):
            outcome.action = "skip"
            outcome.notes.append("current directory")
        elif not force and (worktree.dirty or not worktree.status.deletable):
            outcome.action = "skip"
        elif apply:
            _remove_worktree_and_branch(root, worktree, outcome)
    return outcomes


def _remove_worktree_and_branch(root: Path, worktree: Worktree, outcome: PruneOutcome) -> None:
    try:
        git.remove_worktree(worktree.path, root)
    except CommandError:
        outcome.action = "failed"
        outcome.notes.append("could not remove worktree")
        return
    if worktree.branch is not None:
        try:
            git.delete_branch(worktree.branch, root)
        except CommandError:
            outcome.action = "failed"
            outcome.notes.append("worktree removed, could not delete branch")
            return
    outcome.action = "pruned"


def remove(
    root: Path,
    branch: str,
    *,
    force: bool,
    keep_branch: bool,
    original_cwd: Path,
    pull_requests: PullRequestLookup | None = None,
) -> None:
    """Remove a branch's worktree together with the branch, if that is safe or forced.

    Refuses the default branch and the worktree holding original_cwd even when forced: the first is the
    layout itself, and removing the second would leave the caller's shell in a deleted folder.
    pull_requests is only consulted once the local checks pass, so a lazy lookup costs nothing before that.
    """
    default_ref = git.default_ref(root)
    if branch == default_ref.removeprefix("origin/"):
        raise Refusal(f"'{branch}' is the default branch, its worktree stays")
    worktree = find_worktree(root, branch)
    if worktree is None:
        if keep_branch:
            raise Refusal(f"Branch '{branch}' has no worktree")
        if not git.local_branch_exists(branch, root):
            raise Refusal(f"No local branch '{branch}'")
    elif _holds(worktree.path, original_cwd):
        raise Refusal(f"Worktree '{branch}' is the current directory; leave it first")

    if not force:
        if worktree is not None and worktree.path.is_dir() and git.is_dirty(worktree.path):
            raise Refusal(f"Worktree '{branch}' has uncommitted changes; use --force to remove it anyway")
        if not keep_branch:
            git.fetch(root)
            if not classify_branch(branch, root, default_ref, pull_requests=pull_requests).deletable:
                raise Refusal(
                    f"Branch '{branch}' is not verifiably merged into {default_ref}; "
                    "use --force to remove it anyway, or --keep-branch"
                )

    if worktree is not None:
        git.remove_worktree(worktree.path, root)
    if not keep_branch:
        git.delete_branch(branch, root)


def add(root: Path, branch: str | None, base: str | None, *, fetch: bool = True) -> Path:
    """Create a new branch from origin/HEAD (or base) and a worktree for it. Returns the worktree path."""
    branch = branch or todays_branch_name()
    worktree_path = git.worktree_folder(root, branch)

    if worktree_path.exists():
        raise Refusal(f"Worktree for '{branch}' already exists: {worktree_path}")

    if fetch:
        git.fetch(root)
    if git.local_branch_exists(branch, root):
        raise Refusal(f"Branch '{branch}' already exists locally; use wt:checkout to get a worktree for it")
    if git.remote_branch_exists(branch, root):
        raise Refusal(f"Branch '{branch}' already exists on origin; use wt:checkout to work on it")

    # --no-track: the branch is not pushed yet, so it must not look like it tracks origin/main
    git.git("worktree", "add", "--no-track", "-b", branch, str(worktree_path), base or git.default_ref(root), cwd=root)
    return worktree_path


def checkout(root: Path, branch: str, *, fetch: bool = True) -> tuple[Path, bool]:
    """Create a worktree for an existing local or remote branch. Returns (path, already_existed)."""
    worktree_path = git.worktree_folder(root, branch)

    existing = find_worktree(root, branch)
    if existing is not None:
        if existing.path == worktree_path:
            return worktree_path, True
        raise Refusal(f"Branch '{branch}' is already checked out at {existing.path}")
    if worktree_path.exists():
        raise Refusal(f"{worktree_path} exists but is not a worktree for '{branch}'")

    if fetch:
        git.fetch(root)
    if not (git.local_branch_exists(branch, root) or git.remote_branch_exists(branch, root)):
        raise Refusal(f"No branch '{branch}' locally or on origin; use wt:add to create it")
    # For a branch that only exists on origin, git creates a local tracking branch
    git.git("worktree", "add", str(worktree_path), branch, cwd=root)
    return worktree_path, False


def ensure_worktree(root: Path, branch: str | None) -> Path:
    """The worktree of the branch (default: today's date), checked out or created first when there is none."""
    branch = branch or todays_branch_name()
    existing = find_worktree(root, branch)
    if existing is not None:
        return existing.path

    git.fetch(root)
    if git.local_branch_exists(branch, root) or git.remote_branch_exists(branch, root):
        return checkout(root, branch, fetch=False)[0]
    return add(root, branch, None, fetch=False)


def todays_branch_name() -> str:
    """The branch name used when none is given: today's date."""
    return date.today().isoformat()


def _holds(worktree_path: Path, cwd: Path) -> bool:
    """True when cwd is the worktree folder or inside it. Resolved, since git keeps the path it was added with."""
    return cwd.resolve().is_relative_to(worktree_path.resolve())
