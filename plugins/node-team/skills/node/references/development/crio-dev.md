# CRI-O: Non-Obvious Notes (Tribal Knowledge)

- **Upstream**: `https://github.com/cri-o/cri-o.git`
- **Downstream (OpenShift)**: `https://github.com/openshift/cri-o.git`

For build commands, repo layout, dependencies, and test targets — browse the repo directly (Makefile, README, go.mod).

## Branch Mapping

OCP 4.X uses CRI-O 1.(X-4+17).x. The formula: **CRI-O minor = OCP minor + 13**.

| OCP | CRI-O |
|-----|-------|
| 4.18 | 1.31.x |
| 4.17 | 1.30.x |
| 4.16 | 1.29.x |

Downstream branches are `release-4.X`, upstream are `release-1.X`.

## OpenShift-Specific

- CRI-O **does not build natively on macOS** — CGO is required for seccomp and system libraries. Use a containerized build for cross-compilation.
- On RHCOS, CRI-O config is **managed by the MCO**. Do not edit `/etc/crio/crio.conf` directly — it will be overwritten. Use `ContainerRuntimeConfig` CRs instead.
- Drop-in files in `/etc/crio/crio.conf.d/` follow naming conventions: `00-default` (RHCOS base), `01-ctrcfg-*` (from ContainerRuntimeConfig CR), `10-*` (MCO overrides).
- Registry mirrors on OpenShift: configure via `ImageContentSourcePolicy` or `ImageDigestMirrorSet` CRs, not by editing `/etc/containers/registries.conf`.
- CRI-O exposes Prometheus metrics at `localhost:9537/metrics`.
