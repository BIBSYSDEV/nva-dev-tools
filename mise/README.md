# Shared mise configuration

Shared [mise](https://mise.jdx.dev) tool versions and tasks for working on NVA.
Wire it into your own mise config once, and `git pull` in this repo is the update mechanism from then on.

## Setup

Clone this repo somewhere permanent, then add these lines to your mise config.
That is either the global `~/.config/mise/config.toml`, or a `mise.toml` / `mise.local.toml` in the folder that holds your NVA clones if you want the settings scoped to NVA work.

```toml
include = ["/path/to/nva-dev-tools/mise/nva.toml"]

[task_config]
includes = ["/path/to/nva-dev-tools/mise/tasks"]
```

`~` works in both paths.
Then trust the task directory, since mise does not extend the trust of your config file to file tasks pulled in from elsewhere:

```bash
mise trust /path/to/nva-dev-tools/mise/tasks
```

Check with `mise tasks ls` from inside any NVA repo.

Your own config always wins over the included file, so pin a different tool version locally if you need to.

## What is shared

`nva.toml` holds the `[tools]` every NVA service expects (Java, Node, Python, uv, AWS CLI).
Included files may only contain `[tools]`, `[env]`, `[vars]`, `[hooks]`, `[shell_alias]` and `[bootstrap]`, so every shared task is a file task under `tasks/`.

### What you set yourself

Two things are deliberately not in the shared config, because they differ per machine:

- `NVA_CLI`: the command that runs [nva-aws-cli-tools](https://github.com/BIBSYSDEV/nva-aws-cli-tools).
  Tasks in the `pipeline` and `dlq` groups need it and stop with a clear message when it is unset.
  Example for a clone at `~/projects/nva-aws-cli-tools`:

  ```toml
  [env]
  NVA_CLI = "uv run --quiet --project ~/projects/nva-aws-cli-tools ~/projects/nva-aws-cli-tools/cli.py"
  ```

- AWS profiles named `nva-e2e`, `nva-sandbox`, `nva-dev`, `nva-test`, `nva-prod` and `nva-prod-admin`, under an SSO session named `sikt`.
  The tasks pass these names with `--profile`, so your `~/.aws/config` has to use them.

## Adding a task

Tasks are executable scripts under `tasks/<group>/<name>`, which mise exposes as `<group>:<name>`.

- The group is the tool or domain as a noun (`gradle`, `wt`, `pipeline`), the task a verb or plain noun.
- No abbreviations in task names.
  Add a short form with `#MISE alias="..."` instead.
- Prefer one task with an argument over several near-identical scripts.
- Declare arguments and flags with `#USAGE` lines; mise injects them as `usage_<name>` variables and generates `--help`.
  Copy each one into a named variable right after `set -euo pipefail`: `${usage_thing:?}` for a required argument, `${usage_thing:-}` or `${usage_thing:-default}` for an optional one.
  That documents the contract in one place and keeps shellcheck from flagging the injected variables as unassigned.
- Tasks that call nva-aws-cli-tools split `NVA_CLI` into an array once, `read -ra nva_cli <<< "${NVA_CLI:?...}"`, and run `"${nva_cli[@]}"`, so the command line is word-split exactly once and everything else stays quoted.
- Use `#MISE dir="{{cwd}}"` for anything that should run in the repo you are standing in.

Minimal template:

```bash
#!/usr/bin/env bash
#MISE description="One line shown by mise tasks ls"
#MISE dir="{{cwd}}"
#USAGE arg "<thing>" help="What the argument is"
set -euo pipefail

thing=${usage_thing:?}

echo "doing something with $thing"
```

Make it executable, run `mise tasks ls` to see it, and `mise run <group>:<name> --help` to check the generated usage.
