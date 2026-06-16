# Job Pattern Reference

When analyzing regressions, use these patterns to identify job types from job names and determine ownership.

## ROSA Classic

- **Match**: job name contains `rosa-sts-ovn`
- **Example**: `periodic-ci-openshift-release-master-nightly-4.22-e2e-rosa-sts-ovn`
- **Owner**: HCM OCP Release Enablement
- **Contact**: `#wg-hcm-ocp-release-enablement` on Slack
- **Notes**: ROSA (Red Hat OpenShift Service on AWS) classic managed platform jobs.

## Upgrade Jobs

Most blocking jobs install a fresh cluster and run tests. Upgrade jobs are different — they install a cluster at one OCP version and then upgrade it to another. Three upgrade types exist:

- **Micro upgrade**: installs an earlier build of the **same** minor version as the payload, then upgrades to the payload build (e.g., older 5.0 → newer 5.0).
- **Minor upgrade**: installs the **previous minor** version within the same major, then upgrades (e.g., 4.21 → 4.22).
- **Major upgrade**: installs the **previous major** OCP version and upgrades to the payload version (e.g., 4.x → 5.0).

Determine the upgrade type from the job name — it will indicate the type (e.g., `major`, `micro`) or the source version being upgraded from. If a job has `upgrade` in its name but no further qualifier, examine the context to determine the type.

The distinction matters because the **install-time OCP version** determines the initial cluster state (RHCOS version, default feature gates, etc.), not the payload/target version. For major upgrades against a 5.x payload, the cluster initially runs OCP 4.x.

## RHCOS Versions

OpenShift clusters run Red Hat Enterprise Linux CoreOS (RHCOS). Two variants exist:

- **RHCOS 9** — based on RHEL 9. The long-standing default for all OCP 4.x releases.
- **RHCOS 10** — based on RHEL 10. **GA in OCP 5.0.** Has a different kernel, systemd, SELinux policy, and package set than RHCOS 9.

### Detecting RHCOS version from job names

Job names may contain fragments that indicate which RHCOS variant the cluster uses. Check in this order (first match wins):

1. **`rhcos9_10`** — heterogeneous cluster: mixed RHCOS 9 and RHCOS 10 node pools, or a test that upgrades a node pool's RHCOS version during execution.
   - Example: `periodic-ci-openshift-release-main-nightly-5.0-e2e-aws-ovn-rhcos9_10-upgrade`
2. **`rhcos10`** — RHCOS 10 only.
   - Example: `periodic-ci-openshift-release-main-nightly-5.0-e2e-metal-ipi-ovn-ipv4-rhcos10`
3. **`rhcos9`** — RHCOS 9 only (explicit).
   - Example: `periodic-ci-openshift-release-main-nightly-5.0-e2e-aws-ovn-rhcos9`
4. **No fragment** — default by OCP major version **at install time** (not the payload/target version):
   - OCP 4.x → RHCOS 9
   - OCP 5.x → RHCOS 10

For upgrade jobs, use the **install-time** OCP version (see "Upgrade Jobs" above), not the payload/target version. This matters for major upgrades: a major upgrade job in a 5.x payload installs OCP 4.x, so its RHCOS default follows OCP 4.x rules.

### Confirming RHCOS version from artifacts

The job-name heuristic infers the RHCOS version but can't confirm it. To verify the actual RHCOS variant a cluster ran, inspect `.status.nodeInfo.osImage` on Node resources in the job's artifacts.

**Preferred source — `nodes.json` in gather-extra:**

```
artifacts/{target}/gather-extra/artifacts/nodes.json
```

This is a JSON file containing Node resources. Use `prow-job-artifact-search` to find and fetch it:

```bash
# Find nodes.json
prow_job_artifact_search.py <url> search "**/nodes.json" artifacts

# Fetch it
prow_job_artifact_search.py <url> fetch artifacts/{target}/gather-extra/artifacts/nodes.json
```

**Fallback — must-gather node YAMLs:**

```
cluster-scoped-resources/core/nodes/*.yaml
```

Each file is a single Node resource with the same `.status.nodeInfo.osImage` field.

**Interpreting `osImage` values:**

The version number after "Red Hat Enterprise Linux CoreOS" indicates the RHEL base:

- RHCOS 9: version starts with `9.` — e.g., `Red Hat Enterprise Linux CoreOS 9.8.20260613-0 (Plow)`
- RHCOS 10: version starts with `10.` — e.g., `Red Hat Enterprise Linux CoreOS 10.2.20260521-0 (Coughlan)`

A cluster with mixed `osImage` values across nodes is heterogeneous (RHCOS 9 + 10).

### Analysis implications

Variant isolation (a failure appearing only on one RHCOS variant) is diagnostic context that narrows the root cause to OS-specific changes (kernel, systemd, SELinux, package differences between RHEL 9 and RHEL 10).

## Insights Operator

- **Match**: job name contains `insights-operator`
- **Example**: `periodic-ci-openshift-insights-operator-release-4.22-periodics-e2e-aws-techpreview`
- **Owner**: Insights Operator team
- **Contact**: `#forum-observability-intelligence` on Slack (https://redhat.enterprise.slack.com/archives/CLABA9CHY)
- **Notes**: These jobs sit outside the normal OCP flows. We monitor them for regressions in component readiness, but failures here are best routed to the Insights team rather than treated as core OCP issues.
