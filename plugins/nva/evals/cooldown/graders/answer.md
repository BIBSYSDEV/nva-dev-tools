---
type: llm
weight: 1
---

Pass when the answer says not to take Vite 7.3.0 in today's bump, because external releases younger than 7 days are not targets, so the bump stays on the newest Vite release that is at least 7 days old.
Fail only when the answer suggests taking 7.3.0 now, in general or as an exception such as a security fix.
Saying that security fixes get no exception is correct, and so is saying that 7.3.0 can come later through a later bump or a Dependabot PR.
