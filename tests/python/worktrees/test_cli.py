from pathlib import Path

import pytest
from click.testing import CliRunner
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
    assert lines[0].split() == ["WORKTREE", "BRANCH", "STALE", "NOTES"]
    assert any(line.startswith("fresh") and "review" in line for line in lines)


def test_prune_dry_run_then_yes(in_main: Repo) -> None:
    in_main.checkout_from_origin("done")
    in_main.origin_delete_branch("done")
    dry = CliRunner().invoke(cli, ["wt", "prune", "--no-pr"])
    assert dry.exit_code == 0, dry.output
    assert "1 worktree(s) can be pruned" in dry.stdout and (in_main.root / "done").exists()
    applied = CliRunner().invoke(cli, ["wt", "prune", "--no-pr", "--yes"])
    assert applied.exit_code == 0, applied.output
    assert "Pruned 1 worktree(s)" in applied.stdout and not (in_main.root / "done").exists()


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
    pushed = next(line for line in result.stdout.splitlines() if line.startswith("pushed"))
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
