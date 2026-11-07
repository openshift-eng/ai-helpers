# Workflow design

A Kubernetes rebase can compile and still be wrong: a type conversion may
drop fields, regenerated CRDs may lose validation, or tests may hang behind
a new feature gate. An agent working toward the visible finish line — a
green summary and a PR command — is rewarded for skipping exactly the checks
that make the result trustworthy. That is reward hacking, and this workflow
is shaped so the only route to the finish line runs through those checks.
The patterns apply to any long-running agent workflow; the Kubernetes
details are examples.

## The state machine owns progress

The central pattern is a **state machine above the agent**. Agents do the
work; a script decides whether the work is enough to move on.

```text
init / resume
  → 1. Mechanical rebase       [1 gate]
  → 2. Compilation fixes       [6 gates]
  → 3. Autofix and discovery   [10 gates]
  → 4. Validation and review   [15 gates]
  → DONE                       gated traversal complete
  → 5. Full-rebase review, PR command, cleanup
```

State lives in `.rebase-tmp/state.json`, not in the agent's prose. The
[skill entry point](../skills/k8s-rebase/SKILL.md) is a thin router: it asks
the [orchestrator](../scripts/k8s-rebase-orchestrator.sh) for the current
step, loads that step's instructions and the shared
[rules](../skills/k8s-rebase/steps/rules.md), and loops. Later steps are not
in context while earlier ones run.

Every gated step ends the same way: commit, collect evidence with `gates`,
review what is pending, and return to the parent, which alone calls
`advance`. A step worker's finish line is evidence, not the PR. The
orchestrator advances only when every expected gate has a report with one
recognized verdict, stamped with the current HEAD, and that verdict is PASS
or SKIP. It checks form and freshness; reviewers own the reasoning, counts,
and SKIP justifications behind each verdict. The rules reserve SKIP for checks
that do not apply: a check that could not run is INCONCLUSIVE, so a missing
tool or network outage never reads as a pass. Step 5 runs after DONE and
never calls `advance`.

| Signal | Meaning |
| --- | --- |
| `gates`: PENDING | A judgment is still needed; normal pending output exits 1 |
| `gates`: EXISTING or RESOLVED | A fresh verdict exists; it may be FAIL or INCONCLUSIVE |
| `gates` exit 0 | No judgments pending; does not establish that gates passed |
| Missing report, invalid verdict, missing/mismatched HEAD, FAIL, or INCONCLUSIVE | Blocks normal advancement |
| `advance` exit 2 with FORCE_ADVANCE | State already moved with unresolved checks; read the warning and `status` |
| `advance` exit 2 with ERROR | Hard error; stop |
| DONE | Traversal complete; neither all checks passed nor Step 5 completed |

## Shortcuts and countermeasures

| Shortcut | Countermeasure | Enforced by |
| --- | --- | --- |
| Skip to the finish | Only the current step's instructions are loaded; the PR step loads after DONE | Skill router |
| Declare the rebase finished | Progress is persisted state that only `advance` moves; exit is blocked before DONE | Orchestrator, Stop hook |
| Grade your own work | Workers return evidence; read-only reviewers write verdicts; independent review sees evidence without the implementer's reasoning | Rules, review helpers |
| Pass a check that did not run | Missing, malformed, or stale reports block; an unperformed check is INCONCLUSIVE | Orchestrator, gate rubrics |
| Fix, then reuse old approvals | Any commit makes every current-step report stale | HEAD stamps |
| Delete an inconvenient report | Deleting prior-step reports is blocked; a missing report blocks | Hook, orchestrator |
| Suppress the symptom | No test skips, vendor edits, direct module commands, or disabled linters | Rules, hooks |
| Loop forever or quit quietly | A bounded repair budget, then force-advancement that records what remains | Rules, orchestrator |
| Summarize optimistically | The final inventory starts from every expected gate, not the reports that exist | `reports`, Step 5 |
| Publish unreviewed work | The skill prints a PR command; push and PR creation are blocked | Hooks, pre-push guard |

These are layered safeguards, not proofs. Hooks match commands heuristically
and depend on runtime activation, and nothing stops an agent from editing
`.rebase-tmp/` by hand: the design removes the need to cheat, not the
ability. The [compatibility note](compatibility.md) lists specific limits.

## Put each responsibility in the right layer

| Layer | Responsibility | Source |
| --- | --- | --- |
| Scripts | Repeatable mutations and measurements: dependency resolution, codegen, autofix, validation | [Rebase](../scripts/k8s-rebase.sh), [autofix](../scripts/k8s-rebase-autofix.sh), [validator](../scripts/k8s-rebase-validate.sh) |
| Hooks | Guard prohibited actions: direct module operations, vendor edits, publishing, deleting prior reports, premature exit | [Hook definitions](../hooks/hooks.json) |
| Gates | Ask one bounded question and record counts, findings, and a verdict | [Gate prompts](../gates), [report writer](../scripts/write-gate-report.sh) |
| Skill and orchestrator | Route work, persist state, and decide when to advance | [Skill](../skills/k8s-rebase/SKILL.md), [orchestrator](../scripts/k8s-rebase-orchestrator.sh) |

Move work into scripts as its rules become understood; keep unfamiliar API
migrations and semantic fixes with the agent. Determinism makes a defect
reproducible, not impossible, so scripted work is still gated.

## Separate evidence, judgment, and repair

Nine companion scripts collect facts into `.evidence` files; the gate
reviewer turns them into a verdict. `gates` runs each companion once, caches
fresh reports, and defers crashed companions to review. A crash, empty output,
or missing tool is not evidence of a successful check.

Evidence and reports carry `HEAD:`. If Step 3 has nine PASS reports and one
FAIL at commit A, a fix at commit B makes **all ten** stale: collect and
review them again. Earlier steps' reports remain historical evidence at their
recorded commits. HEAD stamps cannot see uncommitted edits, so use one
writer, commit before review, and keep source mutations out of parallel
evidence collection.

Gate reviewers are read-only except for their own report. They cite counts,
locations, and what they inspected; the implementing agent investigates and
fixes. Compare with the base to separate a rebase regression from existing
debt — but unchanged source can break against a changed dependency, so an
unchanged line alone does not make a failure pre-existing.

Independent review receives evidence and a rubric, not the implementer's
reasoning. Step 4 reviews a selected commit; Step 5 reviews the full branch
and checks the draft PR verification claims against retained logs and reports.
Approval covers only that revision and scope and never changes a gate
verdict; a review that did not run approves nothing.

## Bound retries without hiding failures

A workflow with no honest way out invites a dishonest one: an agent that
can neither pass a gate nor stop is pushed toward faking the pass. Give it
a bounded exit that records what remains.

Repair iterations and blocked advancement attempts are different counters.
The rules share a three-iteration repair budget across parent and workers.
The orchestrator force-advances on the third blocked `advance` for a step.
The skill permits that only after exhausted repairs in Steps 2–4; a Step 1
structural failure stops without advancement. Use `status` to poll: `advance`
mutates state and consumes attempts.

Force-advancement ends unproductive loops; it does not turn failures into
success. `.rebase-tmp/status/INCOMPLETE` records only the latest forced
transition, so Step 5 inventories **every expected gate** with `reports`,
including missing ones, and carries every unresolved finding into the PR
body. `status` groups SKIP under PASS; `reports` keeps them distinct.

## Test the workflow, not just its output

The [test harness](../test/test-skill.sh) runs real rebases from a pinned
baseline and compares them with known-good references. Mutation modes
withhold the pattern guide, autofix functions, or both from a copied plugin:
can the rest of the workflow still discover and repair the breakage?
Unmodified runs check that learned fixes are retained. Neither establishes
generalization to unseen repositories or releases.

`make court` adds prosecution, defense, a fact-checking judge, and three
jurors, who must check the baseline before calling a difference a regression.
A different diff can still be correct. Court and in-run gates answer
different questions; neither result erases the other's findings. See the
[eval guide](../evals/README.md) for coverage, commands, and scoring limits.

Treat agent-facing text as code. A rewording that reads as cleanup can drop
a fix the agent relied on or turn a decisive rubric into an open question
whose only safe answer blocks advancement. Diff step, rule, gate, and
pattern text against the last revision the matrix passed, and rerun it
before trusting the edit.

## Extend without duplicating the contract

The informational [skill-improvement gate](../gates/step4-verification/skill-improvement.md)
closes the learning loop: a manual repair becomes a reusable
[pattern](k8s-rebase-patterns.md), then an autofix with detection and
post-fix verification. Validate detection on the pre-fix revision; zero
matches after repair may be the expected result. Mutation runs then check
that the workflow still recovers when that help is withheld.

Put repeatable measurement in a companion, interpretation in a gate prompt,
and repair in the implementing step. Keep routing in SKILL.md and the shared
loop and verdict contract in rules.md; step files supply their work, gates,
and exceptions.

Every `.md` in a gate directory becomes an expected gate, changing
advancement and the final inventory. Update the step's gate list and the
gate counts in the README, plugin description, and diagram above; list an
always-PASS gate in the harness's `INFO_GATES`. An executable companion
shares its prompt's basename and writes through
[gate-script-lib.sh](../scripts/gate-script-lib.sh); check the pair with
`make assert-evidence-paths`. Explanatory docs belong outside `gates/`.
