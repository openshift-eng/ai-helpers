# Collecting the reliability inventory

The collector is self-contained Python 3.9+ standard library code. It does not import another
plugin, require an experiment checkout, or assume existing evidence. Run it from this
skill directory, or use an absolute path to its `scripts/collect_runs.py`.

## Default: one release and all presubmits, last 24 hours

```bash
python3 scripts/collect_runs.py --release 5.1 --output ./reliability-run
```

`--release` is always required. The default `--scope all` collects **every job in that
Sippy release plus every job in `Presubmits`**, including successful, running, aborted,
and failed outcomes. It imposes no blocking-job or platform filter. The end timestamp
is frozen once when the command starts; the default window is the preceding 24 hours.
Do not restrict the default investigation to payload blockers or to failed results.

Use a new output directory per invocation. Downloads go to a unique directory below
`~/tmp/ci-reliability`, never `/tmp`; change that parent with `--scratch-dir`. Retain
small report evidence in the output directory and inspect the manifest's raw response
paths when more detail is needed. The caller owns scratch retention and cleanup.

## Filters and a reproducible window

```bash
python3 scripts/collect_runs.py --release 5.1 --hours 48 \
  --job-contains aws --job-contains upgrade --variant Platform:aws \
  --output ./aws-upgrade-reliability

python3 scripts/collect_runs.py --release 5.1 \
  --start 2026-09-01T00:00:00Z --end 2026-09-02T00:00:00Z \
  --scope release --output ./frozen-reliability
```

- `--scope all`: selected release plus `Presubmits` (default).
- `--scope release`: selected release only.
- `--scope presubmits`: `Presubmits` only; `--release` remains required for invocation consistency.
- `--scope blocking`: selected release only, admitted by exact release-controller evidence.
- Repeated `--job` values are **OR** across exact job names.
- Repeated `--job-contains` values are **AND** across case-sensitive substrings.
- Repeated `--variant` values are **AND** across exact Sippy variant strings, such as
  `Platform:aws` and `Architecture:amd64`.
- Different filter categories combine with AND. Filters also apply to presubmits.
- `--hours` defaults to 24 and cannot accompany explicit bounds. `--start` and `--end`
  must be supplied together, with UTC `Z` or `+00:00`. Start is inclusive; end is exclusive.

Sippy requests use supported `>=`/`<=` timestamp filters and unique-ID sorting. The
collector independently enforces `[start,end)` after parsing timestamps. It paginates
all outcomes, retains raw responses, and deduplicates IDs without floating-point
conversion. IDs in normalized output are decimal strings, safe for JavaScript consumers.

## Bounded collection and honest completeness

Defaults are 500 rows per page, at most 100 pages per source, 10,000 selected unique
runs, 256 MiB downloaded, 1,000 HTTP requests including retries and metadata, and a
30-minute acquisition budget. One network operation has a maximum 60-second timeout.
An in-flight operation can finish after the overall deadline; another read/request
will not start after that deadline. HTTP 429 and transient server/network failures
receive bounded exponential backoff; requests run sequentially.

Change limits with `--per-page`, `--max-pages`, `--max-runs`, `--max-download-mb`,
`--max-requests`, `--max-seconds`, and `--timeout`. Every limit and observed usage is
recorded. A run/page/download limit, request failure, unstable server total, repeated
page, or unresolved blocking membership yields **`complete: false` and exit status 2**.
Successfully collected rows are still written; status 2 is not permission to call the
sample exhaustive. Exit 0 means the requested inventory and filter proof passed the
collector's checks, not that Sippy ingested every Prow execution or that every run has
finished. Read `errors`, `incomplete_reasons`, and per-source totals before proceeding.

The max-runs cap counts selected unique runs across both sources. Reaching the cap
while additional candidates remain can leave later sources uncollected. Narrow the
window or explicitly increase an appropriate budget; do not silently ignore missing
presubmits. A complete empty result is valid if the source total and applied filters
support it. An empty partial result means acquisition or verification was insufficient.

## Blocking mode: actual release-controller attempts

```bash
python3 scripts/collect_runs.py --release 5.1 --scope blocking \
  --output ./blocking-reliability
```

For each candidate, the collector fetches its actual `prowjob.json`, verifies job/ID,
reads the payload tag and architecture, and retrieves that payload's release-controller
JSON. It admits a run only when its exact ID **and** job occur in
`results.blockingJobs[*].url` or `previousAttemptURLs`. Exact informing references are
excluded. Neither a suggestive job name, a `verify` annotation, a matching test name,
nor membership in the same job family proves blocking status. A Prow execution with
no payload annotation is excluded as having no payload association.

The public endpoints used in the reliability experiment are:

```text
https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/{stream}/tags
https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/{stream}/release/{tag}
https://multi.ocp.releases.ci.openshift.org/api/v1/releasestream/{stream}/release/{tag}
```

For example, a tag `5.1.0-0.nightly-2026-09-01-000000` belongs to stream
`5.1.0-0.nightly`; a `nightly-multi` tag uses the multi controller. The collector also
supports `arm64`, `ppc64le`, and `s390x` architecture hosts from Prow annotations.
Tags outside the timestamped nightly/CI naming convention require an archived detail
snapshot. Do not guess the stable stream from a release number.

The controller can garbage-collect payloads and earlier attempts. Those candidates
remain in `blocking_unverified` and make the collection incomplete. This is a real
evidence gap, not a reason to fall back to name matching. The all-results default has
no release-controller dependency and remains useful when blocking proof is unavailable.

### Reusing controller snapshots without constructing a custom schema

When release-controller detail files already exist, pass their directory directly:

```bash
python3 scripts/collect_runs.py --release 5.1 --scope blocking \
  --blocking-snapshot ./controller-details --output ./blocking-reliability
```

The directory's immediate `*.json` files can be the raw JSON responses from
`/api/v1/releasestream/{stream}/release/{tag}`. Keep these detail files separate from
unrelated JSON. A tags-list response alone does not prove any attempt's blocking role.
The agent can fetch the tags endpoint, select the relevant stream payloads, and save
their detail responses to this directory under the same download/scratch discipline.
The collector reuses exact current/prior attempt references before making metadata
requests; unmatched candidates still use live verification. Local snapshot paths are
retained as proof provenance.

Alternatively `--blocking-evidence FILE` accepts one raw detail document or an
archive that preserves public source URLs:

```json
{
  "snapshots": [
    {
      "source_url": "https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/STREAM/release/TAG",
      "document": {"name": "TAG", "results": {"blockingJobs": {}}}
    }
  ]
}
```

Use actual downloaded documents, not manually invented attempt mappings. Conflicting
blocking/informing evidence fails closed. An empty `blockingJobs` map proves no run
is blocking. Archived evidence must retain the exact attempt URL; it must not be
broadened to every execution of that job.

Blocking mode collects parent attempts; it does **not** expand aggregate or semantic
analysis dependencies. The investigation must inspect each failing parent's actual
selection artifacts, distinguish current-payload inputs from historical baseline
samples, and retain inferred/unknown relationships. Do not add parent and child counts
as independent failures or assume the analyzer itself launches component jobs.

## Output contract

- `OUTPUT/corpus/runs.jsonl`: one normalized record per unique run, with
  `run_id`, `job`, `url`, `timestamp`, `result`, `source_releases`, and the complete
  original `raw` row. Cross-source duplicates add `additional_raw` per additional
  source. Blocking rows carry `blocking_evidence` with exact reference and provenance.
- `OUTPUT/corpus/same_job_green_controls.json`: exact `(job,test)` pairs whose failed
  test names occur in both non-successful and successful runs, with both ID lists.
  This is a warning against causal attribution from a signature alone. Inspect JUnit
  lifecycle and passing retry twins before deciding which test actually failed the job.
- `OUTPUT/manifest.json`: frozen bounds, scope and filters, source pagination counts,
  errors/partial reasons, unknown blocking candidates, result counts, budgets, and
  raw response paths with URLs, fetch timestamps, and SHA-256 hashes.

Running outcomes are retained but excluded from failed-test green-control comparisons.
Aborted outcomes are retained; report them separately from test/install/upgrade failure.
Green controls apply only to the selected population and window. A positive test
control in an otherwise failed job is not an all-green job, and matching PR head SHA
alone does not prove identical tested source when base SHA or extra refs differ.

## Offline verification

From the repository root:

```bash
python3 -m unittest discover \
  -s plugins/ci-extras/skills/investigate-ci-reliability/scripts -p test_collect_runs.py -v
```

Tests mock all HTTP requests and use unique directories under `~/tmp/ci-reliability-tests`.
They cover pagination, ID precision and provenance, all statuses, filters, strict
bounds, partial results, budget stops, green controls, and exact blocking proof.
