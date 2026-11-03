from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BranchStatus:
    """How a branch relates to origin and the default branch."""

    stale: bool = False
    """Pushed and merged, pushed and since deleted on origin, or a merged pull request."""
    review: bool = False
    """Never pushed and no commits beyond the default branch: nothing to lose, but maybe work in progress."""
    deletable: bool = False
    """Every local commit is in the default branch or in the merged pull request."""
    notes: list[str] = field(default_factory=list)


@dataclass
class Worktree:
    """One worktree with its classification. Callers format; this never joins strings."""

    path: Path
    name: str
    """Path relative to the repository root, as shown to the user."""
    branch: str | None
    """None for a detached HEAD."""
    status: BranchStatus = field(default_factory=BranchStatus)
    dirty: bool = False
    missing: bool = False
    """The folder is gone but git still has the bookkeeping."""
    locked: bool = False

    @property
    def notes(self) -> list[str]:
        notes = list(self.status.notes)
        if self.missing:
            notes.append("folder missing")
        if self.dirty:
            notes.append("dirty")
        if self.locked:
            notes.append("locked")
        return notes
