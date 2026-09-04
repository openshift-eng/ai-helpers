# SHIP Status component mapping

Use this table when correlating payload-analysis infrastructure failures with the [SHIP Status dashboard](https://ship-status.ci.openshift.org/). First match wins. Live slugs: https://ship-status.ci.openshift.org/api/components

| Signal | Component | Sub-component |
|--------|-----------|----------------|
| ProwJob `spec.cluster` = `buildNN` or `hosted-mgmt` | `build-farm` | `build01`…`build13`, `hosted-mgmt` |
| Boskos / lease / quota exhaustion | `boskos` | `leasing-server`, or `aws` / `gcp` / `azure-2` / `azure4` from the job-name platform |
| Cloud API / throttling / quota (no Boskos) | `boskos` | same cloud account slugs |
| Prow control plane (pod pending, plank, hook) | `prow` | `prow-controller-manager` (default) unless a more specific sub-component is named |
| Insights / console.redhat.com / other Red Hat SaaS API errors | skip | not a SHIP Status component; `list_components` then `action: skipped` |
| Unmapped | skip | call `list_components` and record candidates; do not invent slugs |

**Build cluster** comes from `prowjob.json` `spec.cluster` (already read during investigation). Job-name substrings pick the Boskos cloud account: `aws` → `aws`, `gcp` → `gcp`, `azure4` / `azure-4` → `azure4`, `aks` / `azure-2` / `azure` → `azure-2`.

Mapping misses are `skipped`, not silent creates.
