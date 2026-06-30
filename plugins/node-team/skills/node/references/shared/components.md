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

| OCPBUGS Component | Downstream Fork | Upstream Repo | Branch Pattern | Language |
|---|---|---|---|---|
| Node / CRI-O | https://github.com/openshift/cri-o | https://github.com/cri-o/cri-o | `release-1.X` | Go |
| Node / Kubelet | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-1.X` | Go |
| Node / CPU manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-1.X` | Go |
| Node / Device Manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-1.X` | Go |
| Node / Memory manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-1.X` | Go |
| Node / Numa aware Scheduling | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-1.X` | Go |
| Node / Pod resource API | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-1.X` | Go |
| Node / Topology manager | https://github.com/openshift/kubernetes | https://github.com/kubernetes/kubernetes | `release-1.X` | Go |
| Driver Toolkit | https://github.com/openshift/driver-toolkit | - | `release-4.Y` | Go |
| Machine Config Operator | https://github.com/openshift/machine-config-operator | - | `release-4.Y` | Go |
| Node / Kueue | - | https://github.com/kubernetes-sigs/kueue | - | Go |
| Node / Kueue (operator) | https://github.com/openshift/kueue-operator | - | `release-4.Y` | Go |
| Node / Node Problem Detector | https://github.com/openshift/node-problem-detector | https://github.com/kubernetes/node-problem-detector | `release-4.Y` | Go |
| Node / Instaslice-operator | https://github.com/openshift/instaslice-operator | - | `release-4.Y` | Go |

## pscomponent Label Mapping

Some CVE trackers use `pscomponent:` labels instead of Jira component names.
Map these to downstream forks:

| Label | Downstream Fork | Branch Pattern | Language |
|---|---|---|---|
| `pscomponent:cadvisor` | https://github.com/openshift/google-cadvisor | `release-4.Y` | Go |
| `pscomponent:conmon` | https://github.com/openshift/conmon | `release-4.Y` | C |
| `pscomponent:conmon-rs` | https://github.com/openshift/conmon-rs | `release-4.Y` | Rust + Go |
| `pscomponent:cri-tools` | https://github.com/openshift/cri-tools | `release-1.X` | Go |

Upstream repos for pscomponent-mapped projects: conmon (`github.com/containers/conmon`),
conmon-rs (`github.com/containers/conmon-rs`), cri-tools (`github.com/kubernetes-sigs/cri-tools`),
cadvisor (`github.com/google/cadvisor`).

## Day-to-Day Dev Shorthand

Quick lookup for development tasks (clone the downstream fork for OCP work,
upstream for community contributions):

| Jira Label / Component | Repo short name |
|-------------------------|-----------------|
| `crio` | cri-o |
| `kubelet` | kubernetes |
| `mco` | machine-config-operator |
| `crun` | crun |
| `conmonrs` | conmon-rs |
| `kueue` | kueue-operator |

## Sub-teams

| Team | Sprint filter | Roster file | Bug components |
|------|--------------|-------------|----------------|
| Core | `Node Core` | `team-roster-core.json` | All Node components not listed under another sub-team |
| DRA/Devices | `Node Devices` | `team-roster-dra.json` | Node / Device Manager, Node / Instaslice-operator |
| Kueue | `OCP Kueue` | `team-roster-kueue.json` | Node / Kueue |
