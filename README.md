# nva-dev-tools

Shared tool versions and commands for working on NVA, through [mise](https://mise.jdx.dev).
Set it up once; after that, pulling this repo updates your tools and commands.

## Get started

1. Install mise and activate it in your shell, as in its [getting started guide](https://mise.jdx.dev/getting-started.html).
   Make sure you can clone from GitHub over SSH.
2. Pick the folder that will hold all your NVA clones, and clone this repo into it:

   ```bash
   export NVA_REPOS_DIR=~/projects/nva
   git clone git@github.com:BIBSYSDEV/nva-dev-tools.git "$NVA_REPOS_DIR/nva-dev-tools"
   ```

3. In the same terminal, point mise at it.
   These commands add to your global mise config and keep what is already there:

   ```bash
   mkdir -p ~/.config/mise && touch ~/.config/mise/config.toml  # mise config set needs the file to exist
   mise trust "$NVA_REPOS_DIR/nva-dev-tools/mise/tasks"
   mise config set --global --append include "$NVA_REPOS_DIR/nva-dev-tools/mise/config.toml"
   mise config set --global --append task_config.includes "$NVA_REPOS_DIR/nva-dev-tools/mise/tasks"
   mise config set --global env.NVA_REPOS_DIR "$NVA_REPOS_DIR"
   ```

4. Install the tools and log in to GitHub:

   ```bash
   mise install
   gh auth login
   gh auth setup-git
   ```

5. Clone the repositories you work on:

   ```bash
   mise run wt:clone nva-nvi
   ```

6. In Claude Code, install the NVA plugin, which holds the team's skills such as `/nva:bump-dependencies`:

   ```text
   /plugin install nva --marketplace BIBSYSDEV/nva-dev-tools
   ```

   Then turn on auto-update for the `nva-dev-tools` marketplace under `/plugin`, so fixes to the skills reach you.

Run `mise run repos:pull` now and then to update every clone, this one included.
`mise tasks ls` lists all tasks, and `mise run <task> --help` explains one.

## How it works

- `mise/config.toml` pins the tool versions: Java, Node, Python, the AWS CLI, gh and a few more.
- `mise/tasks/` holds the commands.
  The ones with real logic call a small Python CLI in `src/`.
- `wt:clone` sets a repository up as a bare clone with one folder per branch, so `main` stays checked out while you work on a branch.
- `plugins/nva/` is the Claude Code plugin, and this repo is the marketplace it is installed from.

## Testing the skills

To try a change to a skill before it is merged, start Claude with `claude --plugin-dir <your clone>/plugins/nva`, which replaces the installed plugin for that session, and run `/reload-plugins` after each edit.

`plugins/nva/evals/` holds the plugin's evals: each case is a question about a rule in a skill (`prompt.md`) and a description of a good answer (`graders/`), which a small model judges.
Run them from your clone before merging a change to a skill:

```bash
claude plugin eval plugins/nva --no-publish
```

Each case runs three times with the plugin and three times without it, so the report shows the score and what the skill adds (Δ); it takes a few minutes, costs a few dollars of Claude usage, and lands in `plugins/nva/evals/results/`.

[mise/README.md](mise/README.md) lists every task, the settings the `pipeline` tasks need (`NVA_CLI` and AWS profiles), and how to add a task.
