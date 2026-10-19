# Live remediation eval

One opt-in case runs today's complete plugin against a disposable Admiral
checkout, with the repository's detected build and tests and real Grype scans.
Branches are pinned; vulnerability data and builder images remain live.
See [setup and commands](../README.md).

| Case | Repository | Scope |
| --- | --- | --- |
| case-001 | Admiral release-0.24 | Actual remediation and evidence-based reporting |

The eval retains local fixes and never publishes them. A confirmed partial
runtime outcome can be reported correctly; missing execution evidence cannot.

Scan scope must exclude evaluation tools and caches. An actual Grype probe
cataloged 439 packages with support artifacts present versus 118 in the clean
application checkout; even `.git` did not shield those artifacts from scanning.
The initial contaminated live trial is invalid and excluded from results.
The helper now places the runtime plugin/scanner, fresh home and temporary
files outside the checkout. Optional host cache paths must also stay outside
it; see [setup](../README.md#setup).

A clean-scope trial exposed a behavioral failure after the real script exited 2:
the agent edited the reporter source, committed `cdba74f`, attempted a second
remediation run, and started `make clean`. The once-only wrapper blocked the
second run. The evaluator and its mounted container were stopped to halt the
cleanup; raw logs and runtime artifacts were retained. This failure is not
explained by the trial's missing ignored-file measurement.

A new trial is running with complete script-completion snapshots, including
ignored-file hashes, and the focused reporting changes in `SKILL.md`. No further
post-run instruction has been added for this trial. No scored live pass is
established yet. The next narrow skill improvement is to make post-run diagnosis
and recommendation explicit, leaving repairs, reruns and cleanup for a user
request. Stronger host isolation belongs in the shared harness.
