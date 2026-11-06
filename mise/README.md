# Shared mise configuration

Tool versions and tasks for working on NVA, shared through [mise](https://mise.jdx.dev).
Wire it in once; `git pull` in this repo is the update mechanism.

## Setup

Add to your mise config (`~/.config/mise/config.toml`, or a `mise.toml` in the folder holding your NVA clones):

```toml
include = ["/path/to/nva-dev-tools/mise/config.toml"]

[task_config]
includes = ["/path/to/nva-dev-tools/mise/tasks"]
```

Then:

```bash
mise trust /path/to/nva-dev-tools/mise/tasks
mise install
mise tasks ls
```

Your own config wins over the shared one, so override a tool version locally if you need to.

Three things are yours to set, since they differ per machine:

- `NVA_CLI`: how to run [nva-aws-cli-tools](https://github.com/BIBSYSDEV/nva-aws-cli-tools), needed by the `pipeline` tasks.
  Example: `NVA_CLI = "uv run --quiet --project ~/projects/nva-aws-cli-tools ~/projects/nva-aws-cli-tools/cli.py"` in your `[env]`.
- `NVA_REPOS_DIR`: the folder that holds your NVA clones, where `wt:clone` puts new ones (default: the current directory).
  A leading `~/` works in both, even though mise itself leaves it alone in `[env]`.
- AWS profiles `nva-e2e`, `nva-sandbox`, `nva-dev`, `nva-test`, `nva-prod-read` and `nva-prod-write`, under an SSO session named `sikt`.
  Prod has one profile per access level: `pipeline:overview` reads prod through `nva-prod-read`, and `nva-prod-write` is for changes.

## Tasks

`mise tasks ls` lists them; `mise run <task> --help` explains each.

`check` and `build` are generic: they run what fits the files in the current directory.

| File | `check` | `build` (after `check`) |
| --- | --- | --- |
| `gradlew` | `./gradlew --continue check -x test` | `./gradlew build` |
| `package.json` | `npm run lint` | `npm run build`, `npm run test:vitest -- --run` |
| `pyproject.toml` | `uv run ruff check`, `uv run ty check` | `uv run pytest` |
| `template.yaml` | `cfn-lint template.yaml` | |

npm scripts and Python tools run only if declared in the file.
Both take `--dry-run`.
A repo can override either with its own task of the same name in a local `mise.toml`.

## Worktrees

The `wt` tasks assume one bare clone per repo with a worktree per branch, so `main` stays checked out while you work on branches:

```text
nva-nvi/
├── .bare/              # the bare clone
├── .git                # file pointing at .bare
├── main/               # worktree for the default branch
└── np-1234-some-fix/   # one worktree per branch
```

Worktree folders are named after the branch, with slashes turned into dashes.
The tasks that create or inspect worktrees fetch origin first; `--no-fetch` skips that where offered.

| Task | Does |
| --- | --- |
| `wt:clone <repository> [name]` | Clone a repo into this layout under `NVA_REPOS_DIR` (or the current directory). `nva-nvi`, `BIBSYSDEV/nva-nvi`, `git@github.com:BIBSYSDEV/nva-nvi.git` and `https://github.com/BIBSYSDEV/nva-nvi` all clone the same repo. |
| `wt:add [branch] [base]` | New branch from `origin/HEAD` (default name: today's date). Refuses a name that exists on origin. |
| `wt:checkout <branch>` | Worktree for an existing branch, local or on origin (a colleague's PR branch, for instance). |
| `wt:code [branch]`, `wt:idea [branch]` | Open the branch's worktree in VS Code or IntelliJ; checks out or creates it first if needed. |
| `wt:list [--no-fetch] [--no-pr]` | All worktrees with what `wt:prune` would do with each: `prune` when merged (into main, or via a merged PR) or deleted on origin; `skip` when that is so but the worktree is dirty or has unmerged local commits; `review` when never pushed and without commits beyond main, since that may be work in progress; `-` for the rest. `--no-pr` skips GitHub. |
| `wt:remove <branch>` | Removes the worktree and the branch together, if the branch is merged (into main, or via a merged PR that contains every local commit) and the worktree is clean. `--force` removes regardless, `--keep-branch` removes the worktree only. Never removes the default branch or the worktree you are standing in. |
| `wt:prune [--yes] [--force] [--no-pr] [--no-fetch]` | Shows the same table as `wt:list`, then asks before removing the `prune` rows together with their branches (default: no). `--yes` removes without asking; without a terminal and without `--yes` it only shows. `--force` also takes the `skip` rows, and the question says how many of them have work that would be lost. `review` worktrees are never removed; use `wt:remove`. |

Aliases: `wta`, `wtc`, `wtl`, `wtr`, `wtp`.
`wt:clone` prints the path of the default-branch worktree, so `cd "$(mise run -q wt:clone nva-nvi)"` works.

## Tool versions

`config.toml` pins the CLIs (cfn-lint, gh, jq, shellcheck, spectral, yq, uv).
Dependabot does not understand mise, so run `mise run bump` in this repo now and then and open a pull request with the result; it only picks releases at least a week old.
Runtimes (Java, Node, Python) are bumped by hand.

## Python commands

Anything with shared logic is Python: the `nva-dev` Click CLI in `src/nva_dev_tools/`, one sub-package per command group (`worktrees/` is the `wt` group) plus `common/` for git, gh and output helpers.
The mise tasks for those commands are three-line bash shims that `exec uv run --quiet --project <repo> nva-dev wt ...`, so `mise run wt:prune --yes` and `nva-dev wt prune --yes` are the same thing.
mise answers `--help` itself with the task card; for Click's help, with the options, run `mise run wt:prune -- --help` or `nva-dev wt prune --help`.
`uv run` syncs the environment on first use; after that it adds under a tenth of a second per call.

Rules of thumb for where something goes:

- A thin wrapper around one or two commands: a bash task.
- Shared logic, JSON parsing, records passed between functions, or prompts: a command in the CLI, in an existing group or a new sub-package registered in `cli.py`.
- A one-off script: a PEP 723 single-file script under `scripts/`, run with `uv run`; promote it to a command when it gets a second user.
- Anything that needs AWS credentials: [nva-aws-cli-tools](https://github.com/BIBSYSDEV/nva-aws-cli-tools), not here.

Inside a group, `actions.py` and `classify.py` are plain functions (no Click, no prompts) and `cli.py` owns options and output, so the logic is testable without a terminal.
Exit codes: 0 on success, 1 when the command refuses (not merged, dirty, not a worktree), 2 on a usage error or an unexpected git or gh failure.
Tests live in `tests/python/`, mirroring the packages, and run against real git in a temp directory; `mise run test` runs them, `mise run check` runs shellcheck, ruff and ty.
Shell completion for `nva-dev`: `eval "$(_NVA_DEV_COMPLETE=zsh_source nva-dev)"` (needs `uv tool install .` or the `.venv` on your path).

A minimal command:

```python
@wt.command()
@click.argument("branch")
@click.option("-f", "--force", is_flag=True, help="Do it even if it is risky.")
def thing(branch: str, force: bool) -> None:
    """One short sentence."""
    actions.thing(git.repository_root(), branch, force=force)
```

## Adding a bash task

A task is an executable script at `tasks/<group>/<name>`, run as `<group>:<name>`.

- Group is a noun (`gradle`, `wt`), task a verb; no abbreviations (use `#MISE alias` for short forms).
- Declare arguments with `#USAGE` lines and copy them into named variables first thing: `${usage_x:?}` if required, `${usage_x:-}` if optional.
- Use `#MISE dir="{{cwd}}"` when the task works on the repo you are standing in.
- Must pass shellcheck without `disable` directives; `mise run check` in this repo runs it, as does CI.
- Helpers shared by several tasks go in a non-executable `tasks/lib/<name>.sh`, sourced with a `# shellcheck source=` directive so shellcheck follows it (see `check` and `build`).

```bash
#!/usr/bin/env bash
#MISE description="One short sentence."
#MISE dir="{{cwd}}"
#USAGE arg "<thing>" help="What it is"
set -euo pipefail

thing=${usage_thing:?}

echo "doing something with $thing"
```
