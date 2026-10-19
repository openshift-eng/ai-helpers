# Live remediation eval

Opt-in cases run today's complete plugin against pinned real repository
checkouts, with detected build and test commands and real Grype scans.
Branches are pinned; vulnerability data and builder images remain live.
See [setup and commands](../README.md).

| Case | Repository | Scope |
| --- | --- | --- |
| case-001 | Admiral release-0.24 | Actual remediation and evidence-based reporting |
| case-002 | Admiral devel | Genuine dependency repair with all canonical gates passing |
| case-003 | Subctl devel | Fresh native Linux/amd64 binary and positive scan coverage |

Select one with `evals/run.sh --live --case case-002` (or repeat `--case`).
The original case remains the default. New case runtime results are pending;
pinned checkout preparation has succeeded for both.

The eval retains local fixes and never publishes them. A confirmed partial
runtime outcome can be reported correctly; missing execution evidence cannot.

Scan scope must exclude evaluation tools and caches. An actual Grype probe
cataloged 439 packages with support artifacts present versus 118 in the clean
application checkout; even `.git` did not shield those artifacts from scanning.
The initial contaminated live trial is invalid and excluded from results.
The helper now places the runtime plugin/scanner, fresh home, temporary files,
logs and completion records outside the checkout. Optional host cache paths
must stay outside it; see [setup](../README.md#setup).

A clean-scope trial exposed a behavioral failure after the real script exited 2:
the agent edited the reporter source, committed `cdba74f`, attempted a second
remediation run, and started `make clean`. The once-only wrapper blocked the
second run. The evaluator and its mounted container were stopped to halt the
cleanup. Cleanup had already removed checkout-local eval files; the full runtime
output was recovered from its external log. The helper now preserves that
evidence outside the checkout and treats destroyed remotes as a contract failure.

The subsequent instrumented trial passed the full evaluation pipeline: contract,
both fact judges with three agreeing, error-free samples each, standard report
and regression checks. The agent preserved the script's result while
investigating and recommending the target-branch backport.

The actual runtime took 379 seconds and exited 2. It retained `430fd4c`, fixing
five CVEs through one x/net update with zero outstanding findings, but canonical
`make unit` failed twice on the reporter vet error. No PR command was emitted.
Agent execution took 456 seconds, 14 turns and $0.62; six judge calls were
unpriced, and independent runtime reviewer costs are unknown. This validates
faithful execution/reporting for one blocked run, not that all remediation gates
passed or that the three-round baseline is complete.

A targeted attribution experiment used `go test -race ./pkg/reporter` in the
same immutable builder image, `sha256:54658089851fc3285c0dba827a9dcb5e8d8f30e18c9e572c1c622f13b5946029`:

| Checkout | Go directive | Reporter result |
| --- | --- | --- |
| Pinned release base | 1.25.0 | Pass |
| Runtime result `430fd4c` | 1.26.0 | Vet failure |
| Base with only the Go directive changed | 1.26.0 | Same vet failure |

The directive raise alone activates the check in this builder: the offending
source pre-existed, but the failure is update-related. The live reply's claim
that the upgrade pulled in tooling is inaccurate; x/tools remained v0.49.0.
This experiment attributes the current live run, not the historical recording,
whose replies lacked baseline evidence.

No additional post-run instruction was added before that successful eval. The
earlier behavioral failure remains relevant. The skill now explicitly limits
post-run work to read-only diagnosis and recommendations. Tightened causal
criteria passed reference/negative calibration; updated skill trials remain
pending. Stronger host isolation belongs in the shared harness.
