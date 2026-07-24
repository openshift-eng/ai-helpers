---
description: Create, update, or delete a Sippy Label (the human-readable tags applied by Symptoms)
argument-hint: "[create|update|delete] [label]"
---

## Name

ci:manage-labels

## Synopsis

```
/ci:manage-labels [create|update|delete] [label]
```

## Description

The `ci:manage-labels` command manages Sippy Labels — the human-readable tags (like `InfraFailure`) that Sippy Symptoms automatically apply to CI job runs when a known failure pattern matches the run's artifacts. Use it to create a new label before a symptom references it, fix a label's title or explanation, hide a label from certain UI contexts, or remove an obsolete label. Write operations require authentication to the sippy-auth API.

## Implementation

1. **Load the skill**: Use the `manage-labels` skill, which documents all script flags, field rules, and the auth workflow.

2. **Obtain the auth token**: Follow the `oc-auth` token-acquisition steps in the `manage-labels` skill (requires `oc login` to the DPCR cluster, `https://api.cr.j7t7.p1.openshiftapps.com:6443`).

3. **Perform the requested action**:
   - **Create** (confirm title and explanation with the user first):
     ```bash
     python3 plugins/ci/skills/manage-labels/manage_labels.py create \
       --token "$TOKEN" --title "<Label Title>" --explanation "<what this label means>"
     ```
     The label `id` is generated from the title unless `--id` is passed (max 80 chars).
   - **Update** (pass only the flags to change — the script merges with the existing label):
     ```bash
     python3 plugins/ci/skills/manage-labels/manage_labels.py update \
       --token "$TOKEN" --id <LabelID> --explanation "<new explanation>"
     ```
     Use `--hide-display-contexts "spyglass,metrics"` to hide the label in specific UI contexts (valid values: spyglass, metrics, jaq-options).
   - **Delete** — **first show the label to the user and get explicit confirmation**:
     ```bash
     python3 plugins/ci/skills/list-symptoms/list_symptoms.py --labels --id <LabelID> --format summary
     # ...after the user confirms:
     python3 plugins/ci/skills/manage-labels/manage_labels.py delete --token "$TOKEN" --id <LabelID>
     ```
     Never delete without the user confirming the specific label. Also check which symptoms still reference it (`list_symptoms.py --label <LabelID>`) and warn the user if any do.

4. **Present the result**: Show the API response. On 401/403, refresh the token via `oc-auth`.

## Return Value

- **Format**: JSON result from the sippy-auth API (or a success/failure summary with `--format summary`)
- **Key fields**: id, label_title, explanation, hide_display_contexts

## Examples

1. **Create a label**:
   ```
   /ci:manage-labels create a "Cluster DNS Flake" label for intermittent in-cluster DNS timeouts
   ```

2. **Update a label's explanation**:
   ```
   /ci:manage-labels update ClusterDNSFlake explanation to mention node-local DNS cache restarts
   ```

3. **Delete a label**:
   ```
   /ci:manage-labels delete ClusterDNSFlake
   ```

## Arguments

- $1: Action (optional) — `create`, `update`, or `delete`. If omitted, infer from the user's request or ask.
- $2: Label (optional) — label ID or title, plus any fields to set. If details are missing, ask the user.

## Skills Used

- `manage-labels`: Creates/updates/deletes labels via the authenticated Sippy API
- `list-symptoms`: Shows the label before delete and finds symptoms that reference it
- `oc-auth`: Provides the Bearer token for the sippy-auth API
