# SHIP Status component mapping

Match on the **root cause**, not on where the Prow job ran. Live slugs: https://ship-status.ci.openshift.org/api/components

`prowjob.json` `spec.cluster` is the execution venue. Every payload job has one (`build01`…`build13` or `hosted-mgmt`). That field is **not** a mapping signal and **must not** be used as a default. Use it only to name the sub-component **after** you have already decided the build cluster itself is at fault.

If the same failure would have happened on any other build cluster, it is **not** a build-farm outage.

## How to map

1. Identify the broken thing from the investigation: CI config, Boskos/cloud account, Prow control plane, **that** build cluster, or something SHIP does not track.
2. Pick the first row whose **failure-domain signal** matches that root cause.
3. If nothing matches, skip (`action: skipped`, `reason: unmapped`, plus `list_components` candidates). Do **not** fall through to build-farm.

| Failure-domain signal | Component | Sub-component |
|--------|-----------|----------------|
| Causal `openshift/release` PR, broken step/workflow, or credential-definition failure (e.g. `resource name may not be empty`, unresolved step ref) | `downstream-ci` | `ci-config` |
| Boskos / lease / quota exhaustion | `boskos` | `leasing-server`, or `aws` / `gcp` / `azure-2` / `azure4` from the job-name platform |
| Cloud API / throttling / quota (no Boskos) | `boskos` | same cloud account slugs |
| Prow control plane (plank/hook/controller; job never launched or is stuck in Prow, not a node on one cluster) | `prow` | `prow-controller-manager` (default) unless a more specific sub-component is named |
| Affirmative **build-cluster** fault (see below) | `build-farm` | the `spec.cluster` value (`build01`…`build13`, `hosted-mgmt`) |
| Insights / console.redhat.com / other Red Hat SaaS API errors | skip | not a SHIP Status component; `list_components` then `action: skipped` |
| Unmapped (including hypershift/cluster-under-test teardown after tests completed, with no SHIP component) | skip | call `list_components` and record candidates; do not invent slugs |

## Build-farm is correct only with cluster-fault evidence

All of the following must be true:

- The failure is in the **CI cluster that ran the job**, not the cluster under test and not a shared config/service.
- Evidence names that cluster's nodes, scheduler, kubelet, console, or API (step pod never scheduled; `DiskPressure` / untolerated taints / unschedulable on the CI cluster; that cluster's console or API unreachable; the canary for that cluster failing).
- Other mapped rows do not explain it. A credential or step-registry bug that happened to run on `build09` is `ci-config`. A GCP 429 is `boskos` / `gcp`.

Then — and only then — copy `spec.cluster` into `sub_component_slug`.

**Not** build-farm (even though `spec.cluster` is always set):

- Merged `openshift/release` change, broken step ref, credential-form / GSM / Vault lookup (`resource name may not be empty`)
- Boskos lease, cloud quota, cloud-provider 429 / throttling / VIP or DNS loss to the cloud
- Hypershift or cluster-under-test **teardown** after tests completed
- Insights / console.redhat.com / other SaaS
- "Pods died" or "job failed on buildNN" with no evidence the **build cluster** caused it

Job-name substrings pick the Boskos cloud account: `aws` → `aws`, `gcp` → `gcp`, `azure4` / `azure-4` → `azure4`, `aks` / `azure-2` / `azure` → `azure-2`.

Mapping misses are `skipped`, not silent creates.
