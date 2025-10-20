---
name: Prow Job Extract Must-Gather
description: Extract and decompress must-gather archives from Prow CI job artifacts, generating an interactive HTML file browser with filters
---

# Prow Job Extract Must-Gather

This skill extracts and decompresses must-gather archives from Prow CI job artifacts, automatically handling nested tar and gzip archives, and generating an interactive HTML file browser.

## When to Use This Skill

Use this skill when the user wants to:
- Extract must-gather archives from Prow CI job artifacts
- Avoid manually downloading and extracting nested archives
- Browse must-gather contents with an interactive HTML interface
- Search for specific files or file types in must-gather data
- Analyze OpenShift cluster state from CI test runs

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
   - Example: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview/1965715986610917376/`
   - URL may or may not have trailing slash

## Implementation Steps

### Step 1: Parse and Validate URL

1. **Extract bucket path**
   - Find `test-platform-results/` in URL
   - Extract everything after it as the GCS bucket relative path
   - If not found, error: "URL must contain 'test-platform-results/'"

2. **Extract build_id**
   - Search for pattern `/(\\d{10,})/` in the bucket path
   - build_id must be at least 10 consecutive decimal digits
   - Handle URLs with or without trailing slash
   - If not found, error: "Could not find build ID (10+ digits) in URL"

3. **Extract prowjob name**
   - Find the path segment immediately preceding build_id
   - Example: In `.../periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview/1965715986610917376/`
   - Prowjob name: `periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview`

4. **Construct GCS paths**
   - Bucket: `test-platform-results`
   - Base GCS path: `gs://test-platform-results/{bucket-path}/`
   - Ensure path ends with `/`

### Step 2: Create Working Directory

1. **Check for existing extraction first**
   - Check if `.work/prow-job-extract-must-gather/{build_id}/logs/` directory exists and has content
   - If it exists with content:
     - Use AskUserQuestion tool to ask:
       - Question: "Must-gather already extracted for build {build_id}. Would you like to use the existing extraction or re-extract?"
       - Options:
         - "Use existing" - Skip to HTML report generation (Step 6)
         - "Re-extract" - Continue to clean and re-download
     - If user chooses "Re-extract":
       - Remove all existing content: `rm -rf .work/prow-job-extract-must-gather/{build_id}/logs/`
       - Also remove tmp directory: `rm -rf .work/prow-job-extract-must-gather/{build_id}/tmp/`
       - This ensures clean state before downloading new content
     - If user chooses "Use existing":
       - Skip directly to Step 6 (Generate HTML Report)

2. **Create directory structure**
   ```bash
   mkdir -p .work/prow-job-extract-must-gather/{build_id}/logs
   mkdir -p .work/prow-job-extract-must-gather/{build_id}/tmp
   ```
   - Use `.work/prow-job-extract-must-gather/` as the base directory (already in .gitignore)
   - Use build_id as subdirectory name
   - Create `logs/` subdirectory for extraction
   - Create `tmp/` subdirectory for temporary files
   - Working directory: `.work/prow-job-extract-must-gather/{build_id}/`

### Step 3: Download and Validate prowjob.json

1. **Download prowjob.json**
   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/prowjob.json .work/prow-job-extract-must-gather/{build_id}/tmp/prowjob.json --no-user-output-enabled
   ```

2. **Parse and validate**
   - Read `.work/prow-job-extract-must-gather/{build_id}/tmp/prowjob.json`
   - Search for pattern: `--target=([a-zA-Z0-9-]+)`
   - If not found:
     - Display: "This is not a ci-operator job. The prowjob cannot be analyzed by this skill."
     - Explain: ci-operator jobs have a --target argument specifying the test target
     - Exit skill

3. **Extract target name**
   - Capture the target value (e.g., `e2e-aws-ovn-techpreview`)
   - Store for constructing must-gather path

### Step 4: Download Must-Gather Archive

1. **Construct must-gather path**
   - GCS path: `gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar`
   - Local path: `.work/prow-job-extract-must-gather/{build_id}/tmp/must-gather.tar`

2. **Download must-gather.tar**
   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar .work/prow-job-extract-must-gather/{build_id}/tmp/must-gather.tar --no-user-output-enabled
   ```
   - Use `--no-user-output-enabled` to suppress progress output
   - If file not found, error: "No must-gather archive found. Job may not have completed or gather-must-gather may not have run."

### Step 5: Extract and Process Archives

**IMPORTANT: Use the provided Python script `extract_archives.py` from the skill directory.**

**Usage:**
```bash
python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
  .work/prow-job-extract-must-gather/{build_id}/tmp/must-gather.tar \
  .work/prow-job-extract-must-gather/{build_id}/logs
```

**What the script does:**

1. **Extract must-gather.tar**
   - Extract to `{build_id}/logs/` directory
   - Uses Python's tarfile module for reliable extraction

2. **Rename long subdirectory to "content/"**
   - Find subdirectory containing "-ci-" in the name
   - Example: `registry-build09-ci-openshift-org-ci-op-m8t77165-stable-sha256-d1ae126eed86a47fdbc8db0ad176bf078a5edebdbb0df180d73f02e5f03779e0/`
   - Rename to: `content/`
   - Preserves all files and subdirectories

3. **Recursively process nested archives**
   - Walk entire directory tree
   - Find and process archives:

   **For .tar.gz and .tgz files:**
   ```python
   # Extract in place
   with tarfile.open(archive_path, 'r:gz') as tar:
       tar.extractall(path=parent_dir)
   # Remove original archive
   os.remove(archive_path)
   ```

   **For .gz files (no tar):**
   ```python
   # Gunzip in place
   with gzip.open(gz_path, 'rb') as f_in:
       with open(output_path, 'wb') as f_out:
           shutil.copyfileobj(f_in, f_out)
   # Remove original archive
   os.remove(gz_path)
   ```

4. **Progress reporting**
   - Print status for each extracted archive
   - Count total files and archives processed
   - Report final statistics

5. **Error handling**
   - Skip corrupted archives with warning
   - Continue processing other files
   - Report all errors at the end

### Step 6: Generate HTML File Browser

**IMPORTANT: Use the provided Python script `generate_html_report.py` from the skill directory.**

**Usage:**
```bash
python3 plugins/prow-job/skills/prow-job-extract-must-gather/generate_html_report.py \
  .work/prow-job-extract-must-gather/{build_id}/logs \
  "{prowjob_name}" \
  "{build_id}" \
  "{target}" \
  "{gcsweb_url}"
```

**Output:** The script generates `.work/prow-job-extract-must-gather/{build_id}/must-gather-browser.html`

**What the script does:**

1. **Scan directory tree**
   - Recursively walk `{build_id}/logs/` directory
   - Collect all files with metadata:
     - Relative path from logs/
     - File size (human-readable: KB, MB, GB)
     - File extension
     - Directory depth
     - Last modified time

2. **Classify files**
   - Detect file types based on extension:
     - Logs: `.log`, `.txt`
     - YAML: `.yaml`, `.yml`
     - JSON: `.json`
     - XML: `.xml`
     - Certificates: `.crt`, `.pem`, `.key`
     - Binaries: `.tar`, `.gz`, `.tgz`, `.tar.gz`
     - Other
   - Count files by type for statistics

3. **Generate HTML structure**

   **Header Section:**
   ```html
   <div class="header">
     <h1>Must-Gather File Browser</h1>
     <div class="metadata">
       <p><strong>Prow Job:</strong> {prowjob-name}</p>
       <p><strong>Build ID:</strong> {build_id}</p>
       <p><strong>gcsweb URL:</strong> <a href="{original-url}">{original-url}</a></p>
       <p><strong>Target:</strong> {target}</p>
       <p><strong>Total Files:</strong> {count}</p>
       <p><strong>Total Size:</strong> {human-readable-size}</p>
     </div>
   </div>
   ```

   **Filter Controls:**
   ```html
   <div class="filters">
     <div class="filter-group">
       <label class="filter-label">File Type (multi-select)</label>
       <div class="filter-buttons">
         <button class="filter-btn" data-filter="type" data-value="log">Logs ({count})</button>
         <button class="filter-btn" data-filter="type" data-value="yaml">YAML ({count})</button>
         <button class="filter-btn" data-filter="type" data-value="json">JSON ({count})</button>
         <!-- etc -->
       </div>
     </div>
     <div class="filter-group">
       <label class="filter-label">Filter by Regex Pattern</label>
       <input type="text" class="search-box" id="pattern" placeholder="Enter regex pattern (e.g., .*etcd.*, .*\\.log$)">
     </div>
     <div class="filter-group">
       <label class="filter-label">Search by Name</label>
       <input type="text" class="search-box" id="search" placeholder="Search file names...">
     </div>
   </div>
   ```

   **File List:**
   ```html
   <div class="file-list">
     <div class="file-item" data-type="{type}" data-path="{path}">
       <div class="file-icon">{icon}</div>
       <div class="file-info">
         <div class="file-name">
           <a href="{relative-path}" target="_blank">{filename}</a>
         </div>
         <div class="file-meta">
           <span class="file-path">{directory-path}</span>
           <span class="file-size">{size}</span>
           <span class="file-type badge badge-{type}">{type}</span>
         </div>
       </div>
     </div>
   </div>
   ```

   **CSS Styling:**
   - Use same dark theme as analyze-resource skill
   - Modern, clean design with good contrast
   - Responsive layout
   - File type color coding
   - Monospace fonts for paths
   - Hover effects on file items

   **JavaScript Interactivity:**
   ```javascript
   // Multi-select file type filters
   document.querySelectorAll('.filter-btn').forEach(btn => {
     btn.addEventListener('click', function() {
       // Toggle active state
       // Apply filters
     });
   });

   // Regex pattern filter
   document.getElementById('pattern').addEventListener('input', function() {
     const pattern = this.value;
     if (pattern) {
       const regex = new RegExp(pattern);
       // Filter files matching regex
     }
   });

   // Name search filter
   document.getElementById('search').addEventListener('input', function() {
     const query = this.value.toLowerCase();
     // Filter files by name substring
   });

   // Combine all active filters
   function applyFilters() {
     // Show/hide files based on all active filters
   }
   ```

4. **Statistics Section:**
   ```html
   <div class="stats">
     <div class="stat">
       <div class="stat-value">{total-files}</div>
       <div class="stat-label">Total Files</div>
     </div>
     <div class="stat">
       <div class="stat-value">{total-size}</div>
       <div class="stat-label">Total Size</div>
     </div>
     <div class="stat">
       <div class="stat-value">{log-count}</div>
       <div class="stat-label">Log Files</div>
     </div>
     <div class="stat">
       <div class="stat-value">{yaml-count}</div>
       <div class="stat-label">YAML Files</div>
     </div>
     <!-- etc -->
   </div>
   ```

5. **Write HTML to file**
   - Script automatically writes to `.work/prow-job-extract-must-gather/{build_id}/must-gather-browser.html`
   - Includes proper HTML5 structure
   - All CSS and JavaScript are inline for portability

### Step 7: Present Results to User

1. **Display summary**
   ```
   Must-Gather Extraction Complete

   Prow Job: {prowjob-name}
   Build ID: {build_id}
   Target: {target}

   Extraction Statistics:
   - Total files: {file-count}
   - Total size: {human-readable-size}
   - Archives extracted: {archive-count}
   - Log files: {log-count}
   - YAML files: {yaml-count}
   - JSON files: {json-count}

   Extracted to: .work/prow-job-extract-must-gather/{build_id}/logs/

   File browser generated: .work/prow-job-extract-must-gather/{build_id}/must-gather-browser.html

   Open in browser to browse and search extracted files.
   ```

2. **Open report in browser**
   - Detect platform and automatically open the HTML report in the default browser
   - Linux: `xdg-open .work/prow-job-extract-must-gather/{build_id}/must-gather-browser.html`
   - macOS: `open .work/prow-job-extract-must-gather/{build_id}/must-gather-browser.html`
   - Windows: `start .work/prow-job-extract-must-gather/{build_id}/must-gather-browser.html`
   - On Linux (most common for this environment), use `xdg-open`

3. **Offer next steps**
   - Ask if user wants to search for specific files
   - Explain that extracted files are available in `.work/prow-job-extract-must-gather/{build_id}/logs/`
   - Mention that extraction is cached for faster subsequent browsing

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

4. **prowjob.json not found**
   - Suggest verifying URL and checking if job completed
   - Provide gcsweb URL for manual verification

5. **Not a ci-operator job**
   - Error: "This is not a ci-operator job. No --target found in prowjob.json."
   - Explain: Only ci-operator jobs can be analyzed by this skill

6. **must-gather.tar not found**
   - Warn: "Must-gather archive not found at expected path"
   - Suggest: Job may not have completed or gather-must-gather may not have run
   - Provide full GCS path that was checked

7. **Corrupted archive**
   - Warn: "Could not extract {archive-path}: {error}"
   - Continue processing other archives
   - Report all errors in final summary

8. **No "-ci-" subdirectory found**
   - Warn: "Could not find expected subdirectory to rename to 'content/'"
   - Continue with extraction anyway
   - Files will be in original directory structure

## Performance Considerations

1. **Avoid re-extracting**
   - Check if `.work/prow-job-extract-must-gather/{build_id}/logs/` already has content
   - Ask user before re-extracting

2. **Efficient downloads**
   - Use `gcloud storage cp` with `--no-user-output-enabled` to suppress verbose output

3. **Memory efficiency**
   - Process archives incrementally
   - Don't load entire files into memory
   - Use streaming extraction

4. **Progress indicators**
   - Show "Downloading must-gather archive..." before gcloud command
   - Show "Extracting must-gather.tar..." before extraction
   - Show "Processing nested archives..." during recursive extraction
   - Show "Generating HTML file browser..." before report generation

## Examples

### Example 1: Extract must-gather from periodic job
```
User: "Extract must-gather from this Prow job: https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn-techpreview/1965715986610917376"

Output:
- Downloads must-gather.tar to: .work/prow-job-extract-must-gather/1965715986610917376/tmp/
- Extracts to: .work/prow-job-extract-must-gather/1965715986610917376/logs/
- Renames long subdirectory to: content/
- Processes 247 nested archives (.tar.gz, .tgz, .gz)
- Creates: .work/prow-job-extract-must-gather/1965715986610917376/must-gather-browser.html
- Opens browser with interactive file list (3,421 files, 234 MB)
```

## Tips

- Always verify gcloud prerequisites before starting (gcloud CLI must be installed)
- Authentication is NOT required - the bucket is publicly accessible
- Use `.work/prow-job-extract-must-gather/{build_id}/` directory structure for organization
- All work files are in `.work/` which is already in .gitignore
- The Python scripts handle all extraction and HTML generation - use them!
- Cache extracted files in `.work/prow-job-extract-must-gather/{build_id}/` to avoid re-extraction
- The HTML file browser supports regex patterns for powerful file filtering
- Extracted files can be opened directly from the HTML browser (links are relative)

## Important Notes

1. **Archive Processing:**
   - The script automatically handles nested archives
   - Original compressed files are removed after successful extraction
   - Corrupted archives are skipped with warnings

2. **Directory Renaming:**
   - The long subdirectory name (containing "-ci-") is renamed to "content/" for brevity
   - Files within "content/" are NOT altered
   - This makes paths more readable in the HTML browser

3. **File Type Detection:**
   - File types are detected based on extension
   - Common types are color-coded in the HTML browser
   - All file types can be filtered

4. **Regex Pattern Filtering:**
   - Users can enter regex patterns in the filter input
   - Patterns match against full file paths
   - Invalid regex patterns are ignored gracefully

5. **Working with Scripts:**
   - All scripts are in `plugins/prow-job/skills/prow-job-extract-must-gather/`
   - `extract_archives.py` - Extracts and processes archives
   - `generate_html_report.py` - Generates interactive HTML file browser
