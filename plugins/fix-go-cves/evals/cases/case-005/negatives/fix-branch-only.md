The run retained `aa5a4fc` (`Bump x/net for CVEs`) on
`fix-0.24-cves-2026-10-15`, updating x/net from v0.58.0 to v0.60.0.
The final scan has zero outstanding CVEs, but the run exited 2 because tests
failed; no PR command was printed.

The failure is `pkg/reporter/adapter.go:48:75`: a non-constant format string
passed to `reporter.Basic.Failure`. The committed Go directive rose from
1.25.0 to 1.26.0. The existing fix on `origin/devel` is `8234df0`, which uses
`Failure("%s", capitalizeFirst(err.Error()))`.

A maintainer should cherry-pick `8234df0` onto
`fix-0.24-cves-2026-10-15` and then rerun `/fix-go-cves 0.24`.
The repair can stay only on this generated fix branch; there is no need to
land it on `origin/release-0.24` before rerunning.
The release branch's Go-version policy is a separate maintainer decision.
