# OCPBUGS Conventions

Project-specific conventions for creating bug reports in the OCPBUGS project.

## Project Information

| Field | Value |
|-------|-------|
| **Project Key** | OCPBUGS |
| **Full Name** | OpenShift Bugs |
| **Issue Types** | Bug only |
| **Used By** | All OpenShift product teams |

## Version Fields

### Affects Version/s (`versions`)

**Purpose:** Version where the bug was found.

- Prompt: "Which version did you encounter this bug in?"
- Common values: `4.19`, `4.20`, `4.21`, `4.22`
- Multiple versions can be specified
- MCP format: `[{"name": "4.21"}]`

### Target Version (`customfield_10855`)

**Purpose:** Version where the fix is targeted.

- Common default: `openshift-4.21` (or current development release)
- Override based on severity, backport requirements, or release schedule
- MCP format: `"openshift-4.21"` (string) — note: OCPBUGS uses a simple string format, unlike the generic `[{"id": "VERSION_ID"}]` array format used by other projects like CNTRLPLANE

**Never set** Fix Version/s (`fixVersions`) — managed by the release team.

## Component Requirements

Components are **team-specific**. OCPBUGS does not enforce component selection at the project level.

- Teams may have their own conventions (e.g., [HyperShift conventions](hypershift.md))
- If not specified, prompt: "Does this bug require a component? (optional)"

## MCP Tool Integration

Use `createJiraIssue` with `contentFormat: "markdown"`, project key `OCPBUGS`, issue type `Bug`:

- `versions`: affects version, e.g. `[{"name": "4.21"}]`
- `customfield_10855`: target version, e.g. `"openshift-4.21"`
- `labels`: `["ai-generated-jira"]`
- `security`: `{"name": "Red Hat Employee"}`
- `components`: set if required by team

## OCPBUGS-Specific Prompts

- **Affects Version** (required): "Which version did you encounter this bug in?" — show common versions: 4.19, 4.20, 4.21, 4.22
- **Target Version** (optional): "Which version should this be fixed in? (default: openshift-4.21)"

## Wrong Issue Type

If user tries to create a story/task/epic in OCPBUGS: inform them that OCPBUGS is for bugs only and suggest [CNTRLPLANE](cntrlplane.md) for stories/epics/features/tasks.

## Team-Specific Extensions

- **HyperShift team:** See [HyperShift conventions](hypershift.md) for component selection
