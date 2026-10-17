# crun and conmon: Non-Obvious Notes (Tribal Knowledge)

- **crun**: `https://github.com/containers/crun.git` (upstream only, no public downstream fork)
- **conmon**: `https://github.com/containers/conmon.git` (upstream only, no public downstream fork)
- **conmon-rs**: `https://github.com/containers/conmon-rs.git` (upstream only; the downstream fork `openshift/conmon-rs` is stale and not used)

"Upstream only" means development and CVE analysis happen against the upstream
repos and tags; OCP ships them as RPMs. `openshift/conmon-rs` exists but is
stale (`main` and `release-4.12` only), and there is no public
`openshift/conmon` or `openshift/crun`. This matches the pscomponent table in
[../shared/components.md](../shared/components.md).

For build commands, repo layout, and test targets: browse each repo directly (Makefile/Cargo.toml, README).

## Version History

- **crun** is the default OCI runtime for new installations starting with
  **OCP 4.18**. Clusters upgraded from 4.17 keep their existing runtime
  (usually runc) until it is changed through a `ContainerRuntimeConfig` CR.
  crun was available as an opt-in runtime in earlier releases.
- **conmon** (C) is the default container monitor on all OCP releases.
- **conmon-rs** is a Developer Preview alternative, enabled per-runtime via
  CRI-O config (`monitor_path` / runtime-handler settings); it uses gRPC
  (defined in `proto/conmon.proto`) instead of conmon's pipe-based IPC.

## Binary Paths on RHCOS

| Binary | Path |
|--------|------|
| crun | `/usr/bin/crun` |
| conmon (default) | `/usr/bin/conmon` |
| conmonrs (Dev Preview) | `/usr/bin/conmonrs` |

After replacing any of these binaries on a node, **restart CRI-O** (`sudo systemctl restart crio`) for it to pick up the change.

## Build Notes

- **crun**: Fully static builds with glibc are not recommended. Use musl libc for true static builds, or use dynamic linking matching RHCOS library versions. A containerized build (Fedora/UBI) is the easiest path for cross-compilation.
- **conmon-rs**: Use `cross` (cargo plugin) for cross-compilation rather than native cross-compilation toolchains. This avoids linker issues.
