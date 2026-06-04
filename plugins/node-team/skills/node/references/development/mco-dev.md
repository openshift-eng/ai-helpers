# MCO (Machine Config Operator): Non-Obvious Notes (Tribal Knowledge)

- **Repo**: `https://github.com/openshift/machine-config-operator.git` (no upstream — MCO is OpenShift-only)

For build commands, repo layout, CRD types, and test targets — browse the repo directly (Makefile, README, go.mod, pkg/apis/).

## Rendering Pipeline

MachineConfigs are sorted **lexicographically by name** before merging. This is why naming conventions matter (e.g., `00-worker`, `01-worker-custom`). Later configs override earlier ones for files (by path) and systemd units (by name). Kernel arguments and extensions are accumulated (union).

## MCD Reboot Rules

The MCD **does** trigger a reboot when:
- Files in `/etc` or `/usr` change
- Systemd units are added/removed/modified
- Kernel arguments or OS extensions change
- The OS image changes

The MCD **does not** reboot when:
- Only SSH keys are updated
- Only node annotations change

## On-Cluster Layering (OCP 4.13+)

On-cluster layering builds custom OS images using `MachineOSConfig` and `MachineOSBuild` resources. The MCD applies layered images via `rpm-ostree rebase` or `bootc switch`.

## Other Notes

- MCP `maxUnavailable` defaults to 1 — nodes update one at a time.
- Machine Config Server (MCS) serves Ignition configs on port **22623**.
