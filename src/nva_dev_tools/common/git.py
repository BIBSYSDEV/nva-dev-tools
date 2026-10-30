from pathlib import Path

from nva_dev_tools.common.output import warn
from nva_dev_tools.common.run import Refusal, run


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    """Run git and return stdout stripped. Raises CommandError on failure unless check is False."""
    return run(["git", *args], cwd=cwd, check=check).stdout.strip()


def git_succeeds(*args: str, cwd: Path | None = None) -> bool:
    """True when the git command exits zero. For questions whose answer is the exit code."""
    return run(["git", *args], cwd=cwd, check=False).returncode == 0


def repository_root(cwd: Path | None = None) -> Path:
    """The folder that holds the worktrees: the parent of the common git dir (the .bare folder).

    Refuses an ordinary clone, whose common dir is its .git folder: the worktree commands would otherwise
    nest worktrees inside the checkout and treat the checkout itself as one of them.
    """
    common_dir = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd))
    if git("config", "--bool", "core.bare", cwd=cwd, check=False) != "true":
        raise Refusal(
            f"{common_dir.parent} is an ordinary clone, not the bare + worktrees layout the wt tasks expect; "
            "clone it with wt:clone first"
        )
    return common_dir.parent


def default_ref(cwd: Path | None = None) -> str:
    """origin/<default branch>, falling back to origin/main when origin/HEAD is unknown."""
    completed = run(["git", "rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=cwd, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "origin/main"


def fetch(cwd: Path) -> None:
    """Fetch and prune origin, warning instead of failing when offline."""
    if not git_succeeds("fetch", "--quiet", "--prune", "origin", cwd=cwd):
        warn("fetch failed, using local state")


def ref_exists(ref: str, cwd: Path) -> bool:
    return git_succeeds("show-ref", "--verify", "--quiet", ref, cwd=cwd)


def local_ref(branch: str) -> str:
    """The full ref of a local branch. A bare branch name would resolve to a tag of the same name first."""
    return f"refs/heads/{branch}"


def remote_ref(branch: str) -> str:
    return f"refs/remotes/origin/{branch}"


def local_branch_exists(branch: str, cwd: Path) -> bool:
    return ref_exists(local_ref(branch), cwd)


def remote_branch_exists(branch: str, cwd: Path) -> bool:
    return ref_exists(remote_ref(branch), cwd)


def tracks_its_own_remote_branch(branch: str, cwd: Path) -> bool:
    """True when the branch is configured to track origin/<branch>, which git sets up when it is pushed.

    A branch created from origin/HEAD may track origin/main instead; that says nothing about it being pushed.
    """
    merge_ref = run(["git", "config", "--get", f"branch.{branch}.merge"], cwd=cwd, check=False).stdout.strip()
    return merge_ref == local_ref(branch)


def is_ancestor(commit: str, of: str, cwd: Path) -> bool:
    return git_succeeds("merge-base", "--is-ancestor", commit, of, cwd=cwd)


def commit_exists(sha: str, cwd: Path) -> bool:
    return git_succeeds("cat-file", "-e", f"{sha}^{{commit}}", cwd=cwd)


def fetch_pull_request_head(number: int, cwd: Path) -> bool:
    """Fetch the head commit of a GitHub pull request into the object store; False when that is not possible."""
    return git_succeeds("fetch", "--quiet", "origin", f"refs/pull/{number}/head", cwd=cwd)


def ahead_behind(branch: str, upstream: str, cwd: Path) -> tuple[int, int]:
    ahead, behind = git("rev-list", "--left-right", "--count", f"{branch}...{upstream}", cwd=cwd).split()
    return int(ahead), int(behind)


def is_dirty(worktree_path: Path) -> bool:
    return bool(git("status", "--porcelain", cwd=worktree_path))


def worktree_folder(root: Path, branch: str) -> Path:
    """Worktree folders are named after the branch, with slashes turned into dashes."""
    return root / branch.replace("/", "-")


def remove_worktree(worktree_path: Path, cwd: Path) -> None:
    """Remove a worktree, also when its folder is already gone.

    With --force git drops just this worktree's bookkeeping, unlike `git worktree prune`, which would drop
    the bookkeeping of every worktree whose folder is missing.
    """
    git("worktree", "remove", "--force", str(worktree_path), cwd=cwd)


def delete_branch(branch: str, cwd: Path) -> None:
    git("branch", "-D", "--quiet", branch, cwd=cwd)
