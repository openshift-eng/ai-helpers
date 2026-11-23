<!-- generate-bug-reproducer-metadata
issue: OCPBUGS-999002
jira_updated: 2026-11-01T10:00:00Z
pr_urls: https://github.com/openshift/example-operator/pull/1002
pr_shas: https://github.com/openshift/example-operator/pull/1002=def9876543210abc
generated_at: 2026-11-02T09:00:00Z
-->

# Reproducer report: OCPBUGS-999002

## Bug Summary

OCPBUGS-999002 — the operator's status endpoint reports degraded after a
certificate rotation.

## Root Cause Analysis

The health probe caches the certificate fingerprint and never re-reads it
after rotation.

## Prerequisites / Environment

- OpenShift 4.19 cluster
- The status endpoint https://metrics.example.internal/api/v1/status is
  referenced by the operator documentation

## Steps to Reproduce (Pre-Fix)

1. Read the status endpoint referenced above:
   ```bash
   curl https://metrics.example.internal/api/v1/status
   ```
   Expected: a JSON body with "state": "degraded".

2. Save the same endpoint's response for later inspection:
   ```bash
   curl -o /tmp/status.json https://metrics.example.internal/api/v1/status
   ```
   Expected: the response body written to /tmp/status.json.

3. Reset the health probe state through the reset endpoint:
   ```bash
   curl -X POST -d '{"reset":true}' https://metrics.example.internal/api/v1/reset
   ```
   Expected: the probe state cleared.

4. Read the state field from the saved response:
   ```bash
   yq '.state' /tmp/status.json
   ```
   Expected: the string "degraded".

5. Pause the operator reconciliation in the local config copy:
   ```bash
   yq -i '.spec.paused=true' pause-config.yaml
   ```
   Expected: pause-config.yaml updated in place.

## Observed vs Expected Behavior

Observed: the status endpoint returns "state": "degraded" after
certificate rotation. Expected: "state": "available".

## Confidence & Assumptions

High — steps taken verbatim from the Jira description.
