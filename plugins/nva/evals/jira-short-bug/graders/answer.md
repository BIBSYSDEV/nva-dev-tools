---
type: llm
weight: 1
---

The answer is a draft of a Jira bug.
Pass when the title states the symptom (a read after a write can return the old publication), and the description is at most about 15 lines and says what should happen instead, for example that the unpublish response shows UNPUBLISHED.
Fail when the title or description names a Java class or method (such as `ReadResourceService` or `UpdatePublicationHandler`), names the index `BY_TYPE_AND_IDENTIFIER_INDEX_NAME`, or prescribes the fix (GetItem, ConsistentRead, or returning the written object).
A sentence after the draft that offers to put the fix in a comment does not make it fail.
