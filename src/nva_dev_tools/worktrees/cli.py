"""The wt command group: options, output and interactivity. Logic lives in classify.py and actions.py."""

import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import click

from nva_dev_tools.common import gh, git
from nva_dev_tools.common.output import error, print_table
from nva_dev_tools.common.run import Refusal
from nva_dev_tools.worktrees import actions
from nva_dev_tools.worktrees.classify import PullRequestLookup, classify, list_repository
from nva_dev_tools.worktrees.model import Worktree

fetch_option = click.option(
    "--no-fetch", "fetch", is_flag=True, default=True, flag_value=False, help="Skip git fetch --prune first."
)
pr_option = click.option(
    "--no-pr",
    "check_pr",
    is_flag=True,
    default=True,
    flag_value=False,
    help="Skip the PR state lookup via gh (faster, but squash merges are not detected).",
)


ACTION_ORDER = {"pruned": 0, "prune": 0, "failed": 1, "skip": 2, "review": 3}
"""Prune table order: what goes (or went) first, then what did not, then what is left for the user."""

STATE_ORDER = {"stale": 0, "review": 1, "-": 2}
"""List table order: stale first, then review, then the rest."""


@click.group()
def wt() -> None:
    """Git worktrees in the bare + one-worktree-per-branch layout."""


def pull_request_lookup(root: Path, branches: list[str]) -> PullRequestLookup | None:
    """A lookup fed by one gh request for all branches, or None when gh fails."""
    pull_requests = gh.latest_pull_requests(branches, root)
    return None if pull_requests is None else pull_requests.get


def classify_with_progress(root: Path, *, fetch: bool, check_pr: bool) -> list[Worktree]:
    """classify() with a progress bar on stderr; Click hides the bar when stderr is not a terminal."""
    listing = list_repository(root, fetch=fetch)
    pull_requests = pull_request_lookup(root, listing.branches) if check_pr else None
    with click.progressbar(
        length=len(listing.entries),
        label="Checking worktrees",
        file=sys.stderr,
        show_eta=False,
        item_show_func=lambda entry: entry.branch if entry is not None else None,
    ) as bar:
        return classify(listing, pull_requests=pull_requests, progress=lambda entry: bar.update(1, entry))


@wt.command("list")
@fetch_option
@pr_option
def list_command(fetch: bool, check_pr: bool) -> None:
    """List worktrees and flag stale ones."""
    root = git.repository_root()
    worktrees = classify_with_progress(root, fetch=fetch, check_pr=check_pr)
    worktrees.sort(key=lambda worktree: (STATE_ORDER[worktree.state], worktree.name))
    rows = [
        [worktree.name, worktree.branch or "(detached)", worktree.state, ", ".join(worktree.notes)]
        for worktree in worktrees
    ]
    print_table(["WORKTREE", "BRANCH", "STALE", "NOTES"], rows, styled_column=2)


@wt.command()
@click.option("-y", "--yes", is_flag=True, help="Actually remove (default: only show).")
@click.option(
    "-f", "--force", is_flag=True, help="Also remove stale worktrees that are dirty or have unmerged local commits."
)
@pr_option
@fetch_option
@click.pass_context
def prune(context: click.Context, yes: bool, force: bool, check_pr: bool, fetch: bool) -> None:
    """Remove stale worktrees together with their branches. Shows what it would do unless --yes."""
    original_cwd = Path.cwd()
    root = git.repository_root()
    worktrees = classify_with_progress(root, fetch=fetch, check_pr=check_pr)
    outcomes = actions.prune(root, worktrees, apply=yes, force=force, original_cwd=original_cwd)

    if outcomes:
        outcomes.sort(key=lambda outcome: (ACTION_ORDER[outcome.action], outcome.worktree.name))
        rows = [
            [outcome.action, outcome.worktree.name, outcome.worktree.branch or "(detached)", ", ".join(outcome.notes)]
            for outcome in outcomes
        ]
        print_table(
            ["ACTION", "WORKTREE", "BRANCH", "NOTES"],
            rows,
            styled_column=0,
            row_style=lambda row: "red" if row[0] == "failed" else None,
        )
        click.echo()

    counts = Counter(outcome.action for outcome in outcomes)
    if yes:
        click.echo(f"Pruned {counts['pruned']} worktree(s) with their branches")
    elif counts["prune"]:
        click.echo(f"{counts['prune']} worktree(s) can be pruned with their branches: mise run wt:prune --yes")
    else:
        click.echo("Nothing to prune")
    if counts["skip"]:
        click.echo(f"{counts['skip']} skipped: dirty or with unmerged local commits (--force includes them)")
    if counts["review"]:
        click.echo(
            f"{counts['review']} never pushed and without own commits: remove by hand with wt:remove if they are done"
        )
    if counts["failed"]:
        click.echo(f"{counts['failed']} failed, see the table")
        context.exit(1)


@wt.command()
@click.argument("branch")
@click.option("-f", "--force", is_flag=True, help="Remove even if dirty or not merged.")
@click.option("-k", "--keep-branch", is_flag=True, help="Remove the worktree only.")
@pr_option
def remove(branch: str, force: bool, keep_branch: bool, check_pr: bool) -> None:
    """Remove a branch's worktree together with the branch."""
    original_cwd = Path.cwd()
    root = git.repository_root()

    def lookup(requested_branch: str) -> gh.PullRequest | None:
        # Asks gh only when the action gets that far, so a refusal for a local reason never waits for GitHub
        return (gh.latest_pull_requests([requested_branch], root) or {}).get(requested_branch)

    actions.remove(
        root,
        branch,
        force=force,
        keep_branch=keep_branch,
        original_cwd=original_cwd,
        pull_requests=lookup if check_pr else None,
    )


@wt.command()
@click.argument("branch", required=False)
@click.argument("base", required=False)
def add(branch: str | None, base: str | None) -> None:
    """Create a branch and a worktree for it.

    BRANCH defaults to today's date; BASE to origin/HEAD.
    """
    worktree_path = actions.add(git.repository_root(), branch, base)
    click.echo(worktree_path)


@wt.command()
@click.argument("branch")
def checkout(branch: str) -> None:
    """Create a worktree for an existing local or remote branch."""
    worktree_path, existed = actions.checkout(git.repository_root(), branch)
    if existed:
        error(f"Worktree for '{branch}' already exists")
    click.echo(worktree_path)


@wt.command("open")
@click.argument("editor")
@click.argument("branch", required=False)
@click.pass_context
def open_command(context: click.Context, editor: str, branch: str | None) -> None:
    """Open a branch's worktree in EDITOR, checking it out or creating it first if needed.

    EDITOR is a command such as code or idea; BRANCH defaults to today's date.
    """
    if shutil.which(editor) is None:
        raise Refusal(f"Editor '{editor}' is not on PATH")
    worktree_path = actions.ensure_worktree(git.repository_root(), branch)
    context.exit(subprocess.run([editor, str(worktree_path)], check=False).returncode)
