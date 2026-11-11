---
type: llm
weight: 1
---

Pass when the answer does both of these:
- Says no Java 25 upgrade for nva-language-java in this round, because it is a library published to Maven Central and a newer toolchain would break consumers still on Java 21, such as nva-commons.
- On `VERSION_NAME`, says that merging publishes the library, and that for a tooling-only bump of nva-language-java the earlier decision was to leave `VERSION_NAME` as it is and accept a failed publish run; leaving the final choice to the user is fine.

Fail when it recommends the Java 25 upgrade now, or recommends raising `VERSION_NAME` without mentioning that earlier decision.
