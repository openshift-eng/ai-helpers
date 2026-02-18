# Sippy API Reference

Additional Sippy APIs that may be useful during analysis. These supplement the skills already available in the CI plugin.

## List Test Failures from a PR

Fetch all test failures from a specific PR (both presubmit and /payload jobs). Useful when a suspect PR has been identified and you want to check if it caused test failures.

```
curl "https://sippy.dptools.openshift.org/api/pull_requests/test_results?org=<org>&repo=<repo>&pr_number=<number>&start_date=<YYYY-MM-DD>&end_date=<YYYY-MM-DD>"
```

- **Parameters**: `org`, `repo`, `pr_number`, `start_date`, `end_date`
- **When to use**: After identifying a suspect PR in step 9, to verify if it caused failures in CI before merging.

## List Changes in a Payload

Fetch all changes in a payload that were not in the previous payload. This is an alternative to the `fetch-new-prs-in-payload` skill.

```
curl "https://sippy.dptools.openshift.org/api/payloads/diff?toPayload=<payload_tag>"
```

- **Parameters**: `toPayload` (required), `fromPayload` (optional, for checking a wider range)
- **When to use**: When you have a specific payload tag and want to see what changed. The `fetch-new-prs-in-payload` skill wraps this API.
