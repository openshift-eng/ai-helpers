# SHIP Status component mapping

Map the **broken system**, not the Prow job's execution venue. Live slugs: https://ship-status.ci.openshift.org/api/components

Every payload job has `prowjob.json` `spec.cluster` (`build01`…`build13` or `hosted-mgmt`). That is where the job ran. It is not a mapping default. Copy it into `sub_component_slug` only after you have already decided **that CI cluster** is the thing that failed.

If the same failure would have occurred on a different build cluster, it is not a build-farm outage. If no row matches, skip (`action: skipped`, `reason: unmapped`, plus `list_components` candidates). Do not fall through to build-farm.

| Failure domain | Component | Sub-component |
|--------|-----------|----------------|
| Shared CI configuration in `openshift/release` (step-registry, job configs, credential refs) that is not specific to one cluster | `downstream-ci` | `ci-config` |
| Boskos / lease / quota exhaustion | `boskos` | `leasing-server`, or the platform account (`aws` / `gcp` / `gcp-arm64` / `azure`) |
| Cloud API / throttling / quota (no Boskos) | `boskos` | same platform account slugs |
| Prow control plane (job never launched or stuck in Prow itself) | `prow` | `prow-controller-manager` (default) unless a more specific sub-component is named |
| The CI cluster that ran the job: its nodes, scheduler, kubelet, console, or API | `build-farm` | the `spec.cluster` value |
| External SaaS (Insights, console.redhat.com, …) | skip | not a SHIP Status component; `list_components` then `action: skipped` |
| Anything else (including cluster-under-test teardown with no SHIP component) | skip | `list_components` candidates; do not invent slugs |

Boskos cloud accounts are platform-level. Cluster-profiles (`azure4`, `azure-2`, `aks`, …) bubble up to a single account (`azure`, `aws`, `gcp`, or `gcp-arm64`). Do not invent per-profile slugs. Use `leasing-server` when the leasing service itself is down.

Mapping misses are `skipped`, not silent creates.
