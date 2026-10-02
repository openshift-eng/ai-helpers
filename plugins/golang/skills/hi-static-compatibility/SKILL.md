---
name: hi-static-compatibility
description: Assess whether a Go project can run on registry.access.redhat.com/hi/static by checking production build linkage, runtime dependencies, container configuration, and deployment behavior. Use when evaluating or planning a migration to the Red Hat Hardened Images static base.
---

# Assess hi/static Compatibility

Assess the requested project against `registry.access.redhat.com/hi/static:latest`, assuming it will be rebuilt with `CGO_ENABLED=0` unless the user specifies otherwise. Give an evidence-based verdict for each production executable and target platform, with blockers, minimal remedies, and verification gaps. Evaluate compatibility first; change project files only when requested.

## Establish the deployment contract

Read repository instructions, Go modules/workspaces, production build targets, Dockerfiles/Containerfiles, CI configuration, and deployment manifests. Identify:

- Executables actually shipped, including helpers, init containers, and sidecars; distinguish containers that use separate base images.
- Target OS/architectures, Go toolchain, build tags, linker flags, CGO setting, vendoring/replacements, and generated inputs.
- Entrypoint, arguments, probes, lifecycle hooks, volumes, identity, capabilities, and required application behavior.

Use the release build's toolchain, targets, tags, and flags as the assessment baseline, with `CGO_ENABLED=0` for the candidate build. A successful `go build ./...` on the workstation is not sufficient. Ask for missing target details only when they affect the verdict; otherwise state the inferred scope.

For operators, distinguish the operator's own deployment from the operand workloads it manages. Trace embedded manifests, templates, ConfigMaps, and generated pod specifications to the container or init container that executes each command, script, probe, or lifecycle hook. Resolve its image through image references, environment variables, and reconciliation code where possible. Record the workload/container, executing image, dependency, and source location. If an image reference cannot be resolved, report that attribution as uncertain.

An operator can be compatible with hi/static while its operand requires a shell or other utilities. Rendering, embedding, or copying a script does not make its interpreter an operator-image dependency; executing it does. Conversely, an init container or helper that reuses the operator image brings its runtime requirements into that image's assessment. Treat separate operand images as migration targets only when the requested scope includes them.

## Verify the image contract

Resolve the mutable tag and record inspection date, digest, and platform. Inspect the selected platform's image configuration, including user, working directory, environment, and entrypoint. Use available tools, for example:

```bash
skopeo inspect --raw docker://registry.access.redhat.com/hi/static:latest
skopeo inspect --override-os linux --override-arch amd64 docker://registry.access.redhat.com/hi/static:latest
skopeo inspect --override-os linux --override-arch amd64 --config docker://registry.access.redhat.com/hi/static:latest
```

Replace `amd64` with the deployment architecture. For a multi-platform index, retain both the index digest and selected platform manifest digest; verify platform availability rather than assuming it.

The image's published contract is a minimal runtime for static executables, with CA certificates, timezone data, and a non-root user, without a shell, package manager, or C library. Reconfirm this against the inspected image rather than treating `latest` as fixed. Verify exact files when the application relies on them, including certificate paths, zoneinfo, passwd/group entries, and directory permissions. Inspect the filesystem using a container export or image tooling; do not try `podman run ... sh` inside this shell-free image. Runtime-injected files such as `/etc/resolv.conf` must be evaluated in the container environment.

Sources for current requirements:

- [Red Hat hi/static catalog](https://catalog.redhat.com/en/software/containers/hi/static/6a16389952373d5696676958)
- [Image source repository](https://gitlab.com/redhat/hummingbird/containers), following the inspected image's source and revision labels

If registry access or tooling is unavailable, continue repository analysis and report the image contract as unverified. Do not convert an inspection failure into an incompatibility finding.

## Verify executable linkage

Build each shipped executable with `CGO_ENABLED=0`, retaining the production toolchain and other required flags. Check build scripts for overrides that re-enable CGO, and confirm the effective setting in the artifact with `go version -m`. Inspect existing production artifacts as baseline evidence, but do not treat their CGO-enabled shared-library dependencies as blockers for the proposed CGO-disabled build. If the candidate cannot be built or inspected, mark its linkage unverified. Put assessment artifacts in the repository's temporary-work directory. Do not rewrite `go.mod`, vendors, or build settings merely to make an assessment pass.

Use `CGO_ENABLED=0 go list -deps -json <main-package>` with the production tags and target platform to inspect selected dependencies. Where native dependencies are suspected, compare the CGO-enabled and CGO-disabled file selections, including `CgoFiles` and `IgnoredGoFiles`, and inspect fallback implementations. Source searches for `import "C"` are leads, not proof: platform constraints and transitive dependencies determine what is compiled.

Inspect the final artifact on the host, for example:

```bash
file path/to/binary
go version -m path/to/binary
readelf -hW path/to/binary
readelf -lW path/to/binary
readelf -dW path/to/binary
```

Check Linux ELF architecture, any `PT_INTERP` loader, and `DT_NEEDED` shared libraries. Match them to the target platform and available filesystem. Use `readelf` or equivalent inspection rather than executing an unknown binary via `ldd`. Distinguish tool failures from an inspected absence of dependencies.

- A normal Go build can use CGO and link dynamically. Go language choice alone proves nothing about static linkage.
- `CGO_ENABLED=0` is the default assessment assumption, not proof of compatibility. A required native dependency without a usable Go implementation may cause the build to fail. Attribute such failures to the dependency and required feature; distinguish them from missing tooling, unavailable modules, or unrelated compiler errors.
- Disabling CGO can also select stubs or fallback implementations and still compile successfully. Check that required features remain functional, especially native drivers, system integration, DNS/NSS, identity lookups, and crypto providers. A stub that errors only at runtime is a blocker when its feature is required.
- No ELF loader or shared-library requirement is strong linkage evidence, but does not exclude `dlopen`, Go plugins, external processes, or required data files.
- `netgo` and `osusergo` may select pure-Go implementations; they are not universal fixes and may change resolver or identity semantics.
- Preserve required FIPS/crypto behavior in the CGO-disabled candidate. Inspect toolchain-specific build tags, native crypto providers, and deployed policy. If required behavior depends on CGO or unavailable shared libraries, report it as a blocker under the default assumption rather than silently removing the requirement.

Record the candidate's flags and evaluate it separately from the existing production build. Re-enabling CGO or adding shared libraries is an alternative approach, not a successful result under the default assessment assumption.

## Trace runtime dependencies

Inspect call sites and deployment configuration, following relevant code paths rather than declaring every textual match a blocker:

- **Commands and scripts:** `os/exec`, shell wrappers/shebangs, git, curl, tar, openssl, and other subprocesses. Check availability and linkage of required helpers. Shell-form `ENTRYPOINT`/`CMD` and shell-based lifecycle hooks need a shell. JSON exec form still fails if the executable itself needs an unavailable interpreter.
- **Exec probes:** inspect startup, readiness, and liveness `exec.command` arrays in deployment manifests and generated configuration. Every invoked executable, helper, script interpreter, and shared library must be available in the probed container's image and usable by its deployment UID. Kubernetes does not automatically run exec probes through a shell; explicit `sh -c` or `bash -c` requires that shell, and direct commands such as `curl`, `cat`, or `test` require those utilities. Exercise the actual probe commands in the candidate container when that image is in migration scope. Kubernetes HTTP/TCP/gRPC probes do not require utilities in the container.
- **Data and trust:** application configuration, templates, embedded versus copied assets, CA bundles/custom trust, named timezones, passwd/group lookups, and hard-coded filesystem paths. Account for files supplied by volumes or the runtime; verify permissions for the deployment UID.
- **DNS and identity:** test resolver behavior needed by the application, including search domains or special NSS integrations. Distinguish numeric UID execution from successful username/home-directory lookups.
- **Writable paths:** temp files, `$HOME`, caches, state, sockets, and working directory. Inspect the image's actual default user and OpenShift arbitrary-UID behavior where applicable; test intended volumes and read-only-root settings. Do not use root as the default remedy.
- **Native runtime loading:** shared objects, plugin loading, native drivers, and crypto providers. A static main executable does not prove these are absent.
- **Privileges and platform:** privileged ports, capabilities, devices, kernel requirements, CPU baseline, and target architecture. Separate deployment-policy constraints from base-image incompatibility.

For example, when assessing `cluster-kube-apiserver-operator`, inspect its managed kube-apiserver `pod.yaml` and startup scripts. Attribute startup-script utilities to the kube-apiserver or init-container image that runs them, following the actual image wiring. Do not mark the operator image incompatible merely because those assets contain shell commands. Separately inspect commands the operator itself executes and any managed containers that reuse its image.

## Validate in the candidate image

When available within the task's authorization, construct a temporary multi-stage candidate using the verified base digest. Copy executable artifacts and required assets from a builder; use an absolute executable path and JSON exec-form entrypoint. Shell-based `RUN` instructions cannot execute in the static final stage; perform preparation in the builder. Do not add an entire operating-system filesystem or silently copy dynamic libraries to claim compatibility with the stock static runtime.

Run bounded, non-production checks under the intended identity, mounts, environment, and security settings. Choose application-specific checks covering startup/readiness, a representative operation, DNS, outbound TLS, required timezone/user lookups, writable paths, helpers, and shutdown as relevant. A `--version` invocation alone is insufficient for a service. Avoid production credentials and external writes. If only a different architecture is runnable locally, report that limit; emulation does not establish native platform behavior.

Do not require an existing runtime image's utilities to survive the migration if the application does not need them. Suggest the smallest remediation, such as copying assets, replacing a shell wrapper with direct execution, or supplying writable volumes. For unavoidable native dependencies, explain why another runtime base may be needed and verify its contents before recommending it.

## Report

Lead with one of these verdicts, scoped to the inspected artifacts and platform:

- **Compatible:** inspected production artifacts and required runtime dependencies fit the image, and representative container checks pass. State tested coverage and remaining limits.
- **Compatible after changes:** concrete remedies are identified; state which were tested and which remain proposed. Do not claim the current release is compatible.
- **Incompatible as built:** a required loader, library, interpreter, helper, or other runtime requirement cannot be satisfied by the proposed image/deployment. Cite the evidence and practical alternatives.
- **Inconclusive:** missing artifacts, unavailable tooling, image inspection, or runtime coverage prevents a confident verdict. List the next checks needed.

Include base digest/platform/date, production build settings, executable linkage evidence, file/line references for blockers, smoke-test outcomes, and minimal next steps. For multiple binaries/platforms, give individual results; do not generalize one success to the entire project. For operators, report operator-image compatibility separately from operand/init-container requirements, identifying the executing image for each finding and whether it is in migration scope. Separate observed facts from hypotheses and candidate fixes.
