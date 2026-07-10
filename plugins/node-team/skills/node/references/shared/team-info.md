# Node Team Info

Operational data for the OpenShift Node team. Referenced by
`node-team:overview`. For onboarding-specific setup instructions, see
`/node-onboarding:checklist`.

## Mission

The Node team owns the node-level runtime stack in OpenShift: everything
between the kubelet and the container. This includes CRI-O, kubelet
customizations, Machine Config Operator (MCO), node resource managers
(CPU, memory, topology, device, NUMA), Node Problem Detector, Kueue
operator, and related components.

## Responsibilities

- Maintain downstream forks of kubelet and node-related Kubernetes components
- Own CRI-O and conmonrs as the container runtime stack
- Manage Machine Config Operator for node configuration
- Handle resource management (CPU, memory, topology, device, NUMA managers)
- Triage and fix bugs in Node components (OCPBUGS)
- Track and remediate CVEs affecting Node components
- Package and ship RPMs (cri-tools, CRI-O) for each OCP release
- Participate in upstream SIG-Node community
- Onboard new team members

## Ceremonies

**Daily:**
- Review Node bugs
- Review PRs
- Standups (per sub-team)
- Feature work

**Weekly:**
- 1:1s with manager (weekly or every other week)

**Sprintly (every 3 weeks):**
- Node Team Planning
- Backlog Refinement
- Sprint Retrospective
- Sprint Demos

Sprints are three weeks long and follow the OpenShift Release Dates
spreadsheet. The "AOS Main Calendar" also has the sprints scheduled.

**Every Release (~4 months):**
- RFE refinement
- Feature planning
- Feature Complete / Code Complete milestones
- Quarterly goals

## Upstream Communities

The team participates in Kubernetes SIG-Node:
- SIG-Node weekly meeting (Tuesdays 1 PM EST)
- SIG-Node CI subgroup (Wednesdays 1 PM EST)
- Kubernetes contributor guide: https://www.kubernetes.dev/docs/guide/

## Slack Channels

- `#team-node` (private, team members)
- `#forum-ocp-node` (public)
- `#4-dev-triage` (general questions)
- User groups: `@node-team`, `@node-core-team`, `@openshift-kueue`

## Mailing List and Groups

- Mailing list / Google group: `aos-node@redhat.com`
- LDAP/Rover groups: `openshift-node-team`, `openshift-dev-node-team`

## Customer Support Tools

When investigating customer issues, the team uses:
- **SupportShell**: remote SSH environment for accessing customer
  must-gather archives without downloading them locally
- **yank**: downloads case attachments from S3 to SupportShell
- **omc**: provides `oc`/`kubectl`-style access to must-gather data offline

For setup instructions (hostnames, authentication), see
`/node-onboarding:checklist`.

## Key Links

- Homepage: `https://source.redhat.com/groups/public/openshift_node`
- Bug dashboard: `https://redhat.atlassian.net/jira/dashboards/12991`
- Bug filter: `https://redhat.atlassian.net/issues/?filter=83963`
- Sprint board: `https://redhat.atlassian.net/jira/software/c/projects/OCPNODE/boards/11478`
- Epics board: `https://redhat.atlassian.net/jira/software/c/projects/OCPNODE/boards/4383`
- Shared Drive: `https://drive.google.com/drive/folders/1rf7-AQVRnxTWqeVrLN7TRAchEDB9Q9xP`

## Plugin Routing

| Plugin | Command / Skill | When to use |
|--------|----------------|-------------|
| `node-team` | `/node-team:overview` | Understand team scope, navigate to the right tool |
| `node-team` | `/node-team:setup` | Set up a local development environment |
| `node-team` | `/node-team:preflight` | Verify GitHub and Jira credentials and required CLI tools |
| `node-team` | `/node-team:cleanup` | Purge cached plugin artifacts: triage reports, cloned repos, dist-git clones, Vagrant VMs, roster cache |
| `node-team` | `node-team:node` (skill) | General Node development, deployment, and debugging questions |
| `node-cve` | `/node-cve:triage` | CVE triage with reachability analysis |
| `node-bug` | `/node-bug:triage` | Bug triage, sub-team routing, assignment suggestions |
| `node-rpm` | `/node-rpm:bump` | Bump downstream RPM packages |
| `node-onboarding` | `/node-onboarding:checklist` | New team member onboarding |
| `node-onboarding` | `/node-onboarding:resources` | Quick-reference bookmarks and links |
