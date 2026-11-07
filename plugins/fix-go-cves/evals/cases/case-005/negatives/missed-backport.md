The run retained `aa5a4fc` (`Bump x/net for CVEs`) on
`fix-0.24-cves-2026-10-15`, updating x/net from v0.58.0 to v0.60.0.
The final scan has zero outstanding CVEs, but the run exited 2 because tests
failed; no PR command was printed.

The failure is `pkg/reporter/adapter.go:48:75`: a non-constant format string
passed to `reporter.Basic.Failure`. The committed Go directive rose from
1.25.0 to 1.26.0. The reporter call needs a format-string repair; I have not identified
a default-branch commit to backport.

A maintainer should repair the reporter call on `release-0.24`, land it on
`origin/release-0.24`, and then rerun `/fix-go-cves 0.24`. Reruns start from
that target branch, so applying the repair only to the generated CVE branch
would not fix the next run's base. The release branch's Go-version policy
is a separate maintainer decision.
