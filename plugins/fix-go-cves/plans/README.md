# Improvement ideas

Candidate follow-ups found while porting and reviewing the plugin, most
valuable first. Each needs a decision or design before it is built.

## Decisions

- **Drop the LLM verification layer.** Every subagent verdict is already
  gated by deterministic companion evidence, so the model can only add
  failures (usage limits caused false ones). Removing it saves about 550
  script and 500 test lines; `review.sh` keeps the useful judgment.
- **Flag, don't delete, pre-existing broad ignores.** Package-only entries on
  the base branch (submariner-operator's `/tools` docker and containerd
  exemptions) are removed, and scan-regression then re-ignores the findings
  as "Regression from dependency update". Flagging keeps maintainer policy
  but leaves such repositories NOT READY until `.grype.yaml` changes.

## Correctness

- **Accurate regression labels.** Label scan-regression ignores by cause;
  findings exposed by an ignore removal are not dependency regressions.
- **OpenShift builder evidence.** Read the Go minor from `.ci-operator.yaml`
  `build_root_image` or the Dockerfile builder tag when the image cannot be
  pulled, and decide how a toolchain edit should behave for ART builds,
  where a `toolchain` line above the builder's Go can break hermetic builds.
- **Workspaces.** Support `go work vendor` and stdlib fixes through the
  `go.work` toolchain instead of routing both to review.
- **YAML parsing.** Replace the awk heuristics that find ignore entries with
  PyYAML node marks, which handle flow maps, multi-line scalars and
  comments exactly.

## Operations

- **Temp space.** Dapper builds use the host `/tmp`; a nearly full tmpfs
  quota surfaced as test and build failures. Preflight the free space, and
  report ENOSPC as an environment failure rather than a fix failure.
- **Interactive tests.** Detect a test command that prompts (for example
  `sudo`) and fail fast with the `test-command` remedy.
- **CI.** Add `actions/setup-go` so `make test` runs the suite instead of
  skipping it on Go older than 1.26.

## Size

- Share one jq helper for finding tuples and `normloc`, repeated about 17
  times in `fix-all.sh` and `subagents/scan-regression.sh`.
- Split `test/test-lib.sh` (about 10,000 lines) by script.

## Upstream

- Port these fixes back to Shipyard's `skills/cve-fix`, or point Shipyard at
  this plugin: Dapper `GOEXPERIMENT` forwarding, generated-file drift, the
  test rerun, release-stream retry and reviewer isolation.
