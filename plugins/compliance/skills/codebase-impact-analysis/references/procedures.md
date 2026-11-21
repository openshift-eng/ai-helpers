# Detailed Procedures for codebase-impact-analysis

This file holds the exact commands for the steps/methods in [SKILL.md](../SKILL.md) whose determinism matters (timeouts, SIGPIPE avoidance, anchored version extraction). SKILL.md links here; read the corresponding section in SKILL.md first for the decision rules that govern how to interpret the output.

## Step 1.5: Go Stdlib Build-Time Version Check — Commands

```bash
echo "=== Step 1.5: Go stdlib build-time version check ==="

DECLARED_GO=$(grep '^go ' "${GO_MODULE_DIR}/go.mod" | awk '{print $2}')
echo "go.mod declared version: ${DECLARED_GO}"

# Build-time version signals, in order of reliability:
# 1. Container build file's FROM line for the build stage. Search the whole
#    repo, not just the root — these files live in subdirectories on some
#    repos (e.g. images/, build/) and can be named Dockerfile.rhel9,
#    Dockerfile.ocp, Containerfile, etc. Match both the public golang: image
#    and Red Hat's go-toolset/UBI-based builder images. OpenShift's own
#    ART-built images pack extra version numbers into the same reference
#    (e.g. registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.26-openshift-5.0,
#    or an OCP release number earlier in the path than "golang") — anchor the
#    extraction to the digits immediately after "golang"/"go-toolset", not
#    "the first dotted number in the line", or an OCP/RHEL version elsewhere
#    in the reference gets picked up instead of the actual Go version.
DOCKERFILE_GO=$(grep -rihE '^FROM .*(golang|go-toolset)' "${REPO_DIR}" --include='Dockerfile*' --include='Containerfile*' --exclude-dir=vendor 2>/dev/null \
  | grep -oE '(golang|go-toolset)[:-][0-9]+\.[0-9]+(\.[0-9]+)?' \
  | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
echo "Build-image Go version: ${DOCKERFILE_GO:-<none found>}"

# 2. toolchain directive, if present (go.mod or go.work — takes precedence over the go.mod 'go' line)
TOOLCHAIN_GO=$(grep '^toolchain ' "${GO_MODULE_DIR}/go.mod" "${GO_MODULE_DIR}/go.work" 2>/dev/null | awk '{print $2}' | head -1)
echo "toolchain directive: ${TOOLCHAIN_GO:-<none found>}"

# 3. Locally installed toolchain — informational only. This is the analysis
#    environment, not necessarily the CI/build environment that produced the
#    shipped binary, so never substitute it for DOCKERFILE_GO/TOOLCHAIN_GO above.
LOCAL_GO=$(go version 2>/dev/null | awk '{print $3}')
echo "locally installed go (informational only): ${LOCAL_GO:-<not found>}"
```

Record `DECLARED_GO`, `DOCKERFILE_GO`, and `TOOLCHAIN_GO` as evidence regardless of outcome, then apply the decision rules in SKILL.md's Step 1.5.

## Method 2: Go Vulnerability Scanner — Detailed Procedure

> **CRITICAL RULES — read before running anything:**
> 1. **Run govulncheck AT MOST ONCE per analysis run.** Keep all Method 2 scratch and cache files under `${OUT_DIR}/` (same per-CVE workspace as call-graph artifacts). The canonical result is `${OUT_DIR}/govulncheck-source.txt` — if it already exists and is non-empty for this run, read it and do not re-run.
> 2. **Never pipe govulncheck to `head`, `tail`, `grep`, or any other command.** Always redirect to a file (`> file 2>&1`). Piping causes govulncheck to hang (SIGPIPE) when the reader closes.
> 3. **"No findings" is a valid and final result** — it means the CVE is not yet in the Go vuln database. Proceed to Method 3 immediately. Do NOT re-run in a different mode or format.
> 4. **Always use `timeout -k 10`** to force-kill if SIGTERM is ignored. Plain `timeout` sends SIGTERM but govulncheck can ignore it when stuck in package loading.

This method has 4 sequential steps. If any step fails or times out, skip the remaining steps and proceed to Method 3 — govulncheck is one signal, not the only one.

```bash
OUT_DIR="${OUT_DIR:-${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}}"
mkdir -p "${OUT_DIR}"
```

---

**Step 2a — go.mod check (instant)**

```bash
VULN_PKG="google.golang.org/grpc"   # replace with actual vulnerable package
echo "=== Step 2a: go.mod check for ${VULN_PKG} ==="
grep "${VULN_PKG}" "${GO_MODULE_DIR}/go.mod" && echo "FOUND in go.mod" || echo "NOT FOUND in go.mod"
```

- IF **NOT FOUND** → record "package not in module graph" as LOW signal; **skip Steps 2b–2d entirely**; proceed to Method 3
- IF **FOUND** → note the version; continue

---

**Step 2b — Pre-flight: download modules and verify toolchain (max 2 min)**

Large repos (300+ deps like spiffe-spire) need all modules cached before govulncheck can load them. Separate this from the scan to isolate network issues from analysis hangs.

```bash
cd "${GO_MODULE_DIR}"
echo "=== Step 2b: Pre-flight ==="

# Download all modules (network-bound, do first)
echo "Downloading modules..."
timeout -k 10 120 env CGO_ENABLED=0 go mod download > "${OUT_DIR}/go-mod-download.txt" 2>&1
if [ $? -ne 0 ]; then
  echo "⚠ go mod download failed or timed out — govulncheck may fail"
  cat "${OUT_DIR}/go-mod-download.txt"
fi

# Verify the Go toolchain can load the package graph (CGO disabled first — many repos fail only with CGO enabled)
echo "Loading package list (CGO_ENABLED=0)..."
timeout -k 10 60 env CGO_ENABLED=0 go list ./... > "${OUT_DIR}/go-list-packages.txt" 2>&1
LIST_EXIT=$?
PKG_COUNT=$(wc -l < "${OUT_DIR}/go-list-packages.txt" 2>/dev/null || echo 0)
echo "Package count: ${PKG_COUNT}, exit code: ${LIST_EXIT}"

if [ $LIST_EXIT -ne 0 ]; then
  echo "go list with CGO_ENABLED=0 failed — retrying after CGO probe (Step 2c) before skipping govulncheck"
fi
```

- IF `go list` succeeds with `CGO_ENABLED=0` → continue to Step 2c, then 2d
- IF `go list` still fails after Step 2c's CGO probe (with the chosen `CGO_SETTING`) → write the error to `${OUT_DIR}/govulncheck-source.txt`, **skip Steps 2c–2d**, proceed to Method 3

---

**Step 2c — CGO probe (max 60s, skip if compiler absent)**

```bash
echo "=== Step 2c: CGO probe ==="
CGO_SETTING=0
if command -v gcc >/dev/null 2>&1 || command -v cc >/dev/null 2>&1; then
  timeout -k 10 60 env CGO_ENABLED=1 go build ./... > "${OUT_DIR}/cgo-probe.txt" 2>&1
  if [ $? -eq 0 ]; then
    CGO_SETTING=1
    echo "✓ CGO works — using CGO_ENABLED=1"
  else
    echo "✗ CGO build failed — using CGO_ENABLED=0"
  fi
else
  echo "✗ No C compiler — using CGO_ENABLED=0"
fi
echo "CGO_ENABLED=${CGO_SETTING}"

if [ $LIST_EXIT -ne 0 ]; then
  echo "Retrying go list with CGO_ENABLED=${CGO_SETTING}..."
  timeout -k 10 60 env CGO_ENABLED=${CGO_SETTING} go list ./... > "${OUT_DIR}/go-list-packages.txt" 2>&1
  LIST_EXIT=$?
  PKG_COUNT=$(wc -l < "${OUT_DIR}/go-list-packages.txt" 2>/dev/null || echo 0)
  echo "Retry package count: ${PKG_COUNT}, exit code: ${LIST_EXIT}"
  if [ $LIST_EXIT -ne 0 ]; then
    echo "✗ go list failed after CGO probe — skipping govulncheck entirely"
    echo "go list failed (exit ${LIST_EXIT})" > "${OUT_DIR}/govulncheck-source.txt"
    cat "${OUT_DIR}/go-list-packages.txt" >> "${OUT_DIR}/govulncheck-source.txt"
  fi
fi
```

- IF `go list` still fails after retry → `${OUT_DIR}/govulncheck-source.txt` is populated; skip Step 2d and proceed to Method 3
- IF `go list` succeeds → continue

---

**Step 2d — govulncheck scan (max 5 min)**

Use `-scan=package` first (fast, checks if CVE is in vuln DB and package imported). Only escalate to symbol-level if package-level finds something.

```bash
if [ ! -s "${OUT_DIR}/govulncheck-source.txt" ] && [ $LIST_EXIT -eq 0 ]; then
  # Package-level scan first (fast — no symbol resolution)
  echo "=== Step 2d: govulncheck package scan ==="
  timeout -k 10 120 env CGO_ENABLED=${CGO_SETTING} govulncheck -scan=package ./... > "${OUT_DIR}/govulncheck-package.txt" 2>&1
  PKG_EXIT=$?
  echo "govulncheck -scan=package exit: ${PKG_EXIT}"
  cat "${OUT_DIR}/govulncheck-package.txt"

  # Check if the package scan found anything worth escalating to symbol level
  if grep -qi "Vulnerability\|finding\|${VULN_PKG}" "${OUT_DIR}/govulncheck-package.txt" 2>/dev/null; then
    echo "=== Step 2d: govulncheck symbol scan (escalating — CVE found at package level) ==="
    timeout -k 10 300 env CGO_ENABLED=${CGO_SETTING} govulncheck ./... > "${OUT_DIR}/govulncheck-source.txt" 2>&1
    SOURCE_EXIT=$?
    if [ $SOURCE_EXIT -eq 124 ] || [ $SOURCE_EXIT -eq 137 ]; then
      echo "govulncheck symbol scan timed out or was killed — using package-level results"
      cp "${OUT_DIR}/govulncheck-package.txt" "${OUT_DIR}/govulncheck-source.txt"
    fi
  else
    echo "Package scan found no findings — CVE likely not in Go vuln DB yet"
    cp "${OUT_DIR}/govulncheck-package.txt" "${OUT_DIR}/govulncheck-source.txt"
  fi
  echo "govulncheck complete"
else
  echo "=== govulncheck (using cached result) ==="
fi
cat "${OUT_DIR}/govulncheck-source.txt"

# Verify the module is still accessible after govulncheck
echo "=== Post-govulncheck repo check ==="
ls "${GO_MODULE_DIR}/go.mod" > /dev/null 2>&1 && echo "✓ Module intact at ${GO_MODULE_DIR}" || echo "✗ WARNING: go.mod missing at ${GO_MODULE_DIR}"
```

- IF CGO was disabled → note in report: "CGO-gated code paths excluded from analysis"
- IF package scan found no findings → CVE is not in Go vuln DB; do NOT escalate to symbol scan; proceed to Method 2.5
- IF symbol scan timed out → use package-level results instead; proceed to Method 2.5
- Save `${OUT_DIR}/govulncheck-source.txt` as a workflow artifact

Return to SKILL.md's Method 2 decision point once this procedure completes (or was skipped per one of the IF branches above).

## Method 2.5: Vendor Directory Verification — Commands

```bash
VULN_PKG="google.golang.org/grpc"                              # same package as Method 1/2
VULN_IMPORT_PATH="google.golang.org/grpc/internal/transport"    # narrow to the vulnerable sub-package/file from the CVE advisory when known

echo "=== Method 2.5: Vendor directory verification for ${VULN_PKG} ==="

if [ ! -d "${GO_MODULE_DIR}/vendor/${VULN_PKG}" ]; then
  echo "NOT VENDORED — ${VULN_PKG} has no directory under vendor/"
  VENDOR_STATUS="not_vendored"
else
  echo "Vendored directory structure:"
  find "${GO_MODULE_DIR}/vendor/${VULN_PKG}" -maxdepth 3 -type d

  if [ -e "${GO_MODULE_DIR}/vendor/${VULN_IMPORT_PATH}" ]; then
    echo "PRESENT — vulnerable sub-package ${VULN_IMPORT_PATH} is vendored"
    VENDOR_STATUS="present"
  else
    echo "PARTIAL — ${VULN_PKG} is vendored but ${VULN_IMPORT_PATH} is not present"
    VENDOR_STATUS="partial_not_vulnerable_part"
  fi
fi
echo "vendor_status=${VENDOR_STATUS}"
```

Record `VENDOR_STATUS` and the `find` output as evidence regardless of outcome, then apply the decision rules in SKILL.md's Method 2.5.
