---
tags: [bump-dependencies, decision]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill]
---

nva-language-java is on Java 21, and so is nva-commons, which uses it. Java 25 is the newest LTS with a Lambda runtime. Should this round of dependency bumps include a Java 25 upgrade PR for nva-language-java? And when I merge its tooling-only bump PR, should that PR raise `VERSION_NAME`? Don't change any files, just tell me.
