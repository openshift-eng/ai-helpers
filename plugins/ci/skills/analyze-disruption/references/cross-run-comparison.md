# Cross-Run Comparison (Step 6)

When multiple job run URLs are provided:

## 6.1: Align Disruption Events

For each backend that shows disruption across multiple runs:

- Compare which backends are disrupted in each run
- Identify backends that are **consistently disrupted** across all runs (systemic issue)
- Identify backends that are **disrupted in only some runs** (intermittent or infrastructure-specific)

## 6.2: Pattern Detection

Look for common patterns:

- **Same backends disrupted at similar relative times** → likely a product bug or test sequencing issue
- **Same backends but different times** → likely infrastructure-sensitive but product-related
- **Different backends across runs** → likely infrastructure/environment-specific
- **ci-cluster-network-liveness disrupted in some runs** → those runs have unreliable disruption
  data. Still include them in the analysis, but note the caveat prominently (in the Runs Analyzed
  table and wherever citing evidence from that run). Do not exclude unreliable runs entirely —
  they can still confirm patterns seen in reliable runs, and their non-disruption signals (etcd
  logs, CPU, alerts) remain valid. The key is to avoid drawing conclusions *solely* from an
  unreliable run's disruption counts.
- **Cache backends consistently disrupted** → systemic etcd or networking issue
- **Non-cache backends consistently disrupted** → component-specific problem

## 6.3: Clean Comparison Analysis (Same-Job A/B)

When the auto-selection included a clean comparison run (0s disruption from the same job as a
disrupted run), perform a same-job A/B comparison to filter out red herrings:

1. **Identify the pair**: The clean run shares a job name with one or more disrupted runs.
   Compare their concurrent events side by side.

2. **Signals present in both**: Any concurrent events that appear in *both* the clean and
   disrupted runs are **not the cause** of disruption — they are normal job behavior. Examples:
   - E2E tests that run during disruption windows but also run in clean runs
   - OVS log entries that appear at similar relative times in both runs
   - Operator rollouts that happen in both upgrade phases

3. **Signals unique to disrupted runs**: Concurrent events that appear *only* in disrupted runs
   (and not in the clean comparison) are the strongest root cause candidates. Highlight these
   in the Cross-Run Comparison section.

4. **Infrastructure differences**: Note any differences in the cluster setup (node types, regions,
   etc.) between the clean and disrupted runs if visible in the artifacts.

This comparison is especially valuable for filtering out E2E test correlation noise — if the same
tests run during disruption windows and during clean runs, they are not causing the disruption.

## 6.4: Correlate etcd and CPU Findings

- Are etcd leader changes present in all runs showing cache-backend disruption?
- Do runs with mass disruption consistently show high CPU or node pressure?
- Are audit log gaps consistent across runs?
