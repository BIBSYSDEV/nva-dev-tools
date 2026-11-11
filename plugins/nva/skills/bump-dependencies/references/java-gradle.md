# Java and Gradle repositories

Where versions live, how the build logic is wired, and the traps that cost the most time.

## Where each version is pinned

| Version | File | Key or line |
| --- | --- | --- |
| Gradle | `gradle/wrapper/gradle-wrapper.properties` | `distributionUrl=...gradle-9.8.2-bin.zip` |
| nva-commons | `gradle.properties` | `nvaCommonsVersion=2.11.0` |
| nva-gradle-plugins | `buildSrc/build.gradle` or `build-logic/build.gradle` | `implementation 'com.github.bibsysdev:nva-gradle-plugins:1.0.12'` |
| foojay toolchain resolver | `gradle.properties` | `foojayResolverVersion=1.0.0` (used in `settings.gradle`) |
| Java, for Gradle | root `build.gradle` or the convention plugin in `build-logic/src/main/groovy/*.gradle` | `nva { java { languageVersion = 25 } }` |
| Java, for Lambda | `template.yaml` | `Runtime: java25` (in `Globals.Function` and on any function that overrides it) |
| Java, for CodeBuild | `buildspec.yaml` or `buildspec.yml` | `runtime-versions: java: corretto25` |
| Java, for GitHub CI | `.github/workflows/build.yml` | `java_version: "25"` passed to the shared workflow |
| Third-party libraries | `gradle/libs.versions.toml` (local, stopgap only) | `[versions]` and `[libraries]` |
| Third-party libraries, shared | nva-commons `gradle/libs.versions.toml`, published as `nvaCatalog` | bumped by bumping nva-commons |

When `nva.java.languageVersion` is not set anywhere, the plugin default applies (21 at the time of writing).
`repos:versions` shows that default like any other Java version, so check the build files to tell the two apart.
That repository is behind on Java, and setting the version explicitly is part of its Java upgrade in Step 8; the right place is wherever the repo already configures the `nva { ... }` extension for subprojects.
The toolchain vendor is fixed to Amazon Corretto by nva-gradle-plugins, and the foojay resolver downloads it when the machine lacks it, so no local JDK install is needed for the build to pass.

## Java upgrade checklist

A Java upgrade is always its own stacked PR (Step 8 in SKILL.md), never a commit in the bump PR.
The target is the newest LTS with a GA Lambda runtime (`java-lambda` from `scripts/latest-versions.sh`).
Missing one of the places below gives a deploy that builds for a different Java than it runs on.

Grep the worktree for the old version, for example `java21`, `corretto21`, `corretto-21`, `JavaVersion.VERSION_21`, plus `languageVersion` (excluding `build/` and `.gradle/`), and fix every hit:

1. `template.yaml`: every `Runtime:` line.
2. `buildspec.y*ml`: `runtime-versions`.
3. `.github/workflows/build.yml`: `java_version`.
4. Gradle: `nva.java.languageVersion`.
5. Anything repo-specific: Dockerfiles, `mise.toml`, README badges or setup instructions.

Then `mise build`.
Error Prone and PMD sometimes gain checks that only fire on newer language levels; fix the code minimally and keep it in the same commit, since the Java bump is what made it appear.

## Catalogs

`settings.gradle` creates two version catalogs from the nva-commons release named in `nvaCommonsVersion`:

- `nvaCatalog`: third-party libraries (jackson, junit, aws-sdk2, wiremock, ...).
- `nvaLibs`: the nva-commons modules themselves (`core`, `apigateway`, `nvatestutils`, ...).

The local `gradle/libs.versions.toml` (`libs.*`) exists only for artifacts the shared catalog lacks.
Three consequences for a bump:

- A library listed in the outdated report that resolves through `nvaCatalog` cannot be bumped in this repo. Note it as an upstream gap.
- After bumping nva-commons, diff the shared catalog (`scripts/nva-commons-changes.sh`) against the local one. Any library that the shared catalog now has should be switched to `nvaCatalog.*` and removed locally, because two sources for one version invite drift.
- `strictly` pins in the local catalog exist to win a conflict with a transitive dependency. When bumping one, keep it `strictly` unless you have checked that nothing else pulls the artifact (with `gradle:why`, see "Reading the outdated report").

AWS SDK 2 artifacts that are not in `nvaCatalog.aws.sdk2.*` use the BOM platform pattern with `nvaCatalog.versions.aws.sdk2`, never a literal version.

## Reading the outdated report

`mise gradle:outdated` runs `./gradlew dependencyUpdates --no-parallel` and writes `build/dependencyUpdates/report.txt` in the root project.
The sections, in order:

1. "using the latest milestone version": nothing to do.
2. "have later milestone versions": the candidates, as `group:name [current -> latest]` with a project URL. Lines like "contributed by a plugin into the 'pmd' configuration" mean the version is set by the plugin, not by this repo.
3. "Gradle current updates": already handled by step 1.

The report is filtered by nva-gradle-plugins: pre-release versions are rejected unless the current version is itself a pre-release, and versions published less than 7 days ago on Maven Central or the plugin portal are rejected too.
So a candidate in the report is eligible by policy; the remaining judgement is major versions and where it is declared.

To find where a candidate is declared, grep the catalog and build files for the artifact name.
`mise gradle:why <name>` shows per module why an artifact is on the classpath and which declaration requested the version, which settles whether a bump here would even take effect.

## Gradle wrapper

`mise gradle:upgrade-wrapper [version]` runs `./gradlew :wrapper --gradle-version=<version>` followed by `./gradlew :wrapper :wrapper --retries 3`.
Without a version it takes the newest release that is at least 7 days old, and does nothing when the wrapper is already on that release or a newer one.
The second run is what regenerates `gradlew`, `gradlew.bat` and `gradle-wrapper.jar` with the new version; without it only the properties file changes.
All four files belong in the commit.

If the new Gradle deprecates something the build uses, the first `mise build` shows it under `org.gradle.warning.mode=all`.
Deprecation warnings are not failures; mention them in "Worth a look" if they will become errors in the next major.

## Build gotchas

- Builds run with the configuration cache and parallel execution on (`gradle.properties`). The `dependencyUpdates` task needs `--no-parallel`, which the mise task already passes.
- `mise build` runs `./gradlew --continue check -x test` first and then `./gradlew build`. The check step surfaces every PMD and Error Prone violation in one go; the build step runs the tests and the JaCoCo coverage verification (100 % methods and classes by default).
- Coverage failures after a bump usually mean a dependency changed behaviour so that a branch is no longer exercised, or a test utility from nva-commons changed. Look at the report under `build/reports/jacoco/` rather than lowering the threshold.
- The dependency-analysis plugin (`buildHealth`) may be enforced in `check`. A bumped library that split or merged artifacts shows up as "unused" or "undeclared" there; fix the declarations rather than relaxing the severity.
- PMD rules come from the ruleset bundled in nva-gradle-plugins, with per-repository exceptions in `nva.pmd.excludedRules` and `nva.pmd.analyzeTests`. A repository that still points `nva.pmd.rulesetFile` at `config/pmd/ruleset.xml` is migrated as part of the plugin bump; see the PMD section of `known-fixes.md`.

## Dependabot

Many repositories have `.github/dependabot.yml` for Gradle and GitHub Actions with a 7-day cooldown and grouped minor/patch updates.
It does not bump majors, nva-commons (it does not follow `gradle.properties` into the catalog), the Gradle wrapper, or the Java runtime, which is exactly what this skill covers.
It only sees the nva-gradle-plugins pin when `directories` lists `/buildSrc` or `/build-logic` next to `/`.
Step 7 in SKILL.md checks the config and adds or fixes it in a stacked follow-up PR.
