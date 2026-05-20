---
name: fix-cve
description: |
  Patch a Go dependency to fix a CVE using the appropriate strategy based on Go version compatibility.
  Use when the user wants to fix a CVE by updating a Go module, replacing it with a patched fork,
  or applying a security patch across all go.mod files in a Go project.
  Triggers on: 'patch CVE', 'fix CVE', 'replace grpc', 'update vulnerable dependency',
  'security patch go module', or any mention of CVE + Go dependency replacement.
---

# fix-cve

Patch a Go module dependency to fix a CVE. The skill determines the right strategy based on Go version compatibility between the project and the fix, then applies the minimum changes needed.

## Parameters

- **module** (required): The Go module to patch, e.g. `google.golang.org/grpc`
- **fix-version** (required): The upstream version that contains the CVE fix, e.g. `v1.75.1` — or a URL to the release/advisory with version info
- **cve** (required): The CVE identifier, e.g. `CVE-2026-33186`
- **ticket** (required): The Jira/bug ticket, e.g. `OCPBUGS-83972`

If any required parameter is missing, ask the user before proceeding.

## Strategy selection

The fix follows one of three paths depending on Go version compatibility. Determine which path to take BEFORE making any changes.

### Gather version info

1. Read the project's Go version from the root `go.mod` (`go` directive), e.g. `go 1.23.6`
2. Determine the Go version required by the CVE fix. Either:
   - Fetch the upstream fix version's `go.mod` to check its `go` directive
   - Parse it from the release page or advisory the user provided
3. Extract the **major.minor** from both (e.g. `1.23` from `go 1.23.6`)

### Path A: Direct upstream update (project Go >= fix Go)

**Condition**: The project's Go version is **equal or higher** than what the fix requires. The fix can be applied by simply updating the dependency to the upstream version that contains the patch.

**Example**: Project uses `go 1.25.0`, fix requires `go 1.23.1` → direct update works.

**Action**: Update the module version in `go.mod` to the fix version (or latest patched version), then follow the standard update workflow (Step 3 onwards).

### Path B: Bump Go patch version (same minor, lower patch)

**Condition**: The project's Go is on the **same minor version** as the fix but a lower patch. Bumping the patch version (Z in X.Y.Z) within `go.mod` is safe enough to unlock the fix.

**Example**: Project uses `go 1.23.1`, fix requires `go 1.23.7` → bump to `go 1.23.7` in go.mod and update the dependency.

**Action**: Update the `go` directive in go.mod to the required patch version, then update the module and follow the standard update workflow. Report the Go patch bump to the user but don't block on it.

### Path C: Use openshift-sustaining fork (project Go minor < fix Go minor)

**Condition**: The project's Go minor version is **lower** than what the upstream fix requires. Bumping Go minor on a release branch is not acceptable — we need a backported patch.

**Example**: Project uses `go 1.22.1`, upstream fix requires `go 1.23.0` → need a fork.

The `openshift-sustaining` team maintains patched forks of common libraries at lower Go versions for exactly this case. These live under `https://github.com/openshift-sustaining/` and follow a naming pattern like `v1.71.3-sec.1` (component version + security patch suffix).

**Action**:
1. **STOP and ask the user** for the replacement module URL. Suggest checking `https://github.com/openshift-sustaining/<module-name>/releases` for available patched versions matching the project's Go minor.
2. Once the user provides the fork URL/version, fetch its `go.mod` to verify its Go version is compatible.
3. Add a `replace` directive in each affected `go.mod` pointing to the fork.
4. Follow the standard update workflow (Step 3 onwards).

The replace directive format:
```text
// <CVE number>
replace <original-module> => <fork-module> <fork-version>
```

## Standard update workflow

Once the strategy is determined and the go.mod changes are made, follow these steps in exact order.

### Step 1: Find all affected go.mod files

```bash
find . -name "go.mod" -not -path "*/vendor/*"
```

For each `go.mod`, check if it references the target module:
```bash
grep "<module>" path/to/go.mod
```

Report which are affected. Only modify affected ones. Apply the same change (version bump or replace directive) to each.

### Step 2: Sync vendor for each affected module (CRITICAL)

This is the most important step. The vendor directory MUST be updated BEFORE running any repo-level checks like `make update`. Without this, codegen tools that use `go/packages` with `-mod=vendor` fail with cryptic errors like `Hit an unsupported type invalid type` because the new module code isn't in vendor yet.

For each affected `go.mod`, from its directory:

```bash
GO111MODULE=on GOWORK=off GOFLAGS="" go mod tidy
GO111MODULE=on GOWORK=off GOFLAGS="" go mod vendor
```

`GOWORK=off` prevents Go workspace interference. `GOFLAGS=""` prevents inheriting `-mod=vendor` which blocks downloads.

`go mod tidy` may bump transitive dependencies — this is expected (MVS).

**After tidy, verify the `go` directive in each go.mod was NOT bumped.** If it was, **STOP and tell the user** — a transitive dependency is forcing a Go version bump.

### Step 3: Handle macOS toolchain issues

If the project's Go version is old enough to have `dyld` issues on modern macOS (typically Go < 1.22.5 on macOS Sequoia/Tahoe), use `GOTOOLCHAIN` to compile with a newer Go while preserving module semantics:

```bash
GOTOOLCHAIN=go1.23.6 make update
```

This compiles using Go 1.23.6 but respects the `go 1.22.x` directive in the module. Delete stale binaries in `hack/tools/bin/` before running if switching toolchain versions.

### Step 4: Run repo checks

Inspect the `Makefile` for update and verify targets:
```bash
grep -E "^(update|verify):" Makefile
```

Run in order:
```bash
make update
make verify
```

If either fails:
- Verify Step 2 completed for ALL affected modules
- Verify Go version / toolchain is correct
- Check for stale binaries in `hack/tools/bin/` — delete and rebuild
- Read the error — don't retry blindly. **STOP and report to the user.**

After success, verify changes:
```bash
git diff --stat
```

### Step 5: Commit

```text
fix(deps): <action> <module-name> to fix <CVE>

<TICKET>

<Description of what was done and why.>
<One-line description of the vulnerability.>
```

Where `<action>` is:
- Path A: `update`
- Path B: `bump go version and update`
- Path C: `replace`

Use `git commit -s` for sign-off if required.

### Step 6: Optionally create a PR

Before any push or PR action:
- Ask the user for explicit permission to push and open the PR.
- Confirm the current branch is not `main` or `master`.
- Never use force push flags (`-f`, `--force`, `--force-with-lease`).
- Discover remotes via `git remote -v`; do not assume names like `origin`.

Format for OpenShift:
```text
[<branch>] <TICKET>: fix <CVE> by <action> <module-name>
```

Include in the PR body:
- CVE ID and description
- Link to Jira ticket
- Link to advisory (GHSA)
- Link to the fix (upstream commit or fork release)

## Hard stops — when to STOP and ask

1. **Path C triggered**: The project's Go minor is lower than the fix requires. Ask the user for the openshift-sustaining fork URL.
2. **Go directive bumped after tidy**: A transitive dependency forced a Go version change.
3. **`make update` or `make verify` fail**: Report the error, don't retry blindly.

## Troubleshooting

### "Hit an unsupported type invalid type" from codegen
The vendor doesn't have the new module code. Ensure `go mod tidy && go mod vendor` ran for the root module BEFORE `make update`.

### `dyld: missing LC_UUID` on macOS
Use `GOTOOLCHAIN=go1.23.6` to compile with a newer Go. Delete stale `hack/tools/bin/*` first.

### `go work sync` bumps workspace modules
Expected when using Go workspaces. The bumps in `api/go.mod` etc. are normal.

### vendor/modules.txt mismatch
Run `go mod vendor` again for the affected module.

## Examples

**Path A** — direct update (project Go 1.25.0, fix needs Go 1.23):
```text
/golang:fix-cve module="google.golang.org/grpc" fix-version="v1.75.1" cve="CVE-2026-33186" ticket="OCPBUGS-83972"
```

**Path C** — fork replace (project Go 1.22.1, fix needs Go 1.23):
```text
/golang:fix-cve module="google.golang.org/grpc" fix-version="v1.75.1" cve="CVE-2026-33186" ticket="OCPBUGS-83972"
```
→ Skill detects Go mismatch, asks user for fork, user provides `github.com/openshift-sustaining/grpc-go v1.71.3-sec.1`, skill applies replace directive.
