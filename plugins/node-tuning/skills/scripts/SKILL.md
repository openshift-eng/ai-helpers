---
name: Node Tuning Helper Scripts
description: Generate tuned manifests and evaluate node tuning snapshots
---

# Node Tuning Helper Scripts

Detailed instructions for invoking the helper utilities that back `/node-tuning` commands:
- `generate_tuned_profile.py` renders Tuned manifests (`tuned.openshift.io/v1`).
- `analyze_node_tuning.py` inspects live nodes or sosreports for tuning gaps.

## When to Use These Scripts
- Translate structured command inputs into Tuned manifests for the Node Tuning Operator.
- Iterate on generated YAML outside the assistant or integrate the generator into automation.
- Analyze CPU isolation, IRQ affinity, huge pages, sysctl values, and networking counters from live clusters or archived sosreports.

## Prerequisites
- Python 3.8 or newer (`python3 --version`).
- Repository checkout so the scripts under `plugins/node-tuning/skills/scripts/` are accessible.
- Optional: `oc` CLI when validating or applying manifests.
- Optional: Extracted sosreport directory when running the analysis script offline.
- Optional (remote analysis): `oc` CLI access plus a valid `KUBECONFIG` when capturing `/proc`/`/sys` or sosreport via `oc debug node/<name>`. The sosreport workflow pulls the `registry.redhat.io/rhel9/support-tools` image (override with `--toolbox-image` or `TOOLBOX_IMAGE`) and requires registry access. HTTP(S) proxy env vars from the host are forwarded automatically when present, but using a proxy is optional.

---

## Script: `generate_tuned_profile.py`

### Implementation Steps
1. **Collect Inputs**
   - `--profile-name`: Tuned resource name.
   - `--summary`: `[main]` section summary.
   - Repeatable options: `--include`, `--main-option`, `--variable`, `--sysctl`, `--section` (`SECTION:KEY=VALUE`).
   - Target selectors: `--machine-config-label key=value`, `--match-label key[=value]`.
   - Optional: `--priority` (default 20), `--namespace`, `--output`, `--dry-run`.
   - Use `--list-nodes`/`--node-selector` to inspect nodes and `--label-node NODE:KEY[=VALUE]` (plus `--overwrite-labels`) to tag machines.

2. **Inspect or Label Nodes (optional)**
   ```bash
   # List all worker nodes
   python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py --list-nodes --node-selector "node-role.kubernetes.io/worker" --skip-manifest

   # Label a specific node for the worker-hp pool
   python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py \
     --label-node ip-10-0-1-23.ec2.internal:node-role.kubernetes.io/worker-hp= \
     --overwrite-labels \
     --skip-manifest
   ```

3. **Render the Manifest**
   ```bash
   python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py \
     --profile-name "$PROFILE" \
     --summary "$SUMMARY" \
     --sysctl net.core.netdev_max_backlog=16384 \
     --match-label tuned.openshift.io/custom-net \
     --output .work/node-tuning/$PROFILE/tuned.yaml
   ```
   - Omit `--output` to write `<profile-name>.yaml` in the current directory.
   - Add `--dry-run` to print the manifest to stdout.

4. **Review Output**
   - Inspect the generated YAML for accuracy.
   - Optionally format with `yq` or open in an editor for readability.

5. **Validate and Apply**
   - Dry-run: `oc apply --server-dry-run=client -f <manifest>`.
   - Apply: `oc apply -f <manifest>`.

### Error Handling
- Missing required options raise `ValueError` with descriptive messages.
- The script exits non-zero when no target selectors (`--machine-config-label` or `--match-label`) are supplied.
- Invalid key/value or section inputs identify the failing argument explicitly.

### Examples
```bash
python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py \
  --profile-name realtime-worker \
  --summary "Realtime tuned profile" \
  --include openshift-node --include realtime \
  --variable isolated_cores=1 \
  --section bootloader:cmdline_ocp_realtime=+systemd.cpu_affinity=${not_isolated_cores_expanded} \
  --machine-config-label machineconfiguration.openshift.io/role=worker-rt \
  --priority 25 \
  --output .work/node-tuning/realtime-worker/tuned.yaml
```
```bash
python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py \
  --profile-name openshift-node-hugepages \
  --summary "Boot time configuration for hugepages" \
  --include openshift-node \
  --section bootloader:cmdline_openshift_node_hugepages="hugepagesz=2M hugepages=50" \
  --machine-config-label machineconfiguration.openshift.io/role=worker-hp \
  --priority 30 \
  --output .work/node-tuning/openshift-node-hugepages/hugepages-tuned-boottime.yaml
```

---

## Script: `analyze_node_tuning.py`

### Purpose
Inspect either a live node (`/proc`, `/sys`) or an extracted sosreport snapshot for tuning signals (CPU isolation, IRQ affinity, huge pages, sysctl state, networking counters) and emit actionable recommendations.

### Usage Patterns
- **Live node analysis**
  ```bash
  python3 plugins/node-tuning/skills/scripts/analyze_node_tuning.py --format markdown
  ```
- **Remote analysis via oc debug**
  ```bash
  python3 plugins/node-tuning/skills/scripts/analyze_node_tuning.py \
    --node worker-rt-0 \
    --kubeconfig ~/.kube/prod \
    --format markdown
  ```
- **Collect sosreport via oc debug and analyze locally**
  ```bash
  python3 plugins/node-tuning/skills/scripts/analyze_node_tuning.py \
    --node worker-rt-0 \
    --toolbox-image registry.example.com/support-tools:latest \
    --sosreport-arg "--case-id=01234567" \
    --sosreport-output .work/node-tuning/sosreports \
    --format json
  ```
- **Offline sosreport analysis**
  ```bash
  python3 plugins/node-tuning/skills/scripts/analyze_node_tuning.py \
    --sosreport /path/to/sosreport-2025-10-20
  ```
- **Automation-friendly JSON**
  ```bash
  python3 plugins/node-tuning/skills/scripts/analyze_node_tuning.py \
    --sosreport /path/to/sosreport \
    --format json --output .work/node-tuning/node-analysis.json
  ```

### Implementation Steps
1. **Select data source**
   - Provide `--node <name>` (with optional `--kubeconfig` / `--oc-binary`). By default the helper runs `sosreport` remotely from inside the RHCOS toolbox container (`registry.redhat.io/rhel9/support-tools`). Override the image with `--toolbox-image`, extend the sosreport command with `--sosreport-arg`, or disable the curated OpenShift flags via `--skip-default-sosreport-flags`. Pass `--no-collect-sosreport` to fall back to the direct `/proc` snapshot mode.
   - Provide `--sosreport <dir>` for archived diagnostics; detection finds embedded `proc/` and `sys/`.
   - Omit both switches to query the live filesystem (defaults to `/proc` and `/sys`).
   - Override paths with `--proc-root` or `--sys-root` when the layout differs.
2. **Run analysis**
   - The script parses `cpuinfo`, kernel cmdline parameters (`isolcpus`, `nohz_full`, `tuned.non_isolcpus`), default IRQ affinities, huge page counters, sysctl values (net, vm, kernel), transparent hugepage settings, `netstat`/`sockstat` counters, and `ps` snapshots (when available in sosreport).
3. **Review the report**
   - Markdown output groups findings by section (System Overview, CPU & Isolation, Huge Pages, Sysctl Highlights, Network Signals, IRQ Affinity, Process Snapshot) and lists recommendations.
   - JSON output contains the same information in structured form for pipelines or dashboards.
4. **Act on recommendations**
   - Apply Tuned profiles, MachineConfig updates, or manual sysctl/irqbalance adjustments.
   - Feed actionable items back into `/node-tuning:generate-tuned-profile` to codify desired state.

### Error Handling
- Missing `proc/` or `sys/` directories trigger descriptive errors.
- Unreadable files are skipped gracefully and noted in observations where relevant.
- Non-numeric sysctl values are flagged for manual investigation.

### Example Output (Markdown excerpt)
```
# Node Tuning Analysis

## System Overview
- Hostname: worker-rt-1
- Kernel: 4.18.0-477.el8
- NUMA nodes: 2
- Kernel cmdline: `BOOT_IMAGE=... isolcpus=2-15 tuned.non_isolcpus=0-1`

## CPU & Isolation
- Logical CPUs: 32
- Physical cores: 16 across 2 socket(s)
- SMT detected: yes
- Isolated CPUs: 2-15
...

## Recommended Actions
- Configure net.core.netdev_max_backlog (>=32768) to accommodate bursty NIC traffic.
- Transparent Hugepages are not disabled (`[never]` not selected). Consider setting to `never` for latency-sensitive workloads.
- 4 IRQs overlap isolated CPUs. Relocate interrupt affinities using tuned profiles or irqbalance.
```

### Follow-up Automation Ideas
- Persist JSON results in `.work/node-tuning/<host>/analysis.json` for historical tracing.
- Gate upgrades by comparing recommendations across nodes.
- Integrate with CI jobs that validate cluster tuning post-change.
