---
tags: [jira, template]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a Jira bug for this, but don't create it, just reply with the title and the description. In publication-api, every read of a publication goes through `ReadResourceService.getResourceByIdentifier`, which queries the GSI `BY_TYPE_AND_IDENTIFIER_INDEX_NAME`, and GSIs are eventually consistent. So `UpdatePublicationHandler.unpublishPublication` writes UNPUBLISHED, reads the publication back through the index, and can return PUBLISHED with a stale ETag; a PUT with that ETag then fails with 412. The API tests in nva-api-integration-test poll around it, and one test that checks the unpublish response is disabled. The fix is to use GetItem with ConsistentRead=true wherever we know the key, and to return the written object instead of reading it back.
