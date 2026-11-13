---
tags: [bump-dependencies, decision]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill]
---

I'm about to open the dependency bump PR for nva-nvi. It is stacked on top of #812 and has three commits: `build: Upgrade Gradle to 9.8.2`, `build: Bump nva-commons to 2.11.2` and `build: Bump dependencies`. The nva-commons bump brings Jackson 2.22.4 and AWS SDK 2.57.4 with it. Reply with only the PR body, nothing else, and don't open anything.
