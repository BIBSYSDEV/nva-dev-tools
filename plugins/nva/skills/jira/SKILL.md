---
name: jira
description: Create, edit, comment on, link, move and find issues in NVA's Jira project (NP on sikt.atlassian.net), writing every issue in the team's short default template. Use whenever the user asks to create, write, draft, file, rewrite, tidy, split, link, comment on, assign, move or close a Jira issue, ticket, bug, spike or sub-task, names an issue key such as NP-1234, asks "lag en sak", "opprett en Jira-sak" or "skriv en kommentar på saken", asks what is on their plate or in a repository's backlog, or wants an issue checked against the template.
---

# Jira for NVA

All NVA work is tracked in one Jira project, and most of it is read by people skimming a board.
This skill keeps issues short and alike: the title says what is wrong or wanted, the description says why and when it is done, and the how is left to the pull request.
`references/template.md` is the template itself; read it before drafting, rewriting or reviewing an issue.

## Project facts

| What | Value |
| --- | --- |
| Site | `sikt.atlassian.net`, links as `https://sikt.atlassian.net/browse/NP-1234` |
| Cloud ID | `03cbbec7-5724-4dce-8a65-494b98e1cb4d` (pass it as `cloudId` to every Atlassian tool) |
| Project | `NP` ("NVA-pilot") |
| Statuses in use | Backlog, Selected for Development, In progress, QA, Done, WontFix |

Developers create four issue types: **Bug**, **Technical debt**, **SPIKE** and **Sub-task**.
Product owners create **Epic**, **Story** and **Task**, so never create those.
When the user asks for one, say so and offer what fits instead: a Sub-task under the product owner's Story or Task, Technical debt for internal work, or a draft the product owner can create themselves.
A Sub-task needs a `parent`, and only expands an existing issue: a Story or Task from the product owners, or a Technical debt issue that groups our own cleanup.
A SPIKE cannot be the child of a Story, so an investigation that belongs under one is a Sub-task with `Spike: ` at the start of the title.

## Ground rules

- **Draft first, write after a yes.** Creating, editing, commenting, linking, assigning and moving are all visible to the team and notify watchers. Show the exact result first (type, title, description, parent, labels, links), and write only after the user approves that draft. A changed draft needs a new yes.
- **Mark what you wrote.** Start every description you draft or rewrite, and every comment you post, with `🤖` and a space, so readers can tell it from what a person typed. Use the emoji character itself, not `:robot:`. The title gets no mark. Text a person wrote never gets one either: a small edit to someone else's description leaves its start as it is, and a review does not ask for the mark.
- **Look before you write.** Before creating, search for an open issue that already covers it. Before editing, read the whole issue, its links and its parent.
- **Keep other people's words.** On an issue someone else wrote, change only what the user asked for. Rewriting a description into the template is a rewrite: show it before and after, and move what you cut into a comment rather than dropping it.
- **Do not lose rich content.** When a read reports `appliedContentFormat: html` (mentions, emoji, images, panels), edit in HTML and write it back with `contentFormat: html`; markdown silently drops those parts.
- **Leave triage fields alone.** Do not set priority, sprint, assignee, story points or fix version unless the user asks. The team sets them when it plans.
- **Labels exist before you use them.** Use the repository's name as the label when the issue is about one repository (`publication-api`, `nva-nvi`, `nva-infrastructure`). Use a label only when `project = NP AND labels = "<label>"` finds other issues with it, and otherwise ask. On edit, send the full list, since labels are replaced, not appended.
- **Close, never delete.** An issue that should not exist is moved to WontFix, or linked as a duplicate and closed. Do not delete issues or comments.
- **Always end with links.** After any write, reply with the clickable issue link and one line on what changed.

## Tasks

### Create an issue

1. Work out the type, the parent (if any) and what the issue is about from the conversation and the repository the user is in. Ask only for what you cannot infer.
2. Search for duplicates: `project = NP AND statusCategory != Done AND text ~ "<two or three key words>"`. Show close matches and ask whether to go on.
3. Read the parent, if any, so the issue does not repeat its context and uses its language.
4. Draft the issue from `references/template.md` and show it.
5. On a yes, call `createJiraIssue` with `projectKey: "NP"`, `issueType`, `summary`, `description` (markdown), `labels` and `parent`.
6. Add issue links with `createJiraIssueLink` through `executeWrite`. With `linkType: "Blocks"`, `inwardIssue` is the one that blocks and `outwardIssue` the one that waits.
7. Reply with the link.

When the user asks for several issues at once (splitting a plan into sub-tasks), draft all of them in one message, with the links between them, and create them in one go after a single yes.

### Edit an issue

Read it with `getJiraIssue` and `view: "evidence"`, which also returns links and parent.
Change only what was asked, show the new title or description next to the old one, and write with `editJiraIssue` after a yes.
When asked to tidy an issue into the template, cut implementation details, logs and status notes from the description and offer to post them as a comment, so nothing the reporter found is lost.

### Comment

Comments are where progress, findings and the how go, since the description is the spec.
Use the comment shape in `references/template.md`, in the issue's language, and post with `addOrEditJiraIssueComment` after a yes.
Edit only comments the user wrote.

### Move or assign

Find the transition with `listJiraIssueTransitions` (`executeRead`) and pass its id to `transitionJiraIssue`; a transition's name is often not the target status.
"Assign to me" uses the account id from `atlassianUserInfo`; other people are looked up with `listJiraIssueAssignableUsers`.

### Find issues

Search with `searchJiraIssuesUsingJql` and `fields: ["summary", "status", "issuetype", "assignee", "labels"]` to keep results small, and answer with a table that links every key.

| Question | JQL |
| --- | --- |
| My open issues | `project = NP AND assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC` |
| Open issues for a repository | `project = NP AND labels = "nva-nvi" AND statusCategory != Done ORDER BY created DESC` |
| Children of an issue | `parent = NP-1234 ORDER BY rank` |
| What I reported lately | `project = NP AND reporter = currentUser() AND created >= -14d` |
| Free text | `project = NP AND text ~ "scopus import" AND statusCategory != Done` |

### Review an issue

Check it against `references/template.md`: a title that stands on its own, a description that fits on one screen, acceptance criteria someone can check, evidence for a bug, and no implementation details.
Answer with what to change and a suggested rewrite; write it only when asked.
