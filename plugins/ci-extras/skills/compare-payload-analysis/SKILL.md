---
name: compare-payload-analysis
description: Blindly analyze an OpenShift payload from another AI agent's snapshot, then adjudicate both agents' findings in a concise evidence-backed HTML comparison. Use when asked to compare payload analyses, audit the payload agent, or produce a "what the other agent got right and wrong" report.
---

# Compare Payload Analysis

Produce an independent payload analysis before exposing the other agent's
findings. Then resolve disagreements against primary artifacts and render a
self-contained comparison report.

## Arguments

```text
<payload-tag> [--other-job-url URL] [--work-dir DIR] [--publish-gist]
```

- `payload-tag` is required.
- `--other-job-url` overrides async-job discovery. Use the Prow URL for the
  other payload agent.
- `--work-dir` defaults to
  `.work/compare-payload-analysis/<sanitized-payload-tag>`.
- `--publish-gist` publishes the final HTML and returns an HTMLPreview link.

## Required Skill

Load and use `payload-analysis` for the independent investigation. Its
required schema skills and job-analysis workflow still apply.

## Phase 1: Stage the Snapshot Blindly

Locate this skill's scripts:

```bash
SKILL_ROOT="${CLAUDE_PLUGIN_ROOT}/skills/compare-payload-analysis"
if [ ! -f "$SKILL_ROOT/scripts/artifact_bridge.py" ]; then
  SKILL_ROOT=$(find ~/.claude/plugins -type f \
    -path "*/ci-extras/skills/compare-payload-analysis/scripts/artifact_bridge.py" \
    -print 2>/dev/null | sort | head -1 | xargs dirname | xargs dirname)
fi
```

Run the bridge's `stage` command:

```bash
python3 "$SKILL_ROOT/scripts/artifact_bridge.py" stage \
  "<payload-tag>" --work-dir "<work-dir>"
```

Add `--job-url "<other-job-url>"` when supplied. The helper:

1. Discovers the succeeded `claude-payload-agent` async job from release
   controller metadata.
2. Lists artifact names without opening their contents.
3. Downloads and safely extracts only `snapshot-<payload-tag>.tar*`.
4. Records the other HTML report URI in a sealed state file.
5. Refuses archives containing HTML or unsafe tar members.

Read the helper's JSON output and use its `snapshot_dir`. Confirm the
snapshot's `summary.json` has the requested `payload_tag`.

### Blindness Rules

Until Phase 3, do not:

- Open, download, render, fetch, grep, summarize, or screenshot the other
  agent's HTML.
- Open the other job's session archive, console log, or any artifact that can
  reveal its conclusions.
- Search for quotations or conclusions from the other analysis elsewhere.

Artifact filenames, job metadata, and snapshot contents are allowed. If the
other findings are exposed accidentally, stop and disclose that the run is
not blind; start a fresh context before claiming an independent comparison.

## Phase 2: Perform and Freeze the Independent Analysis

Create `<work-dir>/independent/` and make it the output working directory.
Load and invoke the `payload-analysis` skill in the current context with:

```text
/ci:payload-analysis <payload-tag> --snapshot-dir <absolute-snapshot-dir>
```

Apply one task-specific override while following that skill: **skip its
"Consult Previous Claude Analyses" step entirely.** The current report is
sealed, so do not discover, fetch, or read any prior analysis through a
separate path. Follow every other payload-analysis step, including its deep
job investigations, scoring, output schemas, completeness review, and final
self-check.

Do the full deep analysis. Do not treat the supplied snapshot as the other
agent's conclusions; it is primary-source scaffolding. Investigate job
artifacts, retries, underlying aggregated runs, exact failing operations,
candidate diffs, CI step changes, and RHCOS changes as required by
`payload-analysis`.

Before unsealing, mechanically confirm these independent outputs exist:

```text
payload-analysis-<payload-tag>-summary.html
payload-analysis-<payload-tag>-autodl.json
payload-results-<payload-tag>.yaml
```

Freeze their hashes and unseal the other report:

```bash
python3 "$SKILL_ROOT/scripts/artifact_bridge.py" unseal \
  "<payload-tag>" \
  --work-dir "<work-dir>" \
  --independent-html "<independent-html>" \
  --independent-json "<independent-autodl-json>" \
  --independent-yaml "<independent-results-yaml>"
```

The helper refuses to download the other report unless all three independent
outputs are non-empty and match the exact payload-analysis filenames. It
records their SHA-256 hashes before changing the state from `staged` to
`unsealed`.

## Phase 3: Read and Adjudicate

Only now read the downloaded `other_report` returned by `unseal`.

Build a claim matrix covering every material conclusion from either report:

| Area | Required comparison |
|---|---|
| Payload verdict | phase, blocking status, force-accept/revert conclusion |
| Job inventory | every failed blocking job, exact Prow run, retries |
| Failure mechanics | exact failing operation, error, timestamps, child run |
| History | failure-mode onset, accepted baseline, recurrence evidence |
| Attribution | payload PRs, CI changes, RHCOS changes, score rationale |
| Non-gating signal | informing jobs, informing tests, flakes |
| Completeness | passed jobs, omitted failures, mislabeled tables or counts |

For each disagreement:

1. State both claims precisely.
2. Identify evidence that distinguishes them.
3. Re-open the primary artifact for the exact failing operation.
4. Record the supported conclusion and link the evidence.

Never choose a claim because it sounds more plausible or because two agents
agree. Adjacent successful activity does not clear the operation that failed.
Missing lines in truncated logs are unknown, not negative evidence. Mark a
disagreement unresolved when the artifacts cannot discriminate.

Credit useful findings even when the other report's final interpretation is
wrong. Separate:

- `right`: supported facts or helpful context from the other analysis.
- `wrong`: factual errors, unsupported claims, omissions, or misleading
  labels.
- `combined`: the best evidence-backed conclusion after adjudication.

## Phase 4: Render the Comparison

Write `<work-dir>/comparison.json` with this shape:

```json
{
  "payload_tag": "5.0.0-0.ci-YYYY-MM-DD-HHMMSS",
  "verdict": "One concise combined verdict.",
  "independent_report": {
    "label": "Independent analysis",
    "path": "/absolute/path/to/independent-report.html"
  },
  "other_report": {
    "label": "Other AI analysis",
    "url": "https://example.invalid/other-report"
  },
  "rows": [
    {
      "topic": "High-level verdict",
      "assessment": "correct",
      "right": "What was supported.",
      "wrong": "What was missing, or “No material issue.”",
      "combined": "Best conclusion after checking artifacts.",
      "evidence": [
        {"label": "Primary artifact", "url": "https://example.invalid/artifact"}
      ]
    }
  ]
}
```

`assessment` must be `correct`, `mixed`, or `incorrect`. Use one row per
meaningful topic; do not inflate the table with trivial wording differences.
Report sources accept either an HTTPS `url` or a local `path`. Use primary
artifact URLs in `evidence` wherever possible.

Render:

```bash
python3 "$SKILL_ROOT/scripts/render_comparison.py" \
  "<work-dir>/comparison.json" \
  --output "payload-analysis-comparison-<payload-tag>.html"
```

The renderer escapes all supplied text and produces a responsive,
self-contained HTML file using the bundled template.

## Final Checks

Before presenting:

1. Every failed blocking job appears in the table.
2. Every `wrong` claim is tied to discriminating evidence or labeled
   `unresolved`.
3. Job-level failure, test failure, informing job, and informing test counts
   are not conflated.
4. The combined verdict agrees with the detailed rows.
5. The blind-state manifest is `unsealed` and contains hashes for all three
   independent outputs.
6. The final HTML is non-empty and contains no unescaped source content.

Report the saved HTML path and a short combined verdict.

If `--publish-gist` was requested:

```bash
gist_url=$(gh gist create --public \
  "payload-analysis-comparison-<payload-tag>.html" \
  -d "Payload analysis comparison for <payload-tag>")
gist_id=${gist_url##*/}
raw_url=$(gh api "gists/$gist_id" \
  --jq '.files | to_entries[0].value.raw_url')
echo "https://htmlpreview.github.io/?${raw_url}"
```

Return both the gist URL and HTMLPreview link.

## Error Handling

- If no succeeded other-agent async job exists, stop and report that the
  comparison is waiting for it. Do not generate a replacement snapshot.
- If the snapshot is incomplete, follow `payload-analysis` and collect the
  missing primary artifacts yourself.
- If the other report is absent after a succeeded job, preserve the
  independent analysis and report the missing artifact.
- If a contradiction cannot be resolved from available artifacts, label it
  `unresolved`; never manufacture certainty.
