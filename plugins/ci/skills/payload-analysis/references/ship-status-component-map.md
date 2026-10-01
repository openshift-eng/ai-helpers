# SHIP Status component mapping

Map the **broken system**, not the Prow job's execution venue. Live slugs: https://ship-status.ci.openshift.org/api/components

Every payload job has `prowjob.json` `spec.cluster` (`build01`…`build13` or `hosted-mgmt`). That is where the job ran. It is not a mapping default. Copy it into `sub_component_slug` only after you have already decided **that CI cluster** is the thing that failed.

If the same failure would have occurred on a different build cluster, it is not a build-farm outage. If no row matches, skip (`action: skipped`, `reason: unmapped`, plus `list_components` candidates). Do not fall through to build-farm.

On every infra `ship_status` observation, record the exact cluster profile name (`cluster_profile` on the job and on `ship_status`). Copy it from the job's CI `cluster_profile`. Do not invent a name from the cloud vendor or the job name.

| Failure domain | Component | Sub-component |
|--------|-----------|----------------|
| Shared CI configuration in `openshift/release` (step-registry, job configs, credential refs) that is not specific to one cluster | `downstream-ci` | `ci-config` |
| Boskos leasing service itself is down | `boskos` | `leasing-server` |
| Quota or cloud API failure on an openshift-org cluster-profile set | `boskos` | platform slug in the set table below |
| Quota or cloud API failure on a Hypershift payload account | `boskos-hypershift` | `aws` or `aks` in the Hypershift table below |
| Prow control plane (job never launched or stuck in Prow itself) | `prow` | `prow-controller-manager` (default) unless a more specific sub-component is named |
| The CI cluster that ran the job: its nodes, scheduler, kubelet, console, or API | `build-farm` | the `spec.cluster` value |
| External SaaS (Insights, console.redhat.com, …) | skip | not a SHIP Status component; `list_components` then `action: skipped` |
| Anything else (including cluster-under-test teardown with no SHIP component) | skip | `list_components` candidates; do not invent slugs |

## OpenShift-org cluster-profile sets (`boskos`)

`boskos/aws`, `boskos/azure`, `boskos/gcp`, and `boskos/gcp-arm64` apply **only** to these sets. Do not bubble any other profile up to them.

| Set | Cluster profiles | Slug |
|-----|------------------|------|
| `openshift-org-aws` | `aws`, `aws-2`, `aws-3`, `aws-4` | `boskos/aws` |
| `openshift-org-azure` | `azure-2`, `azure4` | `boskos/azure` |
| `openshift-org-gcp` | `gcp`, `gcp-openshift-gce-devel-ci-2`, `gcp-3` | `boskos/gcp` |
| `openshift-org-gcp-arm64` | arm64 jobs leasing `openshift-org-gcp-arm64-quota-slice` | `boskos/gcp-arm64` |

The arm64 set reuses profile names `gcp`, `gcp-3`, and `gcp-openshift-gce-devel-ci-2`. Those names are `boskos/gcp` when the job leases `openshift-org-gcp-quota-slice`, and `boskos/gcp-arm64` when it leases `openshift-org-gcp-arm64-quota-slice`. There is no cluster profile named `gcp-arm64`.

Use `leasing-server` when the leasing service itself is down, not when one account is out of quota.

## Hypershift payload accounts (`boskos-hypershift`)

These accounts are Hypershift-owned. They are not openshift-org cluster-profile-set members and they are not Boskos sub-components.

| Cluster profile | Boskos resource | Slug |
|-----------------|-----------------|------|
| `hypershift-aws` | `hypershift-aws-quota-slice` | `boskos-hypershift/aws` |
| `hypershift-aks` | `hypershift-aks-quota-slice` | `boskos-hypershift/aks` |

`hypershift-aks` is the managed AKS management-cluster account on Azure. It is not the openshift-org Azure set and it is not `hypershift-azure`. There is no cluster profile named `aks`.

## Unmapped profiles

`hypershift-azure`, `hypershift-gcp`, QE, ARO, PowerVS, and any other profile that is not in the tables above: `action: skipped`, `reason: unmapped`, unless `list_components` shows a live slug for that exact account.

Mapping misses are `skipped`, not silent creates.
