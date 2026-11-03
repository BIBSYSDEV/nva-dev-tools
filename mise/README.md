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

- `NVA_CLI`: how to run [nva-aws-cli-tools](https://github.com/BIBSYSDEV/nva-aws-cli-tools), needed by the `pipeline` and `dlq` tasks.
  Example: `NVA_CLI = "uv run --quiet --project ~/projects/nva-aws-cli-tools ~/projects/nva-aws-cli-tools/cli.py"` in your `[env]`.
- `NVA_REPOS_DIR`: the folder that holds your NVA clones, where `wt:clone` puts new ones (default: the current directory).
- AWS profiles `nva-e2e`, `nva-sandbox`, `nva-dev`, `nva-test`, `nva-prod` and `nva-prod-admin`, under an SSO session named `sikt`.

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
All `wt` tasks fetch origin first.

| Task | Does |
| --- | --- |
| `wt:clone <repository> [name]` | Clone a repo into this layout under `NVA_REPOS_DIR` (or the current directory). `nva-nvi`, `BIBSYSDEV/nva-nvi`, `git@github.com:BIBSYSDEV/nva-nvi.git` and `https://github.com/BIBSYSDEV/nva-nvi` all clone the same repo. |
| `wt:add [branch] [base]` | New branch from `origin/HEAD` (default name: today's date). Refuses a name that exists on origin. |
| `wt:checkout <branch>` | Worktree for an existing branch, local or on origin (a colleague's PR branch, for instance). |
| `wt:code [branch]`, `wt:idea [branch]` | Open the branch's worktree in VS Code or IntelliJ; checks out or creates it first if needed. |
| `wt:list [--no-fetch] [--pr]` | All worktrees with a stale flag: merged into main, or pushed and since deleted on origin. `--pr` asks GitHub, which also catches squash merges. |
| `wt:remove <branch>` | Removes the worktree and, if merged into `origin/main`, the branch. `--force` for a squash-merged branch or a dirty worktree, `--keep-branch` to keep it. |

Aliases: `wta`, `wtc`, `wtl`, `wtr`.
`wt:clone` prints the path of the default-branch worktree, so `cd "$(mise run -q wt:clone nva-nvi)"` works.

## Tool versions

`config.toml` pins the CLIs (cfn-lint, gh, jq, shellcheck, spectral, yq, uv).
Dependabot does not understand mise, so run `mise run bump` in this repo now and then and open a pull request with the result; it only picks releases at least a week old.
Runtimes (Java, Node, Python) are bumped by hand.

## Adding a task

A task is an executable script at `tasks/<group>/<name>`, run as `<group>:<name>`.

- Group is a noun (`gradle`, `wt`), task a verb; no abbreviations (use `#MISE alias` for short forms).
- Declare arguments with `#USAGE` lines and copy them into named variables first thing: `${usage_x:?}` if required, `${usage_x:-}` if optional.
- Use `#MISE dir="{{cwd}}"` when the task works on the repo you are standing in.
- Must pass shellcheck without `disable` directives; `mise run check` in this repo runs it, as does CI.

```bash
#!/usr/bin/env bash
#MISE description="One short sentence."
#MISE dir="{{cwd}}"
#USAGE arg "<thing>" help="What it is"
set -euo pipefail

thing=${usage_thing:?}

echo "doing something with $thing"
```
