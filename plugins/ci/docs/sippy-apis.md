# Sippy API Reference

Additional Sippy APIs that may be useful during analysis. These supplement the skills already available in the CI plugin.

## List Changes in a Payload

Fetch all changes in a payload that were not in the previous payload. This is an alternative to the `fetch-new-prs-in-payload` skill.

```
curl "https://sippy.dptools.openshift.org/api/payloads/diff?toPayload=<payload_tag>"
```

- **Parameters**: `toPayload` (required), `fromPayload` (optional, for checking a wider range)
- **When to use**: When you have a specific payload tag and want to see what changed. The `fetch-new-prs-in-payload` skill wraps this API.
