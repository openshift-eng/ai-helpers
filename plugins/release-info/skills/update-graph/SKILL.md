---
name: OCP Update Graph Visualizer
description: "Generates a link to the interactive OpenShift update graph visualizer for a specific channel. Auto-applies when asked to show, visualize, or display the upgrade graph for an OCP version or channel."
---

# OCP Update Graph Visualizer

Generates a direct link to the interactive OpenShift update graph visualizer at `ctron.github.io/openshift-update-graph`, pre-selecting the relevant channel.

## When to Use This Skill

This skill automatically applies when:
- Asked to show or visualize the OCP upgrade graph
- Asked to display upgrade paths graphically
- Following up on upgrade path queries with a visual
- Asked "show me the graph for 4.17"

## How to Respond

Construct the URL using the pattern:

```text
https://ctron.github.io/openshift-update-graph#<channel>
```

### Channel Format

Channels follow the pattern `<type>-<minor>`:
- `stable-4.17` — production-ready releases
- `fast-4.17` — early access before stable promotion
- `candidate-4.17` — release candidates
- `eus-4.14` — Extended Update Support

### Examples

| User asks | URL |
|-----------|-----|
| "Show me the upgrade graph for 4.17" | `https://ctron.github.io/openshift-update-graph#stable-4.17` |
| "Visualize fast channel for 4.16" | `https://ctron.github.io/openshift-update-graph#fast-4.16` |
| "Show candidate graph for 4.18" | `https://ctron.github.io/openshift-update-graph#candidate-4.18` |
| "EUS upgrade graph for 4.14" | `https://ctron.github.io/openshift-update-graph#eus-4.14` |

### Behavior

1. Default to `stable` channel unless the user specifies otherwise
2. Present the link to the user and suggest they open it in a browser
3. If the user was just querying upgrade paths with the `upgrade-path` skill, include the matching graph link automatically
4. The visualizer supports Classic, Layered DAG, and Tangled Tree views — mention this if the user wants different perspectives on the graph
