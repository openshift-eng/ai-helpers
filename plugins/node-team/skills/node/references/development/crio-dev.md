# CRI-O: Non-Obvious Notes (Tribal Knowledge)

- **Upstream**: `https://github.com/cri-o/cri-o.git`
- **Downstream (OpenShift)**: `https://github.com/openshift/cri-o.git`

For build commands, repo layout, dependencies, and test targets — browse the repo directly (Makefile, README, go.mod).

## Branch Mapping

CRI-O's minor version tracks the Kubernetes minor version shipped in the OCP
release. See [../shared/version-map.md](../shared/version-map.md) for the full
OCP-to-K8s/CRI-O version table and branch naming conventions.

Shortcut for OCP 4.x only: CRI-O minor = OCP minor + 13.

Downstream branches are `release-4.X` / `release-5.X`, upstream are `release-1.X`.

## OpenShift-Specific

- CRI-O **does not build natively on macOS** — CGO is required for seccomp and system libraries. Use a containerized build for cross-compilation.
- On RHCOS, CRI-O config is **managed by the MCO**. Do not edit `/etc/crio/crio.conf` directly — it will be overwritten. Use `ContainerRuntimeConfig` CRs instead.
- Drop-in files in `/etc/crio/crio.conf.d/` follow naming conventions: `00-default` (RHCOS base), `01-ctrcfg-*` (from ContainerRuntimeConfig CR), `10-*` (MCO overrides).
- Registry mirrors on OpenShift: configure via `ImageContentSourcePolicy` or `ImageDigestMirrorSet` CRs, not by editing `/etc/containers/registries.conf`.
- CRI-O exposes Prometheus metrics at `localhost:9537/metrics`.
