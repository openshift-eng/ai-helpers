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

The current trial uses the corrected scan scope, but began before the helper
recorded hashes of ignored files at script completion. Its runtime evidence is
retained; a deterministic contract failure is expected from that missing
measurement. A subsequent trial will use the corrected measurement, preserving
native build/coverage files while checking that the agent leaves them unchanged.
No scored live pass is established yet.
