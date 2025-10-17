---
name: Prow Job Analyze Resource
description: Analyze Kubernetes resource lifecycle in Prow CI job artifacts by parsing audit logs and pod logs from GCS, generating interactive HTML reports with timelines
---

# Prow Job Analyze Resource

This skill analyzes the lifecycle of Kubernetes resources during Prow CI job execution by downloading and parsing artifacts from Google Cloud Storage.

## When to Use This Skill

Use this skill when the user wants to:
- Debug Prow CI test failures by tracking resource state changes
- Understand when and how a Kubernetes resource was created, modified, or deleted during a test
- Analyze resource lifecycle across audit logs and pod logs from ephemeral test clusters
- Generate interactive HTML reports showing resource events over time
- Search for specific resources (pods, deployments, configmaps, etc.) in Prow job artifacts

## Prerequisites

Before starting, verify these prerequisites:

1. **gcloud CLI Installation**
   - Check if installed: `which gcloud`
   - If not installed, provide instructions for the user's platform
   - Installation guide: https://cloud.google.com/sdk/docs/install

2. **gcloud Authentication (Optional)**
   - The `test-platform-results` bucket is publicly accessible
   - No authentication is required for read access
   - Skip authentication checks

## Input Format

The user will provide:
1. **Prow job URL** - gcsweb URL containing `test-platform-results/`
   - Example: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/pr-logs/pull/30393/pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/`
   - URL may or may not have trailing slash

2. **Resource specifications** - Comma-delimited list in format `[namespace:][kind/]name`
   - Supports regex patterns for matching multiple resources
   - Examples:
     - `pod/etcd-0` - pod named etcd-0 in any namespace
     - `openshift-etcd:pod/etcd-0` - pod in specific namespace
     - `etcd-0` - any resource named etcd-0 (no kind filter)
     - `pod/etcd-0,configmap/cluster-config` - multiple resources
     - `resource-name-1|resource-name-2` - multiple resources using regex OR
     - `e2e-test-project-api-.*` - all resources matching the pattern

## Implementation Steps

### Step 1: Parse and Validate URL

1. **Extract bucket path**
   - Find `test-platform-results/` in URL
   - Extract everything after it as the GCS bucket relative path
   - If not found, error: "URL must contain 'test-platform-results/'"

2. **Extract build_id**
   - Search for pattern `/(\d{10,})/` in the bucket path
   - build_id must be at least 10 consecutive decimal digits
   - Handle URLs with or without trailing slash
   - If not found, error: "Could not find build ID (10+ digits) in URL"

3. **Extract prowjob name**
   - Find the path segment immediately preceding build_id
   - Example: In `.../pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/`
   - Prowjob name: `pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn`

4. **Construct GCS paths**
   - Bucket: `test-platform-results`
   - Base GCS path: `gs://test-platform-results/{bucket-path}/`
   - Ensure path ends with `/`

### Step 2: Parse Resource Specifications

For each comma-delimited resource spec:

1. **Parse format** `[namespace:][kind/]name`
   - Split on `:` to get namespace (optional)
   - Split remaining on `/` to get kind (optional) and name (required)
   - Store as structured data: `{namespace, kind, name}`

2. **Validate**
   - name is required
   - namespace and kind are optional
   - Examples:
     - `pod/etcd-0` → `{kind: "pod", name: "etcd-0"}`
     - `openshift-etcd:pod/etcd-0` → `{namespace: "openshift-etcd", kind: "pod", name: "etcd-0"}`
     - `etcd-0` → `{name: "etcd-0"}`

### Step 3: Create Working Directory

1. **Check for existing artifacts first**
   - Check if `.work/prow-job-analyze-resource/{build_id}/logs/` directory exists and has content
   - If it exists with content:
     - Use AskUserQuestion tool to ask:
       - Question: "Artifacts already exist for build {build_id}. Would you like to use the existing download or re-download?"
       - Options:
         - "Use existing" - Skip to artifact parsing step (Step 6)
         - "Re-download" - Continue to clean and re-download
     - If user chooses "Re-download":
       - Remove all existing content: `rm -rf .work/prow-job-analyze-resource/{build_id}/logs/`
       - Also remove tmp directory: `rm -rf .work/prow-job-analyze-resource/{build_id}/tmp/`
       - This ensures clean state before downloading new content
     - If user chooses "Use existing":
       - Skip directly to Step 6 (Parse Audit Logs)
       - Still need to download prowjob.json if it doesn't exist

2. **Create directory structure**
   ```bash
   mkdir -p .work/prow-job-analyze-resource/{build_id}/logs
   mkdir -p .work/prow-job-analyze-resource/{build_id}/tmp
   ```
   - Use `.work/prow-job-analyze-resource/` as the base directory (already in .gitignore)
   - Use build_id as subdirectory name
   - Create `logs/` subdirectory for all downloads
   - Create `tmp/` subdirectory for temporary files (intermediate JSON, etc.)
   - Working directory: `.work/prow-job-analyze-resource/{build_id}/`

### Step 4: Download and Validate prowjob.json

1. **Download prowjob.json**
   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/prowjob.json .work/prow-job-analyze-resource/{build_id}/logs/prowjob.json --no-user-output-enabled
   ```

2. **Parse and validate**
   - Read `.work/prow-job-analyze-resource/{build_id}/logs/prowjob.json`
   - Search for pattern: `--target=([a-zA-Z0-9-]+)`
   - If not found:
     - Display: "This is not a ci-operator job. The prowjob cannot be analyzed by this skill."
     - Explain: ci-operator jobs have a --target argument specifying the test target
     - Exit skill

3. **Extract target name**
   - Capture the target value (e.g., `e2e-aws-ovn`)
   - Store for constructing gather-extra path

### Step 5: Download Audit Logs and Pod Logs

1. **Construct gather-extra paths**
   - GCS path: `gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/`
   - Local path: `.work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/`

2. **Download audit logs**
   ```bash
   mkdir -p .work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/audit_logs
   gcloud storage cp -r gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/audit_logs/ .work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/audit_logs/ --no-user-output-enabled
   ```
   - Create directory first to avoid gcloud errors
   - Use `--no-user-output-enabled` to suppress progress output
   - If directory not found, warn: "No audit logs found. Job may not have completed or audit logging may be disabled."

3. **Download pod logs**
   ```bash
   mkdir -p .work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/pods
   gcloud storage cp -r gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/ .work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/pods/ --no-user-output-enabled
   ```
   - Create directory first to avoid gcloud errors
   - Use `--no-user-output-enabled` to suppress progress output
   - If directory not found, warn: "No pod logs found."

### Step 6: Parse Audit Logs and Pod Logs

**IMPORTANT: Use the provided Python script `parse_all_logs.py` from the skill directory to parse both audit logs and pod logs efficiently.**

**Usage:**
```bash
python3 plugins/prow-job/skills/prow-job-analyze-resource/parse_all_logs.py <resource_pattern> \
  .work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/audit_logs \
  .work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/pods \
  > .work/prow-job-analyze-resource/{build_id}/tmp/all_entries.json
```

**Resource Pattern Parameter:**
- The `<resource_pattern>` parameter supports **regex patterns**
- Use `|` (pipe) to search for multiple resources: `resource1|resource2|resource3`
- Use `.*` for wildcards: `e2e-test-project-.*`
- Simple substring matching still works: `my-namespace`
- Examples:
  - Single resource: `e2e-test-project-api-pkjxf`
  - Multiple resources: `e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx`
  - Pattern matching: `e2e-test-project-api-.*`

**Note:** The script outputs status messages to stderr which will display as progress. The JSON output to stdout is clean and ready to use.

**What the script does:**

1. **Find all log files**
   - Audit logs: `.work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/audit_logs/**/*.log`
   - Pod logs: `.work/prow-job-analyze-resource/{build_id}/logs/artifacts/{target}/gather-extra/artifacts/pods/**/*.log`

2. **Parse audit log files (JSONL format)**
   - Read file line by line
   - Each line is a JSON object (JSONL format)
   - Parse JSON into object `e`

3. **Extract fields from each audit log entry**
   - `e.verb` - action (get, list, create, update, patch, delete, watch)
   - `e.user.username` - user making request
   - `e.responseStatus.code` - HTTP response code (integer)
   - `e.objectRef.namespace` - namespace (if namespaced)
   - `e.objectRef.resource` - lowercase plural kind (e.g., "pods", "configmaps")
   - `e.objectRef.name` - resource name
   - `e.requestReceivedTimestamp` - ISO 8601 timestamp

4. **Filter matches for each resource spec**
   - Uses **regex matching** on `e.objectRef.namespace` and `e.objectRef.name`
   - Pattern matches if found in either namespace or name field
   - Supports all regex features:
     - Pipe operator: `resource1|resource2` matches either resource
     - Wildcards: `e2e-test-.*` matches all resources starting with `e2e-test-`
     - Character classes: `[abc]` matches a, b, or c
   - Simple substring matching still works for patterns without regex special chars
   - Performance optimization: plain strings use fast substring search

5. **For each audit log match, capture**
   - **Source**: "audit"
   - **Filename**: Full path to .log file
   - **Line number**: Line number in file (1-indexed)
   - **Level**: Based on `e.responseStatus.code`
     - 200-299: "info"
     - 400-499: "warn"
     - 500-599: "error"
   - **Timestamp**: Parse `e.requestReceivedTimestamp` to datetime
   - **Content**: Full JSON line (for expandable details)
   - **Summary**: Generate formatted summary
     - Format: `{verb} {resource}/{name} in {namespace} by {username} → HTTP {code}`
     - Example: `create pod/etcd-0 in openshift-etcd by system:serviceaccount:kube-system:deployment-controller → HTTP 201`

6. **Parse pod log files (plain text format)**
   - Read file line by line
   - Each line is plain text (not JSON)
   - Search for resource pattern in line content

7. **For each pod log match, capture**
   - **Source**: "pod"
   - **Filename**: Full path to .log file
   - **Line number**: Line number in file (1-indexed)
   - **Level**: Detect from glog format or default to "info"
     - Glog format: `E0910 11:43:41.153414 ...` (E=error, W=warn, I=info, F=fatal→error)
     - Non-glog format: default to "info"
   - **Timestamp**: Extract from start of line if present (format: `YYYY-MM-DDTHH:MM:SS.mmmmmmZ`)
   - **Content**: Full log line
   - **Summary**: First 200 characters of line (after timestamp if present)

8. **Combine and sort all entries**
   - Merge audit log entries and pod log entries
   - Sort all entries chronologically by timestamp
   - Entries without timestamps are placed at the end

### Step 7: Generate HTML Report

**IMPORTANT: Use the provided Python script `generate_html_report.py` from the skill directory.**

**Usage:**
```bash
python3 plugins/prow-job/skills/prow-job-analyze-resource/generate_html_report.py \
  .work/prow-job-analyze-resource/{build_id}/tmp/all_entries.json \
  "{prowjob_name}" \
  "{build_id}" \
  "{target}" \
  "{resource_pattern}" \
  "{gcsweb_url}"
```

**Resource Pattern Parameter:**
- The `{resource_pattern}` should be the **same pattern used in the parse script**
- For single resources: `e2e-test-project-api-pkjxf`
- For multiple resources: `e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx`
- The script will parse the pattern to display the searched resources in the HTML header

**Output:** The script generates `.work/prow-job-analyze-resource/{build_id}/{first_resource_name}.html`

**What the script does:**

1. **Determine report filename**
   - Format: `.work/prow-job-analyze-resource/{build_id}/{resource_name}.html`
   - Uses the primary resource name for the filename

2. **Sort all entries by timestamp**
   - Loads audit log entries from JSON
   - Sort chronologically (ascending)
   - Entries without timestamps go at the end

3. **Calculate timeline bounds**
   - min_time: Earliest timestamp found
   - max_time: Latest timestamp found
   - Time range: max_time - min_time

4. **Generate HTML structure**

   **Header Section:**
   ```html
   <div class="header">
     <h1>Prow Job Resource Lifecycle Analysis</h1>
     <div class="metadata">
       <p><strong>Prow Job:</strong> {prowjob-name}</p>
       <p><strong>Build ID:</strong> {build_id}</p>
       <p><strong>gcsweb URL:</strong> <a href="{original-url}">{original-url}</a></p>
       <p><strong>Target:</strong> {target}</p>
       <p><strong>Resources:</strong> {resource-list}</p>
       <p><strong>Total Entries:</strong> {count}</p>
       <p><strong>Time Range:</strong> {min_time} to {max_time}</p>
     </div>
   </div>
   ```

   **Interactive Timeline:**
   ```html
   <div class="timeline-container">
     <svg id="timeline" width="100%" height="100">
       <!-- For each entry, render colored vertical line -->
       <line x1="{position}%" y1="0" x2="{position}%" y2="100"
             stroke="{color}" stroke-width="2"
             class="timeline-event" data-entry-id="{entry-id}"
             title="{summary}">
       </line>
     </svg>
   </div>
   ```
   - Position: Calculate percentage based on timestamp between min_time and max_time
   - Color: white/lightgray (info), yellow (warn), red (error)
   - Clickable: Jump to corresponding entry
   - Tooltip on hover: Show summary

   **Log Entries Section:**
   ```html
   <div class="entries">
     <div class="filters">
       <!-- Filter controls: by level, by resource, by time range -->
     </div>

     <div class="entry" id="entry-{index}">
       <div class="entry-header">
         <span class="timestamp">{formatted-timestamp}</span>
         <span class="level badge-{level}">{level}</span>
         <span class="source">{filename}:{line-number}</span>
       </div>
       <div class="entry-summary">{summary}</div>
       <details class="entry-details">
         <summary>Show full content</summary>
         <pre><code>{content}</code></pre>
       </details>
     </div>
   </div>
   ```

   **CSS Styling:**
   - Modern, clean design with good contrast
   - Responsive layout
   - Badge colors: info=gray, warn=yellow, error=red
   - Monospace font for log content
   - Syntax highlighting for JSON (in audit logs)

   **JavaScript Interactivity:**
   ```javascript
   // Timeline click handler
   document.querySelectorAll('.timeline-event').forEach(el => {
     el.addEventListener('click', () => {
       const entryId = el.dataset.entryId;
       document.getElementById(entryId).scrollIntoView({behavior: 'smooth'});
     });
   });

   // Filter controls
   // Expand/collapse details
   // Search within entries
   ```

5. **Write HTML to file**
   - Script automatically writes to `.work/prow-job-analyze-resource/{build_id}/{resource_name}.html`
   - Includes proper HTML5 structure
   - All CSS and JavaScript are inline for portability

### Step 8: Present Results to User

1. **Display summary**
   ```
   Resource Lifecycle Analysis Complete

   Prow Job: {prowjob-name}
   Build ID: {build_id}
   Target: {target}

   Resources Analyzed:
   - {resource-spec-1}
   - {resource-spec-2}
   ...

   Artifacts downloaded to: .work/prow-job-analyze-resource/{build_id}/logs/

   Results:
   - Audit log entries: {audit-count}
   - Pod log entries: {pod-count}
   - Total entries: {total-count}
   - Time range: {min_time} to {max_time}

   Report generated: .work/prow-job-analyze-resource/{build_id}/{resource_name}.html

   Open in browser to view interactive timeline and detailed entries.
   ```

2. **Open report in browser**
   - Detect platform and automatically open the HTML report in the default browser
   - Linux: `xdg-open .work/prow-job-analyze-resource/{build_id}/{resource_name}.html`
   - macOS: `open .work/prow-job-analyze-resource/{build_id}/{resource_name}.html`
   - Windows: `start .work/prow-job-analyze-resource/{build_id}/{resource_name}.html`
   - On Linux (most common for this environment), use `xdg-open`

3. **Offer next steps**
   - Ask if user wants to search for additional resources in the same job
   - Ask if user wants to analyze a different Prow job
   - Explain that artifacts are cached in `.work/prow-job-analyze-resource/{build_id}/` for faster subsequent searches

## Error Handling

Handle these error scenarios gracefully:

1. **Invalid URL format**
   - Error: "URL must contain 'test-platform-results/' substring"
   - Provide example of valid URL

2. **Build ID not found**
   - Error: "Could not find build ID (10+ decimal digits) in URL path"
   - Explain requirement and show URL parsing

3. **gcloud not installed**
   - Detect with: `which gcloud`
   - Provide installation instructions for user's platform
   - Link: https://cloud.google.com/sdk/docs/install

4. **gcloud not authenticated**
   - Detect with: `gcloud auth list`
   - Instruct: "Please run: gcloud auth login"

5. **No access to bucket**
   - Error from gcloud storage commands
   - Explain: "You need read access to the test-platform-results GCS bucket"
   - Suggest checking project access

6. **prowjob.json not found**
   - Suggest verifying URL and checking if job completed
   - Provide gcsweb URL for manual verification

7. **Not a ci-operator job**
   - Error: "This is not a ci-operator job. No --target found in prowjob.json."
   - Explain: Only ci-operator jobs can be analyzed by this skill

8. **gather-extra not found**
   - Warn: "gather-extra directory not found for target {target}"
   - Suggest: Job may not have completed or target name is incorrect

9. **No matches found**
   - Display: "No log entries found matching the specified resources"
   - Suggest:
     - Check resource names for typos
     - Try searching without kind or namespace filters
     - Verify resources existed during this job execution

10. **Timestamp parsing failures**
    - Warn about unparseable timestamps
    - Fall back to line order for sorting
    - Still include entries in report

## Performance Considerations

1. **Avoid re-downloading**
   - Check if `.work/prow-job-analyze-resource/{build_id}/logs/` already has content
   - Ask user before re-downloading

2. **Efficient downloads**
   - Use `gcloud storage cp -r` for recursive downloads
   - Use `--no-user-output-enabled` to suppress verbose output
   - Create target directories with `mkdir -p` before downloading to avoid gcloud errors

3. **Memory efficiency**
   - The `parse_all_logs.py` script processes log files incrementally (line by line)
   - Don't load entire files into memory
   - Script outputs to JSON for efficient HTML generation

4. **Content length limits**
   - The HTML generator trims JSON content to ~2000 chars in display
   - Full content is available in expandable details sections

5. **Progress indicators**
   - Show "Downloading audit logs..." before gcloud commands
   - Show "Parsing audit logs..." before running parse script
   - Show "Generating HTML report..." before running report generator

## Examples

### Example 1: Search for a namespace/project
```
User: "Analyze e2e-test-project-api-p28m in this Prow job: https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-master-okd-scos-4.20-e2e-aws-ovn-techpreview/1964725888612306944"

Output:
- Downloads artifacts to: .work/prow-job-analyze-resource/1964725888612306944/logs/
- Finds actual resource name: e2e-test-project-api-p28mx (namespace)
- Parses 382 audit log entries
- Finds 86 pod log mentions
- Creates: .work/prow-job-analyze-resource/1964725888612306944/e2e-test-project-api-p28mx.html
- Shows timeline from creation (18:11:02) to deletion (18:17:32)
```

### Example 2: Search for a pod
```
User: "Analyze pod/etcd-0 in this Prow job: https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/pr-logs/pull/30393/pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/"

Output:
- Creates: .work/prow-job-analyze-resource/1978913325970362368/etcd-0.html
- Shows timeline of all pod/etcd-0 events across namespaces
```

### Example 3: Search by name only
```
User: "Find all resources named cluster-version-operator in job {url}"

Output:
- Searches without kind filter
- Finds deployments, pods, services, etc. all named cluster-version-operator
- Creates: .work/prow-job-analyze-resource/{build_id}/cluster-version-operator.html
```

### Example 4: Search for multiple resources using regex
```
User: "Analyze e2e-test-project-api-pkjxf and e2e-test-project-api-7zdxx in job {url}"

Output:
- Uses regex pattern: `e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx`
- Finds all events for both namespaces in a single pass
- Parses 1,047 total entries (501 for first namespace, 546 for second)
- Passes the same pattern to generate_html_report.py
- HTML displays: "Resources: e2e-test-project-api-7zdxx, e2e-test-project-api-pkjxf"
- Creates: .work/prow-job-analyze-resource/{build_id}/e2e-test-project-api-pkjxf.html
- Timeline shows interleaved events from both namespaces chronologically
```

## Tips

- Always verify gcloud prerequisites before starting (gcloud CLI must be installed)
- Authentication is NOT required - the bucket is publicly accessible
- Use `.work/prow-job-analyze-resource/{build_id}/` directory structure for organization
- All work files are in `.work/` which is already in .gitignore
- The Python scripts handle all parsing and HTML generation - use them!
- Cache artifacts in `.work/prow-job-analyze-resource/{build_id}/` to speed up subsequent searches
- The parse script supports **regex patterns** for flexible matching:
  - Use `resource1|resource2` to search for multiple resources in a single pass
  - Use `.*` wildcards to match resource name patterns
  - Simple substring matching still works for basic searches
- The resource name provided by the user may not exactly match the actual resource name in logs
  - Example: User asks for `e2e-test-project-api-p28m` but actual resource is `e2e-test-project-api-p28mx`
  - Use regex patterns like `e2e-test-project-api-p28m.*` to find partial matches
- For namespaces/projects, search for the resource name - it will match both `namespace` and `project` resources
- Provide helpful error messages with actionable solutions

## Important Notes

1. **Resource Name Matching:**
   - The parse script uses **regex pattern matching** for maximum flexibility
   - Supports pipe operator (`|`) to search for multiple resources: `resource1|resource2`
   - Supports wildcards (`.*`) for pattern matching: `e2e-test-.*`
   - Simple substrings still work for basic searches
   - May match multiple related resources (e.g., namespace, project, rolebindings in that namespace)
   - Report all matches - this provides complete lifecycle context

2. **Namespace vs Project:**
   - In OpenShift, a `project` is essentially a `namespace` with additional metadata
   - Searching for a namespace will find both namespace and project resources
   - The audit logs contain events for both resource types

3. **Target Extraction:**
   - Must extract the `--target` argument from prowjob.json
   - This is critical for finding the correct gather-extra path
   - Non-ci-operator jobs cannot be analyzed (they don't have --target)

4. **Working with Scripts:**
   - All scripts are in `plugins/prow-job/skills/prow-job-analyze-resource/`
   - `parse_all_logs.py` - Parses audit logs and pod logs, outputs JSON
     - Detects glog severity levels (E=error, W=warn, I=info, F=fatal)
     - Supports regex patterns for resource matching
   - `generate_html_report.py` - Generates interactive HTML report from JSON
   - Scripts output status messages to stderr for progress display. JSON output to stdout is clean.

5. **Pod Log Glog Format Support:**
   - The parser automatically detects and parses glog format logs
   - Glog format: `E0910 11:43:41.153414 ...`
     - `E` = severity (E/F → error, W → warn, I → info)
     - `0910` = month/day (MMDD)
     - `11:43:41.153414` = time with microseconds
   - Timestamp parsing: Extracts timestamp and infers year (2025)
   - Severity mapping allows filtering by level in HTML report
   - Non-glog logs default to info level
