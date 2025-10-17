# Prow Job Analyze Resource Skill

This skill analyzes Kubernetes resource lifecycles in Prow CI job artifacts by downloading and parsing audit logs and pod logs from Google Cloud Storage, then generating interactive HTML reports with timelines.

## Overview

The skill provides both a Claude Code skill interface and standalone scripts for analyzing Prow CI job results. It helps debug test failures by tracking resource state changes throughout a test run.

## Components

### 1. SKILL.md
Claude Code skill definition that provides detailed implementation instructions for the AI assistant.

### 2. Python Scripts

#### parse_url.py
Parses and validates Prow job URLs from gcsweb.
- Extracts build_id (10+ digit identifier)
- Extracts prowjob name
- Constructs GCS paths
- Validates URL format

**Usage:**
```bash
./parse_url.py "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/pr-logs/pull/30393/pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/"
```

**Output:** JSON with build_id, prowjob_name, bucket_path, gcs_base_path

#### parse_audit_logs.py
Parses Kubernetes audit logs in JSONL format.
- Searches for specific resources by name, kind, and namespace
- Supports prefix matching for kinds (e.g., "pod" matches "pods")
- Extracts timestamps, HTTP codes, verbs, and user information
- Generates contextual summaries

**Usage:**
```bash
./parse_audit_logs.py ./1978913325970362368/logs pod/etcd-0 configmap/cluster-config
```

**Output:** JSON array of audit log entries

#### parse_pod_logs.py
Parses unstructured pod logs.
- Flexible pattern matching with forgiving regex (handles plural/singular)
- Detects multiple timestamp formats (glog, RFC3339, common, syslog)
- Detects log levels (info, warn, error)
- Generates contextual summaries

**Usage:**
```bash
./parse_pod_logs.py ./1978913325970362368/logs pod/etcd-0
```

**Output:** JSON array of pod log entries

#### generate_report.py
Generates interactive HTML reports from parsed log data.
- Combines audit and pod log entries
- Sorts chronologically
- Creates interactive timeline visualization
- Adds filtering and search capabilities

**Usage:**
```bash
./generate_report.py \
  report_template.html \
  output.html \
  metadata.json \
  audit_entries.json \
  pod_entries.json
```

### 3. Bash Script

#### prow_job_resource_grep.sh
Main orchestration script that ties everything together.
- Checks prerequisites (Python 3, gcloud)
- Validates gcloud authentication
- Downloads artifacts from GCS
- Parses logs
- Generates HTML report
- Provides interactive prompts and progress indicators

**Usage:**
```bash
./prow_job_resource_grep.sh \
  "https://gcsweb-ci.../1978913325970362368/" \
  pod/etcd-0 \
  configmap/cluster-config
```

### 4. HTML Template

#### report_template.html
Modern, responsive HTML template for reports featuring:
- Interactive SVG timeline with clickable events
- Color-coded log levels (info=blue, warn=yellow, error=red)
- Expandable log entry details
- Filtering by log level
- Search functionality
- Statistics dashboard
- Mobile-responsive design

## Resource Specification Format

Resources can be specified in the flexible format: `[namespace:][kind/]name`

**Examples:**
- `pod/etcd-0` - pod named etcd-0 in any namespace
- `openshift-etcd:pod/etcd-0` - pod in specific namespace
- `deployment/cluster-version-operator` - deployment in any namespace
- `etcd-0` - any resource named etcd-0 (no kind filter)
- `openshift-etcd:etcd-0` - any resource in specific namespace

**Multiple resources:**
```bash
pod/etcd-0,configmap/cluster-config,openshift-etcd:secret/etcd-all-certs
```

## Prerequisites

1. **Python 3** - For running parser and report generator scripts
2. **gcloud CLI** - For downloading artifacts from GCS
   - Install: https://cloud.google.com/sdk/docs/install
   - Authenticate: `gcloud auth login`
3. **jq** - For JSON processing (used in bash script)
4. **Access to test-platform-results GCS bucket**

## Workflow

1. **URL Parsing**
   - Validate URL contains `test-platform-results/`
   - Extract build_id (10+ digits)
   - Extract prowjob name
   - Construct GCS paths

2. **Working Directory**
   - Create `{build_id}/logs/` directory
   - Check for existing artifacts (offers to skip re-download)

3. **prowjob.json Validation**
   - Download prowjob.json
   - Search for `--target=` pattern
   - Exit if not a ci-operator job

4. **Artifact Download**
   - Download audit logs: `artifacts/{target}/gather-extra/artifacts/audit_logs/**/*.log`
   - Download pod logs: `artifacts/{target}/gather-extra/artifacts/pods/**/*.log`

5. **Log Parsing**
   - Parse audit logs (structured JSONL)
   - Parse pod logs (unstructured text)
   - Filter by resource specifications
   - Extract timestamps and log levels

6. **Report Generation**
   - Sort entries chronologically
   - Calculate timeline bounds
   - Generate SVG timeline events
   - Render HTML with template
   - Output to `{build_id}/{resource-spec}.html`

## Output

### Console Output
```
Resource Lifecycle Analysis Complete

Prow Job: pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn
Build ID: 1978913325970362368
Target: e2e-aws-ovn

Resources Analyzed:
  - pod/etcd-0

Artifacts downloaded to: 1978913325970362368/logs/

Results:
  - Audit log entries: 47
  - Pod log entries: 23
  - Total entries: 70

Report generated: 1978913325970362368/pod_etcd-0.html
```

### HTML Report
- Header with metadata
- Statistics dashboard
- Interactive timeline
- Filterable log entries
- Expandable details
- Search functionality

### Directory Structure
```
{build_id}/
├── logs/
│   ├── prowjob.json
│   ├── metadata.json
│   ├── audit_entries.json
│   ├── pod_entries.json
│   └── artifacts/
│       └── {target}/
│           └── gather-extra/
│               └── artifacts/
│                   ├── audit_logs/
│                   │   └── **/*.log
│                   └── pods/
│                       └── **/*.log
└── {resource-spec}.html
```

## Performance Features

1. **Caching**
   - Downloaded artifacts are cached in `{build_id}/logs/`
   - Offers to skip re-download if artifacts exist

2. **Incremental Processing**
   - Logs processed line-by-line
   - Memory-efficient for large files

3. **Progress Indicators**
   - Colored output for different log levels
   - Status messages for long-running operations

4. **Error Handling**
   - Graceful handling of missing files
   - Helpful error messages with suggestions
   - Continues processing if some artifacts are missing

## Examples

### Single Resource
```bash
./prow_job_resource_grep.sh \
  "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/pr-logs/pull/30393/pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/" \
  pod/etcd-0
```

### Multiple Resources
```bash
./prow_job_resource_grep.sh \
  "https://gcsweb-ci.../1978913325970362368/" \
  pod/etcd-0 \
  configmap/cluster-config \
  openshift-etcd:secret/etcd-all-certs
```

### Resource in Specific Namespace
```bash
./prow_job_resource_grep.sh \
  "https://gcsweb-ci.../1978913325970362368/" \
  openshift-cluster-version:deployment/cluster-version-operator
```

## Using with Claude Code

When you ask Claude to analyze a Prow job, it will automatically use this skill. The skill provides detailed instructions that guide Claude through:
- Validating prerequisites
- Parsing URLs
- Downloading artifacts
- Parsing logs
- Generating reports

You can simply ask:
> "Analyze pod/etcd-0 in this Prow job: https://gcsweb-ci.../1978913325970362368/"

Claude will execute the workflow and generate the interactive HTML report.

## Troubleshooting

### gcloud authentication
```bash
gcloud auth login
gcloud auth list  # Verify active account
```

### Missing artifacts
- Verify job completed successfully
- Check target name is correct
- Confirm gather-extra ran in the job

### No matches found
- Check resource name spelling
- Try without kind filter
- Verify resource existed during test run
- Check namespace if specified

### Permission denied
- Verify access to test-platform-results bucket
- Check gcloud project configuration
