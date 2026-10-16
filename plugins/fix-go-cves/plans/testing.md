# Testing and evals

How each layer of the plugin is tested, and the eval to add for the one
layer that has no measurement yet.

## Layers

- **Scripts** (`scripts/`, `subagents/*.sh`) decide versions, commits,
  ignores and gates. `test/test-lib.sh` covers them: hermetic, about 2,300
  checks, run by `make test`.
- **End to end**, real builds, tests, scans and PRs, is covered by live runs
  on Submariner release branches (manual, 20 to 90 minutes each).
- **The skill** (`SKILL.md`) decides the cause, evidence, action and owner
  for each finding. Nothing measures it yet.

The skill layer matters. On release-0.24 it found a default-branch
backport for a license failure and traced stdlib findings to the build
image. It also invented a policy boundary for x/crypto, and called two
bumps "team input" when a leftover `bin/lichen` was blocking the scan.

## Eval design: replay the run

An eval case is a recorded run, not a new one. No build, scan or Docker is
involved, so a case takes minutes and costs well under $1.

- **Fixture.** `evals/scripts/prepare-case.sh CASE DIR` clones the case's
  repository at its pinned commit, then copies the plugin with only
  `scripts/fix-all.sh` replaced by a replayer. The replayer prints the case's
  trimmed log and exits with the recorded code. `SKILL.md` and the git
  history stay real, so the agent can still search the default branch for
  backports.
- **Prompt.** `/fix-go-cves:fix-go-cves X.Y` run in the clone.
- **Judges** (in `evals/judges.py`):
  1. No edits to `go.mod`, `go.sum`, vendor or `.grype.yaml`, and no
     `git push` or `gh pr create` run.
  2. Each fact in `annotations.yaml` (`required` regexes such as
     `cdc3003` or `1\.26\.9`) appears in the report, and no `forbidden`
     regex does.
  3. The reported PR command matches the log's exactly, or is absent when
     the log has none.
  4. One LLM rubric (1 to 5): each finding gets a cause, evidence, action and
     owner, as `SKILL.md` asks.

### Cases

Taken from the release-0.24 runs, named `case-NNN` and indexed in
`evals/README.md`, as the repository lint requires:

| Case | Run | Must report |
| --- | --- | --- |
| case-001 | lighthouse: license and stdlib | Backport cdc3003; Go 1.26.9 |
| case-002 | submariner: partial, PR printed | PR command verbatim, not run |
| case-003 | cloud-prepare: exit 0 | PR command; no invented review |
| case-004 | subctl: leftover `bin/lichen` | Remove it and rerun |
| case-005 | admiral: govet failure | Backport 8234df0 |

Trim each log to the summary, the flagged lines and their context, and
replace home-directory paths.

## Running it

- **agent-eval-harness.** `evals/eval-fix-go-cves.yaml` uses the
  repository's existing schema: a `cli` runner that calls
  `prepare-case.sh` and then the agent, with judges 1 to 3 referenced by
  `module:`/`function:`.
- **Any agent.** The same three steps work anywhere: prepare the case, send
  the prompt, then run `python3 evals/judges.py CASE REPORT DIR`. That
  covers Codex (the harness's `codex` runner, with `CVE_FIX_AGENT=codex`) and
  Antigravity or another CLI by hand.
- **Make.** `make eval case=NNN agent=claude|codex` prepares, runs and
  scores one case. Unlike `make eval` in k8s-rebase, it executes the judges.
- **Not in CI.** It needs model credentials and spends money. Run it before
  changing `SKILL.md` or the review prompts.

## Optional case

Replay the same evidence through the LLM verification layer. If its
verdicts never change an outcome that the deterministic evidence has not
already decided, that settles the decision in the
[plans index](README.md#decisions) to drop the layer.

## Not planned

- Full live-run evals: too slow and Docker-bound, and the live runs already
  cover them.
- Trigger or description evals: little to learn from them.
- A second suite in the `claude plugin eval` layout: its graders cannot run
  the deterministic checks above.
