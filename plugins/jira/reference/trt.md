# TRT Conventions

Team conventions for issues in the TRT project (Technical Release Team). Use
them when creating TRT cards and when pre-grooming them before the team's
grooming session.

## Project Information

| Field | Value |
|-------|-------|
| **Project Key** | TRT |
| **Project Name** | Technical Release Team |
| **Supported issue types for templates** | Story, Bug, Spike, Task, Ticket |
| **Other issue types** | Epic, Sub-task: no template here; report them as unsupported rather than reshaping them |

## Workflow

New cards are pre-groomed while they are in **New**. The team grooms them in
its weekly session, after which they move to **Refinement**. Anything in
Refinement or later has been groomed by people: do not reshape it.

A card pre-groomed by automation carries the `ai-pre-groomed` label. Never
pre-groom a card that already has it.

## Principles

1. **Flag, never invent.** If required content is missing, name the exact gap.
   Do not supply a beneficiary, acceptance criterion, root cause, owner, scope
   boundary or decision the card does not contain. Restructuring content that
   already exists (for example, turning requirements written as prose into
   acceptance-criteria bullets) is not inventing.
2. **Preserve meaning.** A refined card must let a reader build, verify and
   decide the same things the original did. See [Preservation rules](#preservation-rules).
3. **Concise, not short.** Concision removes repetition, unneeded background
   and excess detail. It is judged by the [concision rubric](#concision-rubric),
   not by a word count.
4. **Leave good cards alone.** Propose a change only when it fixes a
   structural gap or makes the card clearly shorter and easier to scan. A
   rewording that is merely different is not an improvement.

## Templates by issue type

Each template lists **required content** and **recommended headings**. TRT
cards use varied headings, so a template is satisfied by content, not by exact
heading text. The synonyms column lists headings that count. A short card can
satisfy a section with a sentence and no heading.

### Story

A user-visible or team-visible capability or change.

| Section | Required | Satisfied by (synonyms) | Content |
|---|---|---|---|
| Statement | Yes | User story, Problem, Summary, Goal, an opening paragraph | Who benefits, what they need, why. Prefer `As a <role>, I want <capability>, so that <benefit>.` when the role is known; otherwise one or two sentences stating the problem and desired outcome. |
| Acceptance Criteria | Yes | Acceptance criteria, Done when, Success criteria, Validation and acceptance criteria | 1–5 bullets, each an observable, verifiable outcome (see C2). |
| Additional Context | No | Context, Background, Additional context, References, Related, Out of scope | Only facts that change what is built or how it is verified: constraints, decisions already made, out-of-scope statements, links to related issues, PRs and docs. |

Recommended layout:

```markdown
As a <role>, I want <capability>, so that <benefit>.

## Acceptance Criteria

* <observable outcome>
* <observable outcome>
* <observable outcome>

## Additional Context

<constraints, decisions, out of scope, links>
```

### Bug

Something that behaves incorrectly today.

| Section | Required | Satisfied by (synonyms) | Content |
|---|---|---|---|
| Problem | Yes | Summary, Description of problem, Problem, an opening paragraph | What is wrong, where (component, page, job, API), since when if known. |
| Reproduction or evidence | Yes | Steps to reproduce, How reproducible, Evidence, Example, Affected jobs/tests | Either steps to reproduce or at least one concrete example: a job run, test name, API call, screenshot link or error excerpt. |
| Expected vs actual | Yes | Expected results / Actual results, Expected behavior | What should happen and what happens. May be one sentence each. |
| Impact | Yes | Impact, Why it matters | Who or what is affected and how much. |
| Root cause / suggested fix | No | Root cause, Suspected cause, Suggested fix, Scope of a fix, Ruled out | Keep, but label it unconfirmed when the card does not show it was verified. |
| References | No | References, Related, Links | Related issues, PRs, code locations. |

### Spike

A time-limited investigation whose output is a decision or knowledge, not shipped code.

| Section | Required | Satisfied by (synonyms) | Content |
|---|---|---|---|
| Question | Yes | Research question, Question, Goal, an opening paragraph or the summary itself | The question to answer or the decision to enable. |
| Context | Yes | Context, Background, Current state | Why it matters now; the current state; options already known. |
| Exit criteria / deliverable | Yes | Success criteria, Definition of done, Deliverable, Findings documentation, Follow-up actions | What the spike produces (recommendation, design doc, prototype, follow-up cards) and how the team knows it is finished. |
| Approach | No | Investigation approach, Options, Ideas | Candidate approaches or experiments. Keep them as options, not commitments. |
| Timebox | No | Timebox | Recommended. Do not flag its absence as a readiness gap. |

### Task and Ticket

A finite piece of work that is not a user-facing capability: maintenance, migrations, cleanup, configuration, follow-ups. Tickets (often filed from alerts, CI signals or requests from other teams) use the same template.

| Section | Required | Satisfied by (synonyms) | Content |
|---|---|---|---|
| Goal | Yes | Goal, Purpose, Problem, Summary, Why, Ask, Origin, an opening paragraph | What needs to be done and why. For a ticket raised from a signal, the signal and its impact (for example, which alert or job is affected). |
| Scope | Yes for multi-step work | Scope, Action required, Implementation plan, Current behavior and scope, Suggested remediation | What is included, and what is not when that is ambiguous. For a task with a single obvious action, the goal sentence is enough. |
| Done when | Yes | Acceptance criteria, Done when, and Tests and validation or Rollout when they state observable outcomes | Observable completion conditions (1–5, see C2). Test commands and rollout steps are not outcomes. |
| References | No | References, Related, Context, Evidence, Failure signature | Links, repositories, prior work, and evidence for a signal (one representative example, per C4). |

## Readiness

A card is **ready for grooming** when:

1. Every required section for its type is present with real content, not a
   placeholder.
2. Every term a TRT engineer needs to understand the work is defined on the
   card or discoverable from a linked source. An opaque term ("the new flow",
   "the usual fix", an undefined acronym) is a gap.
3. The acceptance criteria or done-when items are verifiable: each says what
   to observe, not just what to do.
4. Nothing on the card contradicts itself (for example, the summary and the
   acceptance criteria describe different work).

Otherwise the card **needs info**. Report each gap as a concrete question
someone can answer, addressed to the reporter where possible:

- Good: "Which Sippy views should switch to named parameters: all
  Component Readiness queries, or only the ones built from multiple fragments?"
- Bad: "Please add more detail."

Do not mark a card ready because a refinement would make it look complete.
Readiness is judged on the content the card actually has.

## Duplicates

Before reshaping a New card, or creating a new one, look for an existing TRT
card covering the same work. Search open TRT cards and cards closed in the
last 90 days.

- **Duplicate:** the same work or defect with the same outcome; finishing one
  would finish the other. When pre-grooming, a likely duplicate is reported
  instead of rewritten. Cite the existing card's key, status and resolution,
  and say in one or two lines why it is the same work.
- **Related, not duplicate:** an overlapping topic, shared components, one
  card being a follow-up to or prerequisite of the other, or the same symptom
  with a different cause. Mention related cards, but do not treat them as
  duplicates.
- **A closed duplicate still counts.** If the existing card was closed as
  Done or Won't Do, the new card is still a duplicate. Report the resolution
  so the team can decide whether the request deserves another look.

## Summary (title) rules

- 5–12 words. State the change or the defect, not the activity of filing it.
- Story, Task, Ticket: start with an action verb ("Persist", "Remove", "Alert on").
- Bug: name the symptom and where it occurs ("Test details rescan does not
  refresh labels").
- Spike: a verb phrase ("Evaluate …", "Research …") or a direct question.
- Keep existing area prefixes the team uses (`[sippy]`, `CR Parity:`,
  `Sippy:`, release names such as `5.2 Branching -`).
- Do not put the user-story sentence, ticket numbers or dates in the summary.

## Concision rubric

Apply each check to every sentence and bullet. The core test:

> **Would removing or shortening this change what gets built, how it is
> verified, or whether someone can start?**
> If not, cut or condense it. If it is evidence, keep it in its smallest
> sufficient form.

| # | Check | Keep (essential) | Cut or condense |
|---|---|---|---|
| C1 | **One statement per fact** | Each requirement, constraint or decision stated once, in its proper section. | The same point repeated in the summary, the statement, the context and the acceptance criteria. Restating the summary as the first sentence. |
| C2 | **Few, testable acceptance criteria** | 1–5 bullets, each an observable outcome, normally under about 40 words. This applies to every list of completion conditions: acceptance criteria, done-when items, and a Spike's exit criteria. | More than five bullets: condense first (see below). Also: bullets that bundle unrelated outcomes, sub-bullet trees that re-describe a linked design doc, and implementation steps posing as criteria. |
| C3 | **Background that matters** | History or context that explains a constraint or decision, in one or two sentences plus a link. | Narrative of how the problem was discovered, meeting recaps, and general explanations of systems the team already knows. |
| C4 | **Minimal sufficient evidence** | One representative example (run ID, test name, error line, link) per distinct symptom; a log excerpt of five lines or fewer. | Full log dumps, multiple examples of the same symptom, long raw URLs (convert to a labelled link with the same target). |
| C5 | **Decisions, not plans** | Implementation decisions and constraints already made ("must stay in sync with the BigQuery provider"). For a Task, scope bullets that define what done means. | Step-by-step implementation plans, dated "repository search findings", option comparisons and onboarding walkthroughs on a Story or Bug. Condense them to at most three bullets of decisions or constraints, or point to where the plan lives. Do not delete a decision. |
| C6 | **No process or meta text** | Out-of-scope statements and explicit "this card does not authorize X" boundaries. | "This story requests …", "Determine during design" duplicated in several places, instructions to the implementer about how to read the card, and AI hedging repeated in several sections. |
| C7 | **Structure helps scanning** | Headings only for template sections; bullets for lists of outcomes or scope; code formatting for identifiers. | Headings for single sentences, deep nesting, bold used for emphasis on most lines. |

### Condensing acceptance criteria to five or fewer

More than five criteria almost always means the list can be condensed. In order:

1. **Remove criteria that are not outcomes.** Implementation steps, test
   commands and rollout procedures go (C5). Keep any constraint they encode as
   a single context bullet.
2. **Merge duplicates.** Criteria that restate each other in different words
   become one.
3. **Combine related outcomes into one bullet that keeps their specifics.**
   For example, "Values turn yellow after 7 days and red after 14, in both the
   Triaged tab and the regression tables" replaces two bullets, and both
   thresholds and both locations survive. Combining must never weaken a
   criterion (see [Preservation rules](#preservation-rules)).
4. **If more than five independent outcomes remain, keep them all** and
   propose a split in the gap comment. Never drop a criterion to reach five.

### Length guidance (not a limit)

Median description length of TRT cards the team has groomed, from a sample of
55 cards in Refinement, In Progress or Review (2026-11):

| Type | Groomed median | Guidance |
|---|---|---|
| Story | about 250 words | 120–350 |
| Bug | about 420 words | 150–450 (evidence makes bugs longer) |
| Task | about 270 words | 100–350 (also Ticket) |
| Spike | about 170 words | 80–250 |

A card above the guidance is fine if every sentence passes the core test. A
card more than about twice the guidance usually fails C1, C3 or C5, or holds
more than one card's worth of work. Say which, and propose a split as a gap
rather than performing one.

### When to propose no change

Propose no change when the card meets its template and readiness criteria
and the only possible edits are stylistic: rewording, reordering, or trimming
less than about a fifth of the text without fixing a rubric failure. Report it
as "no change needed". Assistant-drafted cards have a stricter bar; see the
next section.

### Stricter review for assistant-drafted cards

A card gets the stricter review when **either** of these holds:

- It carries the `ai-generated-jira` label.
- It was created by the Chai Bot Jira service account (`ship-help-jira`), as
  shown by the issue's **creator** field. Do not use the reporter: Chai sets
  the reporter to the person who asked for the card.

These cards were drafted by an assistant, and they are reliably the least
concise TRT cards. In a November 2026 sample, labelled New cards had a median
of about 1,160 words, against about 200 for other New cards. Even after team
grooming they stayed about 40% longer. Bot-created cards without the label
(older cards, or cards filed through other Chai personas) had a median of about
350 words. Review them with these changes:

1. **Assume the card needs condensing.** To report "no change needed", state
   for each check C1–C7 why the card already passes. Do not let "it is
   complete" stand in for "it is concise".
2. **Aim for the lower half of the length guidance** (for example, a Story of
   about 120–250 words). Exceeding it is acceptable only when every sentence
   passes the core test.
3. **Lower the bar for proposing a change.** Propose one when any rubric check
   fails, or when the card can be trimmed by about a tenth or more, instead
   of a fifth.
4. **Look for these generation patterns first:**
   - An "Additional Context" section that restates the acceptance criteria or
     the statement (C1).
   - More than five acceptance-criteria bullets, bullets that bundle several
     outcomes into one long sentence, nested sub-bullet trees, or bullets that
     begin with filler such as "Verify that" (C2, C7). Drop the filler when
     the card is rewritten for another reason; on its own it does not justify
     a proposal.
   - Implementation plans, option comparisons, "preferred approach" sections
     and dated repository search findings in a Story or Bug (C5).
   - Boundary and meta statements repeated across sections ("this story does
     not authorize …", "determine during design", "this story requests …").
     Keep each real boundary once, under Additional Context (C6).
   - Hedges and caveats repeated in several places. Keep each "unverified" or
     "unconfirmed" marker once, next to the claim it qualifies (C1).

What does not change: the [preservation rules](#preservation-rules) and
[readiness](#readiness) criteria apply exactly as for any other card. The
stricter review assumes the card is probably wordy, not that its content is
wrong. Condensing must not drop facts, criteria, links or boundaries. A
generated card can also hold claims nobody has checked, so keep any
"unverified" marker it carries, and never upgrade a claim to fact.

The "AI-generated. Review for accuracy." notice in a description does not
trigger the stricter review. The writing tool adds that notice to any
description it writes, including human-authored text it edited.

## Preservation rules

A refined summary and description must keep, unchanged in meaning:

- **Intent:** the problem, the beneficiary and the desired outcome.
- **Every acceptance criterion's meaning.** Criteria may be merged, split or
  reworded, but none may be weakened, dropped or added. If two conflict, keep
  both and flag the conflict.
- **Facts exactly as written:** numbers, thresholds, versions, dates, IDs,
  test and job names, error strings, code identifiers and file paths.
- **Every link target** (issue keys, PRs, docs, runs). Shortening the link text
  is fine; dropping a link is not, unless it duplicates another link exactly.
- **Out-of-scope statements and stated boundaries.**
- **Unconfirmed status:** if the card says a cause is unverified, the
  refinement must say so too.
- **The attribution line** ("Requested by … via Chai Bot …") at the end, verbatim.
  Omit any existing "AI-generated. Review for accuracy." notice; the writing
  tool adds exactly one.

Never move content into a comment to make the description shorter. Content
that fails the rubric is condensed or removed; content that is essential stays.

## Worked examples

These examples are synthetic. They are paraphrased from patterns seen in TRT
cards, not copied from them.

### E1. Already well groomed: no change

```markdown
As a Sippy developer, I want integration tests to run in the devcontainer,
so that I can validate changes against real integration behavior.

## Acceptance Criteria

* Integration tests run in the devcontainer with one documented command.
* The run records results that another developer can reproduce.
* The setup keeps existing security controls; any extra setup is documented.

## Additional Context

Earlier failures came from a missing container socket; this is unverified.
[Example failing run](https://prow.example/run/123)
```

Outcome: **no change needed.** It has a statement, three testable criteria,
and short context with its evidence marked unverified.

### E2. Requirements written as prose: restructure, flag the missing beneficiary

Before (summary: "UI improvements for regressed tests modal"):

```markdown
A request for several enhancements in the regressed tests modal to better
communicate how long a triage has been going on.

On the Triaged tab, move the "Jira updated" column into a hover popup on the
Jira value. Replace the column with "Regressed Since", showing the earliest
regressed-since date of the triage's regressions as "X days ago" using the
existing timestamp utilities.

Make the Regressed Since values yellow after 7 days and red after 14, using
the accessible colours used elsewhere. Do the same for the Regressed Since
column in the regression tables in this modal.
```

After (summary: "Show regression age in the regressed tests modal"):

```markdown
Make the regressed tests modal show how long each triage and its regressions
have been ongoing.

## Acceptance Criteria

* On the Triaged tab, "Jira updated" moves to a hover popup on the Jira value.
* A "Regressed Since" column replaces it, showing the earliest regressed-since
  date of the triage's regressions as "X days ago" with the existing
  timestamp utilities.
* Regressed Since values are yellow after 7 days and red after 14, using the
  existing accessible colours.
* The regression tables in the modal apply the same colouring to their
  Regressed Since column.
```

Gap comment: "Who uses this modal to decide what to act on (for example, QSE
engineers or TRT on-call)? Adding the role lets the story state its benefit."

Why: every requirement is preserved as an outcome and the thresholds are
kept exactly. The role is not stated on the card, so it is asked, not invented.

### E3. Wordy generated story: condense

Assistant-drafted (labelled `ai-generated-jira`). Before: about 1,500 words.
A user-story sentence; six numbered acceptance-criteria groups with three to six sub-bullets each; an "Additional
Context" section that repeats four of the criteria; a dated "Repository search
findings" section listing a dozen files; a "Preferred implementation option"
section comparing three approaches; and a second "Additional acceptance
criteria" list for reuse by other teams.

After: about 350 words.

- **Statement:** the user-story sentence, unchanged.
- **Acceptance criteria:** five bullets. Each of the six groups collapses to
  its observable outcome. Handoffs and reminders combine into one bullet that
  keeps both outcomes. The reuse criteria fold into the configuration bullet
  ("… and another team can enable it through configuration only").
- **Additional context:**
  - The chosen implementation option and the one constraint that drove it,
    as two bullets.
  - Out of scope, unchanged.
  - Links to the related issue and PR.

Gap comment: "The criteria cover intake, routing, reminders and failure
handling. Should this be split into separate stories before grooming?"

Why: the criteria keep every outcome, while the sub-bullets that described
how were cut (C2, C5). Repeated context (C1) and the dated search findings
(C5) are removed. The option comparison becomes the decision it led to. The
split is proposed, not performed.

### E4. Too thin: no rewrite, gaps only

Before (Story, summary: "Prefer named parameters in SQL queries"):

```markdown
Replace positional parameters with named parameters in SQL queries. This is
particularly beneficial for longer queries and queries built from fragments.
```

Outcome: **needs info, no description change.** Gap comment:

- "Which code is in scope: all PostgreSQL queries in Sippy, or only long and
  multi-fragment ones?"
- "What shows this is done: for example, no positional parameters remain in
  the listed packages, and existing query tests pass?"
- "Is this a Story, or a Task (internal refactor with no user-visible change)?"

Why: rewriting would mean inventing scope and criteria. The card is already concise.

### E5. Bug told as a narrative with a log dump: restructure

Before: three paragraphs in the first person ("I think I've seen this multiple
times …"); a 20-line pasted label listing; a 600-character raw URL; and a
closing guess that it is probably caching.

After:

```markdown
Rescanning job runs for labels from a test details page completes, but the
page does not show the updated labels.

## Steps to Reproduce

1. Open a test details page and use the job run scanner.
2. Select all failed runs and rescan for labels.

## Expected vs Actual

* Expected: the new labels appear on the page.
* Actual: the page shows the old labels. The labels are present in BigQuery
  and in the Sippy PostgreSQL job runs list ([filtered list](<same target>)).

## Impact

Prevents breaking a regression down by a newly defined symptom on the fly.

## Evidence

* Example run: `<run ID>` gained labels `GCPInstanceNotFound` and
  `MachineInstanceVanishedAfterCreate` in BigQuery.
* Suspected cause, unconfirmed: page caching.
```

Why: the same facts, IDs and labels are kept, with the log reduced to the two
labels that matter (C4). The raw URL becomes a labelled link to the same
target, and the guess stays marked as unconfirmed.

### E6. Spike without exit criteria: keep, flag

Before: two paragraphs. Release metadata is maintained by hand today; one idea
is to keep it in the repository and sync it automatically; other ideas are
welcome.

Outcome: **needs info, no description change.** The question and context are
present and concise. Gap comment: "What should this spike produce, for example a
recommendation with follow-up cards or a design doc, and what decision will
it enable?"

### E7. Borderline generated story: the stricter bar applies

Assistant-drafted (created by `ship-help-jira`, no label). Before: about 330
words, within the Story guidance. It has:

- A user-story sentence.
- Six acceptance-criteria bullets, each starting "Verify that". Two restate
  the same outcome in different words, and one is an implementation step
  ("use the existing button component").
- An "Additional Context" section of about 150 words. Its first paragraph
  restates the user-story sentence and two of the criteria. Then comes a
  "determine the approach during design" sentence, the one real boundary
  ("changes to the underlying workflow are out of scope"), and a link to the
  related issue.

A quick review could pass this card: it is complete and within the length
guidance. The stricter review must justify each check, and doing so shows
that it fails C1, C2 and C6, so it gets a proposal. The six
bullets become four (C2): the duplicate pair merges, and the implementation
step goes. The restating paragraph and the design sentence go too (C1, C6).
The boundary and link stay. The result is about 190 words with the same
outcomes, boundary and link.
