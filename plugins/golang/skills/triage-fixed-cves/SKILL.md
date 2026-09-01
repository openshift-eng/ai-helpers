---
name: triage-fixed-cves
description: |
  Triage Go stdlib CVEs against an OpenShift release image to determine which CVEs are fixed by the Go version each component was built with.
  Use when the user asks to triage Go stdlib CVEs against an OpenShift release image, check which Go CVEs are fixed in a release, or cross-reference Go vulnerability fixes across OCP components.
  Triggers on: 'triage Go CVEs', 'Go stdlib CVE triage', 'which Go CVEs are fixed', 'Go vulnerability report for release', or any mention of Go stdlib CVE + OpenShift release image.
---

# triage-fixed-cves

Analyze an OpenShift release image to determine which Go standard library CVE
Jira tickets have been addressed by the Go version used to build each
component. Produces a per-CVE, per-component cross-reference report.

The user provides a release image pullspec (e.g.
`quay.io/openshift-release-dev/ocp-release:4.17.0-x86_64`).

Execute every step below in order. Do not skip steps.

---

## Step 1 — Extract component images from the release

```bash
oc adm release info <RELEASE_IMAGE> --output=json
```

Parse the JSON output to get the list of component image references. Each
entry in `.references.spec.tags[]` provides a `name` (component name) and
`.from.name` (image pullspec).

Each tag also carries `.annotations` metadata. Extract the
`io.openshift.build.source-location` annotation — this is the canonical
source GitHub repository URL for that component (e.g.
`https://github.com/openshift/cluster-version-operator`). Also extract
`io.openshift.build.commit.id` which gives the exact source commit SHA
the image was built from. Record both for every component — they are used
in Steps 2 and 4.

**Auth failure:** If `oc adm release info` fails due to an authentication
error, STOP immediately. Report the auth failure to the user and do not
proceed. Do not attempt to locate pull secrets, probe environment variables,
or try alternative credential paths — the RWS pod's registry proxy handles
authentication transparently, so an auth failure means the proxy does not
have credentials for this registry and manual intervention is required.

Collect the full list of `(component_name, image_pullspec, source_repo,
source_commit)` tuples before proceeding.

---

## Step 2 — Identify the built binary per component via Dockerfile

For each component, identify exactly which binary is built and where it
lands in the final image by looking up the component's Dockerfile. Do NOT
scan the entire image for all ELF binaries.

#### CI images (most components)

Look up the ci-operator config at
`github.com/openshift/release/ci-operator/config/openshift/<repo>/`.
Match the correct config file for the release branch and build variant (e.g.
`openshift-cluster-version-operator-release-4.17.yaml`). The config's
`images.items[]` specifies the `dockerfile_path` for each image. Fetch that
Dockerfile from the component's own repository **at the exact source commit**
recorded in `io.openshift.build.commit.id` from Step 1 — do not use
`tree/main` or the branch tip, as the release image may have been built from
an older revision.

**Builder substitutions:** ci-operator configs may declare builder image
overrides via `images.items[].inputs.as` — these replace `FROM` targets in
the Dockerfile at build time, which can change the Go toolchain version used.
Note any such substitutions when recording the component's build context.

#### Release / nightly images

Check the ocp-build-data config on the matching branch (e.g.
`github.com/openshift-eng/ocp-build-data/tree/openshift-4.17/images/<component>.yml`).
The `from:` and `dockerfile:` fields point to the Dockerfile.

**OKD builds:** The ocp-build-data image config may contain an
`okd_alignment` section that specifies a different Dockerfile for OKD
builds. These are typically named `Dockerfile.scos` or `Dockerfile.okd`.
When this section is present, use the OKD-specific Dockerfile instead of
the default one for OKD images. As with CI images, fetch the OKD
Dockerfile at the exact source commit from `io.openshift.build.commit.id`
(Step 1), not from the branch tip.

#### Parse the Dockerfile

Look for:
- `go build -o <binary>` or `go install` commands — these tell you the output
  binary name.
- `COPY --from=builder <src> <dest>` in multi-stage builds — this tells you
  where the binary is placed in the final image.

Example: a Dockerfile with `go build -o /go/bin/cvo ./cmd/cvo` and
`COPY --from=builder /go/bin/cvo /usr/bin/cluster-version-operator` means
the target binary is `/usr/bin/cluster-version-operator`.

---

## Step 3 — Detect Go version per component

For each component, extract the Go version from the specific binary
identified in Step 2.

```bash
podman pull <IMAGE>
podman create --name tmp-extract <IMAGE>
podman cp tmp-extract:<binary_path> /tmp/target-binary
podman rm -f tmp-extract   # always remove so the name is freed for the next component
go version /tmp/target-binary
```

**Cleanup:** Always run `podman rm -f tmp-extract` unconditionally after
extraction (even on failure) so the container name is available for the
next component. Wrap the extract-copy-remove sequence in a function or
loop body to ensure cleanup is never skipped.

Parse the output. The format is:
```text
/tmp/target-binary: go1.22.5
```
Extract the semver-style version (e.g. `1.22.5`).

#### Important caveats

- **Do NOT assume a single Go version across the release.** Different
  components may use different Go toolchain versions. ci-operator builder
  image substitutions (`images.items[].inputs.as`) mean components can lag
  behind or jump ahead of the "default" Go version for a release.
- **Inspect ONLY the specific binary identified from the Dockerfile.** Do not
  scan the entire image filesystem for ELF binaries — that is slow, wasteful,
  and may pick up unrelated binaries from base images.
- If a component's Dockerfile cannot be found, or the component is not built
  from Go (e.g. a pure shell image or non-Go component), record it as
  `N/A — no Go binary found` and skip it in later steps.
- If the Dockerfile builds multiple Go binaries, checking any one of them
  is sufficient — all binaries in the same image share the same builder
  image and therefore the same Go toolchain version.
- Process components in batches to avoid excessive pull traffic. 10–20 at a
  time is reasonable.

---

## Step 4 — Query Jira for open Go stdlib CVE trackers

Search for open Jira vulnerability issues that track Go standard library CVEs
affecting the components in this release.

#### 4a — Map release components to Jira components

Using the `io.openshift.build.source-location` source repo URLs extracted in
Step 1, map each repo to its corresponding OCPBUGS Jira component name (e.g.
`openshift/cluster-version-operator` → `cluster-version-operator`).

#### 4b — Query for open stdlib CVE trackers

Using the discovered component list, query Jira with the coordinator's
`query_jira` tool:

```jql
project = OCPBUGS
  AND type = Vulnerability
  AND labels in ("arc:stdlib")
  AND status not in (Closed, "Release Pending", Verified)
  AND component in (<discovered components>)
  AND summary ~ "openshift-<version>"
  ORDER BY component ASC
```

Replace `<discovered components>` with the comma-separated list of Jira
component names from step 4a, and `<version>` with the target OCP version
(e.g. `4.17`).

For each returned issue, record:
- Jira issue key (e.g. `OCPBUGS-12345`)
- CVE ID (e.g. `CVE-2024-24790`) — extract the `CVE-YYYY-NNNNN` pattern
  from the issue summary
- Summary text
- Affected component(s) listed in Jira
- Fix version if mentioned in the issue

---

## Step 5 — Exclude vendored dependency CVEs

Filter out CVEs that affect vendored Go dependencies rather than the Go
standard library itself. The goal is to keep only CVEs that are fixed by
upgrading the Go toolchain version.

#### Exclusion rules

1. **`golang.org/x/*` packages**: CVEs affecting `golang.org/x/net`,
   `golang.org/x/crypto`, `golang.org/x/text`, `golang.org/x/image`, etc.
   are vendored dependencies, not stdlib. Exclude them.

2. **Hybrid CVEs**: Some CVEs affect both stdlib packages AND vendored modules
   (e.g. a CVE that affects `net/http` in stdlib but also
   `golang.org/x/net/http2`). Classify these into a **separate "Hybrid"
   category** — do not list them as both included and excluded:
   - The stdlib portion IS fixed by a Go version upgrade — include this
     in the per-CVE cross-reference (Steps 6–7).
   - The vendored portion requires a separate dependency bump — note this
     in the hybrid section of the report.

3. **Detection method**: Read the Jira issue description and any linked
   advisories. Look for:
   - Package paths starting with `golang.org/x/` — vendored
   - Package paths like `net/http`, `crypto/tls`, `os`, `runtime` — stdlib
   - References to the Go vulnerability database entry

Produce three lists from this step:
- **Stdlib-only CVEs** → proceed to Steps 6–7 cross-reference
- **Hybrid CVEs** → proceed to Steps 6–7 cross-reference (stdlib portion)
  AND note in the dedicated hybrid section of the report (Step 7.4)
- **Vendored-only CVEs** → excluded; listed in the report (Step 7.5)

---

## Step 6 — Map CVEs to Go vulnerability DB and cross-reference

For each remaining stdlib CVE, determine which Go versions contain the fix,
then check each component against those fix versions.

#### 6a — Extract GO-* ID from Jira remote links

ProdSec and ARC typically attach a `pkg.go.dev/vuln/GO-*` URL to Go CVE
tracker tickets as a web link (remote link). The coordinator's
`get_jira_issue` tool returns remote links in its output.

For each CVE's Jira issue:
- Call `get_jira_issue(issue_key)` (you already have the issue key from
  Step 4).
- Look through the remote links / web links section of the response for a URL
  matching `pkg.go.dev/vuln/GO-*` (e.g.
  `https://pkg.go.dev/vuln/GO-2024-2887`).
- Extract the `GO-YYYY-NNNN` ID from that URL.

This is more reliable than searching the vuln database by CVE text, because
the Go vulnerability database uses `GO-*` format IDs (not CVE IDs directly)
and text search can miss or return ambiguous results.

#### 6b — Fetch fixed versions

Using the GO-* ID, fetch the vulnerability entry:
```text
https://pkg.go.dev/vuln/<GO_ID>
```
Use `web_fetch` to retrieve the page content, or fetch the JSON:
```bash
curl -s "https://vuln.go.dev/ID/<GO_ID>.json"
```

The vulnerability entry contains `fixed` version fields under each affected
module/package. For stdlib entries the module is `stdlib` (or `std`). The
`fixed` field tells you the first Go version where the vulnerability is
patched (e.g. `1.22.5`).

Note: there may be multiple fix versions for different Go release branches
(e.g. fixed in `1.21.12` and `1.22.5`). Record all of them.

**Fallback if no remote link is present:** If a Jira ticket does not have a
`pkg.go.dev/vuln` remote link, try searching the Go vulnerability database
web interface via `web_fetch`:
```text
https://pkg.go.dev/vuln/list?q=<CVE_ID>
```
If no Go vulnerability database entry exists for a CVE, note it as "not in
Go vuln DB."

#### 6c — Cross-reference: which components are fixed?

For each CVE, compare the fixed Go version(s) against each component's
detected Go version from Step 3.

For a given CVE with fixed versions `[1.21.12, 1.22.5]`:
- A component built with Go `1.22.5` or later on the 1.22 branch → **FIXED**
- A component built with Go `1.22.4` on the 1.22 branch → **AFFECTED**
- A component built with Go `1.21.12` or later on the 1.21 branch → **FIXED**
- A component built with Go `1.23.0` (a newer minor branch) → **FIXED**
  (Go includes all prior fixes in new minor releases)

Version comparison rules:
- Compare within the same minor release branch first (1.22.x vs 1.22.y).
- A component on a newer minor branch (e.g. 1.23.x) than any listed fix
  version is considered fixed.
- A component on an older minor branch that has no fix listed for that branch
  is **AFFECTED** unless explicitly listed as unaffected in the vuln DB entry.

Build a matrix: `CVE × Component → FIXED | AFFECTED | N/A`.

---

## Step 7 — Generate the report

Produce a structured Markdown report with the following sections:

#### 7.1 — Summary of Go versions across the release

- Table of all unique Go versions found, with a count of components using each.
- Flag any outlier versions (components using a significantly older Go version
  than the majority).

#### 7.2 — Per-CVE breakdown

For each CVE (sorted by CVE ID):
- **CVE ID** and Jira issue key (linked)
- **Summary** (one-line description)
- **Fixed in Go versions**: list all fix versions from the vuln DB
- **Affected components**: list components whose Go version is older than
  the fix
- **Fixed components**: count of components already on a fixed Go version
- **Status**: `ALL FIXED` | `PARTIALLY FIXED (N of M)` | `ALL AFFECTED`

#### 7.3 — Outlier components

List components whose Go version is notably older than the release majority.
These are the highest-risk components for stdlib CVEs and likely need
builder image updates.

#### 7.4 — Hybrid CVEs

List CVEs classified as hybrid in Step 5. For each, show:
- The stdlib packages affected (fixed by the Go version upgrade) and their
  cross-reference status from section 7.2.
- The vendored packages affected (require a separate dependency bump) and
  which components still carry the vulnerable vendored version.

This section prevents hybrid CVEs from being ambiguously double-listed as
both "included" and "excluded."

#### 7.5 — Excluded CVEs

List CVEs excluded in Step 5 as vendored-only, with the reason for
exclusion (e.g. `golang.org/x/net` — vendored dependency, not stdlib).

#### Store the report

Write the report to a file and store it via `store_text` with a descriptive
label (e.g. `golang-cve-triage-4.17.0`) so the coordinator can share it with
the user.

```python
store_text(
    local_path="/workspace/golang-cve-report.md",
    label="golang-cve-triage-<version>",
    description="Go stdlib CVE triage report for OCP <version>"
)
```
