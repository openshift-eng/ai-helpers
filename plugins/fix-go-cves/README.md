# fix-go-cves

Scan a Go repository with [Grype](https://github.com/anchore/grype) and fix
every reported CVE on a new branch. Shell scripts own every mutation and gate:
they update dependencies or Go toolchains, add ignores only when no fix is
published, roll back any update that breaks the build or introduces a new
finding, run the repository's tests, rescan rebuilt binaries, and print a
`gh pr create` command. A tool-less Claude or Codex reviewer explains outcomes
the scripts cannot decide; the invoking agent turns those into
recommendations.

The run executes the repository's build and test commands, so run it only on
code you would build yourself.

[`golang:fix-cve`](../golang/skills/fix-cve/SKILL.md) patches one known CVE
from a user-supplied fix version or fork. This plugin starts from a scan and
handles every finding in every module.

## Install

Claude Code:

```text
/plugin marketplace add openshift-eng/ai-helpers
/plugin install fix-go-cves@ai-helpers
```

Codex:

```bash
codex plugin marketplace add openshift-eng/ai-helpers
codex plugin add fix-go-cves@ai-helpers
```

## Run

From a clean checkout, or naming a repository:

```text
/fix-go-cves:fix-go-cves                       # current repository and branch
/fix-go-cves:fix-go-cves 4.18                  # current repository, release-4.18
/fix-go-cves:fix-go-cves /path/to/repo main    # absolute path
/fix-go-cves:fix-go-cves myrepo 4.18           # registry name
/fix-go-cves:fix-go-cves all 4.18              # every registry repository
```

Codex uses `$fix-go-cves:fix-go-cves` with the same arguments. Arguments are
order-independent; `X.Y` expands to `release-X.Y`. Asking only for a scan or
report runs `scripts/report.sh`, which creates no branch or commit and exits 2
when coverage is incomplete.

`origin` must be the upstream repository. The run creates
`fix-<version>-cves-<date>` from `origin/<branch>`, commits
one change per fix, leaves the checkout on that branch, and never pushes. A PR
command is printed only when a GitHub remote owned by someone other than
upstream exists and every readiness gate passes.

## Prerequisites

- `git`, `go`, `jq`, `python3`, `make`, `base64`, GNU `timeout` and
  `sort -V`, and Bash 4+. On macOS, install `bash` and `coreutils` with
  Homebrew and put coreutils' `libexec/gnubin` on `PATH`.
- PyYAML with its libyaml backend (`CSafeLoader`) available to `python3` for
  read-only validation of Grype ignore rules.
- Grype: with `curl`, the latest release is installed into this plugin's
  `bin/`, checked against the release's `checksums.txt`. Set
  `CVE_FIX_GRYPE_VERSION=vX.Y.Z` to pin it. Otherwise Docker or Podman runs
  `anchore/grype` (v0.112.0 pinned by digest; `CVE_FIX_GRYPE_IMAGE` overrides).
- Optional reviewer: the `claude` or `codex` CLI, chosen by `CVE_FIX_AGENT`
  (default `claude`; `CVE_FIX_MODEL` selects a model). Without it the
  deterministic evidence still gates the result. Verification always uses the
  four shell audits directly, without model calls.

## Repository registry

Registry names map to local checkouts, for named and `all` runs. The first
match wins:

1. `$CVE_FIX_REPOS`
2. `${XDG_CONFIG_HOME:-~/.config}/cve-fix/repos.yaml`
3. `repos.yaml` in this plugin directory (development checkouts; plugin
   updates replace installed copies)

Copy [`repos.yaml.example`](repos.yaml.example) to one of these locations.
Absolute paths work without a registry.

## How fixes are chosen

- **Dependencies:** each advisory's earliest fix at or above the installed
  version is combined across grouped advisories without downgrading. Updates
  use native Go commands with `GOWORK=off` per module, then `go work sync`,
  `go mod tidy`, and `go mod vendor` where the module vendors. The build must
  pass, and a source rescan must show no new advisory, before the commit.
- **Parallel release streams:** an installed version reveals only the
  affected range it falls in. When an update is rejected because an advisory
  still matches, the thresholds the rescan reports above it drive one retry.
- **Major versions:** a fix that needs a new major version, a `/vN` module
  path, or a `+incompatible` jump is left as `NEEDS_REVIEW`, never ignored.
- **Workspaces:** a tracked `go.work` is synced after updates. Workspace
  vendoring (`go work vendor`) and stdlib fixes in workspace repositories,
  whose toolchain comes from `go.work`, are left for review.
- **Kubernetes:** set `k8s-version-guard: true` to treat `k8s.io` minor bumps
  as breaking.
- **Go directive:** a dependency may raise `go` only up to the detected build
  image's Go version, or within the same minor when no image is known.
- **Standard library:** a stdlib fix sets the `toolchain` directive, never
  `go`, so consumers are not forced to upgrade. It never lowers a module's
  effective Go. When the build image's Go is unknown, only same-minor patch
  bumps are applied; cross-minor fixes need review. Images older than Go 1.21
  cannot read `toolchain`. A build image still compiles with its own Go:
  products built by a pinned builder (for example OpenShift ART images) are
  patched only when that builder is.
- **Build image:** set `build-image` (or `CVE_FIX_BUILD_IMAGE`) to the image
  that compiles release binaries so Go bumps are bounded by its real Go
  version. For OpenShift, use the `.ci-operator.yaml` build root (for example
  `registry.ci.openshift.org/openshift/release:rhel-9-release-golang-1.26-openshift-5.0`)
  after `oc registry login`. Unknown builders limit bumps to the same minor.
- **Host toolchain:** a distribution default `GOEXPERIMENT` (Fedora sets
  `nodwarf5`) produces binaries Grype cannot match, so runs build with
  upstream defaults unless `GOEXPERIMENT` is set explicitly.
- **No fix available:** an exact `.grype.yaml` ignore, scoped to the reporting
  module when known, that keeps Grype's `fix-state` so it stops matching once
  a fix is published. A repository-wide and a module-scoped ignore for the
  same package and CVE is a policy conflict that blocks the PR command.
- **Repository Grype config:** `.grype.yaml` ignores and excludes apply, but
  `only-notfixed` and `ignore-wontfix` are overridden so fixable findings
  always reach the gate. Invalid or broad inherited ignore rules stop remediation
  before clean, build or scan; maintainers must review that policy first.
- **Reviewer:** reads prefetched evidence from an empty working directory with
  no tools (Claude: `--tools ""`, no MCP servers or project settings; Codex:
  read-only sandbox). Only its
  `UNRESOLVED` verdicts for packages already under review affect the result.

## Configuration

A `.cve-fix.yaml` committed in the target branch's root overrides detection;
every field is optional. `CVE_FIX_BUILD_CMD`, `CVE_FIX_CLEAN_CMD`, `CVE_FIX_TEST_CMD`, and
`CVE_FIX_BUILD_IMAGE` override the file for one run.

| Field | Default |
| --- | --- |
| `build-command` | `make build` when a build target exists |
| `clean-command` | `make clean` when a clean target exists |
| `test-command` | First of `make unit`, `make test`, `make test-unit`, `go test ./...` |
| `build-image` | None; its `go version` bounds Go directive and toolchain bumps |
| `k8s-version-guard` | `false`; `true` treats Kubernetes minor bumps as breaking |
| `upstream-org` | Owner of `origin`, used for the PR command |
| `unset-env` | None; variable names removed from build, test, and reviewer environments |

Repositories using Shipyard's Dapper wrapper build with `make build` inside
the container (forwarding `BUILD_UPX=false` and the run's `GOEXPERIMENT`),
test with `make unit`, take their build image from the branch
(`quay.io/submariner/shipyard-dapper-base:<branch>`), and run no automatic
clean.

## PR readiness

The PR command is withheld when tests fail, a rescan cannot confirm coverage
(failed build, degraded scanner database, packed binaries, empty catalog), the
base branch moved or could not be fetched, a commit lacks `Signed-off-by:`,
`make licensecheck` (when present) fails, or the branch touches files other
than `go.mod`, `go.sum`, `go.work*`, `vendor/`, and `.grype.yaml`. The
scripts never rebase, push, or change licensing policy.

The Summary reports configured commands, scan confirmation, test attempts with
their exits and tested commits, and verification/license status. Unconfigured or
unreached checks remain explicit.

Fetches use `origin` exactly as configured, non-interactively. Private
repositories need a working SSH key or agent; public ones work best with an
HTTPS fetch URL and an SSH `pushurl`.

For durable diagnostics, set `CVE_FIX_EVIDENCE_DIR` to a fresh directory outside
the repository. It retains raw scans, build/test/license logs, audit evidence
and phase results before temporary files are removed. Unreached phases remain
explicitly marked; the option preserves the normal remediation gates.

Timeouts: `CVE_FIX_BUILD_TIMEOUT` and `CVE_FIX_TEST_TIMEOUT` (1800 s each),
`CVE_FIX_SCAN_TIMEOUT` and `CVE_FIX_AGENT_TIMEOUT` (600 s),
`CVE_FIX_LICENSE_TIMEOUT` (300 s), `CVE_FIX_IMAGE_TIMEOUT` (180 s). A timeout
is an unverified result. Scanner limits apply per operation (such as a version
check, database update or scan); fallback and bounded termination/cleanup add time.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Zero packages cataloged | Grype skips virtual filesystems such as `/dev/shm`; move the checkout |
| CVE persists after update | Check `replace` directives and the reported fix version |
| New CVE after an update | The update was rolled back; review the reported finding |
| Stdlib CVEs hidden by a packer | Set a `build-command` that builds unpacked binaries |
| `git fetch` fails | Run it manually; see the remote notes above |
| Tests need `sudo` or other prompts | Set `test-command` (or `CVE_FIX_TEST_CMD`) to a non-interactive command |
| Temp directory full | `export TMPDIR=/path/with/space` |

## Development

```bash
bash plugins/fix-go-cves/test/test-lib.sh </dev/null
plugins/fix-go-cves/scripts/fix-all.sh [REPO] [BRANCH] </dev/null   # outside an agent session
```

The suite is hermetic (no network, scanner, or container runtime) and runs
with the repository's `make test`. Builds read stdin, so keep it at
`/dev/null` when running from a tool that leaves stdin open.
