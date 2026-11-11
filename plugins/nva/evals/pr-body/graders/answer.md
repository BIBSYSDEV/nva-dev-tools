---
type: llm
weight: 1
---

The answer is the PR body.
Pass when it lists the three commit subjects as they are.
Fail when it lists versions the nva-commons bump brings along (Jackson or AWS SDK), mentions the stack or #812 (for example "Stacked on #812"), or lists checks that were run locally.
