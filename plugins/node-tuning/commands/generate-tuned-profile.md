---
description: Generate a Tuned (tuned.openshift.io/v1) profile manifest for the Node Tuning Operator
argument-hint: "[profile-name] [--summary ...] [--sysctl ...] [options]"
---

## Name
node-tuning:generate-tuned-profile

## Synopsis
```
/node-tuning:generate-tuned-profile [profile-name] [--summary TEXT] [--include VALUE ...] [--sysctl KEY=VALUE ...] [--match-label KEY[=VALUE] ...] [options]
```

## Description
The `node-tuning:generate-tuned-profile` command streamlines creation of `tuned.openshift.io/v1` manifests for the OpenShift Node Tuning Operator. It captures the desired Tuned profile metadata, tuned daemon configuration blocks (e.g. `[sysctl]`, `[variables]`, `[bootloader]`), and recommendation rules, then invokes the helper script at `plugins/node-tuning/skills/scripts/generate_tuned_profile.py` to render a ready-to-apply YAML file.

Use this command whenever you need to:
- Bootstrap a new Tuned custom profile targeting selected nodes or machine config pools
- Generate manifests that can be version-controlled alongside other automation
- Iterate on sysctl, bootloader, or service parameters without hand-editing multi-line YAML

The generated manifest follows the structure expected by the cluster Node Tuning Operator:
```
apiVersion: tuned.openshift.io/v1
kind: Tuned
metadata:
  name: <profile-name>
  namespace: openshift-cluster-node-tuning-operator
spec:
  profile:
  - data: |
      [main]
      summary=...
      include=...
      ...
    name: <profile-name>
  recommend:
  - machineConfigLabels: {...}
    match:
    - label: ...
      value: ...
    priority: <priority>
    profile: <profile-name>
```

## Implementation
1. **Collect inputs**
   - Confirm Python 3.8+ is available (`python3 --version`).
   - Gather the Tuned profile name, summary, optional include chain, sysctl values, variables, and any additional section lines (e.g. `[bootloader]`, `[service]`).
   - Determine targeting rules: either `--match-label` entries (node labels) or `--machine-config-label` entries (MachineConfigPool selectors).
   - Decide whether an accompanying MachineConfigPool (MCP) workflow is required for kernel boot arguments (see **Advanced Workflow** below).
   - Use the helper's `--list-nodes` and `--label-node` flags when you need to inspect or label nodes prior to manifest generation.

2. **Build execution workspace**
   - Create or reuse `.work/node-tuning/<profile-name>/`.
   - Decide on the manifest filename (default `tuned.yaml` inside the workspace) or provide `--output` to override.

3. **Invoke the generator script**
   - Run the helper with the collected switches:
     ```bash
     python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py \
       --profile-name "$PROFILE_NAME" \
       --summary "$SUMMARY" \
       --include openshift-node \
       --sysctl net.core.netdev_max_backlog=16384 \
       --variable isolated_cores=1 \
       --section bootloader:cmdline_ocp_realtime=+systemd.cpu_affinity=${not_isolated_cores_expanded} \
       --machine-config-label machineconfiguration.openshift.io/role=worker-rt \
       --match-label tuned.openshift.io/elasticsearch="" \
       --priority 25 \
       --output ".work/node-tuning/$PROFILE_NAME/tuned.yaml"
     ```
   - Use `--dry-run` to print the manifest to stdout before writing, if desired.

4. **Validate output**
   - Inspect the generated YAML (`yq e . .work/node-tuning/$PROFILE_NAME/tuned.yaml` or open in an editor).
   - Optionally run `oc apply --server-dry-run=client -f .work/node-tuning/$PROFILE_NAME/tuned.yaml` to confirm schema compatibility.

5. **Apply or distribute**
   - Apply to a cluster with `oc apply -f .work/node-tuning/$PROFILE_NAME/tuned.yaml`.
   - Commit the manifest to Git or attach to automated pipelines as needed.

## Advanced Workflow: Huge Pages with a Dedicated MachineConfigPool
Use this workflow when enabling huge pages or other kernel boot parameters that require coordinating the Node Tuning Operator with the Machine Config Operator while minimizing reboots.

1. **Label target nodes**
   - Preview candidates: `python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py --list-nodes --node-selector "node-role.kubernetes.io/worker" --skip-manifest`.
   - Label workers with the helper (repeat per node):
     ```bash
     python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py \
       --label-node ip-10-0-1-23.ec2.internal:node-role.kubernetes.io/worker-hp= \
       --overwrite-labels \
       --skip-manifest
     ```
   - Alternatively run `oc label node <node> node-role.kubernetes.io/worker-hp=` directly if you prefer the CLI.

2. **Generate the Tuned manifest**
   - Include bootloader arguments via the helper script:
     ```bash
     python3 plugins/node-tuning/skills/scripts/generate_tuned_profile.py \
       --profile-name "openshift-node-hugepages" \
       --summary "Boot time configuration for hugepages" \
       --include openshift-node \
       --section bootloader:cmdline_openshift_node_hugepages="hugepagesz=2M hugepages=50" \
       --machine-config-label machineconfiguration.openshift.io/role=worker-hp \
       --priority 30 \
       --output .work/node-tuning/openshift-node-hugepages/hugepages-tuned-boottime.yaml
     ```
   - Review the `[bootloader]` section to ensure the kernel arguments match the desired configuration (e.g. `kernel-rt`, huge pages, additional sysctls).

3. **Author the MachineConfigPool manifest**
   - Create `.work/node-tuning/openshift-node-hugepages/hugepages-mcp.yaml` with:
     ```yaml
     apiVersion: machineconfiguration.openshift.io/v1
     kind: MachineConfigPool
     metadata:
       name: worker-hp
       labels:
         worker-hp: ""
     spec:
       machineConfigSelector:
         matchExpressions:
           - key: machineconfiguration.openshift.io/role
             operator: In
             values:
               - worker
               - worker-hp
       nodeSelector:
         matchLabels:
           node-role.kubernetes.io/worker-hp: ""
     ```

4. **Apply manifests (optional `--dry-run`)**
   - `oc apply -f .work/node-tuning/openshift-node-hugepages/hugepages-tuned-boottime.yaml`
   - `oc apply -f .work/node-tuning/openshift-node-hugepages/hugepages-mcp.yaml`
   - Watch progress: `oc get mcp worker-hp -w`

5. **Verify results**
   - Confirm huge page allocation after the reboot: `oc get node <node> -o jsonpath="{.status.allocatable.hugepages-2Mi}"`
   - Inspect kernel arguments: `oc debug node/<node> -q -- chroot /host cat /proc/cmdline`

## Return Value
- **Success**: Path to the generated manifest and the profile name are returned to the caller.
- **Failure**: Script exits non-zero with stderr diagnostics (e.g. invalid `KEY=VALUE` pair, missing labels, unwritable output path).

## Examples

1. **Realtime worker profile targeting worker-rt MCP**
   ```
   /node-tuning:generate-tuned-profile openshift-realtime \
     --summary "Custom realtime tuned profile" \
     --include openshift-node --include realtime \
     --variable isolated_cores=1 \
     --section bootloader:cmdline_ocp_realtime=+systemd.cpu_affinity=${not_isolated_cores_expanded} \
     --machine-config-label machineconfiguration.openshift.io/role=worker-rt \
     --output .work/node-tuning/openshift-realtime/realtime.yaml
   ```

2. **Sysctl-only profile matched by node label**
   ```
   /node-tuning:generate-tuned-profile custom-net-tuned \
     --summary "Increase conntrack table" \
     --sysctl net.netfilter.nf_conntrack_max=262144 \
     --match-label tuned.openshift.io/custom-net \
     --priority 18
   ```

3. **Preview manifest without writing to disk**
   ```
   /node-tuning:generate-tuned-profile pidmax-test \
     --summary "Raise pid max" \
     --sysctl kernel.pid_max=131072 \
     --match-label tuned.openshift.io/pidmax="" \
     --dry-run
   ```

## Arguments:
- **$1** (`profile-name`): Name for the Tuned profile and manifest resource.
- **--summary**: Required summary string placed in the `[main]` section.
- **--include**: Optional include chain entries (multiple allowed).
- **--main-option**: Additional `[main]` section key/value pairs (`KEY=VALUE`).
- **--variable**: Add entries to the `[variables]` section (`KEY=VALUE`).
- **--sysctl**: Add sysctl settings to the `[sysctl]` section (`KEY=VALUE`).
- **--section**: Add lines to arbitrary sections using `SECTION:KEY=VALUE`.
- **--machine-config-label**: MachineConfigPool selector labels (`key=value`) applied under `machineConfigLabels`.
- **--match-label**: Node selector labels for the `recommend[].match[]` block; omit `=value` to match existence only.
- **--priority**: Recommendation priority (integer, default 20).
- **--namespace**: Override the manifest namespace (default `openshift-cluster-node-tuning-operator`).
- **--output**: Destination file path; defaults to `<profile-name>.yaml` in the current directory.
- **--dry-run**: Print manifest to stdout instead of writing to a file.
- **--skip-manifest**: Skip manifest generation; useful when only listing or labeling nodes.
- **--list-nodes**: List nodes via `oc get nodes` (works with `--node-selector`).
- **--node-selector**: Label selector applied when `--list-nodes` is used.
- **--label-node**: Apply labels to nodes using `NODE:KEY[=VALUE]` notation; repeatable.
- **--overwrite-labels**: Allow overwriting existing labels when labeling nodes.
- **--oc-binary**: Path to the `oc` executable (defaults to `$OC_BIN` or `oc`).

