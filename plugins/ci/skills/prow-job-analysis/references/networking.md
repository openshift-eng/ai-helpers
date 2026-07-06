# Networking Reference

Network failures in Prow CI jobs in the **cluster under test** and its **disconnected/proxy
environment**: image pull / registry, DNS, OVN-Kubernetes/SDN, service connectivity, load
balancer/ingress, and network policy. For adjacent layers see:
- Build-farm registry, image promotion, `manifest unknown` *from promotion timing* → [ci-infrastructure-changes.md](ci-infrastructure-changes.md)
- Metal hypervisor mirror registry, squid, dnsmasq, SLAAC/DHCPv6 → [install/metal.md](install/metal.md)
- Network failures *during install* → [install/general.md](install/general.md)
- Disruption (OVS-stall fan-out, backend classification) → [disruption.md](disruption.md)
- Cloud API / quota / LB-provisioning quota → [cloud-provider-errors.md](cloud-provider-errors.md)
- Full artifact tree → [artifacts.md](artifacts.md)

## Fast Triage

| Symptom / log string | Likely area | Section |
|----------------------|-------------|---------|
| `ImagePullBackOff`, `ErrImagePull`, `failed to pull image` | Image pull | [Image Pull Failures](#image-pull-failures) |
| `manifest unknown`, `manifest unknown: manifest unknown` | Registry / promotion | [Image Pull Failures](#image-pull-failures) · [ci-infrastructure-changes.md](ci-infrastructure-changes.md) |
| Job name has `disconnected`, `proxy`, `ipv6`, `oci-disconnected` | Disconnected/proxy | [Disconnected & Proxy](#disconnected-and-proxy-environments) |
| `x509: certificate signed by unknown authority` (pulls) | Mirror trust | [Disconnected & Proxy](#disconnected-and-proxy-environments) |
| `no such host`, `SERVFAIL`, `i/o timeout` on `:53` | DNS | [DNS Failures](#dns-failures) |
| `CNI request failed`, `failed to create pod network sandbox` | OVN/SDN | [OVN-Kubernetes & SDN](#ovn-kubernetes-and-sdn) |
| `Unreasonably long ... poll interval` (OVSVswitchdLog) | OVS stall | [OVN-Kubernetes & SDN](#ovn-kubernetes-and-sdn) · [disruption.md](disruption.md) |
| `connection refused` to a ClusterIP, `no endpoints available` | Service/endpoints | [Service Connectivity](#service-connectivity) |
| Router/ingress not ready, LB `EXTERNAL-IP` pending | LB / ingress | [Load Balancer & Ingress](#load-balancer-and-ingress) |
| Test passes without a NetworkPolicy, times out with one | Network policy | [Network Policy](#network-policy) |

## Where to Look

| Artifact | Path | Use |
|----------|------|-----|
| Cluster events | `gather-extra/artifacts/oc_cmds/events` | `Failed`/`BackOff`/`FailedCreatePodSandBox` events |
| Pod status | `gather-extra/artifacts/oc_cmds/pods` | Pods in `ImagePullBackOff`, `ContainerCreating`, `CrashLoopBackOff` |
| OVN pod logs | `gather-extra/artifacts/pods/openshift-ovn-kubernetes/` | CNI, port-binding, ovn-controller |
| SDN pod logs (legacy) | `gather-extra/artifacts/pods/openshift-sdn/` | sdn/ovs pods |
| DNS pod logs | `gather-extra/artifacts/pods/openshift-dns/` | CoreDNS `dns-default-*` |
| Ingress pod logs | `gather-extra/artifacts/pods/openshift-ingress/` | `router-default-*` |
| Network operator | `gather-extra/artifacts/pods/openshift-network-operator/` | CNO rollout/degraded |
| Node journals | `gather-extra/artifacts/journal_logs/` | OVS stalls, kubelet CNI, link events |
| Operator status | `gather-extra/artifacts/oc_cmds/co` | `network`, `dns`, `ingress` degraded |
| Timeline | `**/e2e-timelines_spyglass_*.json` | `OVSVswitchdLog`, `Disruption`, `NodeMonitor` |
| Proxy config | must-gather `cluster-scoped-resources/config.openshift.io/proxies/cluster.yaml` | HTTP(S)_PROXY, NO_PROXY, trustedCA |
| ICSP/IDMS | must-gather `cluster-scoped-resources/{operator,config}.openshift.io/imagecontentsourcepolicies\|imagedigestmirrorsets` | Mirror routing |

If must-gather is present, the must-gather-analyzer `analyze_network.py` script summarizes CNI
health, network operator status, and pod networking. It is **not** run automatically — download and
extract must-gather first (see the [artifacts reference](artifacts.md)), then run the script
manually from the [must-gather plugin](../../../../must-gather/skills/must-gather-analyzer/SKILL.md).

---

## Image Pull Failures

A recurring CI networking failure class, especially in disconnected/proxy/IPv6 jobs.

### Diagnosis Workflow

1. **Find the affected pods** — grep `oc_cmds/pods` and `oc_cmds/events` for `ImagePullBackOff`,
   `ErrImagePull`, `Back-off pulling image`, `FailedCreatePodSandBox`.
2. **Get the exact pull error** — the *event message* (not just the phase) names the failure.
   In must-gather, read the pod YAML `.status.containerStatuses[].state.waiting.{reason,message}`.
3. **Extract the image reference** — note the registry host and whether it's a mirror
   (e.g. `virthost.../registry`, `registry.build0x...`) vs. an upstream (`quay.io`, `registry.redhat.io`, `registry.ci.openshift.org`).
4. **Classify** using the taxonomy below, then follow the matching section.
5. **Check breadth** — one pod (image-specific) vs. many pods/nodes (registry/DNS/mirror/proxy outage).

### Taxonomy (match the error string)

| Category | Error strings to grep | Meaning / next step |
|----------|----------------------|---------------------|
| **Auth failure** | `unauthorized: authentication required`, `401 Unauthorized`, `pull access denied`, `authentication required` | Pull secret missing/invalid for that registry. Check `pull-secret` in `openshift-config`; for external images check the global pull secret has creds for that host. |
| **Image not found** | `manifest unknown`, `manifest unknown: manifest unknown`, `name unknown`, `blob unknown to registry`, `not found` | Tag/digest doesn't exist. Disconnected: image wasn't mirrored (see mirroring race). Build-farm/promotion timing: see [ci-infrastructure-changes.md](ci-infrastructure-changes.md). |
| **Network connectivity** | `dial tcp ... i/o timeout`, `connection refused`, `no route to host`, `context deadline exceeded` | Node can't reach the registry endpoint. Check DNS to the registry host, node routing, proxy/NO_PROXY, firewall/SG. |
| **DNS** | `dial tcp: lookup <registry> ... no such host`, `server misbehaving` | Registry hostname unresolvable — see [DNS Failures](#dns-failures). Disconnected: mirror host must resolve on the cluster network. |
| **Registry TLS/trust** | `x509: certificate signed by unknown authority`, `tls: failed to verify certificate`, `certificate has expired` | Mirror CA not trusted. Check `additionalTrustedCA`/`image.config` and the mirror registry cert. Common in disconnected jobs. |
| **Registry overload / rate limit** | `toomanyrequests`, `pull rate limit`, `503 Service Unavailable`, `error pinging` | Upstream throttling or registry outage; usually transient and widespread. |
| **Registry down** | `error pinging container registry`, `ping attempt failed`, all pulls from one host fail | Mirror/registry pod not serving — check the registry pod (disconnected) or [ci-infrastructure-changes.md](ci-infrastructure-changes.md) for build-farm registry. |

CRI-O wraps these as `rpc error: code = ... desc = ... reading manifest ...` /
`failed to pull and unpack image` — the underlying cause is the tail of the message.

---

## Disconnected and Proxy Environments

Disconnected jobs run the cluster with **no direct internet**; all images come from a **mirror
registry**, and image references are rewritten by **ICSP** (`ImageContentSourcePolicy`, older) or
**IDMS** (`ImageDigestMirrorSet`, 4.13+). Proxy jobs route egress through an HTTP/HTTPS proxy.

**Detect the environment** — job name contains `disconnected`, `proxy`, `ipv6`, `oci-disconnected`,
or `okd-scos` disconnected variants; or `oc get proxy/cluster` / `imagecontentsourcepolicies` /
`imagedigestmirrorsets` are non-empty in must-gather.

### ICSP/IDMS → Mirror → Pull Verification Chain

Debug the pull path end to end, in order:

1. **Mirror routing exists** — confirm ICSP/IDMS is present and covers the failing image's source
   repo. Read `imagecontentsourcepolicies` / `imagedigestmirrorsets` YAML; each maps a `source`
   (e.g. `quay.io/openshift-release-dev/ocp-v4.0-art-dev`) to `mirrors` (the mirror host). A pull of
   an unlisted source repo goes upstream and fails (disconnected → `i/o timeout`).
2. **Mirror host resolves & is reachable** — the mirror hostname must resolve on the cluster network
   and the registry port (usually `5000`/`8443`) must accept connections. `no such host` → DNS;
   `connection refused`/`i/o timeout` → routing/registry-down.
3. **Mirror trusts** — mirror CA must be in the cluster trust (`image.config.openshift.io/cluster`
   `additionalTrustedCA`, or `user-ca-bundle`). `x509: ... unknown authority` = untrusted CA.
4. **Image is actually mirrored** — a present ICSP/reachable/trusted mirror still fails with
   `manifest unknown`/`blob unknown` if that specific tag/digest was never mirrored (see race below).

### Proxy Infrastructure

- **Config**: `proxies.config.openshift.io/cluster` → `httpProxy`, `httpsProxy`, `noProxy`,
  `trustedCA`. Env on nodes/pods: `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`.
- **`NO_PROXY` gaps** — if the mirror/registry, `.svc`, cluster/service CIDRs, or `.cluster.local`
  are missing from `noProxy`, in-cluster or mirror traffic is wrongly sent to the proxy →
  `connection refused`/`Forbidden`/`403` on internal pulls.
- **SOCKS / proxy pod lifecycle** — CI disconnected/proxy jobs run a proxy (squid/http, or a
  SOCKS/`sshuttle` bastion) providing egress or CI→cluster access. If that proxy **pod/service
  restarts or crashes mid-run**, connectivity blips: transient `ImagePullBackOff`, `i/o timeout`,
  or disruption that self-heals. Correlate the failure window with proxy-pod restarts
  (`restartCount`, `lastState.terminated`) and node journals. Symptom = intermittent, not
  persistent. On metal the **squid proxy is inbound only** (CI→cluster) — see [install/metal.md](install/metal.md).

### Image Mirroring Race Conditions

The mirror step (`oc adm catalog mirror` / `oc-mirror` / `oc image mirror`) and ICSP/IDMS
application race against pods that start pulling:

- **Pods pull before ICSP/IDMS applies** → briefly hit the upstream source → `i/o timeout`,
  then recover once the mirror config lands. Transient `ImagePullBackOff` that clears.
- **Pods pull before the mirror is fully populated** → `manifest unknown`/`blob unknown` for
  images not yet pushed; clears after mirroring completes.
- **Verdict**: if pulls succeed on retry / other pods pull the same image fine, it's a race
  (infra/timing), not a product bug. If a specific image *never* appears in the mirror, mirroring
  of that repo genuinely failed — check the mirror step's build-log.

### `manifest unknown` from Promotion Timing (build-farm)

Distinct from the disconnected case: a periodic/consumer job references a payload/component image
whose **postsubmit promotion hasn't finished**, so the tag doesn't exist yet →
`manifest unknown` / `creating_release_images`. Transient CI infra, not a product bug. Detection
in [ci-infrastructure-changes.md](ci-infrastructure-changes.md).

---

## DNS Failures

Cluster DNS is CoreDNS, served by the `dns-default` **DaemonSet** in `openshift-dns`; the DNS
operator lives in `openshift-dns-operator`.

### Error Patterns

- `dial tcp: lookup <name> on <ip>:53: no such host` — resolution failure (NXDOMAIN or no answer)
- `i/o timeout` / `server misbehaving` on `:53` — CoreDNS unreachable or upstream timing out
- `SERVFAIL` — upstream/forward resolver failure
- CoreDNS logs: `[ERROR] plugin/errors ... i/o timeout`, `[ERROR] ... unreachable`

### Common Causes

- **CoreDNS pod not scheduled on a node** — `dns-default` tolerates all taints and runs everywhere;
  if a node is NotReady/cordoned or the DaemonSet pod is missing, pods on that node lose local DNS.
  Check `dns-default-*` pod count vs. node count and per-node placement. Node-local DNS means one
  bad node causes node-local resolution gaps, not cluster-wide.
- **CoreDNS cascade** — CoreDNS forwards external names upstream; if the upstream (node
  `/etc/resolv.conf`, cloud resolver, or disconnected private resolver) is down, *every* external
  lookup SERVFAILs, which cascades into operator degradation, image pulls (`no such host`), and
  broad test failures that look unrelated. Confirm by checking CoreDNS logs for upstream errors and
  whether in-cluster (`.svc.cluster.local`) names still resolve while external ones fail.
- **Disconnected/IPv6** — verify the private/mirror resolver is configured and (IPv6) that AAAA
  records exist. See [install/metal.md](install/metal.md) for dnsmasq specifics.

---

## IPv6 and Dual-Stack

Jobs with `ipv6`, `dualstack`, or metal `ovn-ipv6`/`ovn-dualstack` in the name. IPv6-only jobs are
almost always **disconnected** (mirror + private DNS) — combine this with the sections above.

- **IPv6-only** — every component and endpoint must be IPv6-capable; a hard-coded IPv4 literal or
  missing AAAA record breaks connectivity. Watch for `no route to host` on `fd00::/fc00::` addresses.
- **Dual-stack** — both families active; failures often stem from address-family preference or a
  service/endpoint present in only one family. Check `ipFamilies`/`ipFamilyPolicy` on Services and
  that EndpointSlices exist for both families.
- **Addressing** (metal) — SLAAC/DHCPv6/NDP/router-advertisement issues; see [install/metal.md](install/metal.md).

---

## OVN-Kubernetes and SDN

OVN-Kubernetes is the default CNI. Pods in `openshift-ovn-kubernetes`: `ovnkube-node-*`
(DaemonSet; containers `ovn-controller`, `ovnkube-controller`, `nbdb`, `sbdb`, `northd`) and
`ovnkube-control-plane-*` (4.14+; older releases: `ovnkube-master-*`). Legacy OpenShift SDN uses
`openshift-sdn` (`sdn-*`, `ovs-*`).

### Pod Networking / CNI Failures

Pods stuck `ContainerCreating` with events:

- `failed to create pod network sandbox ... plugin type="ovn-k8s-cni-overlay" ... failed to send CNI request`
- `failed to configure pod interface`, `failed to get pod annotation`, `timed out waiting for OVS port binding`
- `error while waiting for OVS ... to be ready`

Investigate: `ovnkube-node` logs on the pod's node, then `ovnkube-control-plane`/`ovnkube-master`
(central control), then `nbdb`/`sbdb` health. A single-node pattern = node-local OVN; cluster-wide =
control-plane/db.

### OVS vswitchd Stalls

OVS is the dataplane; a stall freezes **all** traffic on that node.

- Timeline source `OVSVswitchdLog`: `Unreasonably long NNNNms poll interval`
- `>500ms` = degraded; `>1000ms` = effectively frozen (no packets forwarded)
- **A classic root cause is CPU starvation** — OVS shares CPU with other processes. Correlate with
  `CPUMonitor` (>95%) and disk I/O ([resource-exhaustion.md](resource-exhaustion.md)); the
  stall's disruption fan-out is classified in [disruption.md](disruption.md).

```json
{ "source": "OVSVswitchdLog", "message": { "humanMessage": "Unreasonably long 9000ms poll interval" } }
```

Also present in node journals: grep `journal_logs/` for `Unreasonably long`.

---

## Service Connectivity

Pod-to-pod and pod-to-Service reachability.

- **No ready endpoints** — `connection refused` / `no endpoints available for service <ns>/<svc>`.
  The backing pods aren't Ready. Check the pods, then whether EndpointSlices list ready addresses
  (`oc get endpointslices -n <ns>`; audit logs show EndpointSlice churn during disruption).
- **Endpoint propagation lag** — after a readiness change, EndpointSlices update with delay;
  connections to the just-removed pod fail transiently. Correlate with `readyz=false` transitions
  and EndpointSlice modification audit events.
- **ClusterIP unreachable but pod IP works** — service proxying (OVN services / kube-proxy) issue,
  not the app. Check `ovnkube-node` logs for load-balancer/service programming errors.
- **Cross-node pod-to-pod fails, same-node works** — overlay/geneve tunnel or OVS problem on one
  node (see OVS stall) or an MTU mismatch on the overlay.
- **Hairpinning (pod reaching its own Service)** — a pod can reach other services but not its own
  ClusterIP (self-connection times out) while others reach it fine. OVN handles hairpin via
  masquerade; failures point to CNI/masquerade config. Test-only if the workload self-connects.

---

## Load Balancer and Ingress

- **Router pods** — `router-default-*` in `openshift-ingress`; operator in
  `openshift-ingress-operator`. Not-ready routers → `ingress` clusteroperator degraded and
  `*.apps.<cluster>` routes unreachable.
- **Cloud LB provisioning** — `router-default` Service (type `LoadBalancer`) stuck with no
  `EXTERNAL-IP`; events `EnsuringLoadBalancer` / `SyncLoadBalancerFailed`. Points at the cloud
  API/quota layer — the event message carries the cloud error; see [cloud-provider-errors.md](cloud-provider-errors.md).
- **LB health checks failing** — LB provisioned but marks backends unhealthy → intermittent
  ingress/API disruption. Check health-check port/path and router readiness; correlate with
  disruption on ingress-routed backends (image-registry, oauth, console) in [disruption.md](disruption.md).
- **Ingress/API DNS** — `api.<cluster>` / `*.apps.<cluster>` records must resolve; missing records
  present as `no such host` reaching the cluster. The ingress canary route is a quick health signal.

---

## Network Policy

`NetworkPolicy` / `AdminNetworkPolicy` (and OVN `EgressFirewall`, or SDN `EgressNetworkPolicy`) can
block **legitimate** traffic — either a test's own policy or a leftover from a prior test.

- **Signature**: connectivity works with no policy, then a specific test times out (never `connection
  refused`) after applying/for the duration of a policy; removing it restores traffic.
- **Check**: `oc get networkpolicy,adminnetworkpolicy -A`, `oc get egressfirewall -A` (OVN),
  `oc get egressnetworkpolicy -A` (SDN). A default-deny with a missing/incorrect allow rule (wrong
  podSelector/namespaceSelector/ports) silently drops traffic.
- **DNS caveat** — an egress policy that omits UDP/TCP `:53` to `openshift-dns` breaks name
  resolution for selected pods, surfacing as DNS failures rather than an obvious policy block.
- **Enforcement bug vs. config** — if the policy *should* allow the traffic but it's still dropped,
  suspect OVN policy programming: check `ovnkube-node`/`ovnkube-control-plane` logs for ACL errors.

---

## Common Failure Patterns — Quick Reference

| Pattern | Likely cause | Where to look |
|---------|--------------|---------------|
| Many pods `ImagePullBackOff`, one registry host | Mirror/registry down or untrusted | Events, pod logs, registry pod, ICSP/IDMS + CA |
| `manifest unknown` in disconnected job | Image not mirrored / mirroring race | Mirror step log, ICSP/IDMS coverage |
| `manifest unknown` in periodic after merge | Promotion timing | [ci-infrastructure-changes.md](ci-infrastructure-changes.md) |
| `x509: unknown authority` on pulls | Mirror CA not trusted | `image.config` additionalTrustedCA, proxy trustedCA |
| Intermittent pull/`i/o timeout`, self-heals | Proxy/SOCKS pod restart or mirror race | Proxy pod `restartCount`, timeline window |
| `no such host` cluster-wide | CoreDNS upstream cascade | `openshift-dns` CoreDNS logs, node resolv.conf |
| DNS gaps on one node | `dns-default` not scheduled there | `dns-default-*` per-node placement |
| Pods stuck `ContainerCreating`, `CNI request failed` | OVN pod networking | `ovnkube-node` → control-plane → nbdb/sbdb |
| All backends fail on one node | OVS stall (CPU starvation) | `OVSVswitchdLog`, `CPUMonitor`, journals |
| `no endpoints available` / `connection refused` to svc | No ready endpoints / propagation lag | Pods, EndpointSlices, audit logs |
| Router not ready, `*.apps` unreachable | Ingress operator / router pods | `openshift-ingress`, `co` ingress |
| LB `EXTERNAL-IP` pending | Cloud LB provisioning | Service events, [cloud-provider-errors.md](cloud-provider-errors.md) |
| Test times out only with a NetworkPolicy | Policy blocks legit traffic | `networkpolicy`/`egressfirewall`, `:53` allow |
