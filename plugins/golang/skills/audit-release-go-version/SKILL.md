---
name: audit-release-go-version
description: |
  Audit the effective Go builder versions used by images in an OpenShift Container Platform release image or payload against a requested Go version.
  Use when the user asks which OCP release images were built with a different Go version, wants a concise payload Go-version audit, or needs Dockerfile builder evidence for an OpenShift release.
---

# audit-release-go-version

Audit a release without modifying images, repositories, Jira, or external systems. Report only images whose effective Go builder does not match the requested target, plus items that cannot be accounted for with sufficient evidence.

## Inputs

Require:

- **target Go version**: normally major.minor, such as `1.26`; accept `go1.26` and normalize it to `1.26`.
- **release target**: an OCP release pullspec, payload, or equivalent target resolvable to its image references.

Optional:

- **scope**: default to `OCP`. If the requested target is OKD or SCOS, stop and ask for an OCP target or explicit scope; do not substitute their Dockerfiles or configuration.
- **source/ref policy**: honor an explicit branch/ref policy. Otherwise use the release-aligned/current branch policy for the release, and record the ref used. Do not blindly use `io.openshift.build.commit.id` from the payload as the source ref.

Match at the requested precision: `1.26` matches any `1.26.x`; a requested patch version requires that exact patch when explicit builder evidence exposes it.

## Required workflow

1. Resolve the release target read-only (for example, `oc adm release info`) and collect each tag's image pullspec, source repository annotation, and release version. Do not emit the complete inventory.
2. For each source repository, locate its ci-operator configuration across **all relevant** `openshift/release/ci-operator/config/<org>/` trees. Search by repository identity and release variant; do not assume `config/openshift` is the only tree. In particular, account for organization trees such as `openshift-assisted` and `operator-framework` when they own the configuration.
3. Select the config matching the release version and requested/current branch policy. A repository is not unresolved merely because its config lives outside the source repository's organization tree.
4. Resolve the actual build context before reading builder evidence:
   - use the applicable `images.items[].dockerfile_path` and `context_dir`;
   - follow Dockerfile pointer files and repository symlinks until reaching the real Dockerfile;
   - honor `build_root.from_repository` and inspect its repository Dockerfile/context when it supplies the build root;
   - apply `images.items[].inputs` substitutions that replace Dockerfile `FROM` references.
5. Inspect the resolved Dockerfile stages. Associate `FROM` images with stages that execute Go compilation (`go build`, `go install`, `go test`, or an equivalent invoked build). Resolve build arguments and substitutions where possible. Derive the Go version from the effective builder image/tag or its read-only metadata.

Do not infer a Go builder from the final runtime image, scan every binary in an image, or use a release-wide default. One repository may produce multiple images with distinct Dockerfiles/builders; keep their results separate.

## Evidence and classification

Classify each image as follows:

| Classification | Required evidence | Report location |
| --- | --- | --- |
| mismatch | Resolved compiling stage has an effective `FROM` builder whose Go version differs from the target. | Mismatches |
| match | Resolved compiling stage has an effective `FROM` builder matching the target. | Omit |
| limited evidence | No resolvable compiling-stage builder, an unresolved `ARG`/substitution, inaccessible config/source, non-Go build, or only module metadata. | Unaccounted / limited evidence |

Explicit Dockerfile `FROM` evidence always takes precedence over `go.mod`. A `go.mod` directive may be recorded only as **module-only evidence**; it neither proves the image builder nor turns an item into a match or mismatch.

## Output

Return a small Markdown report:

```text
## Go builder audit — OCP <release>, target Go <target>

### Mismatches
| repo | image | effective builder | detected Go | evidence |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | resolved Dockerfile path + FROM stage |

### Explicitly unaccounted / limited evidence
| repo | image | reason | evidence tried |
| --- | --- | --- | --- |
| ... | ... | ... | config tree, ref, Dockerfile/context, or module-only evidence |
```

Omit the Mismatches table rows when none exist, but keep the heading and state `None found with explicit builder evidence.` Do not list matching images or totals from the payload.

## Coverage and failure handling

- State the scope and source/ref policy used.
- If release metadata cannot be resolved, report the failure and stop: coverage cannot be established.
- If a component cannot be traced, retain it only in the limited-evidence section with the precise failed lookup. Never silently treat it as a match.
- If config selection is ambiguous, compare candidate release configs; if it remains ambiguous, report the candidates as limited evidence rather than guessing.
- Preserve repository/image identifiers needed to audit a finding, but do not include credentials, private user data, or unrelated inventory.
