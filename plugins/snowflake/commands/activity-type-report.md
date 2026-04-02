---
description: Classify Jira issues into activity types using AI and generate an interactive sankey report
argument-hint: <projects> [months] [--sample [N]] [--todo | --all]
---

## Name
snowflake:activity-type-report

## Synopsis
```bash
/snowflake:activity-type-report <projects> [months]
/snowflake:activity-type-report <projects> [months] --sample [N]
/snowflake:activity-type-report <projects> [months] --todo
/snowflake:activity-type-report <projects> [months] --all
```

## Description

Fetches Jira issues from Snowflake, classifies each into an activity type using AI, and generates an interactive HTML report with sankey diagrams, charts, and a searchable detail table with direct Jira links.

Activity type categories:
1. **Associate Wellness & Development** -- training, learning, mentorship, team building
2. **Incidents & Support** -- production incidents, customer escalations, on-call, firefighting
3. **Security & Compliance** -- CVE remediation, security vulnerabilities, compliance, audits
4. **Quality / Stability / Reliability** -- bug fixes, flaky tests, CI reliability, monitoring
5. **Future Sustainability** -- tech debt, architecture improvements, infrastructure modernization
6. **Product / Portfolio Work** -- features, enhancements, roadmap items, integrations
7. **Uncategorized** -- insufficient information to classify

## Implementation

**IMPORTANT: Run all phases sequentially without pausing for user confirmation.** This command should execute end-to-end unattended. Do not ask the user to confirm before writing files, running scripts, or proceeding to the next phase. Only stop if an error occurs that requires user intervention (e.g., auth failure, missing MCP server).

### Phase 1: Verify Snowflake Connection

Read and follow the `setup-snowflake` skill. This checks for the Snowflake MCP server, guides the user through setup if needed, and sets the session context (`JIRA_CLOUDMARTS_GROUP` role, `JIRA_DB.CLOUD_MARTS` schema).

If setup fails, abort with the guidance message from the skill. Do not proceed without a working Snowflake connection.

### Phase 2: Discover Schema

Query the available views and columns to build adaptive SQL:

```sql
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = 'CLOUD_MARTS'
ORDER BY TABLE_NAME
```

```sql
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'CLOUD_MARTS' AND TABLE_NAME = 'JIRA_ISSUE'
ORDER BY ORDINAL_POSITION
```

Use the results to determine which columns and join views are available. The schema may vary -- adapt queries accordingly.

**Important**: When joining to lookup views like `JIRA_ISSUETYPE`, always check their column names first via `INFORMATION_SCHEMA.COLUMNS`. For example, `JIRA_ISSUETYPE` uses `PNAME` (not `NAME`) for the type label.

### Phase 3: Fetch Issues

Build and execute a SQL query to fetch issues for the specified projects and time range. Use the Snowflake MCP `execute_sql` tool.

Parse the arguments from the command invocation. The raw args string may contain:
- First token: comma-separated project keys (required)
- Second token: lookback months as an integer (optional, default: 6). If the token is `--sample` or starts with `--`, skip it and use default.
- `--sample` flag anywhere: enable sampling mode. If followed by an integer, use that as sample size; otherwise auto-recommend.
- `--todo` flag anywhere: fetch only non-closed issues (open/backlog work)
- `--all` flag anywhere: fetch all issues regardless of status
- If neither `--todo` nor `--all` is specified, **default to closed issues with work-completed resolutions** (`ji.ISSUESTATUS = 'Closed'` AND resolution is `Done`, `Done-Errata`, or `NULL`). This excludes no-work closures like Duplicate, Won't Do, Obsolete, Not a Bug, Can't Do, Cannot Reproduce, and MirrorOrphan.

For example, `ACM,DPTP,TRT 6 --sample 200` means projects=ACM,DPTP,TRT, months=6, sample mode with N=200, closed issues only.
And `ACM,DPTP,TRT --todo` means projects=ACM,DPTP,TRT, months=6 (default), open/backlog issues only.

Core query pattern (adapt based on available columns/views):

```sql
SELECT
    ji.ISSUEKEY,
    ji.PROJECT_KEY,
    ji.SUMMARY,
    SUBSTR(ji.DESCRIPTION, 1, 2000) AS DESCRIPTION_EXCERPT,
    ji.CREATED,
    -- join for issue type name if JIRA_ISSUETYPE view exists: jit.PNAME AS ISSUE_TYPE
    -- ISSUESTATUS is a string column on JIRA_ISSUE, use directly: ji.ISSUESTATUS AS STATUS
FROM JIRA_ISSUE ji
-- adaptive joins based on schema discovery
WHERE ji.PROJECT_KEY IN ('DPTP', 'TRT', ...)
  -- Date filter depends on mode:
  -- Default (completed work): AND ji.RESOLUTIONDATE >= DATEADD(month, -6, CURRENT_DATE())
  -- --todo (open work):       AND ji.CREATED >= DATEADD(month, -6, CURRENT_DATE())
  -- --all:                    AND ji.CREATED >= DATEADD(month, -6, CURRENT_DATE())
  -- Status/resolution filter (apply based on flags):
  -- Default (no flag):  AND ji.ISSUESTATUS = 'Closed'
  --                     AND (ji.RESOLUTION IN ('Done', 'Done-Errata') OR ji.RESOLUTION IS NULL)
  -- --todo:             AND ji.ISSUESTATUS != 'Closed'
  -- --all:              (no status filter, no resolution filter)
ORDER BY ji.CREATED DESC
```

If `JIRA_NODEASSOCIATION` and `JIRA_COMPONENT` views exist, also fetch components:

```sql
SELECT
    ji.ISSUEKEY,
    LISTAGG(c.CNAME, ', ') WITHIN GROUP (ORDER BY c.CNAME) AS COMPONENTS
FROM JIRA_ISSUE ji
LEFT JOIN JIRA_NODEASSOCIATION na
    ON na.SOURCE_NODE_ID = ji.ID AND na.ASSOCIATION_TYPE = 'IssueComponent'
LEFT JOIN JIRA_COMPONENT c ON c.ID = na.SINK_NODE_ID
WHERE ji.PROJECT_KEY IN (...)
  -- Apply same date filter as main query (RESOLUTIONDATE for default, CREATED for --todo/--all)
  -- Apply same status/resolution filter as main query (default/--todo/--all)
GROUP BY ji.ISSUEKEY
```

**Important**: Snowflake MCP may return results in pages. For large datasets, first run a `COUNT(*)` query to determine the total, then issue parallel `LIMIT 10000 OFFSET N` queries to fetch all pages. Proceed immediately to Phase 3.5 with the results — do not ask the user.

### Phase 3.5: Assemble Data and Compute Output Directory

Write a Python script inline (via Bash tool) that:
1. Reads all the persisted Snowflake tool result JSON files from the current session
2. Parses and deduplicates issues by `ISSUEKEY`
3. Computes the sorted project list and date range
4. Creates the output directory using a hash-based name (avoids filesystem limits for many projects)
5. Writes `issues.json` and `projects.txt`

```python
import json, glob, os, hashlib

# Read persisted tool results — each is a JSON array with a 'text' field containing the SQL results
tool_results_dir = "<path to tool-results dir from persisted-output messages>"
files = sorted(glob.glob(os.path.join(tool_results_dir, "toolu_*.json")))

all_issues = []
for f in files:
    with open(f) as fh:
        data = json.load(fh)
    if isinstance(data, list) and len(data) > 0:
        text = data[0].get("text", "[]")
        all_issues.extend(json.loads(text))

# Deduplicate by ISSUEKEY
seen = set()
deduped = [i for i in all_issues if i.get("ISSUEKEY") not in seen and not seen.add(i["ISSUEKEY"])]

# Compute directory
projects = sorted(set(i["PROJECT_KEY"] for i in deduped))
projects_str = ",".join(projects)
h = hashlib.sha256(projects_str.encode()).hexdigest()[:12]
dates = sorted([i["CREATED"] for i in deduped if i.get("CREATED")])
min_date, max_date = dates[0][:10], dates[-1][:10]

run_dir = f".work/snowflake/reports/{len(projects)}projects_{h}/{min_date}_{max_date}"
os.makedirs(run_dir, exist_ok=True)
with open(f"{run_dir}/issues.json", "w") as fh: json.dump(deduped, fh)
with open(f"{run_dir}/projects.txt", "w") as fh: fh.write(projects_str)
```

**Important**: Be careful to only include tool result files from the *current* Snowflake fetch queries, not from previous runs. Match files by the tool use IDs from the current session's fetch queries.

All subsequent phases write to `$RUN_DIR/`.

### Phase 4: Classify Issues

**Cache check**: If `$RUN_DIR/classified_issues.json` already exists (full mode) or `$RUN_DIR/estimates.json` already exists (sample mode), skip classification entirely and go directly to Phase 5. Tell the user: "Found existing classification in `$RUN_DIR/` — skipping Vertex AI API call to save tokens. Delete the directory to force re-classification."

Otherwise, write the fetched issues to `$RUN_DIR/issues.json` as a JSON array. Each object should include: `ISSUEKEY`, `PROJECT_KEY`, `SUMMARY`, `DESCRIPTION_EXCERPT`, `CREATED`, `ISSUE_TYPE`, `STATUS`, and `COMPONENTS` (if available).

Find the scripts directory:
```bash
SCRIPT_DIR=$(find ~/.claude/plugins -path '*/snowflake/scripts' -type d -print -quit 2>/dev/null)
```

#### Full classification mode (default)

```bash
python3 "$SCRIPT_DIR/classify_issues.py" \
  --input $RUN_DIR/issues.json \
  --output $RUN_DIR/classified_issues.json
```

#### Sample mode (`--sample`)

If the user passed `--sample` (with optional sample size N, default: auto-recommended):

**Step 1: Draw stratified sample**
```bash
python3 "$SCRIPT_DIR/sample_and_estimate.py" \
  --input $RUN_DIR/issues.json \
  --draw-sample $RUN_DIR/sample_to_classify.json \
  --sample-size ${N:-0}
```
(0 = auto-recommend based on ±2.5% target precision, typically ~400 issues)

**Step 2: Classify only the sample**
```bash
python3 "$SCRIPT_DIR/classify_issues.py" \
  --input $RUN_DIR/sample_to_classify.json \
  --output $RUN_DIR/classified_sample.json
```

**Step 3: Bayesian estimation**
```bash
python3 "$SCRIPT_DIR/sample_and_estimate.py" \
  --input $RUN_DIR/issues.json \
  --classified-sample $RUN_DIR/classified_sample.json \
  --output $RUN_DIR/estimates.json
```

The script reads `CLOUD_ML_REGION` and `ANTHROPIC_VERTEX_PROJECT_ID` from environment variables (already set in the org's devcontainer). It uses `ANTHROPIC_SMALL_FAST_MODEL` for the model (defaults to `claude-sonnet-4-6`).

If the script fails with an auth error, tell the user to run: `gcloud auth login`

Full mode processes issues in batches of 15. Sample mode classifies only the sample (~369 issues by default), completing in ~3 minutes.

**Run all steps without asking for confirmation.** Set a generous timeout (600s) on the classify step since it makes sequential API calls. In sample mode, run Steps 1-3 sequentially in a single Bash invocation if possible.

### Phase 5: Generate Report

Locate the `generate_sankey.py` script in the same `scripts/` directory and run it:

Construct the report title based on the status filter and sampling mode:
- Default (closed only): `"Activity Type Report"` or `"Activity Type Report (Sampled Estimate)"`
- `--todo`: `"Activity Type Report — Open/Backlog"` or `"Activity Type Report — Open/Backlog (Sampled Estimate)"`
- `--all`: `"Activity Type Report — All Statuses"` or `"Activity Type Report — All Statuses (Sampled Estimate)"`

#### Full mode:
```bash
PROJECTS=$(cat $RUN_DIR/projects.txt)
USAGE=$(cat $RUN_DIR/classified_issues_usage.txt 2>/dev/null || echo "")
python3 "$SCRIPT_DIR/generate_sankey.py" \
  --input $RUN_DIR/classified_issues.json \
  --output $RUN_DIR/activity-type-report.html \
  --title "$TITLE" \
  --projects "$PROJECTS" \
  --months 6 \
  --usage "$USAGE"
```

#### Sample mode:
```bash
PROJECTS=$(cat $RUN_DIR/projects.txt)
USAGE=$(cat $RUN_DIR/classified_sample_usage.txt 2>/dev/null || echo "")
python3 "$SCRIPT_DIR/generate_sankey.py" \
  --input $RUN_DIR/classified_sample.json \
  --output $RUN_DIR/activity-type-report.html \
  --title "$TITLE" \
  --projects "$PROJECTS" \
  --months 6 \
  --usage "$USAGE" \
  --estimates $RUN_DIR/estimates.json
```

### Phase 6: Present Results

**Always** display a text summary directly in the conversation. This is the most important output — leaders need the distribution at a glance without opening a file.

Include the status filter in the summary header:
- Default: "1,354 closed issues across 5 projects ..."
- `--todo`: "441 open issues across 5 projects ..."
- `--all`: "1,354 issues (all statuses) across 5 projects ..."

#### Full mode summary:

```
Activity Type Report: $RUN_DIR/activity-type-report.html

54,478 issues across 52 projects (2025-10-02 to 2026-04-07)

Activity Type Distribution:
  Quality / Stability / Reliability    98 (39.7%)
  Product / Portfolio Work             62 (25.1%)
  Future Sustainability                38 (15.4%)
  Incidents & Support                  24  (9.7%)
  Security & Compliance                12  (4.9%)
  Associate Wellness & Development      8  (3.2%)
  Uncategorized                         5  (2.0%)

Classification cost: 86,313 input + 13,008 output = 99,321 tokens, $0.45
```

#### Sample mode summary:

Include credible intervals and sample metadata:

```
Activity Type Report (Sampled Estimate): $RUN_DIR/activity-type-report.html

54,478 issues across 52 projects (2025-10-02 to 2026-04-07)
Sample: 369 classified (0.7%) — 25 API calls, $0.45

Activity Type Distribution (95% Credible Intervals):
  Quality / Stability / Reliability  43.4%  [38.4% — 48.3%]
  Product / Portfolio Work           14.9%  [11.5% — 18.6%]
  Security & Compliance              11.4%  [ 8.5% — 14.8%]
  Uncategorized                      11.2%  [ 8.2% — 14.6%]
  Future Sustainability               9.3%  [ 6.6% — 12.5%]
  Associate Wellness & Development    6.4%  [ 4.1% —  9.1%]
  Incidents & Support                 3.5%  [ 1.9% —  5.5%]
```

Read the estimates from `$RUN_DIR/estimates.json` (field: `overall.estimates[]`, each with `category`, `posterior_mean`, `ci_low`, `ci_high`) and the usage from `$RUN_DIR/classified_sample_usage.txt` (or `classified_issues_usage.txt` in full mode).

After the summary, tell the user the HTML report is available at the path shown and can be opened directly in a browser from their host filesystem.

## Arguments

- **$1 - projects** (required)
  - Comma-separated list of Jira project keys
  - Examples: `DPTP`, `DPTP,TRT,ART,OCPERT`
  - Case-sensitive (must match Snowflake data exactly)

- **$2 - months** (optional, default: 6)
  - Number of months to look back from today
  - For completed work (default): filters on `RESOLUTIONDATE` — "work resolved in the last N months"
  - For open work (`--todo`) and all (`--all`): filters on `CREATED` — "issues created in the last N months"
  - Example: `3` for last 3 months, `12` for a full year

- **--sample [N]** (optional)
  - Enable sampling mode: classify a random sample and estimate the full distribution using Bayesian inference (Dirichlet-Multinomial)
  - N = sample size (default: auto-recommended for ±2.5% precision, typically ~400)
  - The report shows posterior means with 95% credible intervals instead of exact counts
  - Dramatically reduces API cost and time for large datasets (e.g., 27 API calls vs. 1,000+)
  - Uses stratified sampling by project to ensure all projects are represented

- **--todo** (optional)
  - Analyze only open/backlog issues (non-closed statuses: New, In Progress, To Do, Refinement, etc.)
  - Useful for understanding "what kind of work is ahead of us"
  - Mutually exclusive with `--all`

- **--all** (optional)
  - Analyze all issues regardless of status (closed + open)
  - Mutually exclusive with `--todo`
  - Without `--todo` or `--all`, only closed issues are analyzed (completed work)

## Return Value

**Format**: Interactive self-contained HTML file at `.work/snowflake/reports/{projects}/{start}_{end}/activity-type-report.html`

Each run produces a directory under `.work/snowflake/reports/` containing the raw issues, classified issues, and HTML report. Re-running the same projects and date range reuses existing classifications.

The report includes:
- Sankey diagram: Project to Activity Type flows
- Summary statistics
- Searchable, paginated detail table with direct Jira links per issue
- CSV export capability

## Examples

1. **Single project, default lookback:**
   ```bash
   /snowflake:activity-type-report DPTP
   ```

2. **Multiple projects, 3 months:**
   ```bash
   /snowflake:activity-type-report DPTP,TRT,ART,OCPERT 3
   ```

3. **Large org, full year:**
   ```bash
   /snowflake:activity-type-report DPTP,TRT,ART,OCPERT,OCPCRT 12
   ```

4. **Sampled estimate (auto sample size):**
   ```bash
   /snowflake:activity-type-report ACM,AGENT,API,ARO,ART,DPTP,TRT 6 --sample
   ```

5. **Sampled estimate (explicit sample size):**
   ```bash
   /snowflake:activity-type-report ACM,AGENT,API,ARO,ART,DPTP,TRT 6 --sample 200
   ```

6. **Open/backlog issues only:**
   ```bash
   /snowflake:activity-type-report DPTP,TRT 6 --todo
   ```

7. **All statuses (closed + open):**
   ```bash
   /snowflake:activity-type-report DPTP,TRT 6 --all
   ```

8. **Sampled backlog analysis:**
   ```bash
   /snowflake:activity-type-report ACM,AGENT,API,ARO,ART,DPTP,TRT 6 --todo --sample
   ```

## See Also

- `/jira:categorize-activity-type` -- Classify a single Jira issue via the Atlassian MCP (does not require Snowflake)
- `/teams:health-check` -- Team health analysis based on regressions and Jira metrics

## Notes

- **Snowflake MCP required**: The Snowflake MCP server must be configured. The command guides users through setup if it is not.
- **AI classification**: Issues are classified by calling Claude directly via Vertex AI API (not sub-agents). Results may vary slightly between runs as models improve.
- **Scalability**: Classification processes ~15 issues per API call. Expect ~30-60 seconds for most datasets, up to 2-3 minutes for very large ones (2000+).
- **No write operations**: This command only reads from Snowflake and writes local files. It never modifies Jira data.
- **Self-contained output**: The HTML report works offline after generation -- no server needed.
- **Cached classifications**: Re-running the same projects and date range skips the Vertex AI API call and reuses the existing `classified_issues.json` (or `estimates.json` in sample mode). Delete the run directory to force re-classification.
- **Completed work by default**: By default, only closed issues with work-completed resolutions (`Done`, `Done-Errata`, or `NULL`) are analyzed — this excludes no-work closures like Duplicate, Won't Do, Obsolete, Not a Bug, Can't Do, Cannot Reproduce, and MirrorOrphan (~25% of closed issues globally). Use `--todo` for open/backlog work, or `--all` for everything.
- **Sampling mode**: For large datasets (thousands of issues), `--sample` uses Bayesian inference to estimate the activity type distribution from a small classified sample. Uses a Dirichlet-Multinomial conjugate model with uninformative priors — implemented entirely with Python stdlib (`random.gammavariate`). The report clearly labels results as estimates and shows credible intervals.
