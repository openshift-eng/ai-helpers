<!-- generate-bug-reproducer-metadata
issue: OCPBUGS-999003
jira_updated: 2026-11-01T10:00:00Z
pr_urls: none
pr_shas: none
generated_at: 2026-11-02T09:00:00Z
-->

# Reproducer report: OCPBUGS-999003

## Bug Summary

OCPBUGS-999003 — node pressure alarms fire while the controller loop is
stuck waiting on an API call that never returns.

## Root Cause Analysis

Inferred from the Jira description alone; no fix PR is linked yet. The
loop holds a large in-memory payload while waiting, which keeps node
memory pressure high.

## Prerequisites / Environment

- OpenShift 4.19 cluster
- A copy of the controller log at controller.log in the working directory

## Steps to Reproduce (Pre-Fix)

1. Check the pods and services together to see the stuck state:
   ```bash
   oc get pods && oc get services
   ```
   Expected: both listings return.

2. Search the local controller log copy for timeout lines:
   ```bash
   cat controller.log | grep -i timeout
   ```
   Expected: timeout lines from the stuck loop.

3. Check the node resource usage:
   ```bash
   oc adm top nodes
   ```
   Expected: one node near its memory limit.

4. In the web console, navigate to the operator's route and confirm the
   page stops loading while the loop is stuck.

5. Watch the pod change events with the observe subcommand:
   ```bash
   oc observe pods -n reproducer-ns
   ```
   Expected: change events stream while the loop is stuck.

## Observed vs Expected Behavior

Observed: node pressure alarms while the API call is stuck. Expected:
the loop times out and frees the node.

## Confidence & Assumptions

Low — no fix PR is linked; root cause relies on the Jira text alone.
