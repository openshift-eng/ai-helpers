---
name: check-pr-ci-status
description: Check CI status on a GitHub PR and detect new failures. Use when monitoring a PR for CI regressions, deciding if CI failures need attention, or building a review-response loop.
---

# Check PR CI Status

Check the CI check status on a GitHub pull request and detect whether any failures are new since the last check. This enables efficient CI monitoring — only act on new failures, not stale ones that were already addressed.

## When to Use This Skill

Use this skill when you need to:

- Check if a PR has any failing CI checks
- Detect new CI failures that appeared since your last check
- Decide whether CI failures need attention in an agentic workflow
- Build a polling loop that reacts to CI status changes

## Prerequisites

1. **`gh` CLI**: Authenticated with `gh auth login`
2. **Repository read access**: The token must have permission to view PR check status

## Implementation

### Basic usage

```bash
result=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/check-pr-ci-status/check_pr_ci_status.sh" \
  --repo owner/repo \
  --pr 123)
```

### With previous failure tracking

```bash
result=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/check-pr-ci-status/check_pr_ci_status.sh" \
  --repo owner/repo \
  --pr 123 \
  --previous-failures "ci/prow/e2e-aws ci/prow/unit")
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--repo` | Yes | GitHub repository in `owner/repo` format |
| `--pr` | Yes | Pull request number |
| `--previous-failures` | No | Space-separated check names that were failing on the last check |

### Output

JSON on stdout:

```json
{
  "failing_checks": [
    {"name": "ci/prow/e2e-aws", "state": "FAILURE"},
    {"name": "ci/prow/unit", "state": "FAILURE"}
  ],
  "failing_count": 2,
  "failing_names": "ci/prow/e2e-aws ci/prow/unit",
  "has_new_failures": true,
  "formatted": "- ci/prow/e2e-aws (FAILURE)\n- ci/prow/unit (FAILURE)"
}
```

### Using in a polling loop

The `failing_names` field is designed to be passed back as `--previous-failures` on the next call:

```bash
LAST_FAILURES=""

while true; do
  sleep 300

  result=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/check-pr-ci-status/check_pr_ci_status.sh" \
    --repo owner/repo --pr 123 --previous-failures "$LAST_FAILURES")

  has_new=$(echo "$result" | jq -r '.has_new_failures')
  if [[ "$has_new" == "true" ]]; then
    formatted=$(echo "$result" | jq -r '.formatted')
    echo "New CI failures detected:"
    echo "$formatted"
    # Address failures...
  fi

  LAST_FAILURES=$(echo "$result" | jq -r '.failing_names')
done
```

## How It Works

1. Runs `gh pr checks` to get all check statuses
2. Filters to checks with state FAIL or FAILURE
3. Compares current failing check names against `--previous-failures`
4. Reports `has_new_failures: true` if the set of failing checks has changed
5. Returns both structured data and pre-formatted text

## New Failure Detection

A failure is considered "new" when the set of failing check names differs from `--previous-failures`. This means:
- A check that was passing and is now failing triggers `has_new_failures`
- A check that was already failing stays in the list but doesn't trigger by itself
- A check that was failing and is now passing changes the set and triggers too

If `--previous-failures` is not provided, any failing check is considered new.

## See Also

- Related Skill: `fetch-pr-comments` — Fetch trusted PR review comments
- Related Skill: `upload-screenshot` — Upload images to GitHub for PR comments
