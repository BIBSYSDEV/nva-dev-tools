"""A scratch origin and a bare + worktrees clone of it, like wt:clone makes, with git isolated from the machine."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from nva_dev_tools.common import git as production_git
from nva_dev_tools.common.gh import PullRequest
from nva_dev_tools.common.git import git
from nva_dev_tools.worktrees.classify import Listing, list_repository, list_worktrees
from nva_dev_tools.worktrees.classify import classify as classify_listing
from nva_dev_tools.worktrees.model import Worktree


@dataclass
class Repo:
    origin: Path
    root: Path
    """The folder holding .bare and the worktrees."""
    main: Path
    """The worktree for the default branch."""

    def origin_branch(self, name: str) -> None:
        git("branch", name, "main", cwd=self.origin)

    def origin_delete_branch(self, name: str) -> None:
        git("branch", "-D", name, cwd=self.origin)

    def origin_commit(self, message: str = "upstream change") -> None:
        git("commit", "--allow-empty", "-m", message, cwd=self.origin)

    def origin_commit_on(self, branch: str, message: str) -> str:
        """A commit on top of a branch in origin without checking it out, like a reviewer pushing. Returns the sha."""
        tree = git("rev-parse", f"{branch}^{{tree}}", cwd=self.origin)
        sha = git("commit-tree", tree, "-p", branch, "-m", message, cwd=self.origin)
        git("update-ref", f"refs/heads/{branch}", sha, cwd=self.origin)
        return sha

    def origin_pull_request_head(self, number: int, sha: str) -> None:
        """The refs/pull/<number>/head ref GitHub keeps for a pull request, also after the branch is deleted."""
        git("update-ref", f"refs/pull/{number}/head", sha, cwd=self.origin)

    def push(self, worktree: Path) -> None:
        git("push", "--quiet", "origin", "HEAD", cwd=worktree)

    def fetch(self) -> None:
        git("fetch", "--prune", "origin", cwd=self.root)

    def checkout(self, branch: str, folder: str | None = None) -> Path:
        """Worktree for an existing branch, local or on origin."""
        path = self.root / folder if folder else production_git.worktree_folder(self.root, branch)
        git("worktree", "add", str(path), branch, cwd=self.root)
        return path

    def checkout_from_origin(self, branch: str) -> Path:
        """A branch created on origin, fetched and checked out: the state after cloning a colleague's branch."""
        self.origin_branch(branch)
        self.fetch()
        return self.checkout(branch)

    def add(self, branch: str) -> Path:
        """New branch from origin/HEAD with a worktree."""
        path = production_git.worktree_folder(self.root, branch)
        git("worktree", "add", "-b", branch, str(path), "origin/HEAD", cwd=self.root)
        return path

    def commit_in(self, worktree: Path, message: str = "local work") -> None:
        git("commit", "--allow-empty", "-m", message, cwd=worktree)

    def tag(self, name: str, target: str = "origin/HEAD") -> None:
        git("tag", name, target, cwd=self.root)

    def lock_worktree(self, worktree: Path) -> None:
        git("worktree", "lock", str(worktree), cwd=self.root)

    def lock_branch_ref(self, branch: str) -> None:
        """A stale lock file on the ref, which makes git refuse to update or delete the branch."""
        lock = self.root / ".bare" / "refs" / "heads" / f"{branch}.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("")

    def commit_exists(self, sha: str) -> bool:
        return production_git.commit_exists(sha, self.root)

    def tip(self, branch: str) -> str:
        return git("rev-parse", branch, cwd=self.root)

    def local_branches(self) -> set[str]:
        return set(git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=self.root).split())

    def worktree_branches(self) -> set[str]:
        return {entry.branch for entry in list_worktrees(self.root) if entry.branch is not None}

    def listing(self, *, fetch: bool = True) -> Listing:
        return list_repository(self.root, fetch=fetch)

    def classify(self, *, fetch: bool = True, pull_requests=None) -> list[Worktree]:
        return classify_listing(self.listing(fetch=fetch), pull_requests=pull_requests)


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's own git config (signing, hooks, aliases) and NVA_REPOS_DIR out of the tests."""
    monkeypatch.delenv("NVA_REPOS_DIR", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    (home / "gitconfig").write_text("")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")


def make_origin(path: Path, default_branch: str = "main") -> Path:
    path.mkdir(parents=True)
    git("init", "-q", "-b", default_branch, cwd=path)
    git("commit", "-q", "--allow-empty", "-m", "init", cwd=path)
    return path


def bare_clone(origin: Path, root: Path) -> Repo:
    """A clone in the bare + worktrees layout, set up the way wt:clone does it."""
    git("clone", "-q", "--bare", "--single-branch", str(origin), str(root / ".bare"), cwd=origin.parent)
    (root / ".git").write_text("gitdir: ./.bare\n")
    git("config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*", cwd=root)
    git("fetch", "-q", "origin", cwd=root)
    git("remote", "set-head", "origin", "--auto", cwd=root)
    default_branch = git("symbolic-ref", "--short", "HEAD", cwd=root)
    git("worktree", "add", "-q", str(root / default_branch), default_branch, cwd=root)
    return Repo(origin=origin, root=root, main=root / default_branch)


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return bare_clone(make_origin(tmp_path / "origin"), tmp_path / "repo")


def fake_pull_requests(**by_branch: PullRequest | None):
    """A PullRequestLookup returning canned answers per branch, None for the rest."""
    return by_branch.get
