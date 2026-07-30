# Payload-analysis eval case index

Case directory names are intentionally opaque because the eval harness exposes
them to the model under test. Keep scenario descriptions here rather than in
directory names.

| Case | Scenario |
| --- | --- |
| `case-018` | Mixed true/false attribution: valid `oc#2279` recommendation alongside cross-tenant etcd evidence contamination falsely attributed to `hypershift#8871` |
| `case-019` | Disjoint ClusterOperator intervals counted as one continuous streak, producing false `api#2920` and `api#2923` revert recommendations |
| `case-020` | Compound GCP and Azure infrastructure causal chains falsely attributed to nearby `ovn-kubernetes#3298` and `cloud-provider-azure#164` changes |
