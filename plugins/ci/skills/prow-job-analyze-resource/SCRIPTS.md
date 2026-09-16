# Prow Job Analyze Resource Scripts

This directory contains Python scripts to parse Prow job artifacts and generate interactive HTML reports.

## Scripts

### create_inline_html_files.py

Converts collected log files into self-contained HTML files for browser-based inspection. Run `python3 create_inline_html_files.py <logs_dir> <build_id>` when the raw logs need an inline viewer before report generation.

### parse_all_logs.py

Parses audit logs from Prow job artifacts and outputs structured JSON.

**Usage:**
```bash
python3 parse_all_logs.py <resource_pattern> <audit_logs_directory>
```

**Arguments:**
- `resource_pattern`: Pattern to search for (e.g., "e2e-test-project-api-p28m")
- `audit_logs_directory`: Path to audit logs directory

**Output:**
- Writes JSON to stdout
- Writes status messages to stderr (first 2 lines)
- Use `tail -n +3` to clean the output

**Example:**
```bash
python3 plugins/ci/skills/prow-job-analyze-resource/parse_all_logs.py \
  e2e-test-project-api-p28m \
  .work/prow-job-analyze-resource/1964725888612306944/logs/artifacts/e2e-aws-ovn-techpreview/gather-extra/artifacts/audit_logs \
  > .work/prow-job-analyze-resource/1964725888612306944/tmp/audit_entries.json 2>&1

tail -n +3 .work/prow-job-analyze-resource/1964725888612306944/tmp/audit_entries.json \
  > .work/prow-job-analyze-resource/1964725888612306944/tmp/audit_entries_clean.json
```

**What it does:**
1. Recursively finds all .log files in the audit logs directory
2. Parses each line as JSON (JSONL format)
3. Filters entries where the resource name or namespace contains the pattern
4. Extracts key fields: verb, user, response code, namespace, resource type, timestamp
5. Generates human-readable summaries for each entry
6. Outputs sorted by timestamp

### generate_html_report.py

Generates an interactive HTML report from parsed audit log entries.

**Usage:**
```bash
python3 generate_html_report.py <entries.json> <prowjob_name> <build_id> <target> <resource_name> <gcsweb_url>
```

**Arguments:**
- `entries.json`: Path to the cleaned JSON file from parse_all_logs.py
- `prowjob_name`: Name of the Prow job
- `build_id`: Build ID (numeric)
- `target`: CI operator target name
- `resource_name`: Primary resource name for the report
- `gcsweb_url`: Full gcsweb URL to the Prow job

**Output:**
- Creates `.work/prow-job-analyze-resource/{build_id}/{resource_name}.html`

**Example:**
```bash
python3 plugins/ci/skills/prow-job-analyze-resource/generate_html_report.py \
  .work/prow-job-analyze-resource/1964725888612306944/tmp/audit_entries_clean.json \
  "periodic-ci-openshift-release-master-okd-scos-4.20-e2e-aws-ovn-techpreview" \
  "1964725888612306944" \
  "e2e-aws-ovn-techpreview" \
  "e2e-test-project-api-p28mx" \
  "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/logs/periodic-ci-openshift-release-master-okd-scos-4.20-e2e-aws-ovn-techpreview/1964725888612306944"
```

**Features:**
1. **Interactive Timeline**:
   - Visual timeline showing all events with color-coded severity (blue=info, yellow=warn, red=error)
   - Hover over timeline to see approximate time at cursor position
   - Click events to jump to detailed entry
   - Start/End times displayed in timeline header

2. **Multi-Select Filters**:
   - Filter by multiple log levels simultaneously (info/warn/error)
   - Filter by multiple verbs simultaneously (create/get/delete/etc.)
   - All levels selected by default, verbs show all when none selected

3. **Search**: Full-text search across summaries and content

4. **Expandable Details**: Click to view full JSON content for each entry

5. **Scroll to Top**: Floating button appears when scrolled down, smoothly returns to top

6. **Dark Theme**: Modern, readable dark theme optimized for long viewing sessions

7. **Statistics**: Summary stats showing total events, top verbs

**HTML Report Structure:**
- Header with metadata (prowjob name, build ID, target, resource, GCS URL)
- Statistics section with event counts
- Interactive SVG timeline with:
  - Hover tooltip showing time at cursor
  - Start/End time display
  - Click events to jump to entries
- Multi-select filter controls (level, verb, search)
- Sorted list of entries with expandable JSON details
- All CSS and JavaScript inline for portability

## Workflow

Complete workflow for analyzing a resource:

```bash
# 1. Set variables
PROW_URL="https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/logs/periodic-ci-openshift-release-master-okd-scos-4.20-e2e-aws-ovn-techpreview/1964725888612306944"
RESOURCE_PATTERN="e2e-test-project-api-p28m"
RESOURCE_NAME="e2e-test-project-api-p28mx"
TARGET="e2e-aws-ovn-techpreview"

# 2. Resolve bucket and path from the job URL.
# parse_url.py remaps only test-platform-results to test-platform-results-public;
# other buckets (including prow-artifact-archive) are kept as-is.
eval "$(
  python3 plugins/ci/skills/prow-job-analyze-resource/parse_url.py "$PROW_URL" \
  | python3 -c 'import json, shlex, sys
d = json.load(sys.stdin)
print("BUILD_ID=" + shlex.quote(d["build_id"]))
print("PROWJOB_NAME=" + shlex.quote(d["prowjob_name"]))
print("GCS_BASE_PATH=" + shlex.quote(d["gcs_base_path"]))
print("BUCKET=" + shlex.quote(d["bucket"]))
print("BUCKET_PATH=" + shlex.quote(d["bucket_path"]))
'
)"
GCSWEB_URL="https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/${BUCKET}/${BUCKET_PATH}"

# 3. Create working directory
mkdir -p .work/prow-job-analyze-resource/${BUILD_ID}/logs
mkdir -p .work/prow-job-analyze-resource/${BUILD_ID}/tmp

# 4. Download prowjob.json
gcloud storage cp \
  "${GCS_BASE_PATH}prowjob.json" \
  .work/prow-job-analyze-resource/${BUILD_ID}/logs/prowjob.json \
  --no-user-output-enabled

# 5. Download audit logs
mkdir -p .work/prow-job-analyze-resource/${BUILD_ID}/logs/artifacts/${TARGET}/gather-extra/artifacts/audit_logs
gcloud storage cp -r \
  "${GCS_BASE_PATH}artifacts/${TARGET}/gather-extra/artifacts/audit_logs/" \
  .work/prow-job-analyze-resource/${BUILD_ID}/logs/artifacts/${TARGET}/gather-extra/artifacts/audit_logs/ \
  --no-user-output-enabled

# 6. Parse audit logs
python3 plugins/ci/skills/prow-job-analyze-resource/parse_all_logs.py \
  ${RESOURCE_PATTERN} \
  .work/prow-job-analyze-resource/${BUILD_ID}/logs/artifacts/${TARGET}/gather-extra/artifacts/audit_logs \
  > .work/prow-job-analyze-resource/${BUILD_ID}/tmp/audit_entries.json 2>&1

# 7. Clean JSON output
tail -n +3 .work/prow-job-analyze-resource/${BUILD_ID}/tmp/audit_entries.json \
  > .work/prow-job-analyze-resource/${BUILD_ID}/tmp/audit_entries_clean.json

# 8. Generate HTML report
python3 plugins/ci/skills/prow-job-analyze-resource/generate_html_report.py \
  .work/prow-job-analyze-resource/${BUILD_ID}/tmp/audit_entries_clean.json \
  "${PROWJOB_NAME}" \
  "${BUILD_ID}" \
  "${TARGET}" \
  "${RESOURCE_NAME}" \
  "${GCSWEB_URL}"

# 9. Open report in browser
xdg-open .work/prow-job-analyze-resource/${BUILD_ID}/${RESOURCE_NAME}.html
```

## Important Notes

1. **Pattern Matching**: The `resource_pattern` is used for substring matching. It will find resources with names containing the pattern.
   - Example: Pattern `e2e-test-project-api-p28m` matches `e2e-test-project-api-p28mx`

2. **Namespaces vs Projects**: In OpenShift, searching for a namespace will also find related project resources.

3. **JSON Cleaning**: The parse script outputs status messages to stderr. Use `tail -n +3` to skip the first 2 lines.

4. **Working Directory**: All artifacts are stored in `.work/prow-job-analyze-resource/` which is in .gitignore.

5. **No Authentication Required**: The `test-platform-results-public` GCS bucket is publicly accessible.

## Troubleshooting

**Issue**: "No log entries found matching the specified resources"
- Check the resource name spelling
- Try a shorter pattern (e.g., just "project-api" instead of full name)
- Verify the resource actually exists in the job artifacts

**Issue**: "JSON decode error"
- Make sure you used `tail -n +3` to clean the JSON output
- Check that the parse script completed successfully

**Issue**: "Destination URL must name an existing directory"
- Create the target directory with `mkdir -p` before running gcloud commands
