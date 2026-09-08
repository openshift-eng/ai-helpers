# Debug a Prow failure from evidence

This reference and `scripts/prow_artifacts.py` are self-contained. They need Python 3 with its standard library and public HTTPS access. No other skill, Python package, cloud SDK, cluster login, or plugin installation is required. Do not post comments, trigger jobs, or modify product repositories during diagnosis unless the user separately authorizes that work.

## Bound acquisition before investigating

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

## Establish the actual failure boundary

Start with the metadata and ci-operator build log. Determine whether the job failed during image build, lease acquisition, installation, upgrade, test execution, collection/reporting, teardown, or lease release. An upgrade-named job that fails bootstrap has not demonstrated an upgrade failure. A successful test step followed by a failed release-of-lease operation has not demonstrated a product regression.

Find the first originating error in the failing operation, not merely its final wrapper. Preserve the exact API error, resource identity, timestamp and source path. Then explain the causal sequence to the gate. A final timeout or `external binary did not produce a result` is a boundary requiring further investigation, not a root cause.

For a clustered job, inspect the relevant operator/node state and logs around the failure, including earlier boots. Do not clear the OS layer from an end-of-run `nodes.json` snapshot. Node journals frequently contain gzip bytes despite lacking `.gz` suffixes. Inspect the file's magic bytes or use a gzip-aware reader; an empty plain-text grep is not evidence of absence. For each available node journal:

1. Identify boot boundaries and compare `Starting CRI-O, version` / `Container runtime initialized` across boots.
2. Correlate reboot, NotReady, missing CNI, MCD rendered-config changes and drain activity with test timestamps.
3. Check kernel panic/Oops/BUG/soft lockup, OCI runtime failures, NetworkManager errors and SELinux denials.
4. Compare the same facts against a same-job successful control and relevant payload boundary.

If journals or intermediate-boot evidence are missing, record the specific gap. An absent journal is neither proof nor exoneration of OS causality. Selective journal acquisition must stay within the download budget; if it cannot, mark the OS investigation incomplete rather than claiming it was checked.

Provider diagnosis must likewise reach the originating error. Distinguish cloud quota/capacity, rejected request parameters, authorization, eventual consistency, DNS/routing, bootstrap ignition, node runtime, and operator reconciliation. Quote the provider error code and affected operation. Examples: a failed cloud instance creation before bootstrap differs from a bootstrap load balancer security rule that blocks a control-plane connection; a kubelet missing ConfigMap shortly before controller creation may be a reconciliation-progress symptom rather than a permanent product defect. Time-correlated load or a noisy log line is a hypothesis until the mechanism is traced.

## Interpret tests and reporting policy

The `junit` command preserves full test names, classname, suite path, artifact path, source image/binary, lifecycle, and individual attempts. It handles both `<failure>` and `<error>`. Skipped attempts are excluded from evaluated-case counts. Explicit `lifecycle` attributes or properties can identify blocking or informing tests; absent lifecycle stays unknown. Never label a test blocking simply because it has a failure element.

Repeated names with both failure and success are `mixed_success_failure`, not an automatic red count or an automatic pass. Such records may represent retries, intentional failure-plus-success flake encoding, or repeated executions. The grouping is restricted to the same artifact directory, suite identity, classname and source. Review the runner's actual retry/flake policy and retain individual files and attempts; independent steps must not be merged into a fictional retry. Conflicting lifecycle metadata requires review. Suite-level failures that do not produce testcases and logs without JUnit remain explicit evidence gaps.

Read the final runner summary and step exit as well as JUnit. Informing failures can appear in successful jobs. Conversely, a test runner can mask a failed test's exit with successful report generation. A generated HTML report, a passing later suite, or a green Prow result alone does not establish that all intended tests executed and passed. Verify discovery, skip reasons, expected suite cardinality, and the exit path when they are implicated by current evidence.

For post-test hangs, separate each collection phase. An earlier `Finished CollectData` does not exonerate a later phase. Compare each monitor's start/finish within that phase, the remaining process budget, and any completion after the outer timeout. A collector finishing four seconds after an exhausted suite budget differs from a collector pending for an hour. Inspect context deadlines, network stream closure, worker waits, cooperative cancellation, and whether partial results survive; without stacks, keep the exact blocked function unresolved.

## Expand aggregates without inventing children

Treat the aggregate parent and its underlying runs as related layers, not independent failures to add together. Read the parent's actual report/log and identify the failing gate: statistical threshold, minimum attempts, missing results, child-job failure, analysis timeout, or report generation. A failure in one child is not by itself proof of the parent's rejection mechanism.

Fetch the relevant recorded parent report to a local file, then use `children --input FILE`. This extracts only literal supported run URLs (including URLs within JSON strings), preserving a source digest and JSON pointer or line/offset. URLs referring to artifacts are normalized to their recorded run root. Duplicate references retain all provenance. Numeric IDs alone, pod names, presumed sibling numbering, and timestamps never generate child URLs.

The output deliberately calls these **child candidates**. A URL in a report can be an unrelated control or historical baseline. Validate membership against the report's explicit attempt/child list and the child's metadata before counting it. `missing_edges` remains unknown until you reconcile expected attempts with observed children. Malformed recorded references stay unresolved. If the parent records only IDs or inaccessible objects, document the missing edge; do not guess a GCS path.

Investigate the actual child failure boundary using the same workflow. Retain the parent-to-child edge and the parent's gate-policy evidence separately from the child's root-cause finding. Dynamic test names and newly appearing tests can fail minimum-attempt gates even with zero failed test assertions; distinguish that policy failure from a product regression.

## Challenge the explanation and write the handoff

Choose a same-job green control near the failed run, preferably using the same payload, topology, feature set and test source. Inspect its actual test output, not just status. A green control can contain the same informing or masked failure. A different architecture or cloud is supporting context, not a substitute for a matched control. Record relevant differences rather than assuming the control is equivalent.

Pin source from the tested binary version, image provenance, PR SHA/merge metadata or explicit source-commit properties. Trace the failing assertion and the product/controller operation it observes. A local checkout or today's branch tip is not the deployed source. Synthetic build commits may not exist in a public GitHub repository; preserve that limitation instead of attaching unrelated current code to the run. Separately check whether a later fix exists and whether it has been tested in the relevant configuration. Do not label an old failure fixed solely because a PR merged.

For each finding, distinguish:

- **Established:** direct runtime evidence plus a supported mechanism explains the gate.
- **Hypothesis:** a plausible mechanism with a named missing discriminator.
- **Insufficient:** required evidence is unavailable or has not been examined.

Keep observed signature matches separate from source-reviewed or experimentally proven causal runs. Record run IDs, parent edges, source revision, evidence paths/URLs and timestamps, control observations, owner, concrete proposed change, acceptance criteria, confidence, and unresolved alternatives. State whether the finding causes rejection, is informing noise, masks missing coverage, or is only a downstream symptom. Provide a short debugging journey with decisive evidence, dead ends and difficulty. Do not submit product patches as part of diagnosis unless requested.
