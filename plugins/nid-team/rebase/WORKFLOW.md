# Manual rebase manager

The agent skill coordinates analysis, Git operations, validation, and review.
`rebase_manager.py` is a standard-library Python 3.10+ state helper for Unix hosts.
It executes only read-only Git queries and writes its external state directory.
It does not call models, run project commands, contact GitHub, or publish messages.

Rebase mechanics and the canonical artifact schema live in the OpenShift plugin's
[shared rebase skill](../../openshift/skills/rebase/SKILL.md) and
[artifact contract](../../openshift/skills/rebase/references/artifacts.md).
The agent resolves that dependency from the installed plugin registry; these
relative links describe the source tree, not an assumption about installation.
The [manager skill](../skills/rebase-manager/SKILL.md) defines authorization and
stage delegation.

## State and transitions

```text
plan → applied → validated
          │          │
          └── draft ─┘ → review → complete (merged)
                 │         │
                 └─ applied┘    (feedback revision, then new evidence)
```

A draft can obtain CI evidence before validation passes. Review readiness requires
all required gates to pass at the current candidate and all imported feedback to
be resolved at that revision. A closed, unmerged PR records `closed`. Completion
records the actual remote merge, rather than inventing missing validation.

Keep state outside the target checkout. `plan.json` is immutable; `result.json`
records application outcomes. `state.json` contains their digests, last recorded
phase, candidate head, imported evidence, feedback versions/resolutions, and exact
PR identity. Log content is hashed on import and checked again at readiness.
The helper locks individual state updates and atomically replaces JSON files;
use one agent writer for the entire run. This is a local workflow, not a
transactional distributed controller. Preserve artifacts after interruption.

`status` is read-only and reports the last phase, actual checkout head,
`checkout_problem`, `result_problem`, missing/stale/failing gates, and pending feedback. A recorded
`validated` phase can have stale evidence after changes. Required gates are
`carry-accounting`, `tree-accounting`, `review`, and plan validations marked
`required`. Only PASS satisfies them. Optional SKIP evidence needs a reason.
An unperformed check is INCONCLUSIVE.

## Helper commands

Bind `MANAGER` to this plugin's absolute `rebase/rebase_manager.py`, and
`STATE_DIR` to the run's absolute directory in each shell call. First let the
shared plan stage write `plan.json` and `release-report.md`, then initialize:

```bash
python3 "$MANAGER" --state-dir "$STATE_DIR" init --plan "$STATE_DIR/plan.json"
python3 "$MANAGER" --state-dir "$STATE_DIR" status
```

After the shared apply stage produces a complete result, then after importing
actual validation evidence:

```bash
python3 "$MANAGER" --state-dir "$STATE_DIR" advance --to applied --result "$STATE_DIR/result.json"
python3 "$MANAGER" --state-dir "$STATE_DIR" record --gate carry-accounting --evidence "$STATE_DIR/carry-accounting.json"
python3 "$MANAGER" --state-dir "$STATE_DIR" advance --to validated
```

Repeat `record` for every gate. A nonzero exit is a blocker; never edit state to
bypass it. The helper checks clean Git state, planned branch, pinned refs during
application, carry coverage, result ancestry, and evidence bindings. It cannot
independently establish semantic correctness or honesty of an agent-authored
PASS. Read the evidence and perform the work described in the skill.

After a code change, overwrite `result.json` with the revised application record
and call `advance --to applied` again; changed results invalidate old gates.
If the accepted plan changes, preserve this directory and initialize a new run.
The previous `--auto`, `--dryrun`, and `--start-over` executor flags are removed.
Use the agent's plan stage for analysis without applying changes; there is no
helper option that discards prior state.

## Feedback snapshots

Fetch the actual PR's conversation, inline threads, and review bodies. Import a
JSON array; prefix IDs to distinguish GitHub object types:

```json
[
  {
    "id": "review-comment:123",
    "url": "https://github.com/openshift/example/pull/42#discussion_r123",
    "body": "Preserve the downstream behavior in this case.",
    "updated_at": "2026-10-30T12:00:00Z"
  }
]
```

```bash
python3 "$MANAGER" --state-dir "$STATE_DIR" feedback --input "$STATE_DIR/feedback.json"
python3 "$MANAGER" --state-dir "$STATE_DIR" resolve-feedback --id review-comment:123 --outcome addressed --rationale "The candidate now preserves the behavior; the focused test and review pass."
```

Receipt does not acknowledge or resolve feedback remotely. Identical bodies are
idempotent; changed bodies retain history and reopen the item. `addressed` needs
a changed revision and current passing gates; `no-change` and `declined` also
require current evidence and a specific rationale. A later candidate revision
requires resolutions to be checked again. The helper posts no replies.

## PR snapshots

Fetch by the saved target repository and number, including closed PRs. Normalize
the live response without guessing defaults:

```json
{
  "number": 42,
  "url": "https://github.com/openshift/example/pull/42",
  "target_repository": "openshift/example",
  "base_ref": "master",
  "head_ref": "rebase-v1.13.2",
  "head_sha": "FULL_CANDIDATE_COMMIT_SHA",
  "state": "OPEN",
  "draft": true
}
```

```bash
python3 "$MANAGER" --state-dir "$STATE_DIR" sync-pr --input "$STATE_DIR/pr.json"
```

The first open draft can be recorded from `applied`. Non-draft requires fresh
passing evidence and resolved feedback. Later snapshots must match the persisted
PR identity. Open snapshots must match the candidate head. For a known PR, a
`MERGED` or `CLOSED` snapshot may record a different final remote head; the saved
candidate/evidence remain unchanged and `pr_head_differs` discloses the mismatch.
A terminal snapshot records the remote state
without deleting any artifacts. The agent is responsible for authenticating the
snapshot against GitHub; importing a fabricated JSON file proves no remote action.

## Local checks

```bash
python3 -m unittest discover -s plugins/nid-team/rebase -p 'test_*.py' -v
```

Tests use temporary synthetic Git histories and local JSON/log artifacts. They
exercise state transitions, accounting, stale evidence, and feedback handling;
they do not establish correctness on historical rebases or qualification for an
unattended service.
