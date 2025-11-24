---
description: Analyze kernel/sysctl tuning from a live node or sosreport snapshot and propose NTO recommendations
argument-hint: "[--sosreport PATH] [--format json|markdown] [--max-irq-samples N]"
---

## Name
node-tuning:analyze-node-tuning

## Synopsis
```text
/node-tuning:analyze-node-tuning [--sosreport PATH] [--collect-sosreport|--no-collect-sosreport] [--sosreport-output PATH] [--node NODE] [--kubeconfig PATH] [--oc-binary PATH] [--format json|markdown] [--max-irq-samples N] [--keep-snapshot]
```

## Description
The `node-tuning:analyze-node-tuning` command inspects kernel tuning signals gathered from either a live OpenShift node (`/proc`, `/sys`), an `oc debug node/<name>` snapshot captured via KUBECONFIG, or an extracted sosreport directory. It parses CPU isolation parameters, IRQ affinity, huge page allocation, critical sysctl settings, and networking counters before compiling actionable recommendations that can be enforced through Tuned profiles or MachineConfig updates.

Use this command when you need to:
- Audit a node for tuning regressions after upgrades or configuration changes.
- Translate findings into remediation steps for the Node Tuning Operator.
- Produce JSON or Markdown reports suitable for incident response, CI gates, or documentation.

## Implementation
1. **Establish data source**
   - Live (local) analysis: the helper script defaults to `/proc` and `/sys`. Ensure the command runs on the target node (or within an SSH session / debug pod).
   - Remote analysis via `oc debug`: provide `--node <name>` (plus optional `--kubeconfig` and `--oc-binary`). The helper defaults to entering the RHCOS `toolbox` (backed by the `registry.redhat.io/rhel9/support-tools` image) via `oc debug node/<name>`, running `sosreport --batch --quiet -e openshift -e openshift_ovn -e openvswitch -e podman -e crio -k crio.all=on -k crio.logs=on -k podman.all=on -k podman.logs=on -k networking.ethtool-namespaces=off --all-logs --plugin-timeout=600`, streaming the archive locally (respecting `--sosreport-output` when set), and analyzing the extracted data. Use `--toolbox-image` (or `TOOLBOX_IMAGE`) to point at a mirrored support-tools image, `--sosreport-arg` to append extra flags (repeat per flag), or `--skip-default-sosreport-flags` to take full control. Host HTTP(S) proxy variables are forwarded when present but entirely optional. Add `--no-collect-sosreport` to skip sosreport generation entirely, and `--keep-snapshot` if you want to retain the downloaded files.
   - Offline analysis: provide `--sosreport /path/to/sosreport-<timestamp>` pointing to an extracted sosreport directory; the script auto-discovers embedded `proc/` and `sys/` trees.
   - Override non-standard layouts with `--proc-root` or `--sys-root` as needed.

2. **Prepare workspace**
   - Create `.work/node-tuning/<hostname>/` to store generated reports (remote snapshots and sosreport captures may reuse this path or default to a temporary directory).
   - Decide whether you want Markdown (human-readable) or JSON (automation-ready) output. Set `--format json` and `--output` for machine consumption.

3. **Invoke the analysis helper**
   ```bash
   python3 plugins/node-tuning/skills/scripts/analyze_node_tuning.py \
     --sosreport "$SOS_DIR" \
     --format markdown \
     --max-irq-samples 10 \
     --output ".work/node-tuning/${HOSTNAME}/analysis.md"
   ```
   - Omit `--sosreport` and `--node` to evaluate the local environment.
   - Lower `--max-irq-samples` to cap the number of IRQ affinity overlaps listed in the report.

4. **Interpret results**
   - **System Overview**: Validates kernel release, NUMA nodes, and kernel cmdline flags (isolcpus, nohz_full, tuned.non_isolcpus).
   - **CPU & Isolation**: Highlights SMT detection, isolated CPU masks, and mismatches between default IRQ affinity and isolated cores.
   - **Huge Pages**: Summarizes global and per-NUMA huge page pools, reserved counts, and sysctl targets.
   - **Sysctl Highlights**: Surfaces values for tuning-critical keys (e.g., `net.core.netdev_max_backlog`, `vm.swappiness`, THP state) with recommendations when thresholds are missed.
   - **Network Signals**: Examines `TcpExt` counters and sockstat data for backlog drops, syncookie failures, or orphaned sockets.
   - **IRQ Affinity**: Lists IRQs overlapping isolated CPUs so you can adjust tuned profiles or irqbalance policies.
   - **Process Snapshot**: When available in sosreport snapshots, shows top CPU consumers and flags irqbalance presence.

5. **Apply remediation**
   - Feed the recommendations into `/node-tuning:generate-tuned-profile` or MachineConfig workflows.
   - For immediate live tuning, adjust sysctls or interrupt affinities manually, then rerun the analysis to confirm remediation.

## Return Value
- **Success**: Returns a Markdown or JSON report summarizing findings and recommended actions.
- **Failure**: Reports descriptive errors (e.g., missing `proc/` or `sys/` directories, unreadable sosreport path) and exits non-zero.

## Examples

1. **Analyze a live node and print Markdown**
   ```text
   /node-tuning:analyze-node-tuning --format markdown
   ```

2. **Capture `/proc` and `/sys` via `oc debug` (sosreport by default) and analyze remotely**
   ```text
   /node-tuning:analyze-node-tuning \
     --node worker-rt-0 \
     --kubeconfig ~/.kube/prod \
     --format markdown
   ```

3. **Collect a sosreport via `oc debug` (custom image + flags) and analyze it locally**
   ```text
   /node-tuning:analyze-node-tuning \
     --node worker-rt-0 \
     --toolbox-image registry.example.com/support-tools:latest \
     --sosreport-arg "--case-id=01234567" \
     --sosreport-output .work/node-tuning/sosreports \
     --format json
   ```

4. **Inspect an extracted sosreport and save JSON to disk**
   ```text
   /node-tuning:analyze-node-tuning \
     --sosreport ~/Downloads/sosreport-worker-001 \
     --format json \
     --max-irq-samples 20
   ```

5. **Limit the recommendation set to a handful of IRQ overlaps**
   ```text
   /node-tuning:analyze-node-tuning --sosreport /tmp/sosreport --max-irq-samples 5
   ```

## Arguments:
- **--sosreport**: Path to an extracted sosreport directory to analyze instead of the live filesystem.
- **--format**: Output format (`markdown` default or `json` for structured data).
- **--output**: Optional file path where the helper writes the report.
- **--max-irq-samples**: Maximum number of IRQ affinity overlaps to include in the output (default 15).
- **--proc-root**: Override path to the procfs tree when auto-detection is insufficient.
- **--sys-root**: Override path to the sysfs tree when auto-detection is insufficient.
- **--node**: OpenShift node name to analyze via `oc debug node/<name>` when direct access is not possible.
- **--kubeconfig**: Path to the kubeconfig file used for `oc debug`; relies on the current oc context when omitted.
- **--oc-binary**: Path to the `oc` binary (defaults to `$OC_BIN` or `oc`).
- **--keep-snapshot**: Preserve the temporary directory produced from `oc debug` (snapshots or sosreports) for later inspection.
- **--collect-sosreport**: Trigger `sosreport` via `oc debug node/<name>`, download the archive, and analyze the extracted contents automatically (default behavior whenever `--node` is supplied and no other source is chosen).
- **--no-collect-sosreport**: Disable the default sosreport workflow when `--node` is supplied, falling back to the raw `/proc`/`/sys` snapshot.
- **--sosreport-output**: Directory where downloaded sosreport archives and their extraction should be placed (defaults to a temporary directory).
- **--toolbox-image**: Override the container image that toolbox pulls when collecting sosreport (defaults to `registry.redhat.io/rhel9/support-tools:latest` or `TOOLBOX_IMAGE` env).
- **--sosreport-arg**: Append an additional argument to the sosreport command (repeatable).
- **--skip-default-sosreport-flags**: Do not include the default OpenShift-focused sosreport plugins/collectors; only use values supplied via `--sosreport-arg`.

