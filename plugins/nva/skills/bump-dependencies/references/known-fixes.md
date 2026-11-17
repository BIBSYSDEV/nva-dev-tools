# Known fixes: decisions that apply to every repository

The same toolchain bump lands in 20 to 30 repositories, so a breakage met in one of them will be met in all of them.
This file is the memory of how we decided to handle each one.
Read it whenever `mise build` fails after a bump, and apply the listed fix instead of deciding again.

When you meet a failure that is not listed, decide how to fix it, apply it, and add a row to `${CLAUDE_PLUGIN_DATA}/known-fixes-pending.md` in the same session, so the next repository gets the decision for free.
Put it under the same section heading and in the same columns as here, so it can be pasted into place; rows reach this file through a pull request to nva-dev-tools.
Keep each row to one sentence of fix: what to change and where.
Say "Decision:" only where the choice could reasonably have gone another way, so a reader knows it was a choice and not a necessity.
If a fix also belongs upstream (the bundled ruleset in nva-gradle-plugins, a catalog entry in nva-commons), say so in the Upstream column so it gets done once instead of being worked around everywhere.

## PMD

PMD comes with nva-gradle-plugins (`pmd.version` in its `nva-plugin.properties`), so a plugin bump is what brings new or renamed rules.
Since nva-gradle-plugins 1.0.14 the bundled `pmd-ruleset.xml` is the shared source of truth, and a repository adds its own exceptions with `nva.pmd.excludedRules` (plain rule names, any category) and `nva.pmd.analyzeTests`.
A repository that still sets `nva.pmd.rulesetFile` has frozen a copy of the ruleset and misses every shared fix, so the migration below is part of the plugin bump wherever `config/pmd/ruleset.xml` exists.

### Migrate a local ruleset to excludedRules

Example: [nva-nvi#827](https://github.com/BIBSYSDEV/nva-nvi/pull/827), commit `build: Upgrade nva-gradle-plugins to 1.0.14`.

1. Run `scripts/pmd-migration.sh <worktree>` (in this skill's folder). It diffs the local ruleset against the bundled one and prints the `excludedRules` list to paste, the local excludes that are now redundant, and what gets looser or stricter.
2. In the convention plugin (or root `build.gradle`) replace `rulesetFile = rootProject.file('config/pmd/ruleset.xml')` with the printed `excludedRules = [...]`, one rule per line, sorted. Add `analyzeTests = false` only when the script says the local ruleset skipped tests and you keep that.
3. Delete `config/pmd/ruleset.xml` and the `config/pmd` folder if it is now empty.
4. Build. Categories the local ruleset never referenced (often `bestpractices`, `multithreading`, `performance`) are now active, so new violations are expected there. Fix them when they are few and real; otherwise add the rule to `excludedRules`, without a comment.
   Rules the script lists as "loosened" (run locally, excluded by the bundled ruleset) are simply accepted; a shared ruleset means the team's exclusions win over one repository's stricter copy, and nva-nvi#827 did the same without comment.
5. Mention the switch in the PR body, as in the example: "Upgrades nva-gradle-plugins to use the new shared PMD configuration, instead of a full local override."

Do not combine `excludedRules` with `rulesetFile`; the plugin fails the build on purpose when both are set.
Only list rules the bundled ruleset does not already exclude, so the list stays a record of this repository's real exceptions.
Never comment the entries, not even to carry over a reason from the old local ruleset: every exclude is a violation we intend to fix and a rule we intend to enable, and a comment justifying it reads as a decision to keep the rule off.
The one exception is a `FIXME` with a ticket key that belonged to a suppression the exclude replaces: it points at the fix rather than justifying the exclude, so it moves onto the entry as a trailing comment.

| Trigger | Since | Fix | Upstream |
| --- | --- | --- | --- |
| Repository has `config/pmd/ruleset.xml` and sets `nva.pmd.rulesetFile` | nva-gradle-plugins 1.0.14 | Migrate to `nva.pmd.excludedRules` as described above, in the same commit as the plugin bump. | None; a rule excluded in many repositories is a cleanup target, not a candidate for the bundled ruleset. |
| `UnnecessaryWarningSuppression` on `@SuppressWarnings("PMD.X")` where `X` is in `excludedRules` (seen with `AvoidCatchingGenericException`) or excluded by the bundled ruleset (seen with `OnlyOneReturn` and `ShortClassName` in search-workspace-service) | PMD 7.29.0, nva-gradle-plugins 1.0.14 | Delete the annotation in the plugin bump commit, since the repository-wide exclude already covers it; do not add `UnnecessaryWarningSuppression` to `excludedRules`. When a `FIXME`/ticket comment sat above the annotation (seen as `// FIXME: NP-48927` in nva-publication-channels-java), move it to the rule's `excludedRules` entry as a trailing comment (`'AvoidCatchingGenericException', // FIXME: NP-48927`) instead of leaving it in the code. Decision: a `FIXME` without a ticket key that asks about the code itself (seen as `// FIXME: Do we need this catch?` in nva-search-api) moves onto the line it asks about, here the `catch`, rather than onto the exclude. When `X` is still an active rule, PMD reports only the suppressions that no longer suppress anything; delete just those and keep the rest (seen with `PMD.CloseResource` on mocked `HttpClient`s in nva-doi-registrar-client). | None. |
| New `ReturnEmptyCollectionRatherThanNull` on a method returning an array or a collection as `nonNull(x) ? ... : null` | PMD 7.29.0, nva-gradle-plugins 1.0.14 (passed with the PMD in 1.0.12 and earlier) | Decision: fix it in the plugin bump commit without changing behaviour, rather than excluding the rule, and check every caller for a null test first, since null may mean "absent". An array whose callers test `nonNull(...)` returns `new String[0]` and the checks become `.length > 0` (seen in nva-search-api `AsType.split`). When null means "leave the field out of the JSON" (seen in nva-cristin-service `getSubUnits`, feeding `hasPart`), return `Optional<...>` and let the callers pass `.orElse(null)`; when every reader already maps null to empty, just return the collection. Avoid adding a lambda: in a repository with a lowered JaCoCo floor, an untested lambda counts as an uncovered method. | None. |
| `pmd-migration.sh` says the local ruleset skips test sources (`<exclude-pattern>.*/test/.*</exclude-pattern>`) | nva-gradle-plugins 1.0.14 | Decision: keep `analyzeTests = false`, since turning PMD on for tests is a policy change rather than part of the migration, and the test violations it finds (`UnitTestContainsTooManyAsserts`, `AvoidThrowingRawExceptionTypes` in fakes) would otherwise push excludes that also loosen main code (seen in nva-orcid-client and nva-fetch-doi). | None. |
| New `GuardLogStatement` violations after the migration, in a repository whose local ruleset never ran `bestpractices` | nva-gradle-plugins 1.0.14 | Decision: add `GuardLogStatement` to `excludedRules`, without a comment, instead of reworking log calls in a bump PR; the exclude is debt to fix later, as in the dozen other repositories that have it. | None. |
| New `OnDemandImport` violations on wildcard imports (`import foo.*;`, `import static Foo.*;`) in main sources | PMD 7.29.0, nva-gradle-plugins 1.0.14 (not reported by the PMD in 1.0.11) | Decision: replace each wildcard with explicit imports in the plugin bump commit rather than excluding the rule, since no repository excludes it and google-java-format never writes wildcards back (seen with 6 imports in search-workspace-service). | None. |
| New `AvoidDeeplyNestedIfStmts` on an `else { if ... else ... }` inside an outer `if` | PMD 7.29.0, nva-gradle-plugins 1.0.14 (not reported by the PMD in 1.0.10) | Flatten it to `else if` in the commit with the other PMD fixes, rather than excluding the rule (seen in nva-cristin-service `QueryBuilderProject`). | None. |
| New `UnitTestContainsTooManyAsserts` violations after the migration, in a repository whose local ruleset analyzed tests but never ran `bestpractices` | nva-gradle-plugins 1.0.14 | Decision: add `UnitTestContainsTooManyAsserts` to `excludedRules`, without a comment, instead of splitting tests in a bump PR, as nva-commons and nva-nvi do; the rule only applies to tests, so the exclude loosens nothing in main code, and the other few test-only `bestpractices` hits (`UnitTestShouldIncludeAssert`, `LooseCoupling`, `LiteralsFirstInComparisons`) get fixed (seen in nva-swagger-generator). | None. |

## Error Prone

Error Prone also comes with nva-gradle-plugins (`errorprone.core.version`).
Repositories with `allErrorsAsWarnings = false` fail the build on new checks.

| Trigger | Since | Fix | Upstream |
| --- | --- | --- | --- |
| `compileJava` or `compileTestJava` fails with "An unhandled exception was thrown by the Error Prone static analysis plugin" (`NoSuchElementException` in `StringConcatToTextBlock.matchLiteral`) on a file that `spotlessApply` rewrote in the same build | Error Prone 2.52.0, nva-gradle-plugins 1.0.14 | Not an Error Prone bug to work around: `spotlessCheck` depends on `spotlessApply`, which rewrote the source while javac was reading it, so run `./gradlew spotlessApply` on its own first (the `style: Reformat` commit) and build again. | nva-gradle-plugins could make `JavaCompile` tasks `mustRunAfter("spotlessApply")` so a build never compiles a file mid-rewrite. |

## Spotless and google-java-format

| Trigger | Since | Fix | Upstream |
| --- | --- | --- | --- |
| `spotlessCheck` fails on untouched files after the plugin bump; lambdas like `attempt(() ->` now start on the call line | Spotless 8.11.0, nva-gradle-plugins 1.0.13 | Run `./gradlew spotlessApply` and commit the result alone as `style: Reformat`, so the formatting noise never shares a commit with a real change. | None. |
| `mise check` fails `verifyCoverage` (methods or classes ratio below 1.000, "Execution data for class ... does not match") right after the reformat, a Java upgrade, or any edit that shifts lines in main sources (even deleting a comment), or after an earlier test run that failed (seen in nva-search-api when Testcontainers got "Status 407: Sign in to continue using Docker Desktop" before the user signed in), which also stops `mise build` before the tests run | Spotless 8.11.0, nva-gradle-plugins 1.0.13; also seen on Java 21 to 25 | Not a real gap: `check -x test` verifies the old JaCoCo data against recompiled classes, so run `./gradlew build` once to regenerate it, then `mise build`. | The `check` task in nva-dev-tools should stop judging coverage when it skips the tests; a plain `-x verifyCoverage` fails in repositories without that task, so this is still open. |
| `spotlessJava` fails with "Could not read path '.../build/classes/java/test/...'" (or `.../build/classes/java/main/...`, seen in nva-search-api's `oai-pmh` with its generated JAXB classes) | Seen with Gradle 9.8.2 and nva-gradle-plugins 1.0.12, intermittent | Rerun `mise build`: `targetExclude("**/build/**")` makes Spotless walk the whole project directory, `build/` included, while a parallel `compileTestJava` in the same project rewrites it. | nva-gradle-plugins could set an explicit `target("src/**/*.java")` so Spotless never walks `build/`. |

## Gradle

| Trigger | Since | Fix | Upstream |
| --- | --- | --- | --- |
| Deprecation warning `Configuration.setVisible(boolean)` at `nva.java-conventions.gradle.kts:14` | Gradle 9.8.2 with nva-gradle-plugins 1.0.12 | Nothing to do in the repo: it comes from a plugin applied by nva-gradle-plugins and is gone after the 1.0.13 bump in step 3. | None, fixed in 1.0.13. |
| Deprecation warning "Using a Project object as a dependency notation" at `nva.root-module-conventions.gradle.kts:18` | Gradle 9.8.2 with nva-gradle-plugins 1.0.11 | Nothing to do in the repo: it comes from the plugin's root convention and is gone after the 1.0.14 bump in step 3 (seen in search-workspace-service). | None, fixed by 1.0.14. |
| `gradle-wrapper.properties` changes `retries=3` to `retries=0` after `./gradlew wrapper --gradle-version <v>` and `./gradlew wrapper` | Gradle 9.8.2 wrapper task | Run the second wrapper call as `./gradlew wrapper --retries 3`, as `mise gradle:upgrade-wrapper` does, so the only line that changes in the properties file is `distributionUrl` (seen in search-workspace-service). | Done: SKILL.md Step 1 runs `gradle:upgrade-wrapper`, which passes `--retries 3`. |
| `mise check` fails `:testCodeCoverageReport` with "Property has implicit dependency ... uses this output of task ':<module>:compileJava'" in a repository that sets `nva.generatedCode`, from the second gate run on (the first run on a fresh worktree skips the task because no JaCoCo data exists yet) | On the default branch since at least Gradle 9.6.1 with nva-gradle-plugins 1.0.11, so not caused by a bump | Decision: change nothing in the repository, and gate each step with `./gradlew --continue build` followed by `cfn-lint template.yaml`, which runs the same checks as `mise build` with the test tasks providing the ordering (seen in nva-data-report-api). | nva-gradle-plugins `configureCoverageExcludes` wraps the class directories in a `provider { fileTree(...) }` that drops their task dependencies; it should keep them, for example with `builtBy`. |

## nva-commons API

| Trigger | Since | Fix | Upstream |
| --- | --- | --- | --- |

## Runtime and infrastructure

| Trigger | Since | Fix | Upstream |
| --- | --- | --- | --- |
| Tests print `WARNING: java.lang.System::load has been called by ...SQLiteLibraryLoader` (DynamoDBLocal's native sqlite4java) after the Java upgrade | Java 25 (JEP 472, any JDK 24+) | Decision: add `jvmArgs '--enable-native-access=ALL-UNNAMED'` to the `test` block that every module with DynamoDBLocal tests shares (the convention plugin when there is one), with the two-line comment from nva-handle-service#78, in the Java upgrade commit, since a future JDK turns the warning into a failure (seen in nva-handle-service and nva-person-preferences). | nva-gradle-plugins could set the flag on all `Test` tasks so repositories stop carrying it. |
| `mise check` fails on a clean default branch with cfn-lint W3005 "dependency already enforced by a 'GetAtt'" on an untouched `template.yaml` | cfn-lint 1.58.0 (local) | Delete the redundant `DependsOn` entry. Decision: the user chose to land it as the first commit of the bump PR (`fix: Remove redundant DependsOn on <Function>`) instead of a separate PR from the default branch, since it is a two-line change that only unblocks the gate (seen in nva-search-api). | None. |
| `template.yaml` has an inline Python Lambda (a `ZipFile` custom resource using `cfnresponse`) on an older `python3.x` runtime | Python 3.14 target, 2026-11 | Decision: upgrade its `Runtime` to the newest GA Lambda Python (`python-lambda`, never a preview runtime) in a runtime PR of its own (Step 8), as `build: Upgrade custom resource Lambda to Python 3.14`; cfn-lint validates the value, but no test runs the inline code, so list it under "Worth a look" since the first deploy exercises it. | None. |
