# Cloud Provider Errors Reference

Cloud infrastructure failures in CI: resource-lease exhaustion, cloud API quota
and rate limits, provisioning failures, leaked resources, credential/auth errors,
and region/zone availability. These fail a job **before or during** cluster
creation — typically environment issues rather than product bugs;
[§6](#6-outage-vs-config-vs-quota-vs-leak) helps classify.

## When to Use

- Job never starts: `build-log.txt` shows a lease/host/claim acquisition failure
- `junit_install.xml` failure mode is `infrastructure` (see
  [Install — General](install/general.md#infrastructure-failures))
- Installer log shows cloud API errors (quota, throttling, auth, capacity)
- Many jobs on **one** cloud fail simultaneously while other clouds pass

**Use a different reference for:**

- Lease mechanics at the ci-operator layer, `openshift/release` PR correlation →
  [CI Infrastructure Changes](ci-infrastructure-changes.md#leases-and-resource-management)
- Node CPU/memory/disk-IOPS pressure on a *running* cluster (EBS burst credits,
  Azure managed-disk IOPS caps) → [Resource Exhaustion](resource-exhaustion.md)
- Azure `CloudMetrics` disk saturation driving disruption →
  [Disruption](disruption.md)
- Reading the installer log itself (work-backwards, eventual consistency) →
  [Install — General](install/general.md)

## Where Cloud Errors Surface

| Location | Failure class | Meaning |
|----------|---------------|---------|
| `build-log.txt` (early, before test phase) | Lease / host / claim acquisition | No CI capacity was free — job never provisioned |
| `.openshift_install*.log` (non-deprovision) | Cloud API quota / throttle / capacity / auth | Installer could not create resources |
| `hive-install-*` provision pod logs | Hive-managed pool install | ClusterDeployment provision failed |
| deprovision `.openshift_install*.log`, `ipi-deprovision-deprovision` | Teardown / leaks | Failed cleanup → leaked resources |

Find installer logs (exclude teardown to isolate provisioning):

```bash
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep -E "\.openshift_install.*\.log$" | grep -v deprovision
```

---

## 1. CI Resource Acquisition (job never provisions)

The cluster does not exist yet. The error is in the top-level `build-log.txt`,
emitted before any product code runs. These are **always** CI infrastructure
issues. Retry once; if fleet-wide, escalate to Test Platform.

### Boskos — cloud quota leases

Boskos hands out cloud-account/quota "slices". Exhaustion:

```text
Failed to acquire resource, current capacity: 0 free
failed to acquire lease for cloud quota slice "aws-quota-slice": all resources are in use
failed to acquire lease: context deadline exceeded
```

- `current capacity: 0 free` / `all resources are in use` — every account/slice
  for that platform is occupied. Transient under high load; sustained means a
  leak is holding leases (see [§5](#5-cascading-resource-leaks)).
- `context deadline exceeded` — no lease freed within the wait window.

The ci-operator failure reason is `acquiring_lease`. See
[CI Infrastructure Changes](ci-infrastructure-changes.md#leases-and-resource-management)
for the lease lifecycle and how to correlate with `openshift/release` changes.

### OFCIR — bare-metal / Equinix host pools

OFCIR (OpenShift Fleeting CI Resources) provisions physical hosts for `metal`/`packet`
(Equinix) jobs. Two CRDs, inspected on the OFCIR management cluster:

| CRD (short) | Key fields | Check |
|-------------|-----------|-------|
| `CIPool` (`cip`) | `.spec.provider`, `.spec.type`, `.spec.size`, `.status.state`, `.status.size` | Is the pool healthy and at requested size? |
| `CIResource` (`cir`) | `.spec.poolRef.name`, `.spec.state` (desired), `.status.state` (current), `.status.address` | Did a host reach `available` and get assigned? |

```bash
oc get cip                 # PROVIDER PRIORITY STATE SIZE REQ-SIZE TYPE
oc get cir                 # ADDRESS STATE REQ-STATE POOL RES-ID
```

Acquisition fails when no `cir` reaches the `available` state (stuck
provisioning, or all `inuse`), or the `cip` `.status.size` is below `.spec.size`
(provider can't deliver hosts). Common CIR states: `available`, `inuse`,
`maintenance`, `error`. A pool full of `error`/`maintenance` CIRs = provider-side
hardware/capacity problem, not a product bug. `.status.size < .spec.size` points
at the underlying `provider` (e.g. Equinix) failing to allocate.

`oc get cip/cir` needs access to the OFCIR management cluster. From job artifacts alone, read
`artifacts/{target}/ofcir-acquire/build-log.txt` and `junit_metal_setup.xml` — see
[install/metal.md](install/metal.md#ofcir-openshift-fleeting-ci-resources).

### Hive — ClusterPool / ClusterClaim

Jobs using pre-baked pools (`cluster_claim` / `hive-openshift-...` profiles)
claim a hibernating cluster instead of installing one. The ci-operator step
waits for the `ClusterClaim` `ClusterRunning` condition to be `True`; on timeout:

```text
failed to wait for the created cluster claim to become ready: ...
timed out waiting for cluster claim to become ready
no clusters in pool are ready to be claimed
```

ci-operator reasons: `acquiring_cluster_claim` / `utilizing_cluster_claim`.
Root cause lives on the Hive management cluster (`hosted-mgmt`); pool definitions
are in `openshift/release` under `clusters/hosted-mgmt/hive/pools/<owner>/`.

| Object | Field / condition | Signal |
|--------|-------------------|--------|
| `ClusterPool` | `.status.Ready` / `.status.Standby` / `.status.Size` | All zero → no capacity to claim |
| `ClusterPool` | `CapacityAvailable: False`, `MissingDependencies: True`, `AllClustersCurrentImages: False` | Pool degraded / stuck |
| `ClusterDeployment` | `ProvisionFailed`, `ProvisionStopped`, `.status.installRestarts` | Underlying install keeps failing |
| `ClusterProvision` | `.spec.stage` = `Failed` (vs `Provisioning`/`Complete`) | Provision job failed |

Frequent pool-install root causes: bad `install-config` in the pool's
`InstallConfigSecretTemplateRef`, invalid platform credentials/certs, or **cloud
quota / API rate limits** (§2) — a claim timeout is often a cloud-quota problem
one layer down. Installer logs are in the `hiveutil` container of the
`hive-install-*` pod (`-l hive.openshift.io/job-type=provision`).

---

## 2. Cloud Quota & API Errors (during infrastructure provisioning)

Failure mode `infrastructure`; errors are in the non-deprovision installer log.
For how to read that log see
[Install — General](install/general.md#infrastructure-failures). Grep quickly:

```bash
grep -iE "quota|limit exceeded|throttl|rate exceed|insufficient|not available|denied" \
  .openshift_install*.log
```

### AWS

| Category | Error strings | Notes |
|----------|--------------|-------|
| Throttling | `RequestLimitExceeded`, `Throttling: Rate exceeded`, `Client.RequestLimitExceeded` | Transient; retry. Fleet-wide = account API pressure |
| vCPU quota | `VcpuLimitExceeded: You have requested more vCPU capacity than your current vCPU limit` | Per-family, per-region (e.g. Standard On-Demand) |
| Instances/volumes | `InstanceLimitExceeded`, `VolumeLimitExceeded`, `MaxSpotInstanceCountExceeded` | Often leaks from failed teardown |
| Elastic IP | `AddressLimitExceeded: The maximum number of addresses has been reached` | Default 5 EIP/region (soft) |
| Capacity | `InsufficientInstanceCapacity`, `Insufficient capacity` | AWS-side shortage in that AZ — see [§7](#7-region--zone-availability) |
| IAM (hard) | `LimitExceeded: Cannot exceed quota for UsersPerAccount: 5000` | Non-adjustable — indicates leaked IAM users |

### GCP

| Category | Error strings | Notes |
|----------|--------------|-------|
| CPU quota | `Quota 'CPUS' exceeded. Limit: N in region R`, `QUOTA_EXCEEDED` | Per-region CPU pool |
| Addresses/disk | `Quota 'IN_USE_ADDRESSES' exceeded`, `Quota 'DISKS_TOTAL_GB' exceeded`, `Quota 'SSD_TOTAL_GB' exceeded` | Common with concurrent jobs / leaks |
| Rate limit | `rateLimitExceeded`, `Rate Limit Exceeded`, `userRateLimitExceeded` | Transient; project-wide API limit |
| Zone capacity | `ZONE_RESOURCE_POOL_EXHAUSTED`, `does not have enough resources available` | GCP-side — try another zone ([§7](#7-region--zone-availability)) |

### Azure

| Category | Error strings | Notes |
|----------|--------------|-------|
| Core quota | `OperationNotAllowed: Operation results in exceeding approved <Family> Cores quota`, `QuotaExceeded` | Per-family (e.g. `standardDSv3Family`), per-region |
| Public IP | `PublicIPCountLimitReached` | Regional public-IP cap |
| Resource groups | `ResourceGroupQuotaExceeded` / subscription RG limit (~980) | Leaked RGs from failed teardown |
| DNS zones | subscription DNS-zone limit reached; record-set-per-zone limit | Leaked private/public zones |
| SKU / zone | `SkuNotAvailable`, `ZonalAllocationFailed` | SKU/zone restriction — see [§7](#7-region--zone-availability) |

### Hard vs soft quotas

- **Soft** (adjustable via support/console; CI manages via account rotation):
  vCPU/core counts, in-use addresses, disk GB, most per-region limits. Recover
  by retrying on another account or waiting for teardown to release resources.
- **Hard** (fixed ceiling — no increase possible): e.g. AWS `UsersPerAccount:
  5000`, IAM roles/policies per account. Hitting a hard limit means **leaked
  resources are not being cleaned up**; the only remedy is manual deletion of
  orphaned resources in the account (§5). A hard-limit error is a signal to hunt
  for a deprovision leak, not to request a quota bump.

---

## 3. Infrastructure Provisioning: CAPI vs Terraform/IPI

The provisioning engine varies by version; error signatures differ. Identify
which is in play before searching:

| Engine | Versions | Log signatures | Where to look |
|--------|----------|----------------|---------------|
| **Cluster API (CAPI)** | Newer (default) | `Machine`/`MachineSet`/`InfraMachine` errors, `failed to reconcile`, CAPI controller logs in the installer's local bootstrap | `.clusterapi_output/`, machine-controller logs in the log bundle; installer log `msg="Creating infrastructure resources"` then CAPI errors |
| **Terraform** | Older | `terraform apply`, `Error: ...`, `error(s) applying`, provider plugin errors | `terraform` lines in `.openshift_install*.log`; `.tfstate` in the log bundle |

Both surface the *same* underlying cloud API errors from §2 — CAPI wraps them in
Machine reconcile failures, Terraform in `apply` errors. Trace to the cloud
error string, then classify with §6. CAPI capacity/quota failures often appear as
Machines stuck `Provisioning` with the cloud error in the machine's status/events.

---

## 4. Credential / Auth Failures

Distinct from quota: the request is *rejected*, not throttled. Usually a rotated,
expired, or misconfigured CI credential (infra issue), occasionally a missing
IAM permission for a newly-used API (can be a product/config change).

| Cloud | Error strings | Typical cause |
|-------|--------------|---------------|
| AWS | `AuthFailure`, `UnauthorizedOperation`, `AccessDenied`, `InvalidClientTokenId`, `SignatureDoesNotMatch` | Bad/rotated key, missing IAM permission |
| AWS STS | `ExpiredToken`, `RequestExpired`, `The security token included in the request is expired`, `AssumeRole` failures | Short-lived STS token expired mid-install (long runs) |
| GCP | `PERMISSION_DENIED`, `Request had invalid authentication credentials`, `oauth2: cannot fetch token`, `invalid_grant` | Service-account key invalid; workload-identity federation misconfigured |
| Azure | `AuthorizationFailed`, `invalid_client`, `AADSTS700016`, `AADSTS7000215`, `ClientSecretCredential authentication failed`, `ManagedIdentityCredential ... failed` | Expired client secret; SP lacks role; managed-identity not attached |

Signals it is **credential** not permission: fails immediately, affects every API
call, and correlates with a credential rotation. A single `AccessDenied` on one
new API call amid otherwise-successful calls suggests a missing permission for a
newly-introduced resource (check recent installer/product changes).

---

## 5. Cascading Resource Leaks

A classic cause of *sustained* quota/lease exhaustion:

```text
failed deprovision → orphaned cloud resources → quota fills → new installs fail
                                              → Boskos slices never free → leases exhausted
```

A deprovision that errors leaves VPCs, EIPs, IAM users, disks, RGs, or DNS zones
behind. These accumulate across many jobs until a quota (often a **hard** one,
§2) is hit. Symptoms: quota/lease errors that **do not clear on retry** and
worsen over time; hard-limit errors like `UsersPerAccount: 5000`.

Inspect teardown (do NOT confuse with provisioning logs):

```bash
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep -E "deprovision|ipi-deprovision-deprovision"
```

Look in the deprovision `.openshift_install*.log` for `failed to delete`, `still
exist`, timeouts, and auth errors during cleanup. Leaks are identified/cleaned by
cluster tags (e.g. `kubernetes.io/cluster/<infraID>`); recovery requires manual
deletion of orphaned resources by Test Platform. Note it in findings — a single
job's leak degrades the whole shared account.

---

## 6. Outage vs Config vs Quota vs Leak

| Evidence | Classification | Action |
|----------|---------------|--------|
| One job fails, retry passes | Transient (throttle/capacity/lease contention) | Retry; no action |
| Many jobs, **one** cloud, others fine | Quota exhaustion or provider outage | Check quota + provider status page |
| All clouds / all jobs fail at same layer | CI platform issue (registry, lease server) | Not cloud-specific — see [CI Infrastructure Changes](ci-infrastructure-changes.md) |
| Error worsens over time, hard-limit hit | Resource leak | Hunt deprovision failures (§5) |
| `AccessDenied`/`AuthFailure` on every call | Credential rotation/expiry | Escalate credential (§4) |
| `AccessDenied` on one new API only | Missing permission (possible config/product change) | Check recent install-config / role changes |
| Validation error before any API call | Config error | Check `install-config.yaml` / cluster profile |

**Outage vs config heuristics:** outages hit multiple *unrelated* jobs on the
same cloud/region at once and correlate with the provider's status page; config
errors reproduce deterministically on every run of *that* job and often correlate
with a recent `openshift/release` or install-config change. Quota/capacity is in
between — fleet-wide but self-resolving as load or leaks clear.

---

## 7. Region / Zone Availability

Capacity is per availability-zone; a shortage is provider-side, not a bug.

| Cloud | Strings | Meaning |
|-------|---------|---------|
| AWS | `InsufficientInstanceCapacity`, `There is no Spot capacity available`, `Unsupported: ... not available in ... zone` | AZ lacks the instance type |
| GCP | `ZONE_RESOURCE_POOL_EXHAUSTED`, `does not have enough resources available to fulfill the request` | Zone exhausted |
| Azure | `SkuNotAvailable`, `ZonalAllocationFailed`, `AllocationFailed` | SKU/zone can't allocate |

Correlate with the instance/SKU family and region in the job's cluster profile.
Common with large/newer instance types in busy regions. Usually transient
(retry) or fixed by the job targeting a different zone/type. Distinguish from
account **quota** (§2): capacity errors mention *availability*; quota errors
mention *limit/quota exceeded*.

---

## Quick Triage Checklist

1. **Where did it fail?** `build-log.txt` before test phase (§1 acquisition) vs
   installer log (§2 provisioning) vs deprovision log (§5 leak).
2. **Grep the log** for `quota|limit|throttl|insufficient|denied|expired|capacity`.
3. **Classify** the string: acquisition, quota, capacity, auth, or leak.
4. **Retry test:** transient (passes on retry) vs persistent (real limit/leak/config).
5. **Scope:** one job (transient/config) vs one cloud (quota/outage) vs all clouds
   (CI platform → [CI Infrastructure Changes](ci-infrastructure-changes.md)).
6. **Hard-limit or worsening?** Suspect a leak (§5); flag for manual cleanup.

## See Also

- [CI Infrastructure Changes](ci-infrastructure-changes.md) — lease lifecycle, cloud-profile/quota changes, `openshift/release` correlation
- [Install — General](install/general.md) — `infrastructure` failure mode, installer-log reading, CAPI/Terraform
- [Resource Exhaustion](resource-exhaustion.md) — node CPU/memory/disk-IOPS pressure on running clusters
- [Disruption](disruption.md) — Azure `CloudMetrics` disk saturation and disruption
- [Artifacts](artifacts.md) — artifact directory structure and paths
