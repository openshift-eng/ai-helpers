---
name: Payload Agent
description: Autonomous agent that analyzes a rejected payload, scores confidence, and takes action — staging reverts, bisecting suspects, or reporting only
---

# Payload Agent

This skill is an autonomous orchestrator that analyzes a rejected payload, determines root causes using a deterministic confidence rubric, and takes action without human interaction. The human's only touchpoint is approving/merging revert PRs on GitHub.

## When to Use This Skill

Use this skill when you want fully autonomous payload triage:

- Analyze a rejected or failing payload
- Automatically stage reverts for high-confidence culprits
- Experimentally bisect medium-confidence suspects via draft revert PRs
- Resume after a CI wait period to collect bisect results
- Generate a comprehensive report with all actions taken

## Prerequisites

1. **Network Access**: Must be able to reach the release controller, Sippy API, and Prow
2. **GitHub CLI (`gh`)**: Installed and authenticated with push access to forks
3. **JIRA MCP**: Configured for creating TRT issues
4. **Python 3**: For running fetch scripts
5. **gcloud CLI**: For downloading Prow job artifacts

## Implementation Steps

### Step 1: Parse Arguments and Detect Resume

Parse the command arguments:

- `payload_tag` (required): Full payload tag (e.g., `4.22.0-0.nightly-2026-02-25-152806`)
- `--lookback N` (optional): Maximum lookback depth (default: 10)

Parse from the tag:
- `version`: e.g., `4.22`
- `stream`: e.g., `nightly`
- `architecture`: e.g., `amd64` (inferred from tag format; see `analyze-payload` Step 1 for parsing rules)

Construct the `release_controller_url`:
```
https://<architecture>.ocp.releases.ci.openshift.org/releasestream/<version>.0-0.<stream>/release/<payload_tag>
```
(For `amd64`, the subdomain is `amd64.ocp.releases.ci.openshift.org`.)

**Check for existing bisect tracking file**: Look for `<payload-tag>-bisect.yaml` in the current working directory. If it exists and contains experiments with `status: pending`, this is a resume — jump directly to Step 5 (Bisect Phase 2).

### Step 2: Run Analysis

Execute the `analyze-payload` skill Steps 1-6 to gather all analysis data:

1. Fetch recent payloads (Step 2)
2. Build failure history with lookback (Step 3)
3. Fetch new PRs in originating payloads (Step 4)
4. Investigate each failed job in parallel via subagents (Step 5)
5. Correlate failures with suspect PRs and score using the rubric (Step 6.1)
6. Identify revert candidates (Step 6.2)
7. Check for existing reverts (Step 6.3)

All results stay in-context (not written to files yet). The `analyze-payload` skill's Steps 7-9 (report generation) are deferred to Step 6 of this skill.

### Step 3: Apply Confidence Scoring

Score each (failed job, suspect PR) pair using the rubric from `analyze-payload` Step 6.1:

| Signal | Weight |
|--------|--------|
| Temporal match | +30 |
| Component match | +10 to +30 |
| Error message match | +30 |
| Single suspect | +10 |

Classify each suspect into confidence tiers:

| Tier | Score Range | Label |
|------|------------|-------|
| HIGH | >= 85 | Revert immediately |
| MEDIUM | 60-84 | Bisect experimentally |
| LOW | < 60 | Report only |

If a suspect PR appears in multiple (job, PR) pairs, use the **highest** score across all pairs for tier classification.

### Step 4: Decision and Dispatch

Based on the confidence tiers, take autonomous action:

| Confidence | Action | Skill Used |
|------------|--------|------------|
| >= 85 (HIGH) | Stage reverts: create TRT JIRA, open revert PR, trigger payload jobs | `stage-payload-reverts` |
| 60-84 (MEDIUM) | Bisect: open draft revert PRs, trigger payload jobs | `bisect-payload-suspects` Phase 1 |
| < 60 (LOW) | Report only — no automated action | None |

**Skip candidates** that already have merged or open revert PRs (identified in Step 2 via `analyze-payload` Step 6.3).

**Execute HIGH and MEDIUM actions in parallel** when both tiers have candidates. Pass all required context in-memory to each skill.

If there are no HIGH or MEDIUM candidates, skip to Step 6 (report generation).

### Step 5: Bisect Phase 2 (Resume)

This step is reached either:
- Automatically when a `<payload-tag>-bisect.yaml` with pending experiments is found in Step 1
- After a CI wait period when Phase 1 was previously initiated

Read `<payload-tag>-bisect.yaml` from the current working directory.

Use the `bisect-payload-suspects` skill Phase 2:
1. Check job results for each experiment
2. For confirmed causes (jobs pass with revert): create TRT JIRA, promote draft PR
3. For innocent PRs (jobs still fail): close draft PR with explanation
4. Update tracking YAML with results

Proceed to Step 6.

### Step 6: Generate Report and Artifacts

Use the `analyze-payload` skill Steps 7-9 to generate the HTML report and `autodl.json` data file. Augment the report with additional sections based on actions taken:

#### 6.1: Staged Reverts Section

If high-confidence reverts were staged (Step 4), add a "Staged Reverts" table after the executive summary:

```html
<div class="revert-recommendations">
  <h2>Staged Reverts</h2>
  <p>The following reverts have been automatically staged. TRT JIRA bugs were created,
     revert PRs were opened, and payload jobs were triggered.</p>
  <table>
    <tr>
      <th>Original PR</th>
      <th>Component</th>
      <th>TRT Ticket</th>
      <th>Revert PR</th>
      <th>Payload Jobs Triggered</th>
      <th>Status</th>
    </tr>
    <tr>
      <td><a href="{pr_url}" target="_blank">#{pr_number}</a></td>
      <td>{component}</td>
      <td><a href="{jira_url}" target="_blank">{jira_key}</a></td>
      <td><a href="{revert_pr_url}" target="_blank">{revert_pr_url}</a></td>
      <td>{comma-separated job names}</td>
      <td><span class="badge badge-{success|partial|failed}">{Status}</span></td>
    </tr>
  </table>
</div>
```

#### 6.2: Bisect In Progress Section

If bisect Phase 1 was initiated but Phase 2 has not completed, add a "Bisect In Progress" section:

```html
<div class="bisect-section">
  <h2>Bisect In Progress</h2>
  <p>Draft revert PRs have been opened and payload jobs triggered for the following
     medium-confidence suspects. Results will be available after jobs complete (typically 1-4 hours).</p>
  <table>
    <tr>
      <th>Suspect PR</th>
      <th>Component</th>
      <th>Confidence</th>
      <th>Draft Revert PR</th>
      <th>Payload Test URL</th>
      <th>Status</th>
    </tr>
    <!-- One row per experiment -->
  </table>
  <p><strong>Resume by running:</strong> <code>/ci:payload-agent {payload_tag}</code> again from the same directory.</p>
</div>
```

#### 6.3: Bisect Results Section

If bisect Phase 2 completed, add a "Bisect Results" section:

```html
<div class="bisect-section">
  <h2>Bisect Results</h2>
  <table>
    <tr>
      <th>Suspect PR</th>
      <th>Component</th>
      <th>Verdict</th>
      <th>Action Taken</th>
      <th>Details</th>
    </tr>
    <tr>
      <td><a href="{pr_url}">#{pr_number}</a></td>
      <td>{component}</td>
      <td><span class="badge badge-{confirmed|innocent|inconclusive}">{Verdict}</span></td>
      <td>{action: "JIRA created + PR promoted" | "Draft closed" | "Pending"}</td>
      <td>{result_summary}</td>
    </tr>
  </table>
</div>
```

Add styles for bisect badges:

```html
.bisect-section {
  background: white;
  border-left: 4px solid #1a73e8;
  padding: 16px 20px;
  margin: 20px 0;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.badge-confirmed { background: #fce8e6; color: #d93025; }
.badge-innocent { background: #e6f4ea; color: #1e8e3e; }
.badge-inconclusive { background: #fef7e0; color: #e37400; }
.badge-success { background: #e6f4ea; color: #1e8e3e; }
.badge-partial { background: #fef7e0; color: #e37400; }
.badge-failed { background: #fce8e6; color: #d93025; }
```

### Step 7: Exit

After report generation:

- **If bisect Phase 1 was initiated** (tracking YAML was written with pending experiments):
  1. Print the tracking file path
  2. Print resume instructions:
     ```
     Bisect experiments are running. Payload jobs typically take 1-4 hours to complete.

     Tracking file: ./<payload-tag>-bisect.yaml

     To collect results and generate the final report, run the same command again
     from this directory:
       /ci:payload-agent <payload-tag>
     ```

- **If no bisect was initiated** (only HIGH or LOW confidence, or Phase 2 just completed):
  - Print the report file paths and a brief summary
  - Done

## Error Handling

- If the `analyze-payload` skill fails partway, report what was collected and note the error.
- If `stage-payload-reverts` or `bisect-payload-suspects` fail for individual candidates, continue with remaining candidates and note errors in the report.
- If the tracking YAML exists but all experiments are already completed (no pending), skip Phase 2 and proceed to report generation.
- Network errors, JIRA failures, and GitHub API errors should be caught and reported without aborting the entire pipeline.

## Notes

- No human interaction during execution. The agent runs fully autonomously.
- The skill is reentrant: it detects the presence of `<payload-tag>-bisect.yaml` in CWD to determine whether to run a fresh analysis or resume bisect Phase 2. Running the same command twice from the same directory automatically resumes.
- The confidence rubric is deterministic — the same signals always produce the same score.
- Deferred suspects (from bisect throttling) are noted in the report for manual follow-up.

## See Also

- Related Command: `/ci:payload-agent` - The user-facing command (`plugins/ci/commands/payload-agent.md`)
- Related Skill: `analyze-payload` - Core analysis logic (`plugins/ci/skills/analyze-payload/SKILL.md`)
- Related Skill: `stage-payload-reverts` - High-confidence revert staging (`plugins/ci/skills/stage-payload-reverts/SKILL.md`)
- Related Skill: `bisect-payload-suspects` - Medium-confidence bisect experiments (`plugins/ci/skills/bisect-payload-suspects/SKILL.md`)
