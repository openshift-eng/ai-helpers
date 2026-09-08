# Bounded Prow artifact helpers

Use `prow-job-analysis` for the debugging workflow. This document describes only the
bundled `prow_artifacts.py` acquisition interface and its limits.


The helper accepts a run URL in these forms:

- `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/JOB/BUILD_ID`
- `https://prow.ci.openshift.org/view/gs/test-platform-results/pr-logs/pull/ORG_REPO/PR/JOB/BUILD_ID`
- The equivalent `gs://test-platform-results/...`, `https://storage.googleapis.com/test-platform-results/...`, or OpenShift GCS browser `/gcs/test-platform-results/...` URL.

Supply the run root, not an artifact URL. Build IDs must contain at least ten digits. URLs outside the supported public results bucket, traversal paths, credentials, query strings, and fragments are rejected. Object names are relative to the validated run root.

Use `python3 scripts/prow_artifacts.py --help` from this skill directory. All subcommands write structured JSON to stdout; fatal acquisition errors use stderr and exit status 2. The default scratch directory is `~/tmp/ci-reliability`. Never silently substitute `/tmp`. `--scratch` explicitly selects a different scratch location; account for environment sandbox approval before writing there.

Examples, with `RUN_URL` set to the actual run URL:

```bash
python3 scripts/prow_artifacts.py list "$RUN_URL" --prefix artifacts/ --max-objects 200
python3 scripts/prow_artifacts.py fetch "$RUN_URL" build-log.txt
python3 scripts/prow_artifacts.py list "$RUN_URL" --prefix artifacts/TARGET/TEST_STEP/artifacts/junit/
python3 scripts/prow_artifacts.py junit "$RUN_URL" --prefix artifacts/TARGET/TEST_STEP/artifacts/junit/
python3 scripts/prow_artifacts.py fetch "$RUN_URL" artifacts/TARGET/TEST_STEP/build-log.txt --output evidence/run/test-step.log
python3 scripts/prow_artifacts.py children "$RUN_URL" --input evidence/run/aggregate-report.txt
```

Replace `TARGET` and `TEST_STEP` with paths recorded in the listing or build log. The helper does not infer them. A successful run's top-level build log may omit the actual test output; fetch the test-step log too.

Each invocation first fetches `prowjob.json`, summarizes job identity, refs, annotations and Prow status, and reports the cached raw metadata path. Inspect its `spec.pod_spec` for `--target`, the explicitly named initial/latest release images, and test configuration. Do not print unrelated secret-bearing environment values. Distinguish Prow state, ci-operator graph failure, individual step exit, and test assertion outcome.

Default limits are 200 listed objects, 16 MiB total bytes, and three additional attempts for retryable network errors or HTTP 429/500/502/503/504. Requests run serially, have 30-second socket timeouts, and retry with bounded exponential backoff. Limits include metadata, listing pages, cached object reads and partially consumed retry bodies. GCS JSON listing pagination is followed, with explicit object/page truncation. Check `listing.truncated`, JUnit `complete`, `unavailable`, and `unresolved`; a partial list is not an exhaustive artifact inventory. Narrow the prefix before increasing a limit. A socket timeout is not an overall investigation deadline; the orchestrator must still enforce its time budget.

Downloads go into a run/object-keyed cache with SHA-256, byte size, source URL, fetch time, and cache-hit status. Cached content is checked against its digest before reuse. Use `--refresh` for changing or unfinished runs; a cached completed-run artifact is historical evidence, not a current service-state check. `--output` is an explicit curated evidence destination for `fetch` and gets a provenance sidecar. It refuses to replace a differing existing file. Curate small decisive excerpts with original line numbers and source provenance separately; do not copy every raw download into a report repository.

Do not recursively download whole buckets, all pod logs, or must-gather archives by default. List the relevant step prefix, select a small set of files, inspect their sizes, and request only those needed to challenge the current hypothesis. A large archive requires a deliberate byte limit and an explanation of the question it will answer.

## Aggregate URL extraction

`children --input FILE` extracts literal recorded run URLs with source-digest and
JSON-pointer or line provenance. The output contains candidate references, not proven
aggregate membership: controls and historical runs can also appear in a report.
Use `prow-job-analysis` to validate parent/child roles before attributing a failure.

## Tests

Run `python3 scripts/test_prow_artifacts.py` from the skill directory for offline
coverage of URL parsing, limits, caching, JUnit lifecycle, and child-reference extraction.
