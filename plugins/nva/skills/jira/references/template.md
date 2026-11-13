# Issue template

The team's default shape for the issues developers create in NP.
It is a baseline to argue over: change it with a pull request to nva-dev-tools, and every developer's Claude picks it up.

## Principles

1. **The issue says what and why; the pull request says how.** Whoever picks the issue up decides the solution.
2. **Short.** The title reads on its own on a board, and the description fits on one screen (about 15 lines before the links).
3. **Done is observable.** Acceptance criteria describe behaviour or a state someone can check, not code to write.
4. **One example beats a paragraph.** A record, a request, a date and an environment make a bug reproducible.

## Title

- States the problem or the outcome, so the reader needs no description to know what the issue is about.
- Bug: the symptom, as "who or what does the wrong thing, and when". `Kurator ser ikke importkandidater etter at enheten er flyttet`, not `Fix import candidates`.
- Technical debt: the problem as it is today. `Scopus import logs expected outcomes as ERROR`, not `Logging cleanup`.
- SPIKE: the question. `Can the NVI report be generated from the search index?`
- Sub-task: the part it delivers. The parent already names the whole.
- At most about 80 characters, with no issue type in it (the type field says that), except `Spike: ` on a Sub-task.
- Put an area in front (`Scopus import: `) only when the title is unclear without it; the label already names the repository.

## Description

Every type starts from the same skeleton:

```markdown
<What is wrong or missing, who notices, and why it matters now. One to three sentences.>

## Acceptance criteria

- <Something someone can check when the work is done.>
- <At most five.>

## Links

- <Example record, log query, Slack thread, design, related issue. Leave the heading out when there is nothing.>
```

Use plain `-` bullets: `- [ ]` checkboxes arrive in Jira as plain bullets anyway.

### Bug

Add the expected behaviour and one example, and drop the acceptance criteria when "Expected" already says when it is fixed.

```markdown
<What goes wrong, for whom, since when if known.>

**Expected:** <What should happen instead.>
**Example:** <Environment, record or request, and the steps when they are not obvious.>
```

### Technical debt

The skeleton as is.
The context says what the problem costs today (time, incidents, risk), since that is what gets it prioritised.

### SPIKE

The questions replace the acceptance criteria, and a timebox keeps the investigation from turning into the implementation.

```markdown
<The question, and why we need the answer now.>

**Timebox:** <Days.>
**Output:** <Usually: the answers as a comment on this issue, a recommendation, and follow-up issues.>

## Questions

- <What we need to know.>
```

### Sub-task

One or two sentences on what this part delivers, and its acceptance criteria.
Do not repeat the parent's context.

## What stays out

| Leave out | Why | Put it in |
| --- | --- | --- |
| Class, method, file and table names | They change, and the reader does not need them to understand the problem | The pull request |
| The proposed solution, design or step list | It is decided when someone picks the issue up | A comment, or the pull request |
| Code, stack traces, long log excerpts | Unreadable in Jira, and they bury the point | A comment, or a link to the log query |
| Progress and findings | The description is the spec | A comment |
| Priority, sprint, story points, assignee | Set when the team plans | Nothing, unless asked |

Naming a service or a part of the product to say where the problem is (publication-api, the Scopus import, the registration wizard) is fine; stop at that level.
A constraint the solution must meet ("must ship with NP-1234", "no change to the public API") is part of the what, so it belongs in the context or the acceptance criteria.

## Language

Write in the language of the parent or epic.
Without one, write in English, unless the user asks for Norwegian bokmål or the issue is meant for the product owner or support.
Headings in Norwegian: `Akseptansekriterier`, `Lenker`, `Spørsmål`, `Forventet`, `Eksempel`, `Tidsramme`, `Resultat`.

## Comments

```markdown
<What happened or what you found. One to three sentences.>
<What comes next, and who it waits for, if anyone.>
```

A comment may hold the details that stay out of the description: a log query, a stack trace, a proposed fix.

## Examples

A bug (invented):

```markdown
Title: Søk gir ingen treff når søketeksten inneholder kolon

Søk på en tittel med kolon gir ingen treff, også når registreringen finnes.
Brukere tror at registreringen mangler, og registrerer den på nytt.

**Forventet:** Søket gir de samme treffene med og uten kolon i søketeksten.
**Eksempel:** Prod, søk på «Klima: en innføring», 2026-11-10.
```

A technical debt issue cut down to the template.
Before, 30 lines: the list of messages logged at ERROR, the Java class that logs failures twice, and two CloudWatch queries.
After:

```markdown
Title: Scopus import logs expected outcomes as ERROR, and every failure twice

Over 99 % of the ERROR lines from the Scopus import are normal outcomes, such as authors who are not in Cristin.
Real errors drown in the noise, and every conversion failure is logged twice.

## Acceptance criteria

- Expected outcomes are logged below ERROR.
- Each conversion failure is logged once.
- Before the "Could not fetch cristin person" message is lowered, its status codes are confirmed to be 404s, not 429 or 5xx.

## Links

- The queries and counts from test on 2026-10-02 are in the first comment.
```
