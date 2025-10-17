# Prow Job Extract Must-Gather Skill

This skill extracts and decompresses must-gather archives from Prow CI job artifacts, automatically handling nested tar and gzip archives, and generating an interactive HTML file browser.

## Overview

The skill provides both a Claude Code skill interface and standalone scripts for extracting must-gather data from Prow CI jobs. It eliminates the manual steps of downloading and recursively extracting nested archives.

## Components

### 1. SKILL.md
Claude Code skill definition that provides detailed implementation instructions for the AI assistant.

### 2. Python Scripts

#### extract_archives.py
Extracts and recursively processes must-gather archives.

**Features:**
- Extracts must-gather.tar to specified directory
- Renames long subdirectory (containing "-ci-") to "content/" for readability
- Recursively processes nested archives:
  - `.tar.gz` and `.tgz`: Extract in place, remove original
  - `.gz` (plain gzip): Decompress in place, remove original
- Handles up to 10 levels of nested archives
- Reports extraction statistics

**Usage:**
```bash
python3 extract_archives.py <must-gather.tar> <output-directory>
```

**Example:**
```bash
python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
  .work/prow-job-extract-must-gather/1965715986610917376/tmp/must-gather.tar \
  .work/prow-job-extract-must-gather/1965715986610917376/logs
```

**Output:**
```
================================================================================
Must-Gather Archive Extraction
================================================================================

Step 1: Extracting must-gather.tar
  From: .work/.../tmp/must-gather.tar
  To: .work/.../logs
  Extracting: .work/.../tmp/must-gather.tar

Step 2: Renaming long directory to 'content/'
  From: registry-build09-ci-openshift-org-ci-op-...
  To: content/

Step 3: Processing nested archives
  Extracting: .../content/namespaces/openshift-etcd/pods/etcd-0.tar.gz
  Decompressing: .../content/cluster-scoped-resources/nodes/ip-10-0-1-234.log.gz
  ... (continues for all archives)

================================================================================
Extraction Complete
================================================================================

Statistics:
  Total files: 3,421
  Total size: 234.5 MB
  Archives processed: 247

Extracted to: .work/prow-job-extract-must-gather/1965715986610917376/logs
```

#### generate_html_report.py
Generates an interactive HTML file browser with filters and search.

**Features:**
- Scans directory tree and collects file metadata
- Classifies files by type (log, yaml, json, xml, cert, archive, script, config, other)
- Generates statistics (total files, total size, counts by type)
- Creates interactive HTML with:
  - Multi-select file type filters
  - Regex pattern filter for powerful searches
  - Text search for file names/paths
  - Direct links to files (relative paths)
  - Same dark theme as analyze-resource skill

**Usage:**
```bash
python3 generate_html_report.py <logs-directory> <prowjob_name> <build_id> <target> <gcsweb_url>
```

**Example:**
```bash
python3 plugins/prow-job/skills/prow-job-extract-must-gather/generate_html_report.py \
  .work/prow-job-extract-must-gather/1965715986610917376/logs \
  "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview" \
  "1965715986610917376" \
  "e2e-aws-ovn-techpreview" \
  "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview/1965715986610917376"
```

**Output:**
- Creates `.work/prow-job-extract-must-gather/{build_id}/must-gather-browser.html`

## Prerequisites

1. **Python 3** - For running extraction and report generator scripts
2. **gcloud CLI** - For downloading artifacts from GCS
   - Install: https://cloud.google.com/sdk/docs/install
   - Authentication NOT required (bucket is publicly accessible)

## Workflow

1. **URL Parsing**
   - Validate URL contains `test-platform-results/`
   - Extract build_id (10+ digits)
   - Extract prowjob name
   - Construct GCS paths

2. **Working Directory**
   - Create `.work/prow-job-extract-must-gather/{build_id}/` directory
   - Create `logs/` subdirectory for extraction
   - Create `tmp/` subdirectory for temporary files
   - Check for existing extraction (offers to skip re-extraction)

3. **prowjob.json Validation**
   - Download prowjob.json
   - Search for `--target=` pattern
   - Exit if not a ci-operator job

4. **Must-Gather Download**
   - Download from: `artifacts/{target}/gather-must-gather/artifacts/must-gather.tar`
   - Save to: `{build_id}/tmp/must-gather.tar`

5. **Extraction and Processing**
   - Extract must-gather.tar to `{build_id}/logs/`
   - Rename long subdirectory to "content/"
   - Recursively extract nested archives (.tar.gz, .tgz, .gz)
   - Remove original compressed files after extraction

6. **HTML Report Generation**
   - Scan directory tree
   - Classify files by type
   - Calculate statistics
   - Generate interactive HTML browser
   - Output to `{build_id}/must-gather-browser.html`

## Output

### Console Output
```
Must-Gather Extraction Complete

Prow Job: periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview
Build ID: 1965715986610917376
Target: e2e-aws-ovn-techpreview

Extraction Statistics:
- Total files: 3,421
- Total size: 234.5 MB
- Archives extracted: 247
- Log files: 1,234
- YAML files: 856
- JSON files: 423

Extracted to: .work/prow-job-extract-must-gather/1965715986610917376/logs/

File browser generated: .work/prow-job-extract-must-gather/1965715986610917376/must-gather-browser.html

Open in browser to browse and search extracted files.
```

### HTML File Browser

The generated HTML report includes:

1. **Header Section**
   - Prow job name
   - Build ID
   - Target name
   - GCS URL (link to gcsweb)
   - Local extraction path

2. **Statistics Dashboard**
   - Total files count
   - Total size (human-readable)
   - Counts by file type (log, yaml, json, xml, cert, archive, script, config, other)

3. **Filter Controls**
   - **File Type Filter**: Multi-select buttons to filter by type
   - **Regex Pattern Filter**: Input field for regex patterns (e.g., `.*etcd.*`, `.*\.log$`, `^content/namespaces/.*`)
   - **Name Search**: Text search for file names and paths

4. **File List**
   - Icon for each file type
   - File name (clickable link to open file)
   - Directory path
   - File size
   - File type badge (color-coded)
   - Sorted alphabetically by path

5. **Interactive Features**
   - All filters work together (AND logic)
   - Real-time filtering (300ms debounce)
   - Regex pattern validation
   - Scroll to top button
   - No results message when filters match nothing

### Directory Structure
```
.work/prow-job-extract-must-gather/{build_id}/
├── tmp/
│   ├── prowjob.json
│   └── must-gather.tar (downloaded, not deleted)
├── logs/
│   └── content/                    # Renamed from long directory
│       ├── cluster-scoped-resources/
│       │   ├── nodes/
│       │   ├── clusterroles/
│       │   └── ...
│       ├── namespaces/
│       │   ├── openshift-etcd/
│       │   │   ├── pods/
│       │   │   ├── services/
│       │   │   └── ...
│       │   └── ...
│       └── ... (all extracted and decompressed)
└── must-gather-browser.html
```

## Performance Features

1. **Caching**
   - Extracted files are cached in `{build_id}/logs/`
   - Offers to skip re-extraction if content already exists

2. **Incremental Processing**
   - Archives processed iteratively (up to 10 passes)
   - Handles deeply nested archive structures

3. **Progress Indicators**
   - Colored output for different stages
   - Status messages for long-running operations
   - Final statistics summary

4. **Error Handling**
   - Graceful handling of corrupted archives
   - Continues processing after errors
   - Reports all errors in final summary

## Examples

### Basic Usage
```bash
# Via Claude Code
User: "Extract must-gather from https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview/1965715986610917376"

# Standalone script
python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
  .work/prow-job-extract-must-gather/1965715986610917376/tmp/must-gather.tar \
  .work/prow-job-extract-must-gather/1965715986610917376/logs

python3 plugins/prow-job/skills/prow-job-extract-must-gather/generate_html_report.py \
  .work/prow-job-extract-must-gather/1965715986610917376/logs \
  "periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview" \
  "1965715986610917376" \
  "e2e-aws-ovn-techpreview" \
  "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview/1965715986610917376"
```

### Using Regex Filters in HTML Browser

**Find all etcd-related files:**
```regex
.*etcd.*
```

**Find all log files:**
```regex
.*\.log$
```

**Find files in specific namespace:**
```regex
^content/namespaces/openshift-etcd/.*
```

**Find YAML manifests for pods:**
```regex
.*pods/.*\.yaml$
```

## Using with Claude Code

When you ask Claude to extract a must-gather, it will automatically use this skill. The skill provides detailed instructions that guide Claude through:
- Validating prerequisites
- Parsing URLs
- Downloading archives
- Extracting and decompressing
- Generating HTML browser

You can simply ask:
> "Extract must-gather from this Prow job: https://gcsweb-ci.../1965715986610917376/"

Claude will execute the workflow and generate the interactive HTML file browser.

## Troubleshooting

### gcloud not installed
```bash
# Check installation
which gcloud

# Install (follow platform-specific instructions)
# https://cloud.google.com/sdk/docs/install
```

### must-gather.tar not found
- Verify job completed successfully
- Check target name is correct
- Confirm gather-must-gather ran in the job
- Manually check GCS path in gcsweb

### Corrupted archives
- Check error messages in extraction output
- Extraction continues despite individual failures
- Final summary lists all errors

### No "-ci-" directory found
- Extraction continues with original directory names
- Check logs for warning message
- Files will still be accessible

### HTML browser not opening files
- Verify files were extracted to `logs/` directory
- Check that relative paths are correct
- Files must be opened from the same directory as HTML file

## File Type Classifications

| Extension | Type | Badge Color |
|-----------|------|-------------|
| .log, .txt | log | Blue |
| .yaml, .yml | yaml | Purple |
| .json | json | Green |
| .xml | xml | Yellow |
| .crt, .pem, .key | cert | Red |
| .tar, .gz, .tgz, .zip | archive | Gray |
| .sh, .py | script | Blue |
| .conf, .cfg, .ini | config | Yellow |
| others | other | Gray |
