# E2E acceptance and simplification

This is the implementation plan following the 2026-10-22 exploration at
`038d0a33`. It selects the next work, not a proven treatment or a new actor run.
The [testing strategy](testing.md) owns durable acceptance and environment rules;
the [latest matrix](../evals/live/README.md#branch-policy-matrix) owns historical
grades, costs and limitations. Keep those results intact.

## Findings and finish line

The stock pipeline already completes execution, collection, extraction, judging,
reporting and regression. Its remaining failures concern actual skill behavior,
scenario coverage and grader reliability. Another orchestration layer would not
address these failures.

| Measured failure | Required improvement |
| --- | --- |
| Admiral release replaces inherited `make unit` with host build/tests | Preserve maintained command selection and verify its actual execution |
| Admiral release rewrites a Summary line | Relay the witnessed terminal result literally |
| All three successful live replies invent publication steps | Relay only the emitted recipe; preserve withheld publication without replacement advice |
| Both replay cases and Admiral release overstate causality | Separate observed errors, available repairs and demonstrated causes while retaining useful actions and owners |
| Subctl replies omit scan scope | Make available coverage evidence easy to find and report its limits |
| Some factual majorities accept known errors | Calibrate the relevant boundaries and review disagreements across the whole reply |

The finish line is a declared final integration cohort covering both packaged
replays, all four live cases and an admitted real positive-publication replay:
every stock run completes and passes its
configured thresholds, required runtime scenarios have actual evidence, and
whole-reply review finds no remaining substantive contradiction or omission.
Keep the existing three-execution replay comparison protocol as a separate
reliability requirement; one green cohort does not establish repeatability.
A correct blocked-result report may pass live 001. Successful repair must be
demonstrated by live 002, and native coverage by live 003. Do not turn the blocked
case into a successful repair by applying a backport during the run.

## Intended design

| Owner | Responsibility |
| --- | --- |
| `detect.sh` | Resolve environment, repository configuration and default commands |
| Remediation scripts | Mutate and roll back, run gates, retain results, decide publication eligibility |
| Invoking skill | Apply user/branch policy, launch once, observe completion, relay results and investigate remaining work read-only |
| Eval helper | Independently check observed execution, retained state and declared scenario evidence |
| Factual judges | Assess useful diagnosis and advice against captured facts, including claims outside the diagnosis paragraph |

Shorten the skill into one ordered procedure with these boundaries. Detection
already chooses default test commands; stop asking the actor to reconstruct that
default unless branch requirements justify a change. Preserve explicit inherited
settings and target-branch configuration unless higher-priority user/branch policy
requires an override. Maintained additional checks still matter; CI/Make target
presence alone does not make a check mandatory. Keep genuine target instructions
in fixtures and inspect their interaction before changing the procedure.

Use the existing Summary as the factual handoff. Copy it unchanged, then add
diagnosis only for actual unresolved outcomes. Each diagnosis should distinguish
the observation, supported repair or investigation, responsible owner and next
verification prerequisite. Finding an available backport is useful without
proving the failure's cause. The repair must reach the remote target branch
before a requested rerun. A passing retry alone does not establish independence
from the update or remove the need to report the first failure.

Coverage needs special care: normal runs do not retain the full native catalog
proof used by evals. A successful build, readable binary or absent coverage-warning
flag is insufficient proof of native catalog coverage. First expose what existing
scan results actually establish; report stronger native coverage only when the
matching build/catalog evidence exists. Keep unknown coverage explicit, including
on clean fast paths and blocked runs. Basic reporting must continue to work without
the optional evidence directory. Add only the minimal missing handoff in the
existing Summary or scan output, not a second result schema or reporting command.

Do not introduce another reviewer, warning template, natural-language policy
parser, campaign manager or plugin-specific sandbox. The shorter procedure is a
testable design hypothesis, not an explanation already established by five
unsuccessful matrices of instruction changes.

## Work sequence and validation

1. **Audit the failing path and freeze the experiment.** Inspect actual launch
   inputs, native tool observations, replies and competing target instructions.
   Map current requirements to retained rules, duplicates or justified removals
   so shortening does not silently drop behavior. Keep one concise change/review
   record using stock artifacts; avoid duplicating consoles, manifests and reviews without an
   additional check. Declare source, cases, criteria, CLI/model, caps and the
   question each execution answers before launching.
2. **Simplify the handoff.** Change the skill and only the runtime output needed
   for truthful scope reporting. Preserve launch/terminal-exit handling, original
   refs, literal Summary and exact publication recipe, read-only diagnosis and
   useful backport advice. Use focused behavioral regressions for changed script
   output, with evidence enabled and disabled. Run the existing helper checks and
   model-free replays; runtime changes also need the shell suite. A passing
   model-free replay proves plumbing, not revised actor behavior.
3. **Check the oracle before trusting new labels.** Review existing references,
   negatives and measured erroneous replies against unchanged requirements.
   Cover unsupported causality despite correct repair advice, retry-only claims,
   replacement publication prose/commands, omitted scope and a fully supported
   positive answer. Reuse reviewed controls; admit a new fixture only for a
   missing distinction. If a grader input/prompt/model changes, calibrate that
   version first and preserve old grades. Do not rerun unchanged calibration
   merely to seek unanimity. Three samples are judge samples, not actor trials;
   stock majority reduction remains unchanged and instability stays visible.
4. **Measure the relevant actor behavior cheaply first.** Use replay 007 for
   distinct failures/causality and 005 for the existing backport prerequisite.
   Begin with a declared diagnostic pilot; it cannot establish the three-run
   replay comparison by itself. A successful-run or positive-publication replay
   requires a complete real recording with applicable annotations, references,
   negatives, pins and runtime archive. The existing Summary excerpt tests exact
   witness handling only. Consider original recording 002 for positive recipe
   relay; verify admission compatibility before extending the replay helper.
   Use existing live cases for successful repair if no suitable success recording
   is available. Local-only live remotes cannot prove positive recipe relay:
   if that recording cannot be admitted, retain the gap rather than claim complete
   publication coverage or manufacture a recipe.
5. **Close targeted live coverage.** Revalidate the shared worker and
   run live 001 for inherited command preservation/blocked diagnosis, live 002
   for successful repair and withheld publication, and Subctl for native scope
   and canonical gates. Retain actual blocked outcomes and missing coverage,
   including loss of findings through database drift.
6. **Remove independently demonstrated duplication.** Keep normalization and
   test-fixture cleanup separate from the actor experiment. Consolidate repeated
   status prose through links to the canonical record. Verify cleanup before the
   final integration cohort.
7. **Verify the complete result.** Run the declared final set against one frozen
   source/configuration. Keep full-model execution, all judge samples, HTML
   reporting, completion checks and regression in the stock path. Manual review
   complements those results; it cannot replace a failed configured threshold.
   Complete the declared replay repetition checks and retain sample disagreement.
   If later changes affect measured behavior, repeat the affected checks.

An unsuccessful pilot calls for inspection of its specific failure and a new
declared change/question before another trial. Do not add undeclared retries,
extend exhausted deadlines, select only passing cells or relax criteria to close
the work. Use existing caps and the environment/evidence rules in
[testing.md](testing.md#environment-evidence-and-limits). Record known actor and
nested-review costs separately from unknown judge/total costs.

## Framework scope

- **Native contract coverage:** live 004 declares `observed`, although recent
  runs have positive native evidence; live 003 declares `binary`. Use the existing
  binary expectation for live 004 as well, enforcing release-native coverage in
  future runs instead of relying on manual proof. Live 001 retains observed
  blocked-outcome coverage. Inspect initial as well as terminal native requirements.
  A clean initial scan exercises native scanning but cannot count as a dependency
  repair. Freeze and validate the stronger case before actor measurement; preserve
  original grades under their original observed-outcome contract.
- **Proof reuse:** move any necessary checks currently found only in manual
  engine reviews into the existing contract where practical. Keep proof checking
  independent of the actor's prose and runtime verdict. Native projection is
  currently Subctl-specific; do not generalize repository matching or add a
  capability schema until an admitted case needs it.
- **Judge evidence:** retain commands, relevant history results, attempts and
  query scope needed to assess investigation. Full tool observations may be
  verbose, but clipping or filtering them can hide contradictions. Reduce them
  only with reviewed controls demonstrating that decisive facts survive; do not
  replace captured observations with an actor-written explanation.
- **Publication:** keep literal command detection deterministic. Free-form
  replacement procedures require semantic review; do not grow a regex policy
  engine or require actual pushes/PR creation for coverage.

## Bloat audit: remove duplication, preserve distinctions

The main suites contain about 13.4k lines; size alone does not establish waste.
Preserve tests of rollback, stale/missing receipts, native coverage, scoped
ignores, no-fix credit, child exits and retained-tree integrity.

| Candidate | Decision rule |
| --- | --- |
| Repeated `normloc` and finding-tuple construction | Share pure normalization/identity only; retain each caller's distinct actionable/ignored/regression coverage rules and multi-module tests |
| Source-text assertions and repeated shell fixtures | Remove a source probe only when a behavioral regression proves the same boundary; extract setup where it reduces maintenance, not just file length |
| Nested `review.sh` and its prompt | Measure whether it adds independent policy decisions. It is distinct from the already removed LLM verification. Remove only redundant responsibilities; preserve unresolved decisions and publication blocking |
| Repeated status narratives | Setup belongs in eval README, acceptance in testing plan, results in live record, next implementation work here |
| Stale “subagent” descriptions | Correct misleading comments when touching the code; renaming audit directories alone adds churn |

Start the nested-review audit from retained outcomes: identify decisions that
changed the result independently of deterministic policy/gates. Confirm the
remaining behavior with existing provider controls and targeted cases before
deletion; do not build a separate reviewer-evaluation campaign for this audit.

Do not replace optional receipts and existing state with a general event system,
rewrite the YAML/config parsers, split every script, or expand to fleet/scheduled
evals as part of getting these cases correct.

## Open boundary and current evidence

Go-minor compatibility policy remains unresolved. Builder capability is not
maintainer approval; preserve user/repository restrictions without a global ban
or inferred authorization. Resolve any applicable restriction before the affected
live treatment, keeping allowed patch updates and unrestricted behavior intact.
The former release lint override was incorrect; do not revive it as a prerequisite.

Fresh checks at `038d0a33`: 3,046/3,046 shell checks, 68/68 helper tests, and stock
model-free replays 005/007 passed with their expected retained commits and engine
exit 2. No fresh actor, judge or live engine run was performed. The prior worker
was stopped; live authentication, ownership mapping and cancellation cleanup need
revalidation before execution. These facts establish preparation, not acceptance.
