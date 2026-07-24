---
name: manage-labels
description: Create, update, or delete Sippy job run Labels (the human-readable tags applied by Symptoms) via the authenticated Sippy API
---

# Manage Labels

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

Labels must exist before a symptom can reference them, so create labels first when building a new symptom.

## When to Use This Skill

Use this skill when you need to:

- Create a new label before creating a symptom that applies it (see `manage-symptoms`)
- Fix a label's title or explanation
- Hide a label from certain UI contexts (Spyglass, metrics, jaq-options)
- Remove an obsolete label

## Prerequisites

1. **OpenShift CLI Authentication**: Required for authenticating to the sippy-auth API
   - Must be logged into the DPCR cluster via `oc login`
   - Cluster API: `https://api.cr.j7t7.p1.openshiftapps.com:6443`
   - Use the `oc-auth` skill to obtain the Bearer token

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Obtain Authentication Token

Use the `oc-auth` skill to obtain a Bearer token from the DPCR cluster:

```bash
# Get token from the DPCR cluster context
# The oc-auth skill's curl_with_token.sh uses this cluster for sippy-auth
DPCR_CLUSTER="https://api.cr.j7t7.p1.openshiftapps.com:6443"

# Find the oc context for the DPCR cluster and get the token
CONTEXT=$(oc config get-contexts -o name 2>/dev/null | while read -r ctx; do
  server=$(oc config view -o jsonpath="{.clusters[?(@.name=='$(oc config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.cluster}" 2>/dev/null)')].cluster.server}" 2>/dev/null || echo "")
  server_clean=$(echo "$server" | sed -E 's|^https?://||')
  if [ "$server_clean" = "api.cr.j7t7.p1.openshiftapps.com:6443" ]; then
    echo "$ctx"
    break
  fi
done)

if [ -z "$CONTEXT" ]; then
  echo "Error: Not logged into DPCR cluster. Please run: oc login $DPCR_CLUSTER"
  exit 1
fi

export SIPPY_TOKEN=$(oc whoami -t --context="$CONTEXT" 2>/dev/null)
if [ -z "$SIPPY_TOKEN" ]; then
  echo "Error: Failed to get token. Please re-authenticate to DPCR cluster."
  exit 1
fi
```

Prefer exporting `SIPPY_TOKEN` as above rather than passing `--token` on the command line — command-line arguments are visible in process listings. `--token` still works and takes precedence over the environment variable.

### Step 2: Create a Label

```bash
python3 plugins/ci/skills/manage-labels/manage_labels.py create \
  --title "Cluster DNS Flake" \
  --explanation "DNS lookups inside the cluster intermittently time out."
```

The label `id` is generated from the title by the server if you omit `--id`. Pass `--id` on create only if you need a specific identifier (max 80 characters).

### Step 3: Update a Label

Only pass the flags you want to change — the script fetches the existing label and merges, because the API's PUT is a full replacement:

```bash
python3 plugins/ci/skills/manage-labels/manage_labels.py update \
  --id ClusterDNSFlake \
  --explanation "DNS lookups inside the cluster intermittently time out. Usually caused by node-local DNS cache restarts."
```

To hide a label from certain UI contexts:

```bash
python3 plugins/ci/skills/manage-labels/manage_labels.py update \
  --id ClusterDNSFlake \
  --hide-display-contexts "spyglass,metrics"
```

### Step 4: Delete a Label

**Before deleting, you MUST show the label to the user (fetch it with the `list-symptoms` skill: `python3 plugins/ci/skills/list-symptoms/list_symptoms.py --labels --id <id> --format summary`) and get their explicit confirmation. Never run delete without the user confirming the specific label.**

```bash
python3 plugins/ci/skills/manage-labels/manage_labels.py delete \
  --id ClusterDNSFlake
```

**Arguments**:
- `action`: `create`, `update`, or `delete` (positional, required)

**Options**:
- `--token <token>`: Bearer token from the oc-auth skill (optional if the `SIPPY_TOKEN` environment variable is set, which is preferred — argv is visible in process listings; `--token` takes precedence)
- `--id <id>`: Label ID (required for update/delete; optional for create)
- `--title <text>`: Human-readable label title (required for create)
- `--explanation <text>`: Markdown explanation of the label
- `--hide-display-contexts <list>`: Comma-separated subset of `spyglass,metrics,jaq-options`
- `--format json|summary`: Output format (default: json)

## API Details

**Base URL (writes)**: `https://sippy-auth.dptools.openshift.org/api/jobs/labels`

- Create: `POST /api/jobs/labels`
- Update: `PUT /api/jobs/labels/{id}` (full replacement — the script fetches the existing label and merges your changes, so only pass flags you want to change)
- Delete: `DELETE /api/jobs/labels/{id}`

**Authentication**: `Authorization: Bearer <token>` from the DPCR cluster.

**Label fields**:

| Field | Description |
|-------|-------------|
| `id` | Immutable identifier, max 80 characters; generated from the title if omitted on create |
| `label_title` | Human-readable title; must be unique |
| `explanation` | Markdown explanation of what the label means |
| `hide_display_contexts` | Optional subset of `spyglass`, `metrics`, `jaq-options` — UI contexts where the label is hidden |

## Error Handling

- **401/403**: Token missing or expired — refresh it via the `oc-auth` skill.
- **501**: You hit the read-only Sippy instance with a write; make sure the sippy-auth base URL is used (the script already does).
- **400**: Server-side validation failure — the server's message is shown in the `detail` field of the output.
- **Client-side validation**: Missing title, over-long ID, or invalid `hide_display_contexts` values are caught locally and reported before any request is sent (exit 1).
- **Concurrent edits**: The update flow is read-merge-replace with no server-side concurrency control, so near-simultaneous edits can overwrite each other — re-check the label after updating if others may be editing.

**Exit Codes**:
- `0`: Success
- `1`: Validation error, API error, or network error

## See Also

- Related Skill: `oc-auth` (provides authentication tokens for sippy-auth)
- Related Skill: `list-symptoms` (list/inspect labels and symptoms, no auth needed)
- Related Skill: `manage-symptoms` (create/update/delete symptoms that apply labels)
- Related Command: `/ci:manage-labels` (invokes this skill)
