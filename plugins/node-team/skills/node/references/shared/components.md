# Node Team Components

Canonical component and repository data for all Node team plugins. Other
plugins (e.g. `node-cve`) reference this file instead of maintaining their own
copies.

## Jira Components (OCPBUGS)

The Jira saved filter **"Node Components"** (ID 91645) defines the general team
components. Prefer `filter = "Node Components"` in JQL over hardcoding this
list.

Full list (filter 91645): Node, Node / CRI-O, Node / Kubelet, Node / CPU
manager, Node / Memory manager, Node / Topology manager, Node / Numa aware
Scheduling, Node / Device Manager, Node / Pod resource API, Node / Node Problem
Detector, Node / Kueue, Node / Instaslice-operator

Additional components owned for CVE triage (not in filter 91645):
Driver Toolkit, Machine Config Operator

## Component to Repository Mapping

Analysis and CVE triage must target downstream forks at release branches. The
`main` branch may have newer dependencies that mask vulnerabilities present in
shipped releases.

Downstream forks under `github.com/openshift` use OCP-aligned branches
(`release-4.Y` or `release-5.Y`). Only the upstream repos use K8s-aligned
branches (`release-1.X`). See [version-map.md](version-map.md) to translate
between the two.

| OCPBUGS Component | Downstream Fork | Upstream Repo | Downstream Branch Pattern | Language |
|---|---|---|---|---|
| Node / CRI-O | https://github.com/openshift/cri-o | https://github.com/cri-o/cri-o | `release-4.Y`, `release-5.Y` | Go |
| Node / Kubelet | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-4.Y`, `release-5.Y` | Go |
| Node / CPU manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-4.Y`, `release-5.Y` | Go |
| Node / Device Manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-4.Y`, `release-5.Y` | Go |
| Node / Memory manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-4.Y`, `release-5.Y` | Go |
| Node / Numa aware Scheduling | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-4.Y`, `release-5.Y` | Go |
| Node / Pod resource API | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-4.Y`, `release-5.Y` | Go |
| Node / Topology manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-4.Y`, `release-5.Y` | Go |
| Driver Toolkit | https://github.com/openshift/driver-toolkit | - | `release-4.Y`, `release-5.Y` | Go |
| Machine Config Operator | https://github.com/openshift/machine-config-operator | - | `release-4.Y`, `release-5.Y` | Go |
| Node / Kueue | https://github.com/openshift/kubernetes-sigs-kueue (operand), https://github.com/openshift/kueue-operator (operator) | https://github.com/kubernetes-sigs/kueue | see Kueue note | Go |
| Node / Node Problem Detector | https://github.com/openshift/node-problem-detector | https://github.com/kubernetes/node-problem-detector | `release-4.Y`, `release-5.Y` | Go |
| Node / Instaslice-operator | https://github.com/openshift/instaslice-operator | - | `release-4.Y` (see note) | Go |
| Node | none (catch-all) | - | - | - |

Notes:

- **Node (bare component):** a catch-all with no single repository. Map the
  issue by its `pscomponent:` label if one is present. Otherwise read the
  summary and description to pick the affected repo from this table, and ask
  the user when it stays ambiguous. Never guess silently.
- **Kueue:** `Node / Kueue` is a single Jira component covering two repos.
  The operand fork `openshift/kubernetes-sigs-kueue` has `release-4.Y` and
  `release-5.Y` branches. The operator `openshift/kueue-operator` ships through
  OLM on its own cadence and uses `release-1.X` branches (operator version)
  next to a few older `release-4.Y` branches. Pick the repo from the affected
  package or image named in the issue.
- **Instaslice-operator:** only `release-4.18` to `release-4.20` exist
  (checked 2026-09). For other versions there is no branch to analyze. Do not
  fall back to `main`, whose newer dependencies can mask a vulnerability:
  node-cve classifies such trackers as Uncertain and says why.

Branch lists change with every release. Before cloning, confirm the branch
exists and fall back as described instead of failing:

```bash
git ls-remote --heads <fork-url> <branch>
```

## pscomponent Label Mapping

Some CVE trackers carry a `pscomponent:` label that names the affected package
more precisely than the Jira component. **When a tracker has both, the
`pscomponent:` label takes precedence over the Jira component for repo
mapping.** Trackers still need a Node team Jira component to show up in the
team queries; the label only refines which repo to analyze.

| Label | Repo to analyze | Ref | Language |
|---|---|---|---|
| `pscomponent:cadvisor` | https://github.com/openshift/kubernetes (vendored under `vendor/github.com/google/cadvisor`) | `release-4.Y`, `release-5.Y` | Go |
| `pscomponent:conmon` | https://github.com/containers/conmon (upstream only) | tag of the shipped RPM version | C |
| `pscomponent:conmon-rs` | https://github.com/containers/conmon-rs (upstream only) | tag of the shipped RPM version | Rust + Go |
| `pscomponent:cri-tools` | https://github.com/kubernetes-sigs/cri-tools (upstream only) | newest `v1.X.*` tag for the K8s minor of the OCP version | Go |
| `pscomponent:crun` | https://github.com/containers/crun (upstream only) | tag of the shipped RPM version | C |

Why upstream: these projects ship as RPMs built from upstream tags. The
`openshift/google-cadvisor`, `openshift/cri-tools` and `openshift/conmon-rs`
repos exist but carry no current OCP release branches (checked 2026-09), and
no public `openshift/conmon` or `openshift/crun` fork exists. If the shipped
RPM version is unknown, analyze the newest upstream tag and lower the
confidence of the result accordingly.

## Day-to-Day Dev Shorthand

Quick lookup for development tasks and `/node-team:setup` (clone the downstream
fork for OCP work, upstream for community contributions):

| Shorthand | Downstream fork | Upstream repo |
|-----------|-----------------|---------------|
| `crio` | https://github.com/openshift/cri-o | https://github.com/cri-o/cri-o |
| `kubelet` | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes |
| `mco` | https://github.com/openshift/machine-config-operator | - |
| `crun` | - | https://github.com/containers/crun |
| `conmon` | - | https://github.com/containers/conmon |
| `conmonrs` | - | https://github.com/containers/conmon-rs |
| `kueue` | https://github.com/openshift/kueue-operator | https://github.com/kubernetes-sigs/kueue |

The shorthands are command arguments, not Jira labels or component names.
Default branches differ per repo (`main` or `master`); read it with
`git symbolic-ref --short refs/remotes/origin/HEAD` instead of assuming.

## Sub-teams

| Team | `--sub-team` value | Sprint filter | Roster file | Bug components |
|------|--------------------|--------------|-------------|----------------|
| Core | `core` | `Node Core` | `team-roster-core.json` | All Node components not listed under another sub-team |
| DRA/Devices | `devices` | `Node Devices` | `team-roster-dra.json` | Node / Device Manager, Node / Instaslice-operator |
| Kueue | `kueue` | `OCP Kueue` | `team-roster-kueue.json` | Node / Kueue |

The DRA/Devices sub-team is called `devices` on the command line and in sprint
names, while its roster file keeps the historical `dra` name.
