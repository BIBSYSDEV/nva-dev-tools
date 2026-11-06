from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from conftest import Repo

from nva_dev_tools.cli import cli


@pytest.fixture
def in_main(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> Repo:
    monkeypatch.chdir(repo.main)
    return repo


def test_list_prints_a_table(in_main: Repo) -> None:
    in_main.add("fresh")
    result = CliRunner().invoke(cli, ["wt", "list", "--no-pr"])
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0].split() == ["STATUS", "WORKTREE", "BRANCH", "NOTES"]
    assert any(line.split()[:2] == ["review", "fresh"] for line in lines)


def stale_worktree(repo: Repo, branch: str = "done") -> None:
    repo.checkout_from_origin(branch)
    repo.origin_delete_branch(branch)


def prune(*args: str, answer: str | None = None) -> Result:
    return CliRunner().invoke(cli, ["wt", "prune", "--no-pr", *args], input=answer)


@pytest.fixture
def in_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nva_dev_tools.worktrees.cli.can_prompt", lambda: True)


def test_list_and_the_prune_preview_show_the_same_table(in_main: Repo) -> None:
    stale_worktree(in_main)
    in_main.add("fresh")
    listed = CliRunner().invoke(cli, ["wt", "list", "--no-pr"])
    previewed = prune()
    assert listed.exit_code == 0 and previewed.exit_code == 0, previewed.output
    assert previewed.stdout.startswith(listed.stdout)
    assert listed.stdout.splitlines()[1].split()[:2] == ["prune", "done"]
    assert "1 not stale, kept" in listed.stdout, "the main worktree is accounted for"


def test_prune_without_a_terminal_removes_nothing_unless_yes(in_main: Repo) -> None:
    stale_worktree(in_main)
    previewed = prune()
    assert previewed.exit_code == 0, previewed.output
    assert "pass --yes" in previewed.stdout and (in_main.root / "done").exists()
    applied = prune("--yes")
    assert applied.exit_code == 0, applied.output
    assert "Pruned 1 worktree(s)" in applied.stdout and not (in_main.root / "done").exists()


@pytest.mark.usefixtures("in_a_terminal")
def test_prune_in_a_terminal_asks_first_and_defaults_to_no(in_main: Repo) -> None:
    stale_worktree(in_main)
    for answer in ("\n", "n\n"):
        declined = prune(answer=answer)
        assert declined.exit_code == 0, declined.output
        assert "Remove 1 worktree(s) and their branches? [y/N]" in declined.stdout
        assert "Nothing removed" in declined.stdout and (in_main.root / "done").exists()
    accepted = prune(answer="y\n")
    assert accepted.exit_code == 0, accepted.output
    assert "Pruned 1 worktree(s)" in accepted.stdout and not (in_main.root / "done").exists()


@pytest.mark.usefixtures("in_a_terminal")
def test_prune_force_names_the_work_it_would_lose(in_main: Repo) -> None:
    in_main.commit_in(in_main.checkout_from_origin("squashed"))
    in_main.origin_delete_branch("squashed")
    declined = prune("--force", answer="n\n")
    assert "including 1 with uncommitted changes or unmerged commits?" in declined.stdout
    assert (in_main.root / "squashed").exists()


@pytest.mark.usefixtures("in_a_terminal")
def test_prune_does_not_ask_when_there_is_nothing_to_prune(in_main: Repo) -> None:
    result = prune()
    assert result.exit_code == 0, result.output
    assert "Nothing to prune" in result.stdout and "Remove" not in result.stdout


def test_prune_exits_one_when_a_removal_fails(in_main: Repo) -> None:
    in_main.checkout_from_origin("locked")
    in_main.origin_delete_branch("locked")
    in_main.lock_worktree(in_main.root / "locked")
    result = CliRunner().invoke(cli, ["wt", "prune", "--no-pr", "--yes"])
    assert result.exit_code == 1
    assert "failed" in result.stdout


def test_list_leaves_pr_state_out_when_gh_fails(in_main: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    in_main.commit_in(in_main.checkout_from_origin("pushed"))
    monkeypatch.setattr("nva_dev_tools.worktrees.cli.gh.latest_pull_requests", lambda branches, cwd: None)
    result = CliRunner().invoke(cli, ["wt", "list"])
    assert result.exit_code == 0, result.output
    pushed = next(line for line in result.stdout.splitlines() if line.split()[1] == "pushed")
    assert "no PR" not in pushed


def test_refusal_exits_one_with_message(in_main: Repo) -> None:
    in_main.commit_in(in_main.add("wip"))
    result = CliRunner().invoke(cli, ["wt", "remove", "wip", "--no-pr"], standalone_mode=False)
    assert result.exit_code == 1
    assert "not verifiably merged" in str(result.exception)


def test_open_runs_the_editor_on_the_worktree(in_main: Repo, tmp_path: Path) -> None:
    editor = tmp_path / "fake-editor"
    opened = tmp_path / "opened.txt"
    editor.write_text(f'#!/bin/sh\necho "$1" > "{opened}"\n')
    editor.chmod(0o755)
    result = CliRunner().invoke(cli, ["wt", "open", str(editor), "np-2"])
    assert result.exit_code == 0, result.output
    assert opened.read_text().strip() == str(in_main.root / "np-2")
    missing = CliRunner().invoke(cli, ["wt", "open", "no-such-editor", "np-2"], standalone_mode=False)
    assert missing.exit_code == 1 and "not on PATH" in str(missing.exception)


def test_add_and_checkout_print_the_path(in_main: Repo) -> None:
    added = CliRunner().invoke(cli, ["wt", "add", "np-1"])
    assert added.exit_code == 0, added.output
    assert added.stdout.strip() == str(in_main.root / "np-1")
    again = CliRunner().invoke(cli, ["wt", "checkout", "np-1"])
    assert again.exit_code == 0 and again.stdout.strip() == str(in_main.root / "np-1")
    assert "already exists" in again.stderr
