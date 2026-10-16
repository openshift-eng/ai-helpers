# Runtime compatibility

Claude Code and Codex share one plugin, skill, orchestrator, and report
format. The [skill](../skills/k8s-rebase/SKILL.md) defines the execution
contract; the [design guide](design.md) explains its boundaries.

## Review and hook requirements

Ordinary step work and gates use native workers when available (`Agent` or
`Task` in Claude, native subagents in Codex), or run inline when none exists.
Execution is sequential unless the user explicitly requests parallel work. The
independent reviews in [Step 4](../skills/k8s-rebase/steps/step4-verification.md)
and [Step 5](../skills/k8s-rebase/steps/step5-pr.md) have different host routes:

| Host | Review route | Infrastructure failure |
| --- | --- | --- |
| Claude Code | Helpers invoke a separate `claude` process | Existing fallback permits continuation; this is not completed independent review |
| Codex | Helpers prepare a prompt with `--print-prompt`; a fresh-context native reviewer reads it | Failed preparation, unavailable reviewer, or missing/malformed verdict stops the path |

Use the parent session's host, including after a handoff. A model vendor or
installed CLI does not select the route. Approval applies only to the
reviewed revision and scope; it does not change gate verdicts. Step 5 also
checks the drafted PR claims against retained logs before presentation.

Hooks activate through `.rebase-tmp/.session-active` relative to the
session cwd. Start at the target checkout root, use separate clones for
concurrent rebases, and retain the marker until cleanup succeeds.
Codex requires review and trust of the installed hook definitions through
`/hooks`; see the [hook documentation](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).
Installation alone is not proof that hooks are active.

## Qualification status

The [offline tests](../test/test_compatibility.py) exercise the shared review,
hook, state, and cleanup contracts. Historical full repo/version runs used Claude Code.
Focused installed-runtime fixtures on both hosts have covered review routing
and finalization; those fixtures do not qualify an unattended full rebase.

On October 6, 2026, Codex CLI 0.160.1 completed a default-configuration
Kubernetes 1.37.1 rebase of `openshift/cloud-network-config-controller`,
from `d3b5de705d133ad568e37b8ccf027d5ccd5e7d38` to
`ff6c288b00fc42c7cb323355ceeb87c7ed157eec`. An independent acceptance audit
verified all 32 current reports (28 PASS, four justified SKIP), completed
producers, fresh-context independent reviews, accurate PR commands, and
cleanup. Build, vet, and lint passed; default tests reported 50 passing test
events (30 top-level tests and 20 subtests). Race compilation
failed on an unchanged baseline constructor mismatch; a completed vulnerability
scan found an unchanged reachable gRPC advisory. Docker registry checks were
partly blocked by authentication; external CI and live cloud tests were not run.
That acceptance is retained as historical evidence. A subsequent audit of all
238 selected dependency manifests disproved the report's claim that Kubernetes
requirements forced its September `sigs.k8s.io/json` pin: every incoming JSON
requirement remained at the July baseline pin. The test and scan outputs retain
their actual meaning, but dependency attribution and scope require correction
and fresh CNCC qualification before draft readiness. Preserve the baseline's
already-higher `k8s.io/utils` floor. Later skill fixes do not retroactively
qualify the earlier candidate or establish unrestricted security clearance.

To qualify both hosts, run the existing `openshift/multus-cni` baseline in
[config-1.36.yaml](../test/config-1.36.yaml) on each, in disposable clones
with the same installed source and environment, including a resume at a
committed boundary. Require applicable gates to pass, justified SKIPs, actual
independent reviews, accurate final reporting, and a restored hook;
force-advancement or a review fallback does not qualify. Retain the source
revision, runtime and model, raw reports, and actual tool outcomes: an agent
declining an action is not a hook denial. Cover these cases on each host:

- Hook denials through each host's tools, with quoted paths and bad arguments.
- Interruption after Step 1's early result marker, missing or malformed state,
  and handoffs that must not duplicate work or reset retry budgets.
- Review rejection followed by repair, large payloads, missing verdicts, and
  an unavailable native reviewer.
- Cleanup failures, which must preserve the session marker and hook backup.

## Known limits

- On Codex CLI 0.160.1, native subagent finalization did not show the Stop
  continuation observed in root sessions. Workers must await every producer;
  the parent must verify completed producer exits at handoff. A completed
  subagent response alone does not establish that its child process finished.
- HEAD stamps cover commits, not uncommitted edits. Hooks are heuristic,
  and Stop observes orchestrator DONE rather than Step 5 completion.
- Two informational gates always PASS; read their details. Build/vet
  evidence records producer exits and incomplete collection; review command
  completion and module coverage before judging it. `go mod verify` checks
  the module cache, not vendor contents.
- Review diffs are filtered and size-limited. Preserve scope and truncation
  warnings.
- The rebase/autofix scripts preserve the caller's `AI_TRAILER`, defaulting to
  Claude for existing callers. The skill binds the actual host's attribution;
  inspect the entire commit range before describing it, especially on resume.

Run the [offline checks](../evals/README.md#choose-the-check) for shared
interfaces and follow the repository's [contribution rules](../../../CONTRIBUTING.md)
for lint, documentation builds, and versioning. Installed-runtime evidence
is still required when changing host behavior.
