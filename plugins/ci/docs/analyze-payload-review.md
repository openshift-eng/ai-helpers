# analyze-payload: Architecture Review & Recommendations

Reviewed: 2026-03-03

## What Works Well

The architectural decomposition is sound: fetch → build history → investigate in parallel → correlate → report. Parallel subagent execution is the right pattern. The HTML report design is thoughtful. The `-autodl.json` output provides a foundation for tracking outcomes over time.

## Vision: Autonomous Payload Agent

The end state is a single autonomous agent that runs the full pipeline without human interaction during execution. The human's only touchpoint is approving/merging (or closing) the revert PR on GitHub. No slash commands chained together, no files passed between invocations, no "should I proceed?" prompts.

### Architecture

```
Scheduler/trigger (payload rejected)
  │
  ▼
Autonomous Agent
  │
  ├─ analyze_payload.py (data gathering, deterministic)
  │     └─ outputs: structured JSON with failed jobs, suspect PRs, streaks
  │
  ├─ Parallel subagents: investigate each failed job
  │     └─ outputs: structured failure analysis per job
  │
  ├─ Correlate + score confidence (rubric-based)
  │
  ├─ HIGH confidence (>= 85)
  │     ├─ Create TRT JIRA bug
  │     ├─ Open revert PR (human reviews on GitHub)
  │     └─ Trigger payload jobs on revert PR
  │
  ├─ LOW confidence (< 85, suspects exist)
  │     ├─ Phase 1: open draft revert PRs, trigger payload jobs on each
  │     ├─ [wait for CI results — hours]
  │     ├─ Phase 2: collect results from CI
  │     ├─ Close innocent revert PRs with explanation
  │     ├─ Confirmed causes: create TRT JIRA, promote draft → real PR
  │     └─ Human reviews on GitHub
  │
  └─ Write artifacts
        ├─ *-summary.html    (human-readable report)
        └─ *-autodl.json     (database ingestion)
```

### Data flow

Data stays in agent context throughout the pipeline — no file-based handoffs between stages. Files are **artifacts for external consumers**, not integration mechanisms:

| File | Consumer | Purpose |
|------|----------|---------|
| `*-summary.html` | Humans reading the report | Visual summary of findings |
| `*-autodl.json` | Database pipeline | Flat table for analytics/trending |
| `*-bisect.json` | Agent self-resume | Persists experiment state across the hours-long CI gap |

### Temporal gap in bisect

Payload jobs take 1-4 hours. The agent needs to persist state and resume:

- **Phase 1**: Set up experiments, write `-bisect.json` tracking file, exit
- **Phase 2**: Re-invoked by scheduler after N hours, reads tracking file, collects results, acts

The `-bisect.json` is the only file used for inter-invocation state, and it exists solely because of the hours-long gap that can't be bridged by context.

### Decision points are rules, not prompts

| Condition | Action |
|-----------|--------|
| Confidence >= 85 | Stage revert immediately |
| Confidence < 85, suspects exist | Bisect (open draft reverts, trigger jobs, wait for results) |
| Confidence < 85, no suspects | Report only, no action |
| Bisect result: job passes with revert | PR is the cause — promote to real revert PR, create JIRA |
| Bisect result: job still fails | PR is innocent — close draft revert with explanation |
| Bisect result: all fail | No single suspect — report as infrastructure/interaction issue |
| Revert has merge conflicts | Skip, note in report |

---

## High Priority

### 1. Create `analyze_payload.py` for Steps 1-4

The orchestration logic (parse tag, fetch payloads, walk back through history, collect suspect PRs) is described in prose for the AI to implement each run. This is the most critical algorithmic part — streak tracking, originating payload identification — and it's pure bookkeeping that should be deterministic.

**Proposal**: A single Python script that:
- Parses the payload tag (regex)
- Calls `fetch_payloads.py` via subprocess using `__file__`-relative paths (sibling skill)
- Implements the walkback algorithm (pure data, no network)
- Calls `fetch_new_prs_in_payload.py` for each originating payload (preserves its fallback logic)
- Outputs structured JSON to stdout

The AI receives the JSON and jumps straight to Step 5 (subagent investigation). No more implementing graph-walk algorithms from prose.

**Cross-skill path resolution**: Use `os.path.dirname(os.path.abspath(__file__))` to find sibling scripts. The relative path within the plugin is stable regardless of install location:
```python
SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
script = os.path.join(SKILLS_DIR, 'fetch-payloads', 'fetch_payloads.py')
```

**Output contract**: See appendix A below.

### 2. Define Structured Subagent Return Format

Step 5 tells subagents to "return a concise summary" but Step 6 needs to programmatically correlate this free-text output with suspect PRs by component and error message. The consumer needs structured data but the producer returns prose.

**Proposal**: Define a return format in the SKILL.md:
```
ANALYSIS_RESULT:
- failure_type: install|test
- root_cause_summary: <1-2 sentences>
- affected_components: <comma-separated>
- key_error_patterns: <comma-separated strings from logs>
- underlying_job_name: <for aggregated jobs, empty otherwise>
```

### 3. Define Confidence Scoring Rubric

The confidence threshold is the autonomous agent's decision-maker — it replaces the human "should I proceed?" judgment. It must be auditable and reproducible.

**Proposal**: Weighted scoring in the SKILL.md:

| Signal | Weight |
|--------|--------|
| Temporal match (job passing before originating payload, failing after) | +30 |
| Component exact match (PR touches the operator/controller that failed) | +30 |
| Error message references PR's code changes (stack trace, package name) | +30 |
| Single suspect (only one PR touched affected component in originating payload) | +10 |

- Score >= 85 → stage revert immediately (high confidence path)
- Score 40-84 with suspects → bisect (low confidence path)
- Score < 40 or no suspects → report only, no action

This rubric is critical for the autonomous model — it's the codified policy that governs when the agent acts vs. reports.

### 4. Implement Aggregated Job Name Extraction

The SKILL.md says to extract the underlying job name from `junit-aggregated.xml` but `prow-job-analyze-test-failure` doesn't include steps to download and parse that XML. The instruction exists in the subagent prompt but the skill it follows doesn't implement it.

**Proposal**: Either:
- Add explicit junit-aggregated.xml download/parse steps to the test-failure skill
- Create a small Python helper `parse_aggregated_junit.py` that extracts underlying job names

### 5. Implement Bisect Logic

When the agent can't reach high confidence, it needs to experimentally determine the cause by testing each suspect PR independently.

**Algorithm:**

```
Phase 1: Set up experiments (parallel, ~5 minutes)
  For each suspect PR:
    - Open a draft revert PR on a fork
    - Trigger the failing payload job(s) on each revert PR
      - Aggregated jobs: /payload-aggregate <underlying-job> <count>
      - Non-aggregated: /payload-job <job-name>
    - Record: {suspect_pr, revert_pr_url, triggered_jobs}
    - Write experiment state to -bisect.json

Phase 2: Collect results (re-invoked after jobs complete)
  For each experiment:
    - Check payload job results (gh pr checks / prow API)
    - Each experiment produces: PASS, FAIL, or FLAKY

Phase 3: Interpret and act
  - Revert A: jobs PASS  → PR A is the cause → create JIRA, promote to real PR
  - Revert B: jobs FAIL  → PR B is innocent → close draft with explanation
  - Revert C: jobs PASS  → PR C is also a cause → create JIRA, promote to real PR
  - All reverts FAIL     → none are the sole cause → close all, report
```

**Edge cases:**

| Scenario | Response |
|----------|----------|
| Multiple PRs are each independently the cause | Both revert PRs promoted. Report notes multi-cause. |
| No revert fixes the failure | Close all draft PRs. Report: infrastructure/interaction issue. |
| Job is flaky | Use `/payload-aggregate` with count > 1 for statistical signal. |
| Revert has merge conflicts | Skip that PR, note in report. |
| Too many suspects (20+ PRs) | Prioritize by component overlap. Test top 5-8 first. |

## Medium Priority

### 6. Eliminate Redundant JIRA Lookup in Revert Staging

When the agent creates a TRT JIRA bug then calls the revert-pr skill, the revert-pr skill has its own "Look Up JIRA Ticket for Context" step. But it's looking up the ticket that was just created — a near-empty ticket. Wasted work.

**Proposal**: The revert-pr skill should accept context as a direct input parameter. In the autonomous pipeline the agent already has all context in memory — pass it directly, skip the JIRA lookup.

### 7. Clarify Lookback Edge Cases

What happens with a "Ready" payload in the middle of a rejection streak? The SKILL says "walk backwards through consecutive rejected payloads" but doesn't clarify whether Ready payloads break the chain.

**Proposal**: Make explicit in SKILL.md (and implement in `analyze_payload.py`):
- Walk through consecutive Rejected payloads only
- Stop at any Accepted or Ready payload
- Stop at lookback limit
- Document: "A Ready payload is excluded because its final phase is unknown"

### 8. Handle Multiple Suspects Per Job

If 3 PRs all touched the network operator and e2e-network jobs failed, the system doesn't specify how to choose. In the autonomous model this matters more — the agent acts without asking.

**Proposal**:
- High confidence path: if multiple suspects score >= 85, revert all (they're independently high-confidence)
- Low confidence path: bisect all suspects in parallel — CI results determine which are guilty
- Report all suspects ranked by confidence regardless of path taken

### 9. Multi-Component PR Handling

A PR touching 5 components is a suspect for failures in any of those 5 components, creating false positives. No confidence weighting for "exact match" vs "one of many."

**Proposal**: When correlating, weight component matches:
- PR touches only the failing component → strong signal (+30)
- PR touches the failing component among 2-3 others → moderate signal (+20)
- PR touches the failing component among 4+ others → weak signal (+10)

## Low Priority

### 10. Stale `--override` Reference

Line 230 of SKILL.md still says "Do NOT pass `--override`" but the flag was removed from revert-pr.

### 11. CSS Class Mismatch

The stylesheet defines `.suspect-prs` but the HTML tables never use that class.

### 12. Step Numbering Confusion

Step 7.4 (Recommended Reverts) appears before 7.3 (Failed Job Details) in the report layout. This is intentional for UX but the numbering is misleading.

## Future Enhancements

### 13. Revert Outcome Tracking

The system stages reverts but never checks whether they worked. The `-autodl.json` output provides a foundation. A follow-up capability could query subsequent payloads and update database records, feeding back into confidence calibration over time.

### 14. Automated Trigger Pipeline

With the autonomous agent model, the trigger is: "a payload was rejected." A scheduler watches for rejected payloads and invokes the agent. The agent runs the full pipeline (analyze → stage or bisect → report), writes artifacts to the database, and the human's only job is to review and approve the revert PR on GitHub.

## Appendix A: Proposed `analyze_payload.py` Output Schema

```json
{
  "payload_tag": "4.22.0-0.nightly-2026-02-25-152806",
  "version": "4.22",
  "stream": "nightly",
  "architecture": "amd64",
  "phase": "Rejected",
  "release_controller_url": "https://amd64.ocp.releases.ci.openshift.org/...",
  "lookback_depth": 10,

  "summary": {
    "total_blocking_jobs": 42,
    "passed_blocking_jobs": 38,
    "failed_blocking_jobs": 4,
    "new_failures": 1,
    "persistent_failures": 3,
    "rejection_streak": 5
  },

  "failed_jobs": [
    {
      "job_name": "periodic-ci-openshift-release-main-ci-4.22-e2e-aws-ovn",
      "prow_url": "https://prow.ci.openshift.org/view/gs/...",
      "streak_length": 5,
      "is_new_failure": false,
      "originating_payload_tag": "4.22.0-0.nightly-2026-02-20-150000",
      "originating_payload_url": "https://amd64.ocp.releases.ci.openshift.org/...",
      "retry_count": 0,
      "new_prs_in_originating_payload": [
        {
          "url": "https://github.com/openshift/cluster-network-operator/pull/2037",
          "pr_number": "2037",
          "component": "cluster-network-operator",
          "description": "Fix OVN gateway mode selection",
          "bug_url": "https://issues.redhat.com/browse/OCPBUGS-12345"
        }
      ]
    }
  ],

  "passed_jobs": [
    "periodic-ci-openshift-release-main-ci-4.22-e2e-metal-ipi",
    "periodic-ci-openshift-release-main-ci-4.22-e2e-aws-sdn"
  ]
}
```

Error cases return JSON with an `error` field and exit code 1:

```json
{
  "error": "payload_not_found",
  "message": "Tag not found in last 20 payloads",
  "available_tags": ["4.22.0-0.nightly-2026-02-25-152806", "..."]
}
```
