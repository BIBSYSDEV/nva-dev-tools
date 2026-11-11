---
tags: [bump-dependencies, decision]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill]
---

I'm bumping nva-gradle-plugins in one of our services. The build now fails with UnnecessaryWarningSuppression on a `@SuppressWarnings("PMD.AvoidCatchingGenericException")` that has a `// FIXME: NP-48927` comment above it, and AvoidCatchingGenericException is in the repository's `excludedRules`. What do we do with the annotation and the comment? Don't change any files, just tell me.
