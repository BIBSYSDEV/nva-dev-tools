---
type: llm
weight: 1
---

Pass when the answer says to delete the `@SuppressWarnings` annotation, because the repository-wide exclude in `excludedRules` already covers the rule, and to move the FIXME onto the rule's entry in `excludedRules` as a trailing comment, such as `'AvoidCatchingGenericException', // FIXME: NP-48927`.
Fail when it suggests adding UnnecessaryWarningSuppression to `excludedRules`, keeping the annotation, or leaving the FIXME in the code or dropping it.
