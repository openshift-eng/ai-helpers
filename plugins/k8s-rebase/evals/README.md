# Testing and evals

The workflow harness and pattern-retention evals exercise real rebases via
Claude. Offline checks cover shared interfaces. These are separate from
[runtime compatibility qualification](../docs/compatibility.md).

## Choose the check

Run these commands from `plugins/k8s-rebase/`. The workflow harness needs
`claude`, Go-based `yq` v4, `jq`, Git, and `rsync` in addition to the
rebase prerequisites. Its background sessions refuse untrusted workspaces:
run `claude` once in each clone under `test/.repos/` and accept the trust
prompt, or a launch fails with that message.

| Check | Command | What it establishes |
| --- | --- | --- |
| Offline contracts | `make test-compatibility test-version-selection test-version-references test-kind-images test-go-version-gate test-rebase-base test-cve-evidence test-validation test-court assert-evidence-paths` | Hook/review/gate interfaces, version selection, OpenShift and KIND images, baseline attribution, complete vulnerability queries, test module/package coverage, court scope/cache behavior, companion paths; no model calls or rebases |
| One full-skill run | `make test repo=ovn-kubernetes/ovn-kubernetes-mcp version=1.35 spec=none` | Launches a background rebase; inspect with `make watch version=1.35`, then `make results version=1.35` |
| Diff review | `make court repo=ovn-kubernetes/ovn-kubernetes-mcp version=1.35` | Adversarial review of the result diff against its configured reference; does not establish that the run completed |
| Configured matrix | `make matrix spec=none` | Runs all configured repo/version cases, court, and bounded retries; takes 4–8 hours |
| Eval artifacts | `make eval case=012` | Synchronous run capturing metrics and evidence for the eval judges |

`version=1.35` selects `test/config-1.35.yaml`, whose target is 1.35.3.
Configs pair a pre-rebase `from_commit` with a `known_good` reference. Court
uses the run's recorded starting commit to check whether a suspected issue was
introduced by that run; it does not infer the run base from the Git merge-base
with the known-good reference. For an older run without recorded metadata, pass
the exact SHA explicitly with `from_commit=<sha>`. Court PASS means only that
the diff review found no supported regression. Check the separate RUN verdict,
target-version evidence, and gate inventory before treating a rebase as
successful. `make results` reports the run and diff review separately, and its
combined overall status stays pending/failing until the required review passes.
Polling waits for the session to finish naturally: a complete gate inventory
must not interrupt Step 5. A recorded workflow PASS also requires completed
orchestrator state and removal of the session marker during cleanup. Inspect
the final response for the actual independent review and PR command.
Unavailable or ambiguous session metadata defers recording; it does not
authorize cancellation. Legacy preliminary records remain unqualified until
the session finishes and its final state is rechecked, even at unchanged HEAD.
Harness state and court transcripts live under
`test/.matrix-state/`.
Accepted gate/state evidence is retained under `test/.matrix-state/evidence/`.
A cached PASS requires that archive and any surviving checkout evidence to
match the recorded run. Missing legacy archives, changed evidence, or a
changed baseline leave the row UNVERIFIED; removing a completed worktree
does not discard its archived proof. An explicit court baseline that differs
from the run baseline produces a diagnostic review and cannot qualify that run.
When a checkout starts a different target version, that version owns its live
state only with a newer matching run-start record for the same repository.
That record also permits the harness's complete main-scratch cleanup before a
new worktree launch; the earlier row still requires unchanged archived proof.
Missing/invalid ownership or partial deletion inside surviving scratch does
not exempt changed evidence.

Court repositories and reviewers run sequentially by default. Set
`MAX_COURT_CONCURRENT` above 1 only when parallel reviews are intended.
The workflow model comes from each repository's `model` override, then the
config's top-level `model`; if both are absent, the CLI default applies.

For evals without a matching matrix run, pass diff_only=1 to make court.
This reviews the current diff without associating the verdict with an older
workflow row for the same repository and version. Use the eval's
run-status.json and final-status.txt for its workflow result.
Eval exports retain nested validation/review attempts, native review prompt
and result files, and gate retry archives in each workspace's `script-logs`.

### Withhold learned fixes

`make test` defaults to `spec=none`; **`make matrix` defaults to `spec=all`**.
Mutations affect a copied plugin, leaving the source intact:

| Spec | What is withheld |
| --- | --- |
| `none` | Nothing: pattern guidance and autofix remain enabled |
| `all-patterns` | Pattern table and detailed sections |
| `all-fns` | Autofix functions except the uncommitted-change cleanup helper |
| `all` | Both pattern content and autofix functions |
| `pattern:<key>` | The section mapped by `TAG_TO_PATTERN` in `test/test-skill.sh` |
| `fn:<tag>` | One `fix_<tag>` function |

`pattern:<key>` removes one `###` section of the pattern guide. Several tags
share a section, some map to loosely related guidance, and table rows stay
intact, so a targeted run withholds less than its tag suggests. Under every
spec, step instructions and gate prompts keep their own migration guidance,
such as Step 3's feature-gate wiring. These runs test recovery with less
help on known cases, not generalization to unseen breakage. See the
[design guide](../docs/design.md).

## Running pattern-retention evals

Full runs call models and build real projects; start with one case at a time.
The eval runner defaults to 200 turns per case. With the default model,
observed cost was about $17–27 for a light case and $40–60 for a heavy one
such as ovn-kubernetes.

### Single-case runs

`make eval case=012` reads the case's `input.yaml` and writes to
`/tmp/k8s-rebase-eval-case-012/output/`. For custom runs,
[run-rebase.sh](scripts/run-rebase.sh) accepts the repo URL, baseline SHA,
target version, model, known-good URL, and known-good ref; output goes under
the caller's `output/` directory. Use a dedicated directory under `.work/`.

The runner caches clones under `evals/.repos/`, or `EVAL_REPO_DIR` when set.
It resets that checkout and deletes prior run changes and rebase branches;
use only disposable eval clones. Run cases sharing a clone sequentially.
Each invocation loads the plugin from a temporary snapshot and explicitly
directs the model to treat plugin and harness files as read-only; edits made
to the snapshot are discarded when the run ends.
Each output directory includes `run-input.json` with the resolved starting
commit and result/reference SHAs so later reviews can use the exact case inputs.

`make eval` and the direct runner collect artifacts; they do **not** execute
the YAML judges.

### Scoring compatibility

The YAML definition uses the
[agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness#evalyaml)
CLI-runner schema with `input.yaml` datasets and inline judges.
Its timeout and budget settings apply per invocation, not across the suite.

This repository does not install or pin a scoring harness, and the built-in
`claude plugin eval` expects a different case layout (`case.yaml` or
`prompt.md`), so it discovers no cases here. Use `make matrix spec=none` and
`make court` to evaluate the workflow and `make eval case=NNN` to collect
artifacts; verify harness and schema compatibility before YAML scoring.

## Coverage

Kubernetes 1.37.1 has six additional exploratory baselines in
[config-1.37.yaml](../test/config-1.37.yaml). They start at pinned 1.36.2
commits and deliberately omit `known_good`. CNCC has retained historical
acceptance on both hosts, but a later dependency-attribution finding requires
fresh qualification with the corrected skill. No portable matrix reference is
configured. Multus has accepted frozen-source workflow evidence with disclosed
verification limits; the other five cases remain deferred and unqualified
for a clean portable reference. Run one with
`make test repo=openshift/multus-cni version=1.37 spec=none`; these are not
new pattern-retention eval cases. See the [1.37 preparation notes](../docs/k8s-1.37.md).
`make matrix` discovers this config too; its overall qualification cannot
pass until references and the required court reviews are available.

Pattern retention covers the repos used to develop the autofix patterns;
it does not test unseen breakage. The 16 cases cover the same repo/version
combinations as `test/config-1.3{4,5,6}.yaml`. Each link opens the case's
pinned baseline and known-good commits.

| Case | Repository | Version |
| --- | --- | --- |
| case-001 | ovn-org/ovn-kubernetes | [1.36.2](cases/pattern-retention/case-001/input.yaml) |
| case-002 | ovn-kubernetes/ovn-kubernetes-mcp | [1.36.2](cases/pattern-retention/case-002/input.yaml) |
| case-003 | openshift/multus-cni | [1.36.2](cases/pattern-retention/case-003/input.yaml) |
| case-004 | openshift/ingress-node-firewall | [1.36.2](cases/pattern-retention/case-004/input.yaml) |
| case-005 | openshift/cloud-network-config-controller | [1.36.2](cases/pattern-retention/case-005/input.yaml) |
| case-006 | openshift/cluster-network-operator | [1.36.2](cases/pattern-retention/case-006/input.yaml) |
| case-007 | ovn-org/ovn-kubernetes | [1.34.1](cases/pattern-retention/case-007/input.yaml) |
| case-008 | openshift/multus-cni | [1.34.1](cases/pattern-retention/case-008/input.yaml) |
| case-009 | openshift/cloud-network-config-controller | [1.34.1](cases/pattern-retention/case-009/input.yaml) |
| case-010 | openshift/cluster-network-operator | [1.34.1](cases/pattern-retention/case-010/input.yaml) |
| case-011 | ovn-org/ovn-kubernetes | [1.35.3](cases/pattern-retention/case-011/input.yaml) |
| case-012 | ovn-kubernetes/ovn-kubernetes-mcp | [1.35.3](cases/pattern-retention/case-012/input.yaml) |
| case-013 | openshift/multus-cni | [1.35.3](cases/pattern-retention/case-013/input.yaml) |
| case-014 | openshift/ingress-node-firewall | [1.35.3](cases/pattern-retention/case-014/input.yaml) |
| case-015 | openshift/cloud-network-config-controller | [1.35.3](cases/pattern-retention/case-015/input.yaml) |
| case-016 | openshift/cluster-network-operator | [1.35.3](cases/pattern-retention/case-016/input.yaml) |

The 1.34 config omits ovn-kubernetes-mcp and ingress-node-firewall.
Case-014's reference is an AI-produced rebase that no configured remote
publishes, so neither the eval runner nor court can compare against it
until that commit is pushed; the other cases use existing rebase references.

Configuration records the cases to run, not their results for a new revision.
For review, retain the plugin commit (`test/.matrix-state/results.tsv` does
not record it), runtime/model, mutation spec, baseline and resolved reference
SHAs, raw gate reports, and court result. Some workflow
configs use moving reference branches; resolve them before comparing runs.

## Interpreting scores

The [eval definition](eval-k8s-rebase-pattern-retention.yaml) has seven
deterministic checks (DONE, report verdicts, no forced advancement, publishing
guard, changed module/vendor files, target minor, printed PR command) and
three LLM judges (correctness, scope, missing/extra changes). The runner also
captures cost, tokens, turns, and model in `metrics.json`.

Read the artifacts behind a score:

- Deterministic checks return an excluded pass for `infra_error` runs,
  including missing/malformed run status. Check `run-status.json` before
  treating a passing score as evidence of a completed run.
- `all_gates_resolved` checks reports that exist; it does not inventory
  all expected gates or verify their HEAD stamps. Use the orchestrator's
  `reports` inventory for completeness and freshness.
- The version check looks for a minor-version anchor in the diff, not exact
  pins in every module. The PR-command check looks for text, not the
  accuracy of its verification claims.
- LLM scores are a smoke check, not the adversarial court. Scope and gap-analysis
  thresholds remain provisional. Known-good references are comparison
  evidence, not the only valid implementation.

The workflow harness requires every expected gate's exact PASS/SKIP verdict
and a valid reviewed commit. Prior-step reviews may cover an ancestor;
Step 4 reviews must cover the final result. Missing, malformed, failed,
inconclusive, and stale final-step reports remain unresolved, including
reports from advisory gates. Extra report names cannot replace missing gates.
A recorded `status/INCOMPLETE` marker forces the workflow run verdict to FAIL,
and `force-advance.log` makes the corresponding eval judge fail.
Court excludes vendor, go.sum, package metadata, and mocks from its diff;
an identical filtered diff returns PASS without a jury. Preserve raw reports
and findings: these summaries do not turn an unresolved gate into PASS.

### Remaining eval work

- Pin and validate a compatible scoring harness, or port the cases and judges
  to the built-in CLI format before documenting a full-suite scoring command.
- Calibrate the scope and gap-analysis thresholds across cases and add deliberately
  bad diffs to check that judges reject plausible regressions.
- Check expected report completeness/freshness and final PR claims directly;
  existing verdict/text checks do not establish those properties.
- LLM prompt templates currently read only `outputs.files`, while deterministic
  checks also read `modified_files`. Verify artifact delivery when changing
  the harness; empty judge inputs must not look like clean diffs.
