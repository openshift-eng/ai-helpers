---
name: Fetch Related Triages
description: Fetch existing triages and untriaged regressions related to a given regression
---

# Fetch Related Triages

Queries the Sippy API to find existing triage records and untriaged regressions that may be related to a given Component Readiness regression. The API matches based on similarly named tests and shared job runs (using the complete `job_runs` history tracked across each regression's entire lifetime).

## When to Use This Skill

- During regression analysis to find existing triages that could cover the current regression
- To find untriaged regressions that share the same root cause and should be triaged together
- To avoid filing duplicate bugs when a related triage already exists

## API Endpoint

```
GET https://sippy.dptools.openshift.org/api/component_readiness/regressions/{id}/matches
```

No authentication required (uses production Sippy URL).

## Usage

```bash
# Fetch all related triages (default: all confidence levels)
python3 plugins/ci/skills/fetch-related-triages/fetch_related_triages.py 35479

# Filter to high confidence matches only
python3 plugins/ci/skills/fetch-related-triages/fetch_related_triages.py 35479 --min-confidence 5

# Human-readable summary
python3 plugins/ci/skills/fetch-related-triages/fetch_related_triages.py 35479 --format summary
```

## Arguments

- `regression_id` (required): The Component Readiness regression ID
- `--min-confidence` (optional): Minimum confidence level to include (1-10, default: 1)
- `--format` (optional): Output format — `json` (default) or `summary`

## Confidence Levels

The API assigns a confidence level (1-10) to each match:

- **10**: High confidence — the triage's regressions include the same test (exact test_id match) or very closely related tests with shared failure patterns
- **5**: Medium confidence — similarly named tests matched by edit distance, suggesting related tests in the same area
- **2**: Low confidence — regressions share the same job runs (identified via the `job_runs` history tracked across each regression's lifetime), which may indicate a shared root cause but could be coincidental in mass failure scenarios

## Output Format

### JSON output

```json
{
  "success": true,
  "regression_id": 35479,
  "triaged_matches": [
    {
      "triage_id": 370,
      "triage_ui_url": "https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages/370",
      "jira_key": "OCPBUGS-76612",
      "jira_url": "https://redhat.atlassian.net/browse/OCPBUGS-76612",
      "jira_status": "New",
      "jira_summary": "Component Readiness: [Networking / ovn-kubernetes] ...",
      "triage_type": "test",
      "triage_description": "...",
      "confidence_level": 10,
      "regressions_on_triage": [
        {
          "id": 35217,
          "test_name": "...",
          "test_id": "...",
          "component": "Networking / ovn-kubernetes",
          "variants": ["..."],
          "opened": "...",
          "closed": null,
          "triages": null,
          "last_failure": "..."
        }
      ]
    }
  ],
  "untriaged_regressions": [
    {
      "id": 35480,
      "test_name": "...",
      "test_id": "...",
      "component": "...",
      "variants": ["..."],
      "opened": "...",
      "closed": null,
      "triages": null,
      "last_failure": "...",
      "match_reason": "similarly_named_test",
      "edit_distance": 1
    }
  ]
}
```

### Key fields

- **triaged_matches**: Existing triage records that look related, sorted by confidence (highest first). Each includes the JIRA bug info and the regressions already on the triage.
- **untriaged_regressions**: Open regressions that are not yet triaged but appear related. These are candidates to be triaged together with the current regression. Each includes a `match_reason` field:
  - `similarly_named_test`: Matched by test name edit distance (lower edit_distance = more similar)
  - `same_last_failure`: Matched by sharing the same job runs (identified via the `job_runs` history tracked across each regression's lifetime)

## How the API Matches Work

The API uses two strategies to find related triages:

1. **Similarly named tests**: Compares the regression's test name against test names on existing triages using edit distance. An edit distance of 0 means the same test name (different variants); 1-2 means very similar test names (e.g., L2 vs L3 variant of the same test).

2. **Shared job runs**: Finds regressions that were observed in the same job runs. The regression data now includes a complete `job_runs` list covering all runs where the failure was observed throughout the regression's entire life (not just the last reporting period). Sippy uses this data to find other regressions that failed in the same Prow job runs, which is a strong signal they share the same root cause (e.g., a mass CI infrastructure failure or a broad product regression). Regressions with high `test_failures` counts in their shared runs are more likely to be collateral damage from a larger issue.

## Notes

- Uses the production Sippy URL (no port-forward needed)
- No authentication required
- The script deduplicates untriaged regressions by ID
- Only open, untriaged regressions are included in `untriaged_regressions`
- Triaged matches are sorted by confidence level (highest first)
- The 60-second timeout handles the potentially large response
