# Sippy API Reference

Additional Sippy APIs that may be useful during analysis. These supplement the skills already available in the CI plugin.

## List Changes in a Payload

Fetch all changes in a payload that were not in the previous payload. This is an alternative to the `fetch-new-prs-in-payload` skill.

```
curl "https://sippy.dptools.openshift.org/api/payloads/diff?toPayload=<payload_tag>"
```

- **Parameters**: `toPayload` (required), `fromPayload` (optional, for checking a wider range)
- **When to use**: When you have a specific payload tag and want to see what changed. The `fetch-new-prs-in-payload` skill wraps this API.

## Historical Release Payloads

Sippy retains release payload metadata after older tags have been garbage
collected from the release controller. The `payload-snapshot` skill uses these
APIs automatically to restore the complete time-ordered payload history while
continuing to prefer release-controller data for tags that are still retained.

### List release tags

```text
GET /api/releases/tags
  ?release=<major.minor>
  &filter={"items":[
    {"columnField":"architecture","operatorValue":"equals","value":"amd64"},
    {"columnField":"stream","operatorValue":"equals","value":"nightly"}
  ]}
  &sortField=release_time
  &sort=desc
```

Important fields:

- `release_tag`: payload tag
- `previous_release_tag`: prior release used for payload comparison (not
  necessarily the immediately preceding assembled payload)
- `phase`, `release_time`, `architecture`, and `stream`: payload metadata
- `failed_job_names`: failed job summary

### List PRs introduced by a payload

```text
GET /api/releases/pull_requests
  ?filter={"items":[
    {"columnField":"release_tag","operatorValue":"equals","value":"<payload-tag>"}
  ]}
  &sortField=pull_request_id
  &sort=asc
  &limit=1000
```

Each row includes `url`, `pull_request_id`, component `name`, `description`,
and (when present) `bug_url`. When the chronological predecessor is known,
`payload-snapshot` first uses `/api/payloads/diff` to retain an incremental
changelog. This per-payload endpoint is the fallback when that diff cannot be
computed.

### List payload job runs

```text
GET /api/releases/job_runs
  ?filter={"items":[
    {"columnField":"release_tag","operatorValue":"equals","value":"<payload-tag>"}
  ]}
  &sortField=kind
  &sort=asc
  &limit=1000
```

Each row includes `job_name`, `kind` (`Blocking` or `Informing`), `state`,
`url`, and `retries`.

### Payload UI

```text
https://sippy.dptools.openshift.org/sippy-ng/release/<release>/tags/<payload-tag>
```

Sippy does not preserve every release-controller-only field. In particular,
its PR data has no `nodeImageStreams` RHCOS RPM diff, and its job data does
not include release-controller async jobs or `previousAttemptURLs`.
