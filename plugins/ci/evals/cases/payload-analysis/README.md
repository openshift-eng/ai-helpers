# Payload-analysis eval case index

Case directory names are intentionally opaque because the eval harness exposes
them to the model under test. Keep scenario descriptions here rather than in
directory names.

| Case | Scenario |
| --- | --- |
| `case-001` | OCP 4.22 nightly with both a CI-configuration regression and a product regression |
| `case-002` | OCP 5.0 nightly whose blocking failures are all new |
| `case-003` | OCP 5.0 CI regression requiring a cluster-network-operator NetworkPolicy revert |
| `case-004` | OCP 4.22 payload with two independent valid revert candidates |
| `case-005` | OCP 4.22 CI cloud-credential-operator revert |
| `case-006` | OCP 4.22 CI HyperShift revert |
| `case-007` | OCP 4.22 OLM revert |
| `case-008` | OCP 5.0 nightly cluster-monitoring-operator monitoring regression |
| `case-009` | OCP 5.0 CI HyperShift builder false-positive trap |
| `case-010` | OCP 4.18 rejected payload with multiple independent failures |
| `case-011` | OCP 5.0 CI infrastructure-only rejection with no valid payload candidate |
| `case-012` | OCP 4.20 rejected payload with a consecutive failure streak |
| `case-013` | OCP 4.20 accepted payload that still contains failures |
| `case-014` | OCP 5.0 nightly failure caused by a step-registry infrastructure change |
| `case-018` | Mixed true/false attribution: valid `oc#2279` recommendation alongside cross-tenant etcd evidence contamination falsely attributed to `hypershift#8871` |
| `case-019` | Disjoint ClusterOperator intervals counted as one continuous streak, producing false `api#2920` and `api#2923` revert recommendations |
| `case-020` | Compound GCP and Azure infrastructure causal chains falsely attributed to nearby `ovn-kubernetes#3298` and `cloud-provider-azure#164` changes |

`case-015` through `case-017` are reserved by the eval additions in
[PR #626](https://github.com/openshift-eng/ai-helpers/pull/626). That PR should
use the same opaque directory naming before merge.
