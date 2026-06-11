# crun and conmon: Non-Obvious Notes (Tribal Knowledge)

- **crun**: `https://github.com/containers/crun.git` (upstream only, no downstream fork)
- **conmon**: `https://github.com/containers/conmon.git` (upstream only, no downstream fork)
- **conmon-rs**: `https://github.com/containers/conmon-rs.git` (upstream only, no downstream fork)

For build commands, repo layout, and test targets — browse each repo directly (Makefile/Cargo.toml, README).

## Version History

- **crun** replaced runc as the default OCI runtime starting in **OCP 4.12**.
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
- **conmon-rs**: Use `cross` (cargo plugin) for cross-compilation rather than native cross-compilation toolchains — avoids linker issues.
