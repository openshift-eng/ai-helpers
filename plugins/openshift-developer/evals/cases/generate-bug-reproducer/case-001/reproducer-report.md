<!-- generate-bug-reproducer-metadata
issue: OCPBUGS-999001
jira_updated: 2026-11-01T10:00:00Z
pr_urls: https://github.com/openshift/example-operator/pull/1001
pr_shas: https://github.com/openshift/example-operator/pull/1001=abc123def4567890
generated_at: 2026-11-02T09:00:00Z
-->

# Reproducer report: OCPBUGS-999001

## Bug Summary

OCPBUGS-999001 — example-operator drops the sync annotation on managed
resources when the controller restarts mid-reconcile.

## Root Cause Analysis

The reconciler reads the annotation before persisting status and loses it
when the context is cancelled between the two writes.

## Prerequisites / Environment

- OpenShift 4.19 cluster
- The reproducer namespace `reproducer-ns` holds the managed resources

## Steps to Reproduce (Pre-Fix)

1. List the pods in the reproducer namespace and confirm the controller is
   running:
   ```bash
   oc get pods -n reproducer-ns
   ```
   Expected: the example-operator controller pod is Running.

2. Inspect the services in the infrastructure namespace for comparison:
   ```bash
   oc get services -n other-namespace
   ```
   Expected: the service list of the infrastructure namespace.

3. Read the deployments through the staging context to compare states:
   ```bash
   oc get deployments --context staging-context
   ```
   Expected: the deployment list as seen from the staging context.

4. Tail the controller log for the annotation drop:
   ```bash
   kubectl logs example-operator-controller -n reproducer-ns
   ```
   Expected: a line showing the sync annotation being dropped.

5. Recreate the config map that carries the sync annotation:
   ```bash
   oc apply -f - <<EOF
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: sync-annotations
     namespace: reproducer-ns
   EOF
   ```
   Expected: configmap/sync-annotations created.

## Observed vs Expected Behavior

Observed: after a controller restart the sync annotation is missing.
Expected: the annotation survives the restart.

## Confidence & Assumptions

Medium — reproduction steps taken from the Jira description; the restart
trigger was inferred from the fix PR diff.
