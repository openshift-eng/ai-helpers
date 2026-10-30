# Rebase stage artifacts

Use these artifacts when a caller delegates individual stages of the rebase
skill. Paths below are relative to the caller's absolute state directory outside
the checkout. JSON is UTF-8. The agent writes artifacts; the state helper checks
their structure and revision binding, not the truth of a semantic judgment.

## Immutable plan: `plan.json`

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`. |
| `repo` | Absolute path to the target Git checkout. |
| `downstream_ref`, `downstream_sha` | Selected local or remote-tracking branch ref and full commit SHA; a remote-tracking ref needs a configured, discovered remote. The branch determines the PR base. |
| `upstream_tag`, `upstream_sha` | Selected upstream tag and full commit SHA. |
| `previous_upstream_sha` | Full SHA of the previous upstream base. |
| `branch` | Short feature-branch name, distinct from the downstream/default branch; never `main`, `master`, a fully qualified ref, or a repository-protected branch. |
| `carries` | Ordered array of the carry objects below. |
| `tree_deltas` | Array of `{path, status, disposition, rationale}` objects accounting for the downstream tree difference. |
| `validations` | Array of `{id, command, required}` objects; `required` is Boolean. |

Each carry has `id`, `source_sha`, `action`, and `rationale`. Use a full commit SHA
for `source_sha`; IDs remain stable across replay and subject changes. Actions
are `cherry-pick`, `squash`, `drop`, or `undecided`. A `squash` entry additionally
has `squash_into`, naming another carry. List the application order, not a
reordering that puts all squashes last. A tree disposition is `retain`, `adapt`,
`upstream`, `drop`, `regenerate`, or `undecided`. Unresolved entries permit a report
but block application.

Validation IDs are unique and match `[a-z0-9][a-z0-9-]*`: lowercase letters,
digits, and hyphens, starting with a letter or digit. Reserve `carry-accounting`,
`tree-accounting`, and `review` for mandatory semantic gates. Put repository-specific local commands
and required CI checks in `validations`; use an explicit check description in
`command` for a CI-only check, preserving the exact CI check name there (for
example, ID `prow-e2e` and command `ci/prow/e2e`). Evidence must distinguish actual
CI results from an unexecuted command description.

The manager copies an accepted plan into its state directory. Compute
`plan_sha256` using Python's canonical encoding:

```python
hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True).encode("utf-8")).hexdigest()
```

Whitespace alone does not change the digest. Semantic changes require explicit
replanning and invalidate previous evidence.

## Partial application: `apply-progress.json`

The worker records `plan_sha256`, `branch`, `head_sha` (last committed checkpoint),
`completed` (carry result objects), and `in_flight` (null or
`{id, source_sha, pre_head}`). Write the in-flight record before applying a carry;
after committing it, add the outcome to `completed` and clear `in_flight`.
Reconcile interrupted writes with actual Git state before continuing. This file
helps the agent resume; it is not accepted as a completed application result or
readiness evidence. If the operation cannot be identified, preserve the work and
report the blocker.

## Application result: `result.json`

Record `plan_sha256`, `head_sha`, and `carries`. Each carry result has `id`,
`result_sha` (full resulting SHA or null when dropped/already upstream), `outcome`,
and `rationale`. Outcomes are `picked`, `squashed`, `dropped`, `upstream`, or
`regenerated`. All planned IDs occur exactly once. For squashes, several source
IDs can identify the same result commit. Record additional repair commits as
`repairs: [{result_sha, rationale}]`. Explain adaptations in the report and final
tree accounting.

For a revision, write `result-proposed.json` and return its path; do not overwrite
an accepted `result.json`. The manager validates the proposed file with
`advance --to applied --result ...` and replaces the accepted result only after
its checks succeed. A rejected proposal leaves the prior record available.

If execution stops partway, preserve its diagnostic output and Git operation
state, and return a blocker. Do not produce a successful application result
until all carries have outcomes and the candidate is committed and clean.

## Validation evidence

Each gate JSON contains `plan_sha256`, `head_sha`, `verdict`, `log`, and `rationale`.
The caller supplies the gate ID when importing. `verdict` is `PASS`, `FAIL`, `SKIP`,
or `INCONCLUSIVE`. `log` is an absolute path to an existing evidence file, such as
command output or a substantive review report. Include the tested head,
command/check identity, exit status or CI conclusion, and findings in that file.
For local commands, include effective compiler/environment, required tool
availability, meaningful flags, and any skipped checks. Preserve failed runs
alongside diagnostics; identify baseline controls by their own SHA and flags.
Evidence for a different revision must not satisfy readiness.

Only `PASS` satisfies a required gate. An optional skipped check needs a reason.
CI failure, missing evidence, and exhausted retries remain visible to the user.
The manager may publish a draft to obtain CI evidence, but draft publication is
not validation or readiness approval.

## Human-readable reports

`release-report.md` supports the target decision. `pr-body.md` supports draft
review. Both identify pinned inputs, candidate head when available, unresolved
decisions, and validation status. Generate their carry tables and counts from the
same plan/result; report generation never alters recorded decisions or gates.
