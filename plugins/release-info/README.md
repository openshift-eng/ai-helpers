# release-info

OCP release information plugin providing:

- **Product Pages MCP** — queries Red Hat Product Pages for release schedules, milestones, GA dates, and program contacts
- **PR to Release Version** — traces a GitHub PR to the first OCP z-stream release that shipped it
- **Upgrade Path** — queries Cincinnati to find available OCP upgrade paths from a given version
- **Update Graph Visualizer** — generates links to the interactive upgrade graph visualizer

## Examples

Ask in natural language — the plugin picks the right tool automatically.

### Release schedules and milestones (Product Pages)

- "When is the GA date for OCP 4.18?"
- "What's the feature freeze date for 4.17?"
- "Show me the full schedule for OCP 4.21"
- "Who is the TPM for OpenShift Container Platform?"
- "What releases are currently in development?"
- "List all OCP releases under maintenance"

### Tracing a PR to a release (pr-to-release-version)

- "Which z-stream shipped PR https://github.com/openshift/hypershift/pull/7685 in 4.21?"
- "Has PR #1893 from cluster-kube-apiserver-operator landed in any 4.17 z-stream?"
- "When did the fix for OCPBUGS-76447 ship?"

### Upgrade paths (upgrade-path)

- "What upgrades are available from 4.16.3?"
- "Can a cluster on 4.16.3 upgrade to 4.17.8?"
- "Is 4.17.12 in the stable channel?"
- "Show upgrade paths from 4.14.10 on arm64"
- "What EUS upgrade options exist from 4.14.35?"

### Upgrade graph visualization (update-graph)

- "Show me the upgrade graph for 4.17"
- "Visualize the fast channel for 4.16"
- "Show the candidate graph for 4.18"

### Combining tools

- "My fix is in PR #7685 on openshift/hypershift. Has it shipped in 4.21, and can customers on 4.21.10 upgrade to get it?"
- "When is 4.18 GA, and what does the current upgrade graph look like for the stable channel?"

## Skills

### product-pages (MCP)

Connects to the Red Hat Product Pages MCP server, providing access to release schedules, milestones, lifecycle phases, and program contacts. Authentication is handled via browser-based OIDC flow on first use.

**Prerequisites:** Red Hat SSO credentials (Kerberos/OIDC).

### pr-to-release-version

Determines which OCP z-stream release first shipped a given GitHub PR. Works for any repo that ships a component in the OCP release payload.

**Prerequisites:** `oc`, `gh` (authenticated), `jq`, `curl`, and a pull secret with access to `quay.io/openshift-release-dev`.

### upgrade-path

Queries the Cincinnati update graph API to find available upgrade paths from a given OCP version. Supports channel selection, architecture filtering, and reachability checks to specific target versions.

**Prerequisites:** `curl`, `jq` (no authentication needed).

### update-graph

Generates a direct link to the interactive OpenShift update graph visualizer pre-selecting the relevant channel. Supports stable, fast, candidate, and EUS channels.
