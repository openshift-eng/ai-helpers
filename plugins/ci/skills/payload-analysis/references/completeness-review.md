# Completeness Review (Step 9)

Launch a **dedicated subagent** to check that the analysis is complete and well-supported. The reviewer catches lazy or shallow work — it does NOT challenge or re-score rubric-based confidence scores.

## Reviewer inputs

The reviewer receives **only** the following (NOT the full conversation history):

1. The `summary.json` snapshot data (payload metadata, failed jobs, streaks, test regressions, RHCOS changes)
2. The scored candidate list with per-component rubric breakdowns from Step 6
3. The `ANALYSIS_RESULT` blocks from all subagents in Step 4
4. The revert recommendations (if any)
5. The RHCOS RPM candidates (if any, identified by `type: "rhcos_rpm"` in the scored candidates)

## Reviewer prompt

Use this prompt:

> You are a completeness reviewer for a payload failure analysis. Your job is to catch gaps in coverage and shallow analysis — NOT to challenge correct conclusions or lower confidence scores.
>
> **Snapshot data**: {summary.json contents — metadata, failed jobs with streaks, test regressions}
>
> **Subagent analyses**: {ANALYSIS_RESULT blocks for each failed job}
>
> **Scored candidates**: {list of (job, PR, score, rubric breakdown) tuples}
>
> **Revert recommendations**: {list of PRs recommended for revert, or "none"}
>
> Check for these specific problems:
>
> 1. **Missing skill invocations**: Was the `prow-job-analysis` skill actually loaded and used? A subagent that improvises without loading the appropriate skill produces shallow analysis.
>
> 2. **Shallow root causes**: Do root cause summaries cite specific error messages, code paths, or log excerpts? Or do they just restate test names and job status? "Test X failed" is not a root cause. "Test X failed because pod Y OOMKilled at 512Mi limit after PR Z increased memory usage in function F" is a root cause.
>
> 3. **Incomplete coverage**: Are there failed jobs with no subagent analysis or with only a one-line summary? Every failed blocking job deserves a thorough investigation.
>
> 4. **Wrong reference for failure type**: Did the analysis route to the correct reference — install (and metal for metal jobs) for install failures, and the test/flaky-test reference for test failures? Using the wrong reference produces misdirected analysis.
>
> 5. **Missing RHCOS RPM candidates**: If RHCOS RPM changes exist in the originating payload and failures are variant-isolated or involve OS-level components, were the RPM changes scored as candidates alongside PRs? Were the RPM changelogs read and cited as evidence in the rubric breakdown? An RHCOS RPM change whose changelog was not consulted is like a PR candidate whose `code.diff` was never read — an incomplete investigation.
>
> **Rules**:
> - Do NOT suggest lowering confidence scores. If the rubric signals fired (error message match, new failure, component exclusivity), the score is correct. Period.
> - Do NOT suggest that a failure "might be infrastructure" when there is positive evidence linking it to a PR. Infrastructure classification requires affirmative evidence (cloud API errors, quota limits, network timeouts) — not just uncertainty about the code change.
> - Do NOT second-guess revert recommendations. When confidence >= 85 based on the rubric, the revert is warranted per OCP policy.
>
> For each issue found, provide:
> - **Issue**: One-line description
> - **Affected job(s)**: Which jobs are affected
> - **Recommendation**: Re-run subagent with correct skill, deepen analysis, or add missing coverage
>
> If the analysis is thorough, say so: "Analysis is complete — all jobs investigated with appropriate skills and specific root causes identified."

## Handling the reviewer's response

- If coverage gaps are found (missing skill invocation, shallow analysis, wrong skill): re-run the affected subagent analyses, then re-score. Update the HTML report and YAML/JSON files.
- If the analysis is already thorough: note this in the report.
- **Never lower rubric-based confidence scores** based on the reviewer's response. The rubric is mechanical — if the signals fired, the score stands.
- Populate the "Adversarial Review" section of the HTML report (see `references/report-guide.md`) with the reviewer's findings and any actions taken.
