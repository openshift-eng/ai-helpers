---
description: Summarize the CI health of an OpenShift release using live data from the openshift-ci-mcp server
argument-hint: <release version>
allowed-tools:
  - mcp__plugin_ci-extras_openshift-ci-mcp__get_release_health
  - mcp__plugin_ci-extras_openshift-ci-mcp__get_payload_status
  - mcp__plugin_ci-extras_openshift-ci-mcp__get_recent_test_failures
  - mcp__plugin_ci-extras_openshift-ci-mcp__get_regressions
---

## Name

ci-extras:check-release-health

## Synopsis

```bash
/ci-extras:check-release-health <release version>
```

## Description

Fetches live CI health data for a given OpenShift release and produces a concise summary covering payload acceptance, test regressions, and recent failures.

Useful for a quick read on overall release quality before a payload promotion decision or during a release readiness review.

## Implementation

1. Retrieve release health metrics with `get_release_health` for the specified version.
2. Obtain payload acceptance status with `get_payload_status` and gather recent test failures via `get_recent_test_failures`.
3. Collect active regressions with `get_regressions`.
4. Synthesize the data into a brief health summary covering:
   - Overall pass rate trend
   - Payload acceptance rate and last accepted payload
   - Count and severity of active regressions
   - Notable recent test failures
5. Highlight any signals that warrant immediate investigation.
