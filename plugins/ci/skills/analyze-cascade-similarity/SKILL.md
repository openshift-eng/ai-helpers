---
name: Analyze Cascade Similarity
description: Perform deep root cause analysis on potential cascades to confirm they are real backport cascades with the same underlying issue
---

# Analyze Cascade Similarity

This skill performs deep root cause analysis on potential cascades identified by the `detect-potential-cascades` skill. It fetches actual Prow job failures, launches parallel subagents to analyze each failure, and compares the root causes to determine if cascades are real or false positives.

## When to Use This Skill

Use this skill when you need to:

- Confirm that potential cascades are real cascades with the same root cause
- Filter out false positives where the same test fails for different reasons
- Get detailed root cause analysis for each release in a cascade
- Generate similarity scores and comparison data for cascade validation

## Prerequisites

1. **Input file**: `.work/detect-backport-regressions/potential_cascades.json` from `detect-potential-cascades` skill
2. **Network Access**: Must reach Sippy API and GCS (Google Cloud Storage for Prow artifacts)
3. **Available skills**:
   - `ci:fetch-regression-details` - Get Prow job URLs from regression IDs
   - `ci:prow-job-analyze-test-failure` - Analyze individual Prow job failures

## Implementation Steps

### Step 1: Load Potential Cascades

Read the JSON output from the `detect-potential-cascades` skill:

```bash
potential_cascades=$(cat .work/detect-backport-regressions/potential_cascades.json)
```

Parse the data:

```python
import json
data = json.loads(potential_cascades)
cascades = data["potential_cascades"]
```

### Step 2: For Each Potential Cascade, Fetch Prow Job URLs

For each cascade, you need representative Prow job URLs from each affected release.

**Get regression IDs**:

```python
cascade = cascades[0]  # Example: first cascade
origin_regression_id = cascade["origin"]["regression_id"]
cascade_regression_ids = {
    rel["release"]: rel["regression_id"]
    for rel in cascade["cascade_releases"]
}
```

**Fetch Prow URLs using fetch-regression-details**:

```bash
# For origin release (e.g., 4.22)
python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py \
  "$origin_regression_id" \
  --format json \
  | jq -r '[.sample_failed_jobs | to_entries[].value.failed_runs[0].job_url] | .[0]' \
  > .work/detect-backport-regressions/cascade_${cascade_index}/4.22_prow_url.txt

# For each cascade release
for release in "${cascade_releases[@]}"; do
  regression_id="${cascade_regression_ids[$release]}"
  python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py \
    "$regression_id" \
    --format json \
    | jq -r '[.sample_failed_jobs | to_entries[].value.failed_runs[0].job_url] | .[0]' \
    > .work/detect-backport-regressions/cascade_${cascade_index}/${release}_prow_url.txt
done
```

**Handle cases where no Prow URL is available**:
- Some regressions may not have `sample_failed_jobs` yet
- Log a warning and mark that release as "unable to analyze"
- Continue with other releases that have URLs

### Step 3: Launch Parallel Subagents for Root Cause Analysis

**CRITICAL**: Launch subagents **in parallel** (single message with multiple Task tool calls) for maximum performance.

**Subagent Prompt Template**:

```
Analyze the test failure "{test_name}" in this Prow job: {prow_url}

Use the ci:prow-job-analyze-test-failure skill to perform a thorough root cause analysis.

IMPORTANT:
- Trace to the actual root cause, not just symptoms
- Download log bundles, examine pod logs, cite specific error messages
- Never stop at symptoms like "0 nodes ready", "operator degraded", or "crash-looping"
- Look for the underlying reason (network issues, CNI config loss, registry failures, etc.)

At the end of your analysis, you MUST provide an ANALYSIS_RESULT block in this exact format:

ANALYSIS_RESULT:
- root_cause_summary: <one-line summary of the actual root cause>
- affected_components: <comma-separated list of affected operators/components>
- key_error_patterns: <comma-separated key error strings for matching>
- known_symptoms: <comma-separated symptom summaries, or "none">
- test_name: {test_name}
- confidence_level: <1-5, where 5 is highest confidence in the root cause>
- release: {release}
```

**Launch agents in parallel**:

```python
# Build list of (release, prow_url) tuples
analysis_tasks = [
    ("4.22", prow_url_422),
    ("4.21", prow_url_421),
    ("4.20", prow_url_420),
    # ... etc
]

# Launch all agents in a SINGLE message with multiple Task tool calls
# This is critical for parallel execution
agents = []
for release, prow_url in analysis_tasks:
    if prow_url and prow_url != "null":
        agents.append({
            "release": release,
            "prow_url": prow_url,
            "prompt": build_analysis_prompt(test_name, prow_url, release)
        })

# Agent launches all tasks in parallel and waits for all to complete
```

### Step 4: Extract and Parse ANALYSIS_RESULT Blocks

From each subagent response, extract the `ANALYSIS_RESULT` block:

```python
def extract_analysis_result(agent_response: str, release: str) -> dict:
    """Extract structured analysis result from agent response."""

    # Find ANALYSIS_RESULT block
    if "ANALYSIS_RESULT:" not in agent_response:
        return {
            "error": "No ANALYSIS_RESULT block found",
            "release": release,
            "confidence_level": 0
        }

    # Parse the structured data
    result = {
        "release": release,
        "raw_response": agent_response
    }

    lines = agent_response.split("ANALYSIS_RESULT:")[1].strip().split("\n")
    for line in lines:
        if line.startswith("- "):
            key_value = line[2:].split(":", 1)
            if len(key_value) == 2:
                key = key_value[0].strip()
                value = key_value[1].strip()
                result[key] = value

    return result

# Extract results from all agents
analysis_results = {}
for agent in completed_agents:
    release = agent["release"]
    analysis_results[release] = extract_analysis_result(
        agent["response"],
        release
    )
```

### Step 5: Compare Root Causes Across Releases

**Similarity Analysis**:

Compare the ANALYSIS_RESULT blocks to determine if failures have the same root cause:

```python
def compare_root_causes(results: dict) -> dict:
    """
    Compare analysis results across releases.

    Returns:
        {
            "same_root_cause": bool,
            "similarity_score": float (0.0-1.0),
            "comparison_details": {...}
        }
    """

    if len(results) < 2:
        return {
            "same_root_cause": False,
            "similarity_score": 0.0,
            "reason": "Insufficient data for comparison"
        }

    # Extract origin release result
    origin_release = list(results.keys())[0]
    origin_result = results[origin_release]

    # Compare with each cascade release
    comparisons = []
    for release, result in results.items():
        if release == origin_release:
            continue

        comparison = compare_two_results(origin_result, result)
        comparisons.append(comparison)

    # Aggregate comparisons
    if not comparisons:
        return {"same_root_cause": False, "similarity_score": 0.0}

    avg_similarity = sum(c["similarity_score"] for c in comparisons) / len(comparisons)
    all_same = all(c["same_root_cause"] for c in comparisons)

    return {
        "same_root_cause": all_same,
        "similarity_score": avg_similarity,
        "comparisons": comparisons,
        "origin_release": origin_release
    }

def compare_two_results(result1: dict, result2: dict) -> dict:
    """Compare two analysis results."""

    # Check confidence levels
    conf1 = int(result1.get("confidence_level", 0))
    conf2 = int(result2.get("confidence_level", 0))

    if conf1 < 3 or conf2 < 3:
        return {
            "same_root_cause": False,
            "similarity_score": 0.0,
            "reason": "Low confidence in one or both analyses"
        }

    # Compare affected components
    components1 = set(result1.get("affected_components", "").lower().split(", "))
    components2 = set(result2.get("affected_components", "").lower().split(", "))

    component_overlap = len(components1 & components2) / max(len(components1 | components2), 1)

    # Compare error patterns
    patterns1 = set(result1.get("key_error_patterns", "").lower().split(", "))
    patterns2 = set(result2.get("key_error_patterns", "").lower().split(", "))

    # Look for common error substrings (fuzzy matching)
    pattern_matches = 0
    for p1 in patterns1:
        for p2 in patterns2:
            if p1 in p2 or p2 in p1:
                pattern_matches += 1
                break

    pattern_similarity = pattern_matches / max(len(patterns1), len(patterns2), 1)

    # Compare root cause summaries (semantic similarity)
    summary1 = result1.get("root_cause_summary", "").lower()
    summary2 = result2.get("root_cause_summary", "").lower()

    # Simple keyword matching (can be enhanced with NLP)
    words1 = set(summary1.split())
    words2 = set(summary2.split())
    summary_overlap = len(words1 & words2) / max(len(words1 | words2), 1)

    # Calculate overall similarity score
    similarity_score = (
        component_overlap * 0.4 +
        pattern_similarity * 0.4 +
        summary_overlap * 0.2
    )

    # Determine if same root cause (threshold: 0.6)
    same_root_cause = similarity_score >= 0.6 and component_overlap > 0.3

    return {
        "same_root_cause": same_root_cause,
        "similarity_score": similarity_score,
        "component_overlap": component_overlap,
        "pattern_similarity": pattern_similarity,
        "summary_overlap": summary_overlap
    }
```

### Step 6: Generate Output JSON

Create structured output with confirmed cascades and false positives:

```json
{
  "generated": "2026-04-02T22:30:00Z",
  "analysis_type": "root_cause_comparison",
  "similarity_analyzed": true,
  "confirmed_cascades": [
    {
      "test_name": "[sig-etcd] etcd should not lose data",
      "severity": "HIGH",
      "same_root_cause": true,
      "similarity_score": 0.85,
      "origin": {
        "release": "4.22",
        "regression_id": 35000,
        "root_cause_summary": "etcd data corruption due to fsync failures",
        "affected_components": "etcd, storage",
        "confidence_level": 5
      },
      "cascade_releases": [
        {
          "release": "4.21",
          "regression_id": 36000,
          "root_cause_summary": "etcd data corruption due to fsync failures",
          "affected_components": "etcd, storage",
          "confidence_level": 5,
          "similarity_to_origin": 0.85
        }
      ],
      "analysis_by_release": {
        "4.22": { /* full ANALYSIS_RESULT */ },
        "4.21": { /* full ANALYSIS_RESULT */ }
      }
    }
  ],
  "false_positives": [
    {
      "test_name": "[sig-arch][Feature:ClusterUpgrade] Cluster should remain functional",
      "severity": "CRITICAL",
      "same_root_cause": false,
      "similarity_score": 0.15,
      "reason": "Different root causes across releases",
      "origin": {
        "release": "4.22",
        "root_cause_summary": "Local registry ImagePullBackOff on bare metal"
      },
      "cascade_releases": [
        {
          "release": "4.21",
          "root_cause_summary": "CNI configuration loss during upgrade",
          "similarity_to_origin": 0.10
        },
        {
          "release": "4.20",
          "root_cause_summary": "External quay.io registry HTTP 502 errors",
          "similarity_to_origin": 0.20
        }
      ],
      "analysis_by_release": {
        "4.22": { /* full ANALYSIS_RESULT */ },
        "4.21": { /* full ANALYSIS_RESULT */ },
        "4.20": { /* full ANALYSIS_RESULT */ }
      }
    }
  ],
  "unable_to_analyze": [
    {
      "test_name": "...",
      "reason": "No Prow job URLs available"
    }
  ]
}
```

**Save to file**:

```bash
cat > .work/detect-backport-regressions/confirmed_cascades.json <<< "$output_json"
```

## Output Format

The skill outputs JSON to stdout and saves it to `.work/detect-backport-regressions/confirmed_cascades.json`.

**Key sections**:
- `confirmed_cascades`: Cascades with `same_root_cause: true`
- `false_positives`: Cascades with `same_root_cause: false`
- `unable_to_analyze`: Cascades missing data for analysis

## Similarity Threshold

The default similarity threshold is **0.6** (60% similarity required).

Adjust the threshold based on:
- **Higher threshold (0.7-0.8)**: Fewer false positives, more false negatives
- **Lower threshold (0.4-0.5)**: More false positives, fewer false negatives

## Performance Considerations

**Parallel Execution**: This skill can be time-intensive because it launches multiple subagents. To maximize performance:

1. **Launch all subagents in a single message** with multiple Task tool calls
2. **Limit cascade analysis**: Use `--min-cascade 2` to focus on more severe cases
3. **Batch processing**: Process cascades in groups if there are many

**Typical execution times**:
- 1 cascade (5 releases): ~3-5 minutes
- 5 cascades (avg 3 releases each): ~10-15 minutes
- 10+ cascades: Consider running in batches

## Error Handling

**Missing Prow URLs**:
- Some regressions may not have sample failed jobs
- Mark as "unable_to_analyze" and continue with others

**Subagent failures**:
- If a subagent fails to analyze a job, mark that release as low confidence
- Can still compare remaining releases

**Low confidence results**:
- If confidence_level < 3, flag for manual review
- Don't automatically classify as false positive

## Example Usage

This skill is typically invoked after `detect-potential-cascades`:

```bash
# Step 1: Detect potential cascades
# (Skill: detect-potential-cascades)

# Step 2: Analyze similarity (this skill)
# Agent reads this skill and executes the steps above

# Step 3: Generate report
# (Skill: generate-cascade-report)
```

## See Also

- `detect-potential-cascades` - Identify potential cascades by test name matching
- `generate-cascade-report` - Generate HTML/Markdown reports from confirmed cascades
- `ci:fetch-regression-details` - Get Prow job URLs from regression IDs
- `ci:prow-job-analyze-test-failure` - Analyze individual Prow job failures
