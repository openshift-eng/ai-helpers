# CRI-O: Non-Obvious Notes (Tribal Knowledge)

- **Upstream**: `https://github.com/cri-o/cri-o.git`
- **Downstream (OpenShift)**: `https://github.com/openshift/cri-o.git`

For build commands, repo layout, dependencies, and test targets — browse the repo directly (Makefile, README, go.mod).

## Branch Mapping

**CRI-O's minor version tracks the Kubernetes minor version shipped in the OCP
release.** This rule holds across OCP major versions (including 5.x) — find
the Kubernetes version via `oc version` or the OCP release notes.

| OCP | Kubernetes | CRI-O |
|-----|------------|-------|
| 5.0 | 1.36 | 1.36.x |
| 4.23 | 1.36 | 1.36.x (shares the 5.0 base) |
| 4.18 | 1.31 | 1.31.x |
| 4.17 | 1.30 | 1.30.x |
| 4.16 | 1.29 | 1.29.x |

Shortcut for OCP 4.x only: CRI-O minor = OCP minor + 13.

Downstream branches are `release-4.X` / `release-5.X`, upstream are `release-1.X`.

## OpenShift-Specific

- CRI-O **does not build natively on macOS** — CGO is required for seccomp and system libraries. Use a containerized build for cross-compilation.
- On RHCOS, CRI-O config is **managed by the MCO**. Do not edit `/etc/crio/crio.conf` directly — it will be overwritten. Use `ContainerRuntimeConfig` CRs instead.
- Drop-in files in `/etc/crio/crio.conf.d/` follow naming conventions: `00-default` (RHCOS base), `01-ctrcfg-*` (from ContainerRuntimeConfig CR), `10-*` (MCO overrides).
- Registry mirrors on OpenShift: configure via `ImageContentSourcePolicy` or `ImageDigestMirrorSet` CRs, not by editing `/etc/containers/registries.conf`.
- CRI-O exposes Prometheus metrics at `localhost:9537/metrics`.
