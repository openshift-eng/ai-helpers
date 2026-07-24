---
description: List, search, and inspect Sippy Symptoms and Labels (known CI failure signatures)
argument-hint: "[search-text]"
---

## Name

ci:list-symptoms

## Synopsis

```text
/ci:list-symptoms [search-text]
```

## Description

The `ci:list-symptoms` command lists and searches Sippy Symptoms — known-failure signatures for OpenShift CI that automatically apply human-readable Labels (like `InfraFailure`) to job runs when their artifact files match a pattern. Use it to browse the symptom catalog, check whether a failure pattern already has a symptom before creating one, look up what a label means, or find which symptoms apply a given label. No authentication is required.

## Implementation

1. **Load the skill**: Use the `list-symptoms` skill, which documents all script flags and API details.

2. **Run the query**:
   - No arguments — list all symptoms:
     ```bash
     python3 plugins/ci/skills/list-symptoms/list_symptoms.py --format summary
     ```
   - With search text (`$1`) — case-insensitive search over symptom id, summary, and match string:
     ```bash
     python3 plugins/ci/skills/list-symptoms/list_symptoms.py --search "<search-text>" --format summary
     ```
   - If the user asks about labels rather than symptoms, add `--labels`; to filter by a label a symptom applies, use `--label <label-id>`; to fetch a single item, use `--id <id>`.

3. **Present the results**: Show the matching symptoms (or labels) with their summary, matcher type, file pattern, match string, and applied labels. If nothing matches, say so and suggest broader search text or listing everything.

## Return Value

- **Format**: Human-readable summary (one block per symptom or label) plus a total count
- **Key fields**: id, summary, matcher_type (string|regex|none|cel), file_pattern, match_string, label_ids, updated_by/updated_at
- **Labels mode**: id, label_title, explanation, hide_display_contexts

## Examples

1. **List all symptoms**:
   ```text
   /ci:list-symptoms
   ```

2. **Search for symptoms about credentials**:
   ```text
   /ci:list-symptoms credentials
   ```

3. **Ask about labels**:
   ```text
   /ci:list-symptoms what does the InfraFailure label mean?
   ```

## Arguments

- $1: Search text (optional) — case-insensitive match over symptom id, summary, and match string. If omitted, all symptoms are listed.

## Skills Used

- `list-symptoms`: Queries the public Sippy symptoms/labels API (read-only, no auth)
