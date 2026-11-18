---
name: jira
description: Create, edit, comment on, link, move and find issues in NVA's Jira project (NP on sikt.atlassian.net), writing every issue in the team's short default template. Use whenever the user asks to create, write, draft, file, rewrite, tidy, split, link, comment on, assign, move or close a Jira issue, ticket, bug, spike or sub-task, names an issue key such as NP-1234, asks "lag en sak", "opprett en Jira-sak" or "skriv en kommentar på saken", asks what is on their plate or in a repository's backlog, or wants an issue checked against the template.
---

# Jira for NVA

All NVA work is tracked in one Jira project, and most of it is read by people skimming a board.
`references/template.md` is the team's issue template; read it before drafting, rewriting or reviewing an issue.

## Project facts

| What | Value |
| --- | --- |
| Site | `sikt.atlassian.net`, issues link as `https://sikt.atlassian.net/browse/NP-1234` |
| Project | `NP` ("NVA-pilot") |
| Statuses in use | Backlog, Selected for Development, In progress, QA, Done, WontFix |

Developers create **Bug**, **Technical debt**, **SPIKE** and **Sub-task**.
Product owners create **Epic**, **Story** and **Task**, so never create those.
When the user asks for one, say so and offer what fits: Technical debt for internal work, a Sub-task when there is a parent to hang it on, or a draft the product owner creates themselves.
A Sub-task needs a parent and only expands an existing issue.
A SPIKE cannot sit under a Story, so an investigation that belongs there is a Sub-task titled `Spike: …`.

## Ground rules

- **Draft first, write after a yes.** Every write is visible to the team and notifies watchers.
  Show the exact result (type, title, description, parent, labels, links) and write only after the user approves it.
  A changed draft needs a new yes.
- **Mark what you wrote.** A description you wrote or rewrote in full, and every comment you post, starts with `🤖` and a space: the emoji itself, not `:robot:`.
  A targeted edit inside someone else's description leaves its opening alone, and a title never gets the mark.
- **Look before you write.** Search for an issue that already covers it before creating.
  Read the whole issue, its links and its parent before editing.
- **Keep other people's words.** Change only what was asked.
  A rewrite into the template is still a rewrite: show before and after, and move what you cut into a comment instead of dropping it.
- **Keep rich content.** An issue holding mentions, images or panels is returned as HTML, because markdown cannot hold those parts.
  Edit it as HTML and write it back as HTML instead of converting it to markdown.
- **Labels are replaced, not appended**, so send the full list.
  Use a repository name (`publication-api`, `nva-nvi`, `nva-infrastructure`) when the issue is about one repository, and use a label only when `project = NP AND labels = "<label>"` finds other issues with it.
- **Close, never delete.** An issue that should not exist goes to WontFix, or is linked as a duplicate and closed.
- **End with the link.** After any write, reply with the clickable issue link and one line on what changed.

## Tasks

**Create.** Work out type, parent and subject from the conversation and the repository the user is in, asking only for what you cannot infer.
Check for duplicates with `project = NP AND statusCategory != Done AND text ~ "<two or three key words>"` and show close matches.
Read the parent so the issue does not repeat its context and uses its language.
Draft from the template, show it, and create it after a yes.
When linking as Blocks, the inward issue is the one that blocks and the outward issue the one that waits.
Several issues at once (a plan split into sub-tasks) are drafted together, links included, and created in one go after a single yes.

**Edit.** Read the issue with its links and parent.
Show the new title or description next to the old one.
Tidying into the template means cutting implementation details, logs and status notes, and offering to post them as a comment so nothing the reporter found is lost.

**Comment.** Progress, findings and the how go here, since the description is the spec.
Use the comment shape in the template, in the issue's language.
Edit only comments the user wrote.

**Move or assign.** Pick the transition from the ones the issue actually offers and go by its id: a transition's name is often not the target status.
"Assign to me" uses the user's own account id; other people are looked up by name first.

**Find.** Ask for only the fields you need (summary, status, type, assignee, labels) so results stay small, and answer with a table that links every key.

| Question | JQL |
| --- | --- |
| My open issues | `project = NP AND assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC` |
| Open issues for a repository | `project = NP AND labels = "nva-nvi" AND statusCategory != Done ORDER BY created DESC` |
| Children of an issue | `parent = NP-1234 ORDER BY rank` |
| What I reported lately | `project = NP AND reporter = currentUser() AND created >= -14d` |
| Free text | `project = NP AND text ~ "scopus import" AND statusCategory != Done` |

**Review.** Check against the template: a title that stands on its own, a description that fits on one screen, acceptance criteria someone can check, evidence for a bug, no implementation details.
Answer with what to change and a suggested rewrite; write it only when asked.
