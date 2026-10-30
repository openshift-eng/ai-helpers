---
name: analyze-release-go-versions
description: |
  Analyze Go builder images, declared Go versions, or Go module versions across an OpenShift release using the golang plugin's release inventory scripts.
  Use when the user asks to filter or compare component results.
---

# Analyze release Go versions

Use only the scripts below to collect release data. Do not independently inspect registries, GitHub, repositories, Dockerfiles, `go.mod` files, or build configs. Your job is to interpret and filter script output for the user's question. If the user supplies output from these scripts, analyze that output directly.

Run from the repository root, replacing placeholders with the user's values:

```bash
python3 plugins/golang/scripts/release_go_builder_versions.py <release-image> --correlate-builder --build-root
python3 plugins/golang/scripts/release_go_builder_versions.py <release-image> --correlate-builder
python3 plugins/golang/scripts/release_go_builder_versions.py <release-image> --build-root
python3 plugins/golang/scripts/release_go_module_versions.py <release-image> <module>
python3 plugins/golang/scripts/release_go_module_versions.py <release-image> --go-version
```

`<module>` is the full Go module path the user is asking about (e.g. `google.golang.org/protobuf`, `golang.org/x/net`, `k8s.io/client-go` — any valid module works).

- Run only the needed script and mode.
- `--correlate-builder` scans Dockerfiles or Containerfiles selected by release image build configs, including distinct OKD variants. Omit it only when the user wants all matching files in each source repository.
- `--build-root` reports Go versions from each component's `.ci-operator.yaml` build root image tag (e.g. `rhel-9-release-golang-1.26-openshift-5.0` → `1.26`). This shows the CI build environment Go version, which may differ from the Dockerfile builder.
- **Combine both flags** (`--correlate-builder --build-root`) when the user asks about both Dockerfile builders and CI build roots. This avoids a redundant pass over the release — both lookups share the same source-repo resolution. The combined output appends `build root tag` and `build root go version` columns to each Dockerfile row. Prefer the combined form when both kinds of evidence are needed.
- Used alone, `--build-root` produces a compact 4-column output (component, repository, build root tag, go version) without Dockerfile scanning.
- The builder script explicitly maps the two installer artifact components to build-data configs without `payload_name`. For `nutanix-cluster-api-controllers`, it scans `openshift/Dockerfile.openshift` in the source repository at the release-recorded ref when no build-data config matches; identify that row as source-repository evidence.
- For a requested module, use its exact Go module path (e.g. `google.golang.org/grpc`). Use `--go-version` only when the user asks about `go` directives in `go.mod`. Run multiple scripts when the question needs both kinds of evidence.
- Filter by component, repository, version, or variant as requested. Treat every returned row as separate evidence; the module script can return multiple rows per component and does not identify the `go.mod` path in its output.
- Preserve `(none)`, unknown values, and lookup errors as unknown or unavailable. Report module replacements as declared in script output, including local paths and fork modules. A builder tag such as `golang-1.26` identifies the declared builder image version; a `go` directive or module declaration does not prove which compiler built the final image or which module version its binary contains.
- Report the filtered results and any material coverage gaps. Do not fill gaps by fetching data yourself.
