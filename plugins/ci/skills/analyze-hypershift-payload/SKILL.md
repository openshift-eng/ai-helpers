---
name: analyze-hypershift-payload
description: Use when investigating a HyperShift operator payload from the HCP release controller to explain blocking failures and produce an evidence-backed HTML report.
argument-hint: "<hypershift-payload-tag or saved snapshot.json>"
---

# Analyze a HyperShift payload

## Collect

Use Go 1.26 or newer for the [bundled CLI](cli/). Set `SKILL_DIR` and `RUN_DIR`
to the absolute paths of this skill and the output directory. Create `RUN_DIR` if needed.

For a saved snapshot, set `SNAPSHOT` to its absolute path. For a live payload,
set `TAG` to the full tag and run the collector.

```sh
SNAPSHOT="$RUN_DIR/snapshot.json"
go -C "$SKILL_DIR/cli" run . collect -out "$SNAPSHOT" "$TAG"
```

Use `-max-predecessors N` before the tag to change the history limit (default 19).

## Investigate

Use the snapshot as read-only evidence. For each failed blocking job, compare
retries and predecessor results and review the payload changes. Match jobs by
name and testcases by suite, class, and name. Cite matching failures to establish
recurrence and the JUnit results for each affected test's last observed pass.
Check `collection_errors` for missing evidence.
If the snapshot leaves a question open, follow a specific lead such as a failing
step log or a source diff.

Write `$RUN_DIR/findings.json` with the target `tag` and one entry in `jobs` per
failed blocking target job. Use an empty array if none failed. Follow the
[findings schema](cli/internal/api/types.go).

- Set `job` to the job name and describe the diagnosis in `explanation`, which
  can use Markdown. If the cause is uncertain, state what the evidence establishes
  and what is missing.
- Cite at least one source. Use `evidence` for URLs of payloads, runs, or readable
  JUnit artifacts in the snapshot. For a source you inspected separately, record
  its `url` in `supplemental_evidence` with a plain-text `caption` stating what
  you observed. Quote a short verbatim `excerpt` when the exact wording matters.
- Include a PR URL in `candidate_prs` only when the collected changelog contains
  it and the evidence connects it to the failure.

## Report

Render the report and return its path.

```sh
go -C "$SKILL_DIR/cli" run . report -snapshot "$SNAPSHOT" -findings "$RUN_DIR/findings.json" -out "$RUN_DIR/report.html"
```
