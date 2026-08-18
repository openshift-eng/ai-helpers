# Completeness Review and Claim Audit (Step 9)

Launch a **dedicated subagent** that performs two passes over the analysis:

- **Part A — completeness review**: catches gaps in coverage and shallow analysis.
- **Part B — claim audit**: verifies the itemized evidence behind every candidate at or above the revert threshold. This is the only mechanism through which a confidence score may change.

## Reviewer inputs

The reviewer receives **only** the following (NOT the full conversation history):

1. The `summary.json` snapshot data (payload metadata, failed jobs, streaks, test regressions, RHCOS changes)
2. The scored candidate list with per-component rubric breakdowns from Step 6
3. The `ANALYSIS_RESULT` blocks from all subagents in Step 4
4. The revert recommendations (if any)
5. The RHCOS RPM candidates (if any, identified by `type: "rhcos_rpm"` in the scored candidates)
6. For every candidate scoring >= 85: the paths (relative to the snapshot) of the artifacts its evidence lines cite — the PR `code.diff`, the junit/build-log files, the child-run artifacts — so each claim can be checked against its source

## Reviewer prompt

Use this prompt:

> You are the reviewer for a payload failure analysis. You perform two passes: a completeness review and a claim audit. You do NOT invent new hypotheses, and speculation is inadmissible in both passes.
>
> **Snapshot data**: {summary.json contents — metadata, failed jobs with streaks, test regressions}
>
> **Subagent analyses**: {ANALYSIS_RESULT blocks for each failed job}
>
> **Scored candidates**: {list of (job, PR, score, rubric breakdown) tuples}
>
> **Revert recommendations**: {list of PRs recommended for revert, or "none"}
>
> **Cited artifacts for candidates >= 85**: {list of (candidate, signal, artifact path) entries}
>
> ## Part A — completeness review
>
> Check for these specific problems:
>
> 1. **Missing skill invocations**: Was the `prow-job-analysis` skill actually loaded and used? A subagent that improvises without loading the appropriate skill produces shallow analysis.
>
> 2. **Shallow root causes**: Do root cause summaries cite specific error messages, code paths, or log excerpts? Or do they just restate test names and job status? "Test X failed" is not a root cause. "Test X failed because pod Y OOMKilled at 512Mi limit after PR Z increased memory usage in function F" is a root cause. Treat hedged causal language on a scored candidate ("likely caused by", "could be related to") as a shallow-analysis flag: the investigation stopped at a hypothesis.
>
> 3. **Incomplete coverage**: Are there failed jobs with no subagent analysis or with only a one-line summary? Every failed blocking job deserves a thorough investigation.
>
> 4. **Wrong reference for failure type**: Did the analysis route to the correct reference — install (and metal for metal jobs) for install failures, and the test/flaky-test reference for test failures? Using the wrong reference produces misdirected analysis.
>
> 5. **Missing RHCOS RPM candidates**: If RHCOS RPM changes exist in the originating payload and failures are variant-isolated or involve OS-level components, were the RPM changes scored as candidates alongside PRs? Were the RPM changelogs read and cited as evidence in the rubric breakdown? An RHCOS RPM change whose changelog was not consulted is like a PR candidate whose `code.diff` was never read — an incomplete investigation.
>
> ## Part B — claim audit (candidates >= 85 only)
>
> For each candidate at or above the revert threshold, verify every itemized signal against the artifact its evidence line cites:
>
> - **error_message_match**: Open the cited diff/changelog and the cited failure output. For +40, confirm the claimed string/symbol appears verbatim in both. For +20-30, confirm an *observed* artifact (stack frame, log line, event, timestamped transition) places the failing operation in code the candidate modified — shared subsystem vocabulary does not qualify.
> - **new_failure_mode**: Confirm the claim holds at the failure-mode level: the same failure signature is absent from prior payloads' data, not merely that the job previously passed. A job-level streak or onset is not mode-level evidence.
> - **component_exclusivity**: Confirm the modifier count against the originating payload's actual PR and RPM lists.
> - **multi_job_correlation / presubmit_coverage_gap**: Confirm against the job lists and presubmit configuration actually cited.
>
> **Audit rules — these are strict:**
> - You may strike a signal ONLY by citing the specific artifact evidence that contradicts it, or by showing the cited evidence does not exist or does not say what the claim asserts. Name the artifact and quote the relevant content.
> - Speculative objections are inadmissible: "this might be infrastructure", "this could be flaky", "if this were the cause other jobs would fail too" strike nothing.
> - You may NOT propose alternative root causes, add candidates, or raise scores.
> - A signal whose cited evidence checks out survives, whatever your intuition says. A candidate whose signals all survive keeps its score untouched.
>
> ## Output
>
> For each Part A issue found, provide:
> - **Issue**: One-line description
> - **Affected job(s)**: Which jobs are affected
> - **Recommendation**: Re-run subagent with correct skill, deepen analysis, or add missing coverage
>
> For each Part B struck signal, provide:
> - **Candidate** and **signal** struck
> - **Contradicting evidence**: the artifact path and the quoted content that falsifies the claim
> - **Recomputed score**: the mechanical sum of surviving signals
>
> If the analysis is thorough and all audited claims survive, say so: "Analysis is complete — all jobs investigated with appropriate skills, specific root causes identified, and all revert-threshold claims verified against their cited artifacts."

## Handling the reviewer's response

- If coverage gaps are found (missing skill invocation, shallow analysis, wrong skill): re-run the affected subagent analyses, then re-score. Update the HTML report and YAML/JSON files.
- If the audit struck signals: recompute each affected candidate's score as the sum of surviving signals (capped at 100). If a candidate drops below the revert threshold, remove its revert recommendation. Update the YAML, JSON, and HTML consistently — divergent scores across outputs are a Step 10 defect.
- Scores change through the audit mechanism only. Never lower a score because the reviewer "has doubts" — a struck signal requires named, quoted contradicting evidence. Never raise a score based on the review.
- Populate the "Adversarial Review" section of the HTML report (see `references/report-guide.md`) with the findings, struck signals with their evidence, and actions taken.
