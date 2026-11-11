---
name: bump-dependencies
description: Do the routine "bump dependencies" maintenance pull request for one NVA repository, end to end. Creates a worktree, upgrades the build system (Gradle wrapper, uv), the runtime patch level, the internal libraries (nva-commons, nva-gradle-plugins), the other dependencies, and the pinned GitHub Actions, with a full build and one commit per step, then opens the PR. Follows up with stacked PRs when the Dependabot config is missing or off, and for each runtime major upgrade (new Java LTS, Node major or Python minor) that AWS Lambda supports. Use whenever the user asks to bump, upgrade, update, refresh or "do maintenance on" dependencies, Gradle, Java, Node, Python, nva-commons or nva-gradle-plugins in an NVA repository (nva-*, NVA-*, search-workspace-service, dlr-nva-email-service), even when they name just one dependency or one step, and when they ask which versions a repo is behind on.
---

# Bump dependencies in an NVA repository

Every NVA service gets a periodic pull request that moves its toolchain and dependencies to the current targets.
The work is mechanical but has many small places where a version can hide, and a half-done bump is worse than none.
This skill turns it into a fixed sequence of steps where each step is verified by a full build and lands as its own commit, so the reviewer can read the PR commit by commit and bisect if something regresses later.

## Targets

| What | Target | Where it is pinned |
| --- | --- | --- |
| Gradle | newest release at least 7 days old | `gradle/wrapper/gradle-wrapper.properties` |
| uv | newest release at least 7 days old | `.github/workflows/*.y*ml` (`astral-sh/setup-uv` `version:`), `mise.toml` |
| Java | newest LTS with a GA Lambda runtime (`java`, `java-lambda`) | `template.yaml`, `buildspec.y*ml`, `.github/workflows/build.yml`, Gradle `nva.java.languageVersion` |
| Node | newest LTS (`node`), capped at the newest GA Lambda runtime (`node-lambda`) when the code runs on Lambda | `package.json` (`engines`, `volta`), `.nvmrc`, workflows, `template.yaml` |
| Python | newest release (`python`), capped at the newest GA Lambda runtime (`python-lambda`) when the code runs on Lambda | `.python-version`, `pyproject.toml` `requires-python`, workflows, inline Lambdas in `template.yaml` |
| nva-commons | latest, no cooldown | `gradle.properties` (`nvaCommonsVersion`) |
| nva-gradle-plugins | latest, no cooldown | `buildSrc/build.gradle` or `build-logic/build.gradle` |
| Everything else | newest stable at least 7 days old | local `gradle/libs.versions.toml`, `package.json`, `pyproject.toml`, action pins |

Run `${CLAUDE_SKILL_DIR}/scripts/latest-versions.sh` first to get the current numbers instead of guessing them.
It applies the cooldown for you: each line is the newest eligible version, with the newer one it skipped named in parentheses, and its first line `cooldown-cutoff <date>` is the date to hand to tools that enforce the cooldown themselves.
Pin every version explicitly, with no ranges and no "latest" aliases in committed files, so a build today and a build in six months resolve the same thing.

Runtime targets are never hardcoded here, because they move: the script prints each language's newest release next to the newest runtime that is generally available on Lambda.
Only Java LTS releases get a Lambda runtime, so a non-LTS Java is never a target.
Never target a Lambda runtime in public preview: it is not covered by the Lambda SLA, and the script leaves preview runtimes out for that reason.
When code runs on Lambda, everything else in the repository (Gradle toolchain, `.python-version`, `.nvmrc`, CI) uses the same version as the Lambda runtime, so nothing is built or tested on a newer version than production runs.
A target above the repository's current major (a new Java LTS, Node major or Python minor) is a runtime major upgrade, which always gets its own PR in Step 8.

Skip a step when it does not apply to the repository, and say so in the final summary.
Most repositories are Java/Gradle with a SAM `template.yaml`; a few are Node or Python.
Read `references/java-gradle.md` for the Gradle repositories and `references/node-python.md` for the others before changing files, since they list the exact files and the traps.
`references/known-fixes.md` is the decision log: one row per breakage a bump has caused somewhere, with the fix we settled on.
Decisions made on this machine that have not reached it yet are in `${CLAUDE_PLUGIN_DATA}/known-fixes-pending.md`, in the same table format; read that file too when it exists, since it holds rows from earlier repositories in the same round of bumps.
Never edit files in this skill's folder: it is a cached copy that every plugin update replaces.
The reference files name the bundled scripts as `scripts/<name>`; run them as `${CLAUDE_SKILL_DIR}/scripts/<name>`, because the shell's working directory is the worktree, not this folder.

## Ground rules

- **Work in a branch worktree, never in the default branch.** Step 0 finds out whether the user already made one and creates it only if not. Run every later command there, with `mise --cd <path> ...` or `git -C <path> ...` or an absolute path, because the shell's working directory does not reliably survive between tool calls.
- **`mise build` is the gate.** Run it after every step that changed what the build reads. It runs the static checks (`check`: Gradle check without tests, npm lint, ruff, ty, cfn-lint) and then the full build with tests. A step is only done when the gate is green. Note the commit of the last green gate; when `git -C <worktree> add -A` followed by `git -C <worktree> diff --cached --name-only <that commit>` lists nothing, or only files under `.github/`, the gate has nothing new to check (CI checks the workflows), so skip it and say so in the summary.
- **One commit per step**, only when the step changed something. Split a bump out into its own commit when it needed code changes, so the reviewer sees the code change next to the version that forced it.
- **Fix forward, within reason, and the same way every time.** When the gate fails after a bump, read `references/known-fixes.md` and the pending file first: the same bump lands in 20 to 30 repositories, so most failures have already been decided, and applying a different fix in one repo is worse than any of the choices. A new Error Prone or PMD rule, a deprecated API, a changed test utility: fix it in the same step with the smallest change that satisfies the new version. If the fix would be a real refactoring, revert that one bump, keep the rest, and report it in the final summary. Never get to green by lowering coverage thresholds, adding suppressions, or disabling a check.
- **Record new decisions.** A failure that is in neither file yet gets a row in `${CLAUDE_PLUGIN_DATA}/known-fixes-pending.md` in the same session, written as the top of `references/known-fixes.md` describes. Delete pending rows that `references/known-fixes.md` already has, since they reached the plugin through an update. Mention the new rows in the final summary so the user can veto them.
- **Respect the catalog rules.** Third-party versions come from `nvaCatalog` (published by nva-commons), nva-commons modules from `nvaLibs`, and the local `gradle/libs.versions.toml` is only for what the shared catalog lacks. A bump that makes a local entry redundant should delete the local entry rather than bump it.
- **Seven-day cooldown on everything external.** A release that is going to be yanked, patched or found compromised is usually caught within days, so no external version younger than 7 days goes into a pin: not a library, not Gradle, uv, a runtime patch or an action. The Gradle outdated report, Dependabot and the scripts in this skill all apply the same window, so a version they do not offer is not a target, however new and shiny. The two exceptions are nva-commons and nva-gradle-plugins, which the team releases itself, usually to get a fix out, so they are taken as soon as they are published. There are no others, not even for a security fix.
- **Runtime majors are their own PR, always.** A new Java LTS, Node major or Python minor changes the platform the code runs on, so it never rides along in the bump PR, however small the diff. The bump PR only moves runtime patch pins.
- **Read-only first, then write.** `mise gradle:outdated`, the scripts in this skill, and `gh api` lookups are safe to run freely. Pushing and opening pull requests happen only in steps 6 to 8.

## Steps

### Step 0: Prepare

1. Confirm the shared mise tasks are available: `mise tasks ls` in the repository should list `build`, `wt:add` and `gradle:upgrade-wrapper`. If not, the nva-dev-tools include is missing on this machine; stop and tell the user rather than improvising raw commands.
2. Find out where you are. When the user names a repository instead of starting in it, it is under `$NVA_REPOS_DIR/<repo>`; a clone made with `wt:clone` keeps each branch in a subfolder named after it, such as `main`. `git rev-parse --abbrev-ref HEAD` gives the checked-out branch and `git rev-parse --abbrev-ref origin/HEAD` the default one (usually `origin/main`; `develop`, `v2` and `master` in a few repos).
   - Already on another branch: the user set the worktree up, so use it as is. Do not create a second one and do not rename the branch.
   - On the default branch: create the worktree with `mise wt:add "$(date +%F)-bump-dependencies"`. It fetches, branches from `origin/HEAD`, and prints the path. Use that path for everything that follows.
3. When the branch already has commits beyond `origin/HEAD` (`git log --oneline origin/HEAD..HEAD`) or uncommitted changes (`git status --short`), the user started the work. Read those commits and the diff, map them onto the steps below, and continue from the first step not yet done. Leave their commits as they are, and leave uncommitted changes for the step they belong to rather than sweeping them into yours. Say in the summary which steps were already done when you arrived.
4. Run `${CLAUDE_SKILL_DIR}/scripts/latest-versions.sh` and compare with what the repository has. `mise run repos:versions <repo>` gives Java, Gradle, nva-commons and plugin versions at a glance.
5. Run `mise --cd <worktree> build` once before touching anything. A red build on a clean checkout means the gate cannot tell you anything, so stop and report it instead of mixing a fix for the default branch into a dependency PR. If the user's own commits are what broke it, say so and ask before touching them.

### Step 1: Build system

Gradle: run the wrapper task without a version, so it picks the target itself (the `gradle` line from `scripts/latest-versions.sh`, same rule):

```bash
mise --cd <worktree> gradle:upgrade-wrapper
```

When it says the wrapper is already on that version, there is nothing to commit for Gradle; `references/java-gradle.md` says what the task runs.

Check that `gradle-wrapper.properties`, `gradle-wrapper.jar`, `gradlew` and `gradlew.bat` are all in the diff, then build and commit: `build: Upgrade Gradle to 9.8.2`.

uv: bump the pinned version in the workflow (`astral-sh/setup-uv` `with: version:`) and in `mise.toml` if present.
Commit: `build: Bump uv to 0.13.7`.

### Step 2: Runtime patch level, and checking for a major upgrade

Move runtime pins to the latest patch of the version the repository already uses: `.python-version` (3.14.4 to 3.14.10), `volta.node` in `package.json`, a patch-pinned Node in a workflow.
Commits: `build: Bump Python to 3.14.10`, `build: Bump Node to 26.13.0`.
Java has no patch pin (Lambda, CodeBuild and the Gradle toolchain take the major only), so this is usually empty for Java.

Then compare every runtime the repository uses with its target from `scripts/latest-versions.sh`, including the places that are easy to miss: inline Lambdas in `template.yaml` (custom resources with `ZipFile`), Dockerfiles, a Java version left at the plugin default (no `languageVersion` in the build files or build logic, see `references/java-gradle.md`).
Each one behind its target is a runtime major upgrade for Step 8.
Change no major here.

### Step 3: Internal dependencies

Bump nva-gradle-plugins first, since it defines the build logic the rest of the build runs under, then nva-commons.
Both are published to Maven Central under `com.github.bibsysdev`; the latest versions come from `scripts/latest-versions.sh`.

Bumping `nvaCommonsVersion` also moves every third-party version in `nvaCatalog`, so this step is where most transitive upgrades arrive.
Run `${CLAUDE_SKILL_DIR}/scripts/nva-commons-changes.sh <old> <new>` to see the nva-commons commits and the catalog diff between the two versions; it tells you which local catalog entries just became redundant and whether a change belongs under "Worth a look".
After the bump, check the local `gradle/libs.versions.toml` for libraries that the shared catalog now provides, and switch those usages to `nvaCatalog.*` (or `nvaLibs.*`) and delete the local entry.

A plugin bump also moves PMD, Error Prone, JaCoCo and Spotless, since their versions are pinned inside nva-gradle-plugins.
Expect renamed or new PMD rules and a formatter that lays code out differently; `references/known-fixes.md` says what to do with each.
Run `./gradlew spotlessApply` in the worktree right after changing the plugin version, before the gate: the new formatter almost always rewrites files, so a gate run first only fails on formatting after compiling sources that are about to change.
Commit the version change as the bump commit and the formatter output on its own as `style: Reformat` (no commit body), so formatting noise stays out of the other commits.
When the repository has its own `config/pmd/ruleset.xml`, the plugin bump also replaces it with `nva.pmd.excludedRules` (plugins 1.0.14 and later); the migration recipe and `scripts/pmd-migration.sh` are in `references/known-fixes.md`.

Commits: `build: Bump nva-gradle-plugins to 1.0.14`, `style: Reformat`, `build: Bump nva-commons to 2.11.1`.
If nva-commons removed or renamed something the repo used, the fix is part of the same commit when small.

### Step 4: Other dependencies

Gradle: `mise --cd <worktree> gradle:outdated` writes `build/dependencyUpdates/report.txt`.
Read the section "The following dependencies have later milestone versions"; the plugin already filters out pre-releases and anything published less than 7 days ago, so what remains is a candidate list, not a to-do list.
For each entry decide where it is declared (see the reference), then:

- Local catalog entry: bump it in `gradle/libs.versions.toml`.
- Comes from `nvaCatalog`: it cannot be bumped here. Leave it, and note it in the summary as a gap to propose upstream in nva-commons. The exception is a security fix the repo needs now, which may be pinned with `strictly` in the local catalog together with a comment saying why and when it can go; the pinned version still has to be at least 7 days old.
- Gradle plugin in `buildSrc` or `build-logic`: bump there.
- A major version: read its release notes (`gh release view <tag> --repo <owner>/<repo>`) before bumping, and list it under "Worth a look" in the PR.

Node: `npm --prefix <worktree> outdated --min-release-age 7` is `npm outdated` with the cooldown applied (it reads the `node_modules` from the baseline `npm ci`); raise the pinned versions in `package.json` to its Latest column and run `npm --prefix <worktree> install --min-release-age 7` so the lockfile follows under the same cooldown.
Python: `uv lock --upgrade --exclude-newer <cooldown-cutoff>` with the date from `scripts/latest-versions.sh`, then raise the minimum versions in `pyproject.toml` to match the lockfile.

Build, then commit `build: Bump dependencies`, with one extra commit per bump that needed a code change.

### Step 5: CI workflow

`${CLAUDE_SKILL_DIR}/scripts/outdated-actions.sh <worktree>` lists every `uses:` pinned by commit SHA in `.github/workflows`, with the version in its trailing comment, the newest release tag outside the cooldown, and the commit that tag points to.
Update both the SHA and the comment, since the comment is what humans and Dependabot read.
A `uses:` with a branch ref, such as `BIBSYSDEV/nva-github-workflows/.github/workflows/java.yml@v2`, is a shared workflow that pins its own actions; only check that the repo is on the newest major (the README in nva-github-workflows says which).
Many repositories have Dependabot for minor and patch bumps, so this step is often empty; when it is not, commit `ci: Bump GitHub Actions`.

### Step 6: Pull request

Run the gate on the final state, unless nothing outside `.github/` changed since the last green one (see the ground rules), then push and open the PR:

```bash
git -C <worktree> push -u origin HEAD
gh pr create --repo BIBSYSDEV/<repo> --title "build: Bump dependencies" --body-file <body.md>
```

Use a narrower title when the PR does one thing, such as `build: Bump nva-commons to 2.11.0`.
Write the body to a file in the scratchpad first; the shape is below.
Then give the user the PR link and the same summary.

### Step 7: Dependabot config (stacked follow-up PR)

Dependabot handles the minor and patch bumps between these maintenance PRs, so every repository should have `.github/dependabot.yml`, configured like its siblings.
A missing or deviating config is a separate concern from the bump, so it goes in its own PR stacked on top of the bump PR, not in the bump PR itself.
Skip the step when the config already matches the checklist below, and say so in the summary.

A config is set up properly when it has:

- One `updates` entry per package ecosystem the repository uses (`gradle`, `npm` or `uv`), plus one for `github-actions`.
- For Gradle, `directories` listing `/` and the build-logic folder (`/buildSrc` or `/build-logic`), since that is where nva-gradle-plugins is pinned and Dependabot does not look there otherwise.
- `cooldown: default-days: 7`, matching the 7-day rule used for the outdated report.
- Minor and patch updates grouped (`<ecosystem>-minor-and-patch`), so each ecosystem gets one PR a week instead of one per library.
- `commit-message.prefix` set to `build` for packages and `ci` for actions, so Dependabot's commits follow the conventions below.
- A weekly schedule on Monday at 07:00, `timezone: Europe/Oslo`.

Templates: nva-handle-service for `buildSrc`, nva-search-api or nva-publication-api for `build-logic`, NVA-Frontend for npm and nva-aws-cli-tools for uv.
nva-nvi has the same shape, but lists only `/` even though it has `build-logic`.
Validate the file with `uvx check-jsonschema --builtin-schema vendor.dependabot .github/dependabot.yml`; the gate has nothing to check here, since only `.github/` changes.

`gh stack` has no `-C` flag, so run each call as `cd <worktree> && gh stack ...`:

```bash
git -C <worktree> config rerere.enabled true   # avoids gh stack's interactive rerere prompt
cd <worktree> && gh stack init <bump-branch>    # adopts the bump branch and its PR as the bottom layer
cd <worktree> && gh stack add "$(date +%F)-dependabot-config"
# write or fix .github/dependabot.yml, then validate it
git -C <worktree> add .github/dependabot.yml
git -C <worktree> commit -m "ci: Add Dependabot config" -m "<what it updates and from which template>"
cd <worktree> && gh stack submit --auto --open  # PR title and body come from the commit
cd <worktree> && gh stack bottom                # put the worktree back on the branch it is named after
```

Use `ci: Update Dependabot config` when fixing an existing file, and say in the commit body what was missing.
If `submit` exits with code 9 (stacked PRs not enabled on the repository), push the branch and open the PR with `gh pr create --base <bump-branch>` instead.

### Step 8: Runtime major upgrade (stacked PR)

Do this for every runtime Step 2 found behind its target, one PR per language, each as its own layer on top of the stack.
The riskiest change goes on top, so the bump and Dependabot PRs can merge without waiting for it.
When nothing is behind, skip the step and say in the summary why for each language, for example "Java 25 is the newest GA Lambda runtime" or "Python 3.15 is still in preview on Lambda, so it is next time's upgrade".
A library published to Maven Central (no `template.yaml`, such as nva-language-java) gets no Java upgrade while any repository that uses it is still on the older Java, since a newer toolchain raises the bytecode level it publishes and breaks them; report it as blocked until every consumer, nva-commons first, is on the target.
Merging to such a library's default branch also publishes it, so ask the user whether the bump PR should raise `VERSION_NAME`; for a tooling-only bump of nva-language-java the answer was to leave it and accept a failed publish run.

Before changing files, read what the new version removes or changes, since that is what breaks at runtime rather than at compile time:

- Java: the JDK release notes for every version skipped (removed APIs, changed defaults), and whether nva-gradle-plugins and its Error Prone version support the new language level.
- Python: the "What's new" removals and deprecations, and whether every dependency in `uv.lock` has a release for the new version (`uv sync` fails when one does not).
- Node: the major's breaking changes, and the `engines` ranges of the dependencies.

Then apply the checklist: Java in `references/java-gradle.md`, Node and Python in `references/node-python.md`.

```bash
cd <worktree> && gh stack top                              # gh stack init <bump-branch> first when Step 7 made no stack
cd <worktree> && gh stack add "$(date +%F)-java-25"
# change every pin on the checklist, mise build
git -C <worktree> commit -am "build: Upgrade to Java 25" -m "<what moved, and anything only a deploy exercises>"
cd <worktree> && gh stack submit --auto --open
cd <worktree> && gh stack bottom
```

Commits: `build: Upgrade to Java 25`, `build: Upgrade to Node 24`, `build: Upgrade to Python 3.14`, `build: Upgrade custom resource Lambda to Python 3.14`.
Code changes the new version forces go in the same PR as their own `fix:` commits.
`submit` takes the PR title and body from the commit when the branch has one commit, and names the PR after the branch otherwise; fix that with `gh pr edit --title ... --body-file ...`.
The body follows the bump PR's shape, with "Worth a look" naming what only a deploy exercises (the Lambda runtime, the CodeBuild image, inline custom resources) and any behaviour change from the release notes.
If the new version needs more than small fixes (a dependency without support, a real refactoring), drop the PR and report what blocked it.

## Commit messages

Conventional commits, with a capitalised, specific subject that names the version:

| Change | Prefix | Example |
| --- | --- | --- |
| Toolchain, runtime, dependency versions | `build:` | `build: Bump nva-commons to 2.11.0` |
| GitHub workflow or action pins | `ci:` | `ci: Bump actions/checkout to v7.0.1` |
| Code change forced by a bump | `fix:` or `refactor:` | `fix: Use Generator return type for contextmanager` |
| Formatter output only | `style:` | `style: Reformat` |

`style: Reformat` gets no commit body, since a formatter-only commit needs no explanation.
A Jira key, when the user gave one, goes in the PR body's `Ticket:` line rather than in every commit.

## Pull request body

```markdown
Routine dependency bump.
Ticket: https://sikt.atlassian.net/browse/NP-XXXXX   <- only when the user gave one

Changes:

- build: Upgrade Gradle to 9.8.2
- build: Bump nva-commons to 2.11.0
- build: Bump dependencies

Worth a look:

- polars 1.44 -> 2.0 is a major bump. The report module is fully covered and passes; the export path is not, so try one by hand.
```

The body describes what the PR changes and nothing else.
List each commit subject as it is, without adding what a bump brings along (tool versions, transitive libraries); the diff shows that.
Steps that were skipped or already current, upstream gaps and reverted bumps go in the final summary to the user, not in the PR.
Do not list the checks you ran locally; CI runs them.
Do not mention the stack or the PR this one builds on (no "Stacked on #123"), in the PR body or in a commit body that becomes one; GitHub shows the base branch and the stack.
Keep "Worth a look" for anything a reviewer should think about rather than just scan: major versions, behaviour changes, code you had to touch.
Never mention `style: Reformat` there, since formatter output needs no explanation.
Drop a heading when it has nothing under it.

## Final summary to the user

State the PR link, the commits in order, what was skipped and why, and what is left for upstream (usually catalog gaps in nva-commons, or a ruleset fix in nva-gradle-plugins).
Give the Dependabot follow-up PR link too, or say that the existing config already matched.
Give the link to each runtime upgrade PR, or for each runtime why there is none: already on the target, the newer version is only in preview on Lambda, or what blocked it.
If any step was reverted because the fix grew too big, say what broke so the user can decide whether to pick it up separately.
List any rows added to the pending file, quoted, since they will steer the next 20 repositories.
When the pending file has rows, end with a reminder to add them to `plugins/nva/skills/bump-dependencies/references/known-fixes.md` in nva-dev-tools with a pull request, so the rest of the team gets them too.
