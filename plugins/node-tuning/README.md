# Node Tuning Operator Plugin (node-tuning)

## Overview
The `node-tuning` plugin automates common workflows for the OpenShift Node Tuning Operator. Use it when you need to:
- Generate reproducible Tuned manifests (`tuned.openshift.io/v1`) that capture sysctl settings, tuned daemon sections, and recommendation rules without hand-writing YAML.
- Audit live nodes or captured sosreports for kernel tuning gaps (CPU isolation, IRQ affinity, huge pages, net/sysctl state) and receive actionable remediation guidance.

## Commands
- `/node-tuning:generate-tuned-profile` – Generate a Tuned profile manifest from a natural language description of the desired parameters, sections, and targeting rules. The command also supports advanced workflows such as coordinating huge pages or kernel-rt boot parameters with a dedicated MachineConfigPool.
- `/node-tuning:analyze-node-tuning` – Inspect a live node or sosreport snapshot for tuning signals (isolcpus, IRQ affinity, huge pages, sysctls, networking counters) and surface recommended adjustments.

## Prerequisites
- Python 3.8 or newer must be available in the execution environment (the helper script is dependency-free beyond the standard library).
- Access to an OpenShift cluster if you plan to apply the generated manifest (`oc` CLI recommended for validation and application).
- Extracted sosreport directories when analyzing offline diagnostics (optional).

## Typical Workflow
1. Invoke `/node-tuning:generate-tuned-profile` with a profile name, summary, and any sysctl, include, or section options.
2. Review the rendered YAML returned by the command or written to `.work/node-tuning/<profile-name>/tuned.yaml` when using the helper script directly.
3. Validate the manifest with `oc apply --server-dry-run=client -f <path>` if desired.
4. Apply the manifest to the cluster or commit it to version control for automation.
5. Use the helper’s `--list-nodes` and `--label-node` options when you need to inspect or tag nodes before generating manifests.
6. For huge pages or other kernel boot parameters, coordinate with a dedicated MachineConfigPool as described in the advanced workflow inside `commands/generate-tuned-profile.md`.
7. Diagnose tuning gaps with `/node-tuning:analyze-node-tuning --format markdown` and translate the recommendations into updated Tuned profiles. When you cannot SSH to the node, supply `--node <name>` (plus optional `--kubeconfig`/`--oc-binary`) and the analyzer will, by default, enter the RHCOS `toolbox` (support-tools image) via `oc debug node/<name>`, run `sosreport -e openshift ... --all-logs --plugin-timeout=600`, download the archive, and analyze it offline. Override the container image with `--toolbox-image` (or `TOOLBOX_IMAGE`) and extend/tune the sosreport flags with `--sosreport-arg`. HTTP(S) proxy variables are forwarded automatically when set, but they are entirely optional. Add `--no-collect-sosreport` if you prefer the lighter `/proc` snapshot workflow.

## Related Files
- Command definition: `commands/generate-tuned-profile.md`
- Command definition: `commands/analyze-node-tuning.md`
- Helper implementation: `skills/scripts/generate_tuned_profile.py`
- Helper implementation: `skills/scripts/analyze_node_tuning.py`
- Skill documentation: `skills/scripts/SKILL.md`
