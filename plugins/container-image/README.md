# Container Image Plugin

Container image analysis tools: multi-source CVE scanning and triage.

## Skill

### `cve-scan`

`/container-image:cve-scan [<image>] [--output=triage|remediation|evidence] [--severity=critical,important,moderate,low]`

Scans a container image for CVEs using two complementary sources at once — Red Hat's
own security data (Hydra Security Data API + Pyxis catalog) and the open-source scanners
grype, trivy, and govulncheck — then merges them into one de-duplicated report and
applies **AI triage** on top: it prioritizes findings by real-world risk, explains
coverage gaps (container-level CVEs that NVD scanners miss vs NVD-only findings),
adjudicates severity disagreements with Red Hat as authoritative, and can produce a
remediation plan or an auditable compliance-evidence narrative.

The scanners run **only inside a container image** that the skill builds from the bundled
toolkit — nothing is installed on your host. The skill uses `docker` or `podman` (chosen
from your session; it asks if both are present and tells you to install one if neither is).

**Examples:**

```text
/container-image:cve-scan registry.access.redhat.com/ubi9/ubi-micro:latest
/container-image:cve-scan quay.io/myorg/myapp:tag --output=triage,remediation
/container-image:cve-scan --severity=critical,important          # infer image from session
```

If `<image>` is omitted, the skill infers the target from the current session (locally
built images, a `Dockerfile` in the working directory, image refs discussed earlier, the
repo's component image) and asks you to pick when there is more than one candidate.

**Features:**

- Merged report with **PROVENANCE** (which tools found each CVE), **COVERAGE**
  (Red-Hat-only / scanner-only / both), and **DISAGREE** (severity disagreements).
- Red Hat backport-aware fix status (no false positives from backported fixes).
- Container-only execution; no host installs.
- CI-style gate decision from the scan exit code (`0` clean / `1` Critical or Important
  present / `2` error / `3` incomplete Red Hat data).

**Prerequisites:**

- `docker` or `podman` available in the session.
- Network access to Red Hat's security-data APIs and to the target registry
  (`REGISTRY_AUTH_FILE` for authenticated registries). See
  [skills/cve-scan/references/scanning.md](skills/cve-scan/references/scanning.md).

## When to use this (and when not)

`cve-scan` works on a **built container image** — it scans the image's RPMs, Go
binaries, and layers and reports which CVEs affect the artifact you are about to ship,
with Red Hat's security data authoritative. Reach for a different plugin when the
question is about source code or a different stage of the lifecycle:

| Use instead | When |
|---|---|
| [`compliance`](../compliance/README.md) | You have the **Go source** and want call-graph reachability, source-impact analysis, CVE intelligence, or remediation planning / fix PRs — not just "is the image affected". |
| [`golang:fix-cve`](../golang/README.md) | You want to **remediate** a Go dependency CVE: patch or replace the module, rebuild, test, and rescan the repository. |
| [`golang:triage-fixed-cves`](../golang/README.md) | You want to triage **Go stdlib** CVEs against an OpenShift release by the Go version each component was built with. |
| [`node-cve`](../node-cve/README.md) | You are triaging CVEs across **Node-team** repositories. |

These are complementary: use `cve-scan` to decide *whether an image is affected and how
urgently*, then hand off to `compliance` / `golang` for source-level reachability and
remediation. Shrinking the CVE surface by migrating to a smaller base image is out of
scope for this skill.

## Installation

```bash
/plugin install container-image@ai-helpers
```
