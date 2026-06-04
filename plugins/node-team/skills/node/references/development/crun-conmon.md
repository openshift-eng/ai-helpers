# crun and conmon-rs: Non-Obvious Notes (Tribal Knowledge)

- **crun**: `https://github.com/containers/crun.git` (upstream only, no downstream fork)
- **conmon-rs**: `https://github.com/containers/conmon-rs.git` (upstream only, no downstream fork)

For build commands, repo layout, and test targets — browse each repo directly (Makefile/Cargo.toml, README).

## Version History

- **crun** replaced runc as the default OCI runtime starting in **OCP 4.12**.
- **conmon-rs** replaced the C-based conmon starting in **OCP 4.14**. conmon-rs uses gRPC (defined in `proto/conmon.proto`) instead of pipe-based IPC.

## Binary Paths on RHCOS

| Binary | Path |
|--------|------|
| crun | `/usr/bin/crun` |
| conmonrs | `/usr/libexec/crio/conmonrs` |
| conmon (legacy) | `/usr/bin/conmon` |

After replacing any of these binaries on a node, **restart CRI-O** (`sudo systemctl restart crio`) for it to pick up the change.

## Build Notes

- **crun**: Fully static builds with glibc are not recommended. Use musl libc for true static builds, or use dynamic linking matching RHCOS library versions. A containerized build (Fedora/UBI) is the easiest path for cross-compilation.
- **conmon-rs**: Use `cross` (cargo plugin) for cross-compilation rather than native cross-compilation toolchains — avoids linker issues.
