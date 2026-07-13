If e2e infrastructure was modified (kind-common.sh, kind.yaml.j2,
e2e-kind.sh), read the patterns doc (find k8s-rebase-patterns.md
in the plugin directory) for the expected state of each component.
Verify each modified file matches what the patterns doc prescribes.

Common e2e components to check:
- MetalLB: version and FRR image consistent with patterns doc?
- KubeVirt: bumped to latest stable release? (not nightly)
- kubeadm: extraArgs format matches required kubeadm API version?
- KIND: version and feature gates match patterns doc?
- Test skips: any conditional skips added for version compatibility?

List each item checked and whether it passes. Report issues.

If the repo has no e2e infrastructure files, skip this check.

Rules: you are read-only — do not edit files. Cite file:line
for any issues.
