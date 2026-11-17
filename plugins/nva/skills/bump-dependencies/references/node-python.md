# Node and Python repositories

A handful of NVA repositories are not Gradle builds.
The same steps apply, with these files and commands.

## Node (npm)

Examples: NVA-Frontend (default branch `develop`), nva-language-js, nva-api-integration-test.

| Version | File | Key |
| --- | --- | --- |
| Node, for tooling | `package.json` | `"engines": { "node": "^26.0.0" }` and, when present, `"volta": { "node": "26.x.y", "npm": "..." }` |
| Node, for developers | `.nvmrc` | `26` |
| Node, for CI | `.github/workflows/*.y*ml` | `actions/setup-node` `node-version`, or `volta-cli/action` which reads `package.json` |
| Node, for Lambda | `template.yaml` | `Runtime: nodejs24.x` (the `node-lambda` line; `nodejs26.x` is in preview) |
| Libraries | `package.json` and `package-lock.json` | `dependencies`, `devDependencies`, `overrides` |

The values above are examples for a repository without Lambda code, which follows the newest LTS (`node`).
A repository whose Node code runs on Lambda uses the `node-lambda` major in every file above, so it is never built or tested on a newer Node than it runs on.

Run `npm ci` once before the baseline build, and again only when `package-lock.json` changed outside `npm install` or the Node major changed; a new patch release of the same Node keeps the installed `node_modules` working, and `npm install` updates them itself.
Patch bump (Step 2, in the bump PR): raise the exact version in `volta` and any patch-pinned workflow, then `mise build` (runs `npm run lint`, `npm run build` and `npm run test:vitest -- --run` when those scripts exist).
Major upgrade (Step 8, always its own stacked PR): change every file above, `npm ci`, then `mise build`.
Pin the exact Node version in `volta` when the repo uses it; `engines` and `.nvmrc` carry the major.

Dependency bump: `npm --prefix <worktree> outdated --min-release-age 7` lists each outdated package, with the newest version that clears the 7-day cooldown in the Latest column; it reads the installed `node_modules` from the baseline `npm ci`.
Plain `npm outdated` shows what the cooldown held back.
Raise the versions in `package.json` by hand to that Latest column so the diff shows what moved, then `npm --prefix <worktree> install --min-release-age 7` to update the lockfile, so transitive dependencies also stay outside the cooldown.
`min-release-age` needs a recent npm 11 (the one with the shared toolchain's Node 24 has it); an older npm only warns about an unknown setting and ignores it, so check that `npm config ls -l` lists `min-release-age` first.
Do not use `npm update` alone, because it moves the lockfile without touching the ranges in `package.json`.
`overrides` entries are pins for transitive vulnerabilities; check whether the parent dependency now ships a fixed version so the override can go.
Major bumps of build tooling (Vite, ESLint, TypeScript, MUI) need their migration notes read first and go under "Worth a look".

## Python (uv)

Example: nva-aws-cli-tools.

| Version | File | Key |
| --- | --- | --- |
| Python, for uv | `.python-version` | `3.14.4` |
| Python, minimum | `pyproject.toml` | `requires-python = ">=3.14"` |
| Python, for linting | `pyproject.toml` | `[tool.ruff] target-version = "py314"`, when set |
| Python, for Lambda | `template.yaml` | `Runtime: python3.14` (the `python-lambda` line; `python3.15` is in preview), inline `ZipFile` custom resources included |
| uv, for CI | `.github/workflows/*.y*ml` | `astral-sh/setup-uv` `with: version: "0.13.7"` |
| uv, locally | `mise.toml` or the shared nva-dev-tools `mise/config.toml` | `uv = "0.13.7"` |
| Libraries | `pyproject.toml` and `uv.lock` | `dependencies`, `[dependency-groups] dev`, `[tool.uv] constraint-dependencies` |

A repository without Lambda code follows the newest release (`python`); one whose Python code runs on Lambda uses the `python-lambda` minor everywhere.

Patch bump (Step 2, in the bump PR): set `.python-version` to the latest patch of the minor the repository already uses (`uv python install 3.14` fetches it), then `uv sync` and `mise build` (runs `ruff check`, `ty check` and `pytest` when declared in `pyproject.toml`).
Minor upgrade (Step 8, always its own stacked PR): change every Python row above to the new minor, grep for the old one (`3.14`, `py314`) to catch the rest, then `uv sync` and `mise build`.
A dependency without a release for the new minor makes `uv sync` fail; that blocks the upgrade, so drop the PR and report which package.

Dependency bump: `uv lock --upgrade --exclude-newer <cooldown-cutoff>` moves the lockfile to the newest allowed versions published before the cutoff date (the first line of `scripts/latest-versions.sh`), which is how uv enforces the 7-day cooldown.
Then raise the `>=` minimums in `pyproject.toml` to match the lockfile, so a fresh install elsewhere cannot resolve below what was tested.
`constraint-dependencies` under `[tool.uv]` hold security floors for transitive packages (certifi after the emSign CA incident, for instance); keep them unless the direct dependency now requires the fixed version itself.
Type checker and linter bumps (ty, ruff) often add findings; fix the code in a separate `fix:` commit so the reviewer sees why.

## Shared tool pins

The shared `mise/config.toml` in nva-dev-tools pins uv, cfn-lint, gh, jq, shellcheck, spectral and yq for every developer.
That file is bumped in its own repository with `mise run bump`, not as part of a service PR.
Mention it in the summary when a service bump depended on a newer shared tool.
