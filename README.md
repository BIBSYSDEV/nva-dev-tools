# nva-dev-tools

Shared tool versions and commands for working on NVA, through [mise](https://mise.jdx.dev).
Set it up once; after that, pulling this repo updates your tools and commands.

## Get started

1. Install mise and activate it in your shell, as in its [getting started guide](https://mise.jdx.dev/getting-started.html).
   Make sure you can clone from GitHub over SSH.
2. Clone this repo into the folder that will hold all your NVA clones:

   ```bash
   git clone git@github.com:BIBSYSDEV/nva-dev-tools.git ~/projects/nva/nva-dev-tools
   ```

3. Add this to `~/.config/mise/config.toml`:

   ```toml
   include = ["~/projects/nva/nva-dev-tools/mise/config.toml"]

   [task_config]
   includes = ["~/projects/nva/nva-dev-tools/mise/tasks"]

   [env]
   NVA_REPOS_DIR = "~/projects/nva"
   ```

4. Install the tools and log in to GitHub:

   ```bash
   mise trust ~/projects/nva/nva-dev-tools/mise/tasks
   mise install
   gh auth login
   ```

5. Clone the repositories you work on:

   ```bash
   mise run wt:clone nva-nvi
   ```

Run `mise run repos:pull` now and then to update every clone, this one included.
`mise tasks ls` lists all tasks, and `mise run <task> --help` explains one.

## How it works

- `mise/config.toml` pins the tool versions: Java, Node, Python, the AWS CLI, gh and a few more.
- `mise/tasks/` holds the commands.
  The ones with real logic call a small Python CLI in `src/`.
- `wt:clone` sets a repository up as a bare clone with one folder per branch, so `main` stays checked out while you work on a branch.

[mise/README.md](mise/README.md) lists every task, the settings the `pipeline` tasks need (`NVA_CLI` and AWS profiles), and how to add a task.
