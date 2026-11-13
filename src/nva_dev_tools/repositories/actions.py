"""Operations over every clone in a folder: plain arguments in, results out. No Click, no prompts."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from nva_dev_tools.common import git
from nva_dev_tools.common.run import CommandError, Refusal, run
from nva_dev_tools.worktrees.classify import find_worktree

UPDATED = "updated"
UP_TO_DATE = "up to date"
SKIPPED = "skipped"
FAILED = "failed"

PARALLEL_CLONES = 8
"""Work on a clone mostly waits for the network or git, so a few at a time cut the wall-clock time for 30+ clones."""


@dataclass(frozen=True)
class PullResult:
    repository: str
    status: str
    """UPDATED, UP_TO_DATE, SKIPPED or FAILED."""
    detail: str


def find_repositories(clones_folder: Path, names: tuple[str, ...] = ()) -> list[Path]:
    """The clones directly in the folder, sorted by name, or only the named ones in the order given.

    A clone is a folder with a .git entry, so both the bare + worktrees layout and an ordinary clone count.
    """
    if not clones_folder.is_dir():
        raise Refusal(f"{clones_folder} is not a folder; set NVA_REPOS_DIR to the folder that holds your NVA clones")
    clones = sorted(
        (path for path in clones_folder.iterdir() if (path / ".git").exists()),
        key=lambda path: path.name.lower(),
    )
    if not clones:
        raise Refusal(
            f"No git clones in {clones_folder}; run from the folder that holds your NVA clones or set NVA_REPOS_DIR"
        )
    if not names:
        return clones
    clones_by_name = {clone.name: clone for clone in clones}
    unknown_names = [name for name in names if name not in clones_by_name]
    if unknown_names:
        raise Refusal(f"No clone named {', '.join(unknown_names)} in {clones_folder}")
    return [clones_by_name[name] for name in names]


def in_parallel[Result](
    function: Callable[[Path], Result], clones: list[Path], *, progress: Callable[[Path], None] | None = None
) -> list[Result]:
    """function() for every clone, a few at a time. Results keep the order of clones; progress hears of each clone
    as it ends."""
    with ThreadPoolExecutor(max_workers=PARALLEL_CLONES) as executor:
        clones_by_future = {executor.submit(function, clone): clone for clone in clones}
        for finished in as_completed(clones_by_future):
            if progress is not None:
                progress(clones_by_future[finished])
        return [future.result() for future in clones_by_future]


def fetch_origin(clone: Path) -> str | None:
    """Fetch and prune origin. None when that worked, otherwise the reason git gives."""
    fetched = run(["git", "fetch", "--quiet", "--prune", "origin"], cwd=clone, check=False)
    return None if fetched.returncode == 0 else first_line(fetched.stderr)


def pull(clone: Path) -> PullResult:
    """Fetch origin and fast-forward the worktree that has the default branch checked out, whatever its folder.

    A worktree with uncommitted changes, or with local commits that are not on origin, is never touched.
    Untracked files do not count: a fast-forward refuses to overwrite them, so it cannot lose them.
    A failure is a result, not an exception, so one broken clone does not stop the others.
    """
    try:
        status, detail = _pull(clone)
    except CommandError as failure:
        status, detail = FAILED, str(failure)
    return PullResult(clone.name, status, detail)


def _pull(clone: Path) -> tuple[str, str]:
    fetch_failure = fetch_origin(clone)
    if fetch_failure is not None:
        return FAILED, f"fetch failed: {fetch_failure}"
    default_ref = git.default_ref(clone)
    default_branch = default_ref.removeprefix("origin/")
    if not git.remote_branch_exists(default_branch, clone):
        return FAILED, f"{default_ref} not found"
    default_worktree = find_worktree(clone, default_branch)
    if default_worktree is None:
        return SKIPPED, f"no worktree has {default_branch} checked out"

    worktree = default_worktree.path
    if git.git("status", "--porcelain", "--untracked-files=no", cwd=worktree):
        return SKIPPED, "uncommitted changes"
    ahead, behind = git.ahead_behind("HEAD", default_ref, worktree)
    if ahead:
        return SKIPPED, f"{_commits(ahead)} not on {default_ref}"
    before = git.git("rev-parse", "--short", "HEAD", cwd=worktree)
    if not behind:
        return UP_TO_DATE, before
    merged = run(["git", "merge", "--ff-only", "--quiet", default_ref], cwd=worktree, check=False)
    if merged.returncode != 0:
        return FAILED, f"fast-forward failed: {first_line(merged.stderr)}"
    after = git.git("rev-parse", "--short", "HEAD", cwd=worktree)
    return UPDATED, f"{before}..{after} ({_commits(behind)})"


def _commits(count: int) -> str:
    return f"{count} commit" if count == 1 else f"{count} commits"


def first_line(stderr: str) -> str:
    """The reason git gives. What follows is generic advice, such as "make sure ... the repository exists"."""
    lines = stderr.strip().splitlines()
    return lines[0] if lines else "no message from git"
