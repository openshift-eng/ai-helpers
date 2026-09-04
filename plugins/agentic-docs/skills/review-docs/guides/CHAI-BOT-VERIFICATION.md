# Cross-Repo Claim Verification via chai-bot

Verify all cross-repo claims that could not be resolved locally.

## Step 1 — Confirm the selected Chai Bot access path

- [ ] Use the access path selected in `SKILL.md`
- [ ] If hosted: use the callable Chai Bot knowledge/search capability explicitly provided by the host; do not probe, configure, or call a second Chai Bot MCP server
- [ ] If external: call the available Chai Bot `ask_persona` MCP capability with a simple test question; hosts may normalize the server name differently
  - Tool not found → restart Claude Code to reload MCP servers
  - 401 → bearer token expired, request new token from the Chai Bot Slack app
  - Timeout → check VPN connection to the Red Hat network
  - See [plugin README](../../../README.md#setup) for external MCP setup details
- [ ] If Chai Bot is unavailable or the external test call fails, inform the user and skip to Phase 5 with cross-repo claims marked "unverified"

## Step 2 — Batch verification

Batch related claims into grouped queries to reduce round-trips — each call takes ~15-25 seconds. Group all field claims for the same API type into one query, all convention claims for the same repo into one query, all enhancement references into one query, etc.

- [ ] Verify ALL cross-repo claims — prioritize high-risk claims first (API fields, feature gate definitions, cross-component behavior)
- [ ] Parse responses for confirmations, contradictions, or unknowns
- [ ] Classify each chai-bot response by confidence:
  - **Confirmed** — response cites specific files, structs, or line references that match the claim
  - **Contradicted** — response cites evidence that conflicts with the claim
  - **Unverified** — response is hedged ("I think", "probably", "I'm not sure"), lacks source references, or chai-bot was unavailable. These MUST NOT be treated as confirmed
- [ ] Expect 10-20+ queries for a comprehensive review

## Question construction templates

Substitute `{component}`, `{api-type}`, etc.:

```text
API fields (batch all fields for one type): "In github.com/openshift/api,
what fields are defined in the {api-type}Spec struct? Please list field
names, types, and any documented default values from the actual Go type
definition."

Feature gates (batch per operator): "What feature gates are defined for
{component} in openshift/api? List gate names, stages, and version
information."

Enhancements (batch related): "Do the following enhancements exist in
openshift/enhancements, and do they match the claimed descriptions?
1. enhancements/{area}/{enhancement-file-1}.md
2. enhancements/{area}/{enhancement-file-2}.md"

Terminology: "In the official OpenShift documentation, how is {component}
described? What is the correct terminology?"

Cross-component: "How does {other-component} interact with {component}
during {operation}?"

Convention check: "What are the platform conventions for {pattern} in
OpenShift operators? Does the pattern used by {component} match?"
```
