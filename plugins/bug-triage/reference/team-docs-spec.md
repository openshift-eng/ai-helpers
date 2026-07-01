# Team Documentation Specification

This document describes the format and contents of the team-specific documentation files that enrich the `/bug-triage:scrub` command. These files live in the team's own repository and are passed via the `--team-docs` argument.

## Directory Structure

```text
team-docs/
├── sub-areas.md           # Recommended: enables sub-area classification
├── routing-guide.md       # Recommended: enables misrouting detection
└── context/               # Optional: additional context docs
    ├── faqs.md            # Common issues and known patterns
    ├── triage-policies.md # Team-specific triage conventions
    └── *.md               # AGENTS.md copies, dev guides, etc.
```

## File Formats

### sub-areas.md (recommended)

Defines the team's sub-area taxonomy. Each sub-area is a markdown heading (`##`) followed by a prose description. The AI uses these descriptions to semantically classify bugs — write descriptions that explain what each area covers, not just keyword lists.

```markdown
# Sub-Area Taxonomy

## Router / HAProxy
The HAProxy-based router handles all ingress traffic in OpenShift. Issues in
this area involve haproxy configuration, reload behavior, route annotations,
route certificates, backend health checks, connection handling (408s, 503s),
sticky sessions, and TLS termination modes (reencrypt, edge, passthrough).

## Cluster Ingress Operator (CIO)
The operator that manages IngressController custom resources. Issues here
involve the ingresscontroller CR lifecycle, canary checks, default
certificates, wildcard policies, route admission, publish strategies, and
endpoint publishing.

## Non-functional Categories
If the issue is not about a functional problem in any sub-area above:
- Documentation — AGENTS.md, README, docs, enhancement proposals
- CI / Infrastructure — test infra, prow jobs, CI config, Dockerfiles
- Tooling — developer tooling, scripts, automation
- Dependency Management — go.mod bumps, image updates, ART reconciliation
```

### routing-guide.md (recommended)

Defines keyword groups for bugs that don't belong to this team, with suggested reroute targets. Each group is a markdown heading followed by keywords and a suggested component.

```markdown
# Bugs That Don't Belong to This Team

## OVN / SDN
Keywords: ovn, ovs, sdn, networkpolicy, egressip, egressfirewall, multus,
whereabouts, macvlan, ipvlan, ovn-kubernetes, ovnkube
Suggested component: Networking / ovn-kubernetes

## Load Balancer / Cloud
Keywords: metallb, load balancer type, cloud-provider, CCM, cloud controller,
keepalived, IPVS, speaker, frr, bgp peer
Suggested component: Networking / metal

## Service Mesh
Keywords: istio sidecar, service mesh, envoy proxy, ossm, maistra, kiali
Suggested component: Networking / service-mesh
```

### context/*.md (optional)

Any additional markdown files that provide useful context for triage. These are read by the AI and used to inform its analysis — common issues, known quirks, team conventions, component architecture docs, etc.

Examples:
- `faqs.md` — "HAProxy reload failures are commonly caused by X, Y, Z"
- `triage-policies.md` — "Bugs affecting the canary route should always be prioritized"
- Copies of `AGENTS.md` from component repos — gives the AI architectural context

## Graceful Degradation

All team docs are optional. If `--team-docs` is not provided, or if specific files are missing:

| Missing File | Impact |
|---|---|
| `sub-areas.md` | Sub-area reported as Jira component name (e.g., "Networking / router") |
| `routing-guide.md` | Routing check skipped; assumes correctly assigned |
| `context/*.md` | No extra context; core analysis proceeds normally |
