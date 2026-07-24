# diagnose-job-run-symptoms

Explain which Sippy Symptoms and failure Labels apply to a Prow CI job run, given only the Prow URL.

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

## Two modes

**Default mode** — no authentication. Reads the labels already applied to the run from its public GCS artifacts (`artifacts/job_labels/*.json`) and explains each one, including the matched file and text:

```bash
python3 diagnose_job_run.py \
  "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id>"
```

**Deep mode** — server-side dry-run rescan with the current symptom set (writes nothing). Requires a Bearer token from the DPCR cluster via the `oc-auth` skill — prefer `export SIPPY_TOKEN=$(oc whoami -t --context="$CONTEXT")` over `--token` (argv is visible in process listings):

```bash
python3 diagnose_job_run.py "<prow_url>" --deep
```

Use deep mode when the run predates the current symptoms or shows no labels.

If nothing matched and you have identified the failure cause, create a new symptom with the `manage-symptoms` skill so future runs are labeled automatically.
