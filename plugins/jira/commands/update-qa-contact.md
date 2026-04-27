---
description: Update QA contact for JIRA issues by status, issue key, component owners from CSV, or bug list
argument-hint: <status> <from> <to> [project] | --issue-key <KEY> <to> | --issue-key <KEY> <from> <to> | --defaultcomponentowners --csv-file <path> | --bugs <list>
---

## Name
jira:update-qa-contact

## Synopsis
```bash
# Bulk mode - update by status filter
/jira:update-qa-contact <bug_status> <old_qa_contacts_name> <new_qa_contacts_name> [project-key] [--dry-run]

# Single issue mode - direct update or validated update
/jira:update-qa-contact --issue-key <ISSUE-KEY> <new_qa_contacts_name> [--dry-run]
/jira:update-qa-contact --issue-key <ISSUE-KEY> <old_qa_contacts_name> <new_qa_contacts_name> [--dry-run]

# Auto-assign from CSV file - process bugs from dashboard export using component owners
/jira:update-qa-contact --defaultcomponentowners --csv-file <path-to-csv> [--component-map path] [--dry-run]

# Auto-assign from bug list - process multiple specific bugs
/jira:update-qa-contact --bugs <bug1,bug2,bug3,...> [--component-map path] [--dry-run]
```bash

## Quick Reference: FROM → TO Pattern

**Understanding the argument order:**

1. **Single issue mode (2-arg) - Direct update TO new QA:**
   ```bash
   /jira:update-qa-contact --issue-key OCPBUGS-78997 "xxxx@redhat.com"
```bash
   → Updates **TO** xxxx (no validation of current QA)

2. **Single issue mode (3-arg) - Safe update FROM → TO:**
   ```bash
   /jira:update-qa-contact --issue-key OCPBUGS-78997 "yyyy@redhat.com" "xxxx@redhat.com"
```bash
   → Updates **FROM** yyyy **TO** xxxx (validates current QA matches)

3. **Bulk mode - Update all matching issues FROM → TO:**
   ```bash
   /jira:update-qa-contact NEW "yyyy" "xxxx" OCPBUGS
```bash
   → Updates all NEW status issues **FROM** yyyy **TO** xxxx in OCPBUGS project

**Remember:** The pattern is always **FROM** (old) → **TO** (new), except in single-issue 2-arg mode where you only specify **TO** (new).

## Component-Based Auto-Assignment

For bulk operations across multiple issues, you can auto-assign QA contacts based on component ownership using a mapping file.

**How it works:**
1. Fetch issues from CSV file or bug list
2. Extract component field from each issue (e.g., "Workloads", "etcd", "api")
3. Look up component in XML mapping file to find default QA owner
4. Update QA contact to the mapped owner

**Component mapping file format (`plugins/jira/component-qa-mapping.xml`):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<component-qa-mapping>
  <component name="Workloads">
    <default-qa>xxxx@redhat.com</default-qa>
  </component>
  <component name="etcd">
    <default-qa>yyyy@redhat.com</default-qa>
  </component>
  <component name="api">
    <default-qa>zzzz@redhat.com</default-qa>
  </component>
  <component name="auth">
    <default-qa>bbbb@redhat.com</default-qa>
  </component>
</component-qa-mapping>
```bash

**Custom mapping file location:**
```bash
/jira:update-qa-contact --defaultcomponentowners --csv-file bugs.csv --component-map /path/to/custom-map.xml
```bash

**4. CSV file-based auto-assignment - Process bugs from dashboard export using component owners:**
   ```bash
   /jira:update-qa-contact --defaultcomponentowners --csv-file /path/to/dashboard-export.csv
```bash
   → Reads bug keys from CSV file (exported from JIRA dashboard), determines each bug's component, assigns QA based on mapping

**How to export CSV from JIRA dashboard:**
1. Open your JIRA dashboard in browser
2. Click on the dashboard gadget showing the bugs
3. Export to CSV (usually via "..." menu or export button)
4. Save the CSV file locally

**Supported CSV formats:**
   - JIRA Rich Filter export: `T,Key,P,Summary,Assignee,Status`
   - Standard JIRA export: `Issue key,Summary,Status`
   - Any CSV with a column named "Key" or "Issue key"

**How it works:**
1. Read CSV file and extract bug keys from "Key" or "Issue key" column
2. For each bug key:
   - Fetch bug details from JIRA API
   - Extract component field
   - Look up component in XML mapping
   - Update QA contact to mapped owner
3. Display summary of updated issues
4. Skip bugs with placeholder QA contacts (aaaa@, bbbb@, etc.)

**Example:**
   ```bash
   # Dry-run to preview changes
   /jira:update-qa-contact --defaultcomponentowners --csv-file ~/Downloads/dashboard-bugs.csv --dry-run
   
   # Actually update
   /jira:update-qa-contact --defaultcomponentowners --csv-file ~/Downloads/dashboard-bugs.csv
```bash

**5. Bug list auto-assignment - Process specific bugs:**
   ```bash
   /jira:update-qa-contact --bugs OCPBUGS-56893,OCPBUGS-56894,OCPBUGS-56895
```bash
   → Process only these 3 specific bugs, assign QA based on their components

**Supported bug list formats:**
   - Comma-separated: `OCPBUGS-1,OCPBUGS-2,OCPBUGS-3`
   - Space-separated: `OCPBUGS-1 OCPBUGS-2 OCPBUGS-3`
   - Mixed projects: `OCPBUGS-1,RFE-234,HYPE-567`

**Example with specific bug list:**
   ```bash
   # Process these specific bugs
   /jira:update-qa-contact --bugs OCPBUGS-78326,OCPBUGS-8755,OCPBUGS-56893
```bash

**Component handling:**
- If bug has no component: Skip with warning
- If bug has one component: Use it for QA lookup
- If bug has multiple components: Prompt user to select (or auto-select first in non-interactive mode)
- If component not in mapping: Skip with error listing available components

## Prerequisites

Before using this command, you must set the following environment variables:

```bash
export JIRA_USERNAME="your-email@redhat.com"
export JIRA_API_TOKEN="your-api-token-here"
```bash

**How to obtain your API token:**
1. Visit [Atlassian API Token Management](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a label (e.g., "Claude Code JIRA Plugin")
4. Copy the token and store it securely
5. Add both variables to your `~/.bashrc` or `~/.zshrc` for persistence

**Optional environment variable:**
```bash
export JIRA_QA_CONTACT_FIELD="customfield_10470"  # Default for OCPBUGS
```bash

**For component-based auto-assignment** (CSV and bug list modes):
- A component-to-QA mapping file is required: `plugins/jira/component-qa-mapping.xml`
- This file is included in the repository with sample mappings
- **Customize it** with your actual component owners before using component-based modes
- Replace placeholder emails (aaaa@, bbbb@, etc.) with real QA contact emails
- See the "Component-Based Auto-Assignment" section above for details

## Description
The `jira:update-qa-contact` command updates the QA contact field for JIRA issues. It supports four modes:

1. **Bulk mode**: Filter issues by status criteria and update all matching issues
2. **Single issue mode**: Update a specific issue by its key (e.g., OCPBUGS-78997)
3. **CSV-based component auto-assignment**: Process bugs from CSV export and assign QA based on component owners
4. **Bug list auto-assignment**: Process multiple specific bugs and assign QA based on components

**Validation behavior:**
- **Bulk mode** (Mode 1): Always validates - verifies current QA contact matches the old name before updating
- **Single issue 3-arg safe mode** (Mode 2): Validates - verifies current QA contact matches the old name before updating  
- **Single issue 2-arg quick mode** (Mode 2): No validation - updates directly to new QA contact without checking current value
- **CSV and bug list modes** (Modes 3-4): No validation - automatically determine and assign QA contact from component mapping file

This command is particularly useful for:
- Updating QA contact assignments when team members change roles
- Reassigning QA responsibilities during team transitions
- Bulk updating QA contacts for organizational changes
- Fixing incorrect QA contact assignments on specific issues
- Auto-assigning QA contacts based on component ownership
- Maintaining component-to-QA mappings for consistent assignments
- Auditing QA contact assignments with dry-run mode

## Key Features

- **Multiple Operating Modes** - Bulk update by status filter, single issue update, CSV-based component auto-assignment, or bug list update
- **Flexible Status Filtering** - Specify any combination of statuses (comma-separated) in bulk mode
- **Single Issue Update** - Update a specific issue using `--issue-key OCPBUGS-12345`
- **Component-Based Auto-Assignment** - Automatically assign QA contacts based on component ownership from CSV exports
- **Dry-Run Mode** - Preview changes before applying them with `--dry-run` flag
- **Batch Processing** - Handles multiple issues efficiently in bulk mode
- **Progress Tracking** - Shows real-time progress during bulk updates
- **Error Handling** - Continues processing even if individual updates fail
- **Summary Report** - Displays detailed summary of all changes

## Implementation

The command uses the JIRA REST API to search and update issues:

### CRITICAL: Account ID Resolution

**IMPORTANT:** When searching for issues by QA Contact, you MUST use account IDs, not display names or emails in the JQL query. This is because:

1. ❌ `"QA Contact" = "Ying Zhou"` returns 0 results
2. ✅ `"QA Contact" = 70121:498e9c9b-9ca5-4fa2-8c39-4e43a4b1e232` returns actual results

**Implementation Steps:**
1. Resolve user name/email → account ID using `/rest/api/3/user/search`
2. Use account ID in JQL queries: `"QA Contact" = <accountId>`
3. Use POST endpoint `/rest/api/3/search/jql` (the GET endpoint is deprecated)

### API Endpoints

**New JQL Search Endpoint (use this):**
```bash
curl -X POST -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jql": "status = New AND \"QA Contact\" = 70121:abc123...", "fields": ["key", "summary"], "maxResults": 100}' \
  "https://redhat.atlassian.net/rest/api/3/search/jql"
```bash

**Old GET endpoint (deprecated, do NOT use):**
```bash
# This is deprecated and will fail
curl "https://redhat.atlassian.net/rest/api/3/search?jql=..."
```

### Performance Optimizations

**IMPORTANT:** For processing large numbers of bugs (10+), implement these optimizations to reduce execution time by 4-10x:

#### 1. Parallel Bug Fetching (Critical)

**❌ Naive Sequential Approach (SLOW):**
```bash
for bug in "${BUG_ARRAY[@]}"; do
  curl fetch bug  # 500ms each
done
# Time for 16 bugs: 16 × 500ms = 8 seconds
# Time for 100 bugs: 100 × 500ms = 50 seconds
```

**✅ Optimized Parallel Approach (FAST):**
```bash
fetch_bug() {
  local BUG_KEY="$1"
  curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
    "https://redhat.atlassian.net/rest/api/3/issue/${BUG_KEY}?fields=key,summary,components,customfield_10470" \
    > ".work/jira/fetched/${BUG_KEY}.json"
}
export -f fetch_bug
export JIRA_USERNAME JIRA_API_TOKEN

# Fetch all bugs in parallel (max 10 concurrent to avoid overwhelming API)
printf '%s\n' "${BUG_ARRAY[@]}" | xargs -P 10 -I {} bash -c 'fetch_bug "$@"' _ {}

# Time for 16 bugs: ~500ms
# Time for 100 bugs: ~2 seconds (10 batches of 10)
```

**Performance Gain:** 16x faster for 16 bugs, 25x faster for 100 bugs

#### 2. Account ID Caching (Important)

**❌ Naive Approach (SLOW):**
```bash
for bug in update_queue; do
  # Resolve account ID for EVERY bug (even duplicates)
  ACCOUNT_ID=$(resolve_user "$NEW_QA")  # 500ms
  update_bug "$bug" "$ACCOUNT_ID"
done
# If 50 bugs all map to same QA: 50 × 500ms = 25 seconds wasted
```

**✅ Optimized with Caching (FAST):**
```bash
declare -A ACCOUNT_ID_CACHE

# Resolve each UNIQUE QA contact once
UNIQUE_QAS=$(cut -d'|' -f5 update-queue.txt | sort -u)
for QA_EMAIL in $UNIQUE_QAS; do
  ACCOUNT_ID=$(resolve_user "$QA_EMAIL")
  ACCOUNT_ID_CACHE["$QA_EMAIL"]="$ACCOUNT_ID"
done

# Use cached account IDs for updates
for bug in update_queue; do
  ACCOUNT_ID="${ACCOUNT_ID_CACHE[$NEW_QA]}"  # Instant lookup
  update_bug "$bug" "$ACCOUNT_ID"
done
# If 50 bugs map to 3 unique QAs: 3 × 500ms = 1.5 seconds (instead of 25s)
```

**Performance Gain:** 16x faster when many bugs share same QA contacts

#### 3. Parallel Updates (Moderate)

**❌ Naive Sequential Approach:**
```bash
for bug in update_queue; do
  curl update bug  # 200ms each
done
# Time for 100 bugs: 100 × 200ms = 20 seconds
```

**✅ Optimized Parallel Approach:**
```bash
update_bug() {
  local KEY="$1"
  local ACCOUNT_ID="$2"
  curl -s -X PUT -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"fields\": {\"customfield_10470\": {\"accountId\": \"$ACCOUNT_ID\"}}}" \
    "https://redhat.atlassian.net/rest/api/3/issue/${KEY}"
}
export -f update_bug
export JIRA_USERNAME JIRA_API_TOKEN

# Update in parallel (max 10 concurrent)
cat update-queue.txt | xargs -P 10 -n 2 bash -c 'update_bug "$@"' _

# Time for 100 bugs: ~2 seconds (10 batches of 10)
```

**Performance Gain:** 10x faster for 100 bugs

#### Combined Performance Comparison

| Operation | Sequential | Optimized | Speedup |
|-----------|-----------|-----------|---------|
| Fetch 16 bugs | 8.0s | 0.5s | **16x** |
| Resolve 3 unique QAs (16 bugs) | 8.0s | 1.5s | **5x** |
| Update 16 bugs | 3.2s | 0.5s | **6x** |
| **Total (16 bugs)** | **19.2s** | **2.5s** | **8x** |
| **Total (100 bugs)** | **120s** | **8s** | **15x** |

#### Implementation Notes

- **Concurrency Limit:** Use `xargs -P 10` to limit to 10 parallel requests
  - Prevents overwhelming JIRA API
  - Avoids rate limiting (HTTP 429)
  - Adjust based on your network/API limits
- **Error Handling:** Check each fetched file exists before processing
- **Cleanup:** Remove `.work/jira/fetched/` directory after completion
- **Compatibility:** `xargs -P` works on Linux/macOS; Windows requires WSL or alternative

### Process Flow

1. **Validate Arguments and Determine Mode**:
   - Check if $1 is `--issue-key`, `--defaultcomponentowners`, `--bugs`, or status filter
   
   - **CSV Component Owners Mode** (if $1 == `--defaultcomponentowners`):
     - Verify that $2 is `--csv-file`
     - Verify that $3 (csv-file-path) is provided
     - Validate that CSV file exists and is readable
     - Look for `--component-map` flag to specify custom XML file path
       - Default: `plugins/jira/component-qa-mapping.xml`
     - Check for --dry-run flag in remaining arguments
   
   - **Bug List Auto-Assignment Mode** (if $1 == `--bugs`):
     - Verify that $2 (bug-list) is provided
     - Parse bug list from $2:
       - Comma-separated: `OCPBUGS-1,OCPBUGS-2,OCPBUGS-3`
       - Space-separated: `OCPBUGS-1 OCPBUGS-2 OCPBUGS-3`
       - Validate each bug key format (PROJECT-NUMBER)
     - Look for `--component-map` flag to specify custom XML file path
       - Default: `plugins/jira/component-qa-mapping.xml`
     - Check for --dry-run flag in remaining arguments
   
   - **Single Issue Mode** (if $1 == `--issue-key`):
     - Verify that $2 (issue-key) is provided and valid format (e.g., OCPBUGS-12345)
     - Check argument count to determine if old_qa_contacts_name is provided:
       - **2 arguments mode** (quick update, no validation):
         - $2 = issue-key
         - $3 = new_qa_contacts_name
         - old_qa_contacts_name is optional (will fetch current value from issue)
       - **3 arguments mode** (safe update with validation):
         - $2 = issue-key
         - $3 = old_qa_contacts_name
         - $4 = new_qa_contacts_name
     - Check for --dry-run flag in remaining arguments
   
   - **Bulk Mode** (if $1 is not `--issue-key`, `--defaultcomponentowners`, or `--bugs`):
     - Verify that $1 (bug_status) is provided and valid
     - Verify that $2 (old_qa_contacts_name) is provided
     - Verify that $3 (new_qa_contacts_name) is provided
     - Parse optional $4 (project-key) and check for --dry-run flag

2. **Authentication Setup**:
   - Verify JIRA_USERNAME and JIRA_API_TOKEN environment variables are set
   - If not set, provide instructions to obtain credentials from [Atlassian API Token Management](https://id.atlassian.com/manage-profile/security/api-tokens)
   - Exit with error if credentials are missing

3. **Parse Status Filter OR Fetch Specific Issue**:
   
   **For Bulk Mode:**
   - Split $1 by comma to get list of statuses
   - Common valid statuses: `NEW`, `ON_QA`, `Assigned`, `In Progress`, `POST`, `MODIFIED`, etc.
   - Normalize status names (handle case variations)
   - Examples:
     - `on_qa,new,assigned` → `["ON_QA", "NEW", "Assigned"]`
     - `on_qa` → `["ON_QA"]`
     - `new,assigned,in_progress` → `["NEW", "Assigned", "In Progress"]`
   
   **For Single Issue Mode:**
   - Validate issue key format (PROJECT-NUMBER)
   - Fetch the specific issue via API:
     ```bash
     curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
       -H "Content-Type: application/json" \
       "https://redhat.atlassian.net/rest/api/3/issue/$2?fields=key,summary,status,customfield_10470"
```bash
   - Verify issue exists, if not exit with error:
```text
     Error: Issue $2 not found in JIRA.
     Please verify the issue key is correct.
```bash
   - Extract current QA contact from the issue
   - **If old_qa_contacts_name was provided** (3-argument mode):
     - Verify current QA contact matches old_qa_contacts_name, if not:
```text
       Error: Issue $2 has QA contact "<actual-qa>" but expected "<old-qa-name>".
       Cannot update. Current QA contact does not match.
```bash
   - **If old_qa_contacts_name was NOT provided** (2-argument mode):
     - Use the fetched current QA contact name for display purposes only
     - No validation performed (quick update mode)
   - Store issue details for later update

3a. **CSV Component Owners Processing** (Only for `--defaultcomponentowners` mode):
   
   **Load Component Mapping:**
   - Load component-to-QA mappings from XML file
   - Default: `plugins/jira/component-qa-mapping.xml`
   - Verify file exists and parse XML
   
   **Read CSV File and Extract Bug Keys:**
   - Read CSV file from path specified in $3
   - Parse CSV to extract bug keys from "Key" or "Issue key" column
   - Supported CSV formats:
     - JIRA Rich Filter export: `T,Key,P,Summary,Assignee,Status`
     - Standard JIRA export: `Issue key,Summary,Status`
     - Any CSV with "Key" or "Issue key" column
   - Example extraction:
     ```bash
     tail -n +2 "$CSV_FILE" | cut -d',' -f2
```bash
   - Collect all unique bug keys
   
   **Fetch and Process Each Bug:**
   - **PERFORMANCE:** For 10+ bugs, use parallel fetching (see Performance Optimizations section)
   - For each bug key from CSV:
     - Fetch issue via API:
       ```bash
       curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
         "https://redhat.atlassian.net/rest/api/3/issue/<BUG-KEY>?fields=key,summary,components,customfield_10470"
```bash
     - If issue not found, skip with error:
```text
       Error: Issue <BUG-KEY> not found. Skipping.
```bash
     - Extract components array: `.fields.components[]`
     - **If no components**: Skip issue with warning:
```text
       Warning: Skipping <ISSUE-KEY> (no components assigned)
```bash
     - **If one component**: Use it for QA lookup
     - **If multiple components**: 
       - In interactive mode: Prompt user to select component
       - In non-interactive mode (CI): Use first component with warning:
```text
         Warning: <ISSUE-KEY> has multiple components, using first: <component-name>
```bash
     - Look up component in loaded XML mappings
     - **If component found**: 
       - Extract `<default-qa>` value
       - **Skip if placeholder email** (matches pattern `^[a-z]{4}@redhat\.com$`):
```text
         Warning: Skipping <ISSUE-KEY> (component "<name>" has placeholder QA contact)
```bash
       - Store as target QA for this issue
       - Add issue to update queue
     - **If component NOT found**: Skip issue with warning:
```text
       Warning: Skipping <ISSUE-KEY> (component "<name>" not in mapping)
```bash
   
   **Display Preview:**
   - Show table of all issues to be updated:
```bash
     Found X issues from CSV to update:
     
     KEY            SUMMARY                 COMPONENT         CURRENT QA    NEW QA
     ==================================================================================
     OCPBUGS-123    Bug in scheduler        kube-scheduler    unassigned    ropatil@...
     OCPBUGS-456    Auth failure            apiserver-auth    unassigned    ksiddiqui@...
     ...
```bash
   - If `--dry-run`, display and exit
   - Otherwise, prompt for confirmation and proceed to update (step 10)

3b. **Bug List Processing** (Only for `--bugs` mode):
   
   **Load Component Mapping:**
   - Same as step 3a: Load component-to-QA mappings from XML file
   
   **Parse Bug List:**
   - Split $2 by comma or space to get array of bug keys
   - Validate each bug key format (PROJECT-NUMBER)
   - Example: `OCPBUGS-1,OCPBUGS-2,OCPBUGS-3` → `["OCPBUGS-1", "OCPBUGS-2", "OCPBUGS-3"]`
   
   **Fetch Each Bug:**
   - **PERFORMANCE:** For 10+ bugs, use parallel fetching (see Performance Optimizations section)
   - For each bug key in the list:
     - Fetch issue via API:
       ```bash
       curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
         "https://redhat.atlassian.net/rest/api/3/issue/<BUG-KEY>?fields=key,summary,components,customfield_10470"
```bash
     - If issue not found, skip with error:
```text
       Error: Issue <BUG-KEY> not found. Skipping.
```bash
     - Extract components array
     - **Component handling**: Same logic as CSV mode (3a)
       - No components: Skip with warning
       - One component: Use it
       - Multiple components: Prompt or use first
     - Look up component in XML mappings
     - Add to update queue if component found
     - Skip if component not in mapping
   
   **Display Preview:**
   - Same preview table as CSV mode
   - If `--dry-run`, display and exit
   - Otherwise, prompt for confirmation and proceed to update (step 10)

4. **Determine QA Contact Field ID**:
   - The QA contact field in Red Hat JIRA is a custom field
   - Common custom field IDs for QA Contact:
     - OCPBUGS: `customfield_10470` (QA Contact)
     - Other projects may use different custom field IDs
   - Check environment variable JIRA_QA_CONTACT_FIELD first
   - If not set, use default `customfield_10470`
   - If field ID is unknown for the project, fetch project metadata to identify the correct field:
     ```bash
     curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
       "https://redhat.atlassian.net/rest/api/3/field" | \
       jq '.[] | select(.name | contains("QA Contact"))'
```bash

5. **Resolve QA Contact Users to Account IDs**:
   - **CRITICAL:** Resolve BOTH old and new QA contacts to account IDs
   - Search for user by name or email:
     ```bash
     curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
       "https://redhat.atlassian.net/rest/api/3/user/search?query=$3&maxResults=5"
```bash
   - Parse response to get user accountId
   - **Smart matching logic** (check in order):
     1. **Exact email match** (case-insensitive): If query is an email and one user has exact email match → auto-select
     2. **Exact display name match** (case-sensitive): If one user has exact displayName match → auto-select
     3. **Single result**: If only 1 user returned → auto-select
     4. **Multiple results**: Prompt user to select
   - If multiple matches found and no exact match, prompt user to select:
```bash
     Multiple users found for "$3":
     1. Jane Smith (jsmith@redhat.com) - accountId: 557058:12345...
     2. Jane Smith-Anderson (jsmithanderson@redhat.com) - accountId: 557058:67890...
     
     Select user (1-2):
```bash
   - **Example of smart matching**:
     - Query "Rohit Patil" returns 5 users, but only "Rohit Patil (ropatil@redhat.com)" has exact displayName match → auto-select without prompting
     - Query "ropatil@redhat.com" returns 1 user with exact email match → auto-select without prompting
   - If no matches found, display error and exit:
```text
     Error: QA contact '<user-query>' not found in JIRA. Please verify the name or email address.
```bash
   - **Store BOTH account IDs:**
     - `OLD_QA_ACCOUNT_ID` - for JQL search query
     - `NEW_QA_ACCOUNT_ID` - for update API call
   - This is required because JQL searches by name don't work reliably

6. **Build JQL Search Query OR Prepare Single Issue**:
   
   **For Bulk Mode:**
   - **CRITICAL:** Use OLD_QA_ACCOUNT_ID (not name) in JQL query
   - Construct JQL to find matching issues based on parsed statuses:
```bash
     status IN (ON_QA, NEW, Assigned) AND "QA Contact" = <OLD_QA_ACCOUNT_ID>
```bash
   - Example with actual account ID:
```bash
     status = New AND "QA Contact" = 70121:498e9c9b-9ca5-4fa2-8c39-4e43a4b1e232
```bash
   - If project-key ($4) is provided and is not --dry-run, add to query:
```bash
     status IN (ON_QA, NEW, Assigned) AND "QA Contact" = <OLD_QA_ACCOUNT_ID> AND project = "<project-key>"
```bash
   - Prepare JSON payload for POST request (do NOT URL-encode for POST)
   
   **For Single Issue Mode:**
   - Skip JQL search - already have the issue from step 3
   - Prepare single-issue array with issue details

7. **Search for Issues (Bulk Mode Only)**:
   
   **For Bulk Mode:**
   - **USE POST ENDPOINT** (GET endpoint is deprecated):
     ```bash
     PAYLOAD=$(jq -n \
       --arg jql "status = New AND \"QA Contact\" = 70121:abc123..." \
       --argjson fields '["key", "summary", "status", "customfield_10470", "project"]' \
       '{jql: $jql, fields: $fields, maxResults: 100}')
     
     curl -s -X POST -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
       -H "Content-Type: application/json" \
       -d "$PAYLOAD" \
       "https://redhat.atlassian.net/rest/api/3/search/jql"
```bash
   - Response format is `.issues[]` (not `.values[]`)
   - Handle pagination if needed (check `.isLast` field)
   - Parse JSON response to extract issue keys, summaries, statuses, and current QA contacts
   - Store results in array for processing
   
   **For Single Issue Mode:**
   - Skip search - already have the issue from step 3

8. **Display Preview**:
   
   **For Bulk Mode:**
   - Show found issues in a table format:
```bash
     Found X issues matching criteria:
     
     KEY            SUMMARY                                    STATUS      CURRENT QA           NEW QA
     ====================================================================================================
     OCPBUGS-12345  Fix login bug on mobile                    ON_QA       <old-qa-name>        <new-qa-name>
     OCPBUGS-12346  Update API endpoint for auth               Assigned    <old-qa-name>        <new-qa-name>
     OCPBUGS-12347  Improve error handling in controller       NEW         <old-qa-name>        <new-qa-name>
     ...
```bash
   - If no issues found, display message and exit:
```bash
     No issues found with status(es): <bug_status>
     And QA Contact: <old-qa-name>
     
     Possible reasons:
     - QA contact name doesn't match exactly
     - No issues in specified statuses
     - Project filter too restrictive
```bash
   
   **For Single Issue Mode:**
   - Show the specific issue details:
```bash
     Found 1 issue to update:
     
     KEY            SUMMARY                                    STATUS      CURRENT QA           NEW QA
     ====================================================================================================
     OCPBUGS-78997  Fix authentication timeout issue           ON_QA       <old-qa-name>        <new-qa-name>
```bash
   
   **For Both Modes:**
   - If `--dry-run` flag is present, display preview and exit without updating:
```bash
     DRY-RUN MODE: No changes will be made.
     
     Would update X issue(s) from "<old-qa-name>" to "<new-qa-name>"
```bash

9. **Confirm Update** (if not dry-run):
   
   **For Bulk Mode:**
   - Prompt user for confirmation:
```bash
     Update QA contact for X issues?
     From: "<old-qa-name>"
     To:   "<new-qa-name>"
     Statuses: <bug_status>
     
     Proceed with update? (yes/no):
```bash
   
   **For Single Issue Mode:**
   - Prompt user for confirmation:
```bash
     Update QA contact for issue <issue-key>?
     Summary: <issue-summary>
     Status: <issue-status>
     From: "<old-qa-name>"
     To:   "<new-qa-name>"
     
     Proceed with update? (yes/no):
```bash
   
   **For Both Modes:**
   - If user says no or anything other than "yes", exit without changes
   - If user says yes, proceed to update

10. **Update Issues**:
    
    **PERFORMANCE OPTIMIZATIONS:**
    - **Account ID Caching:** Resolve each unique QA contact once, cache the account ID
    - **Parallel Updates:** For 10+ bugs, update in parallel (see Performance Optimizations section)
    
    **For Bulk Mode:**
    - Process issues in batches of 50 to avoid overwhelming the API
    
    **For Single Issue Mode:**
    - Process the single issue (no batching needed)
    
    **For Both Modes:**
    - For each issue, execute update API call:
      ```bash
      curl -s -X PUT \
        -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
          "fields": {
            "customfield_10470": {"accountId": "<new-qa-accountId>"}
          }
        }' \
        "https://redhat.atlassian.net/rest/api/3/issue/<issue-key>"
```bash
    - Track successful and failed updates in separate arrays
    - Display progress indicator with percentage:
```bash
      Updating issues: [===========>          ] 55% (27/50)
```bash
    - Implement retry logic with exponential backoff for transient failures:
      - Initial retry delay: 2 seconds
      - Max retries: 3
      - Exponential backoff multiplier: 2x
    - Handle rate limiting (HTTP 429):
```bash
      Rate limit exceeded. Pausing for 60 seconds...
```bash
      - Wait for Retry-After header duration or 60 seconds
      - Retry the request

11. **Generate Summary Report**:
    - Write detailed log to `.work/jira/update-qa-contact-<timestamp>.log`
    
    **For Bulk Mode:**
    - Display final results to user:
```bash
      ===== Update Summary =====
      Mode: Bulk Update
      Status Filter: <bug_status>
      Total issues found: X
      Successfully updated: Y
      Failed updates: Z
      
      Successfully updated issues:
      ✓ OCPBUGS-12345: Fix login bug on mobile
      ✓ OCPBUGS-12346: Update API endpoint for auth
      ✓ OCPBUGS-12347: Improve error handling in controller
      ...
      
      Failed updates (if any):
      ✗ OCPBUGS-12348: Error: Field not editable (issue is closed)
      ✗ OCPBUGS-12349: Error: Permission denied (no edit access)
      
      QA Contact updated:
      From: "<old-qa-name>"
      To:   "<new-qa-name>"
      
      Log file: .work/jira/update-qa-contact-<timestamp>.log
```bash
    
    **For Single Issue Mode:**
    - Display final results to user:
```bash
      ===== Update Summary =====
      Mode: Single Issue Update
      Issue: <issue-key>
      
      ✓ Successfully updated <issue-key>: <issue-summary>
      
      QA Contact updated:
      From: "<old-qa-name>"
      To:   "<new-qa-name>"
      
      View issue: https://redhat.atlassian.net/browse/<issue-key>
      Log file: .work/jira/update-qa-contact-<timestamp>.log
```bash
    
    **If single issue update failed:**
```bash
      ===== Update Summary =====
      Mode: Single Issue Update
      Issue: <issue-key>
      
      ✗ Failed to update <issue-key>: <error-message>
      
      Possible reasons:
      - QA Contact field not editable
      - Permission denied
      - Issue workflow restrictions
      
      Log file: .work/jira/update-qa-contact-<timestamp>.log
```bash

### API Endpoints Used

**Search Users:**
```http
GET https://redhat.atlassian.net/rest/api/3/user/search
Parameters:
  - query: User name or email to search
  - maxResults: Maximum number of results (default: 5)
```bash

**Search Issues:**
```http
POST https://redhat.atlassian.net/rest/api/3/search/jql
Content-Type: application/json

Body (JSON):
{
  "jql": "status = New AND \"QA Contact\" = <accountId>",
  "fields": ["key", "summary", "status", "customfield_10470"],
  "maxResults": 100,
  "startAt": 0
}
```

**Update Issue:**
```http
PUT https://redhat.atlassian.net/rest/api/3/issue/{issueKey}
Body:
{
  "fields": {
    "customfield_10470": {"accountId": "<accountId>"}
  }
}
```bash

**Get Field Metadata (for QA Contact field discovery):**
```http
GET https://redhat.atlassian.net/rest/api/3/field
```bash

### QA Contact Field Format

The QA Contact field in JIRA is a user field. The correct update payload format is:

**✅ Correct format (using accountId):**
```json
{
  "fields": {
    "customfield_10470": {"accountId": "557058:12345678-abcd-1234-abcd-123456789abc"}
  }
}
```bash

**❌ Incorrect formats (will fail):**
```json
// Don't use display name
{"customfield_10470": {"name": "Jane Smith"}}

// Don't use email
{"customfield_10470": {"email": "jsmith@redhat.com"}}

// Don't use string value
{"customfield_10470": "Jane Smith"}
```bash

**User Resolution Strategy:**
1. Search for user using the name/email provided in $3
2. Extract accountId from search results
3. Use accountId in all update API calls
4. This ensures reliable, unambiguous user assignment

### Error Handling

**Common Errors:**

1. **Missing Mandatory Arguments**:
   - **Bulk mode**: "Error: Missing required arguments. Usage: /jira:update-qa-contact <bug_status> <old_qa_contacts_name> <new_qa_contacts_name> [project-key] [--dry-run]"
   - **Single issue mode**: "Error: Missing required arguments. Usage: /jira:update-qa-contact --issue-key <ISSUE-KEY> <old_qa_contacts_name> <new_qa_contacts_name> [--dry-run]"
   - Action: Display usage and exit

1a. **Issue Not Found (Single Issue Mode)**:
   - Message: "Error: Issue OCPBUGS-78997 not found in JIRA. Please verify the issue key is correct."
   - Action: Verify issue key spelling and ensure it exists

1b. **QA Contact Mismatch (Single Issue Mode - 3-argument mode only)**:
   - Message: "Error: Issue OCPBUGS-78997 has QA contact 'Alice Brown' but expected 'John Doe'. Cannot update. Current QA contact does not match."
   - Action: Either use 2-argument mode (no validation) or provide correct current QA contact name
   - Tip: Check the issue in JIRA UI to see current QA contact, or use 2-argument mode to skip validation

2. **Authentication Failed (401)**:
   - Message: "JIRA authentication failed. Please check JIRA_USERNAME and JIRA_API_TOKEN environment variables."
   - Action: 
```bash
     Set environment variables:
     export JIRA_USERNAME="your-email@redhat.com"
     export JIRA_API_TOKEN="your-api-token"
     
     Obtain token from: https://id.atlassian.com/manage-profile/security/api-tokens
```bash

3. **Permission Denied (403)**:
   - Message: "Permission denied for issue OCPBUGS-12345. You may not have edit access."
   - Action: Skip this issue, continue with others, report in summary

4. **Field Not Found**:
   - Message: "QA Contact field not found. This field may not exist in project <project>."
   - Action: Verify field availability or set JIRA_QA_CONTACT_FIELD environment variable

5. **New QA Contact User Not Found**:
   - Message: "Error: QA contact '<new-qa-name>' not found in JIRA. Please verify the name or email address."
   - Action: Exit before making any changes

6. **Issue Not Editable**:
   - Message: "Cannot update OCPBUGS-12345: Issue is closed or workflow doesn't allow QA contact changes."
   - Action: Skip this issue, continue with others, report in failed updates section

7. **Rate Limiting (429)**:
   - Message: "Rate limit exceeded. Pausing for 60 seconds..."
   - Action: Wait for Retry-After header duration, then retry automatically

8. **Network/Connection Errors**:
   - Message: "Failed to connect to JIRA API. Check network connectivity and VPN."
   - Action: Retry with exponential backoff (max 3 attempts), then fail

### Implementation Notes

- **Batch Size**: Process issues in batches of 50 to avoid overwhelming the API
- **Retry Logic**: Implement retry with exponential backoff for transient failures (2s, 4s, 8s)
- **Logging**: Write detailed logs to `.work/jira/update-qa-contact-<timestamp>.log` including:
  - Timestamp of operation
  - Parameters used (statuses, old QA, new QA, project)
  - Each API call made (JQL query, update requests)
  - Success/failure for each issue
  - Final summary statistics
- **Validation**: Validate that new QA contact exists in JIRA before starting any updates
- **Working Directory**: Create `.work/jira/` directory if it doesn't exist
- **Status Normalization**: Handle different case formats (on_qa → ON_QA, assigned → Assigned)

## Usage Examples

### Bulk Mode Examples

1. **Update QA contact for ON_QA, NEW, and Assigned statuses with dry-run preview**:
```bash
   /jira:update-qa-contact on_qa,new,assigned "John Doe" "Jane Smith" --dry-run
```bash
   → Shows which issues would be updated without making changes

2. **Update QA contact for ON_QA status only in OCPBUGS project**:
```bash
   /jira:update-qa-contact on_qa "John Doe" "Jane Smith" OCPBUGS
```bash
   → Updates QA contact only for OCPBUGS project issues in ON_QA status

3. **Update QA contact for multiple statuses across all accessible projects**:
```bash
   /jira:update-qa-contact on_qa,new,assigned "John Doe" "Jane Smith"
```bash
   → Updates QA contact for all projects where user has access

4. **Update QA contact using email addresses**:
```bash
   /jira:update-qa-contact new,assigned "jdoe@redhat.com" "jsmith@redhat.com" OCPBUGS
```bash
   → Uses email addresses to identify QA contacts

5. **Update QA contact for POST and MODIFIED statuses**:
```bash
   /jira:update-qa-contact post,modified "Old QA" "New QA" --dry-run
```bash
   → Preview changes for issues in POST or MODIFIED status

6. **Update QA contact for single status**:
```bash
   /jira:update-qa-contact on_qa "John Doe" "Jane Smith" OCPBUGS
```bash
   → Updates only issues in ON_QA status

### Single Issue Mode Examples

7. **Update QA contact for a specific issue (quick mode - no validation)**:
```bash
   /jira:update-qa-contact --issue-key OCPBUGS-78997 "Yingzhao Zhou" --dry-run
```bash
   → Preview QA contact change for OCPBUGS-78997 without knowing current value

8. **Update QA contact for a specific issue (quick mode)**:
```bash
   /jira:update-qa-contact --issue-key OCPBUGS-78997 "Yingzhao Zhou"
```bash
   → Updates QA contact directly to "Yingzhao Zhou" (no validation of current value)

9. **Update QA contact for a specific issue (safe mode with validation)**:
```bash
   /jira:update-qa-contact --issue-key OCPBUGS-78997 "John Doe" "Jane Smith" --dry-run
```bash
   → Preview and validate current QA is "John Doe" before changing to "Jane Smith"

10. **Update QA contact using email addresses**:
```bash
    /jira:update-qa-contact --issue-key OCPBUGS-78997 "jsmith@redhat.com"
```bash
    → Quick update using email address

11. **Update with validation using email addresses**:
```bash
    /jira:update-qa-contact --issue-key OCPBUGS-78997 "jdoe@redhat.com" "jsmith@redhat.com"
```bash
    → Validates current QA is jdoe@redhat.com before updating

12. **Update QA contact for RFE issue**:
```bash
    /jira:update-qa-contact --issue-key RFE-1234 "New QA"
```bash
    → Works with any JIRA project (RFE, CNTRLPLANE, etc.)

### CSV Component Owners Examples

13. **Auto-assign bugs from CSV export with dry-run**:
```bash
    /jira:update-qa-contact --defaultcomponentowners --csv-file ~/Downloads/dashboard-bugs.csv --dry-run
```bash
    → Preview which QA contacts would be assigned based on components

14. **Auto-assign bugs from CSV export**:
```bash
    /jira:update-qa-contact --defaultcomponentowners --csv-file ~/Downloads/dashboard-bugs.csv
```bash
    → Process all bugs from CSV file, assign QA based on component ownership

15. **CSV with custom component mapping**:
```bash
    /jira:update-qa-contact --defaultcomponentowners --csv-file bugs.csv --component-map /path/to/custom-map.xml
```bash
    → Use custom component-to-QA mapping file

16. **CSV from JIRA Rich Filter export**:
```bash
    /jira:update-qa-contact --defaultcomponentowners --csv-file /home/user/Downloads/rich-filter-export.csv
```bash
    → Works with JIRA Rich Filter CSV exports

### Bug List Auto-Assignment Examples

17. **Auto-assign specific bugs by list**:
```bash
    /jira:update-qa-contact --bugs OCPBUGS-56893,OCPBUGS-56894,OCPBUGS-56895
```bash
    → Process only these 3 bugs, assign QA based on their components

18. **Bug list with space separation**:
```bash
    /jira:update-qa-contact --bugs "OCPBUGS-78326 OCPBUGS-8755 OCPBUGS-56893"
```bash
    → Space-separated bug list (use quotes)

19. **Bug list across multiple projects**:
```bash
    /jira:update-qa-contact --bugs OCPBUGS-123,RFE-456,HYPE-789
```bash
    → Works with bugs from different JIRA projects

20. **Bug list with dry-run**:
```bash
    /jira:update-qa-contact --bugs OCPBUGS-1,OCPBUGS-2,OCPBUGS-3 --dry-run
```bash
    → Preview QA assignments before applying

21. **Bug list with custom mapping**:
```bash
    /jira:update-qa-contact --bugs OCPBUGS-123,OCPBUGS-456 --component-map /path/to/map.xml
```bash
    → Use custom component-to-QA mapping file

## Arguments

### Bulk Mode Arguments

- **$1 – bug_status** *(required in bulk mode)*
  Comma-separated list of JIRA statuses to filter.
  Status names are case-insensitive and will be normalized.
  
  **Common valid statuses:**
  - `new` or `NEW` - New/untriaged issues
  - `on_qa` or `ON_QA` - Issues in QA testing
  - `assigned` or `Assigned` - Assigned but not started
  - `in_progress` or `In Progress` - Work in progress
  - `post` or `POST` - Posted for review
  - `modified` or `MODIFIED` - Modified/updated
  
  **Examples:**
  - `on_qa,new,assigned` - Multiple statuses
  - `on_qa` - Single status
  - `NEW,Assigned,In Progress` - Different case styles

- **$2 – old_qa_contacts_name** *(required)*
  Current QA contact name to search for and replace.
  Can be display name or email address.
  Must match exactly as it appears in JIRA (case-sensitive for display names).
  
  **Examples:**
  - `"John Doe"` - Display name
  - `"jdoe@redhat.com"` - Email address
  - `"John D. Doe"` - Full name with middle initial

- **$3 – new_qa_contacts_name** *(required)*
  New QA contact name to update to.
  Can be display name or email address.
  Will be validated against JIRA users before any updates.
  
  **Examples:**
  - `"Jane Smith"` - Display name
  - `"jsmith@redhat.com"` - Email address
  - `"Jane S. Smith"` - Full name with middle initial

- **$4 – project-key** *(optional)*
  JIRA project key to limit the search scope.
  If omitted, searches across all accessible projects.
  
  **Examples:**
  - `OCPBUGS` - OpenShift bugs project
  - `RFE` - Feature requests
  - `CNTRLPLANE` - Control plane project

- **--dry-run** *(optional flag)*
  Preview changes without applying them.
  Shows which issues would be updated.
  Can be provided as $4, $5, or anywhere in arguments.
  
  **Example:**
```bash
  /jira:update-qa-contact on_qa,new "Old" "New" --dry-run
  /jira:update-qa-contact on_qa,new "Old" "New" OCPBUGS --dry-run
```bash

### Single Issue Mode Arguments

- **$1 – --issue-key** *(required flag for single issue mode)*
  Flag to indicate single issue mode.
  Must be exactly `--issue-key`.

- **$2 – ISSUE-KEY** *(required in single issue mode)*
  The specific JIRA issue key to update.
  Format: PROJECT-NUMBER (e.g., OCPBUGS-78997, RFE-1234, CNTRLPLANE-5678)
  
  **Examples:**
  - `OCPBUGS-78997` - Specific OpenShift bug
  - `RFE-1234` - Specific feature request
  - `CNTRLPLANE-5678` - Specific control plane issue

- **$3 – old_qa_contacts_name OR new_qa_contacts_name** *(context-dependent)*
  
  **2-argument mode (quick update, no validation):**
  - $3 is the **new QA contact name** to update to
  - Current QA contact is fetched but NOT validated
  - Faster workflow when you just want to set a value
  
  **3-argument mode (safe update with validation):**
  - $3 is the **old QA contact name** (current value)
  - Must match the issue's current QA contact, otherwise update fails
  - $4 becomes the **new QA contact name**
  
  **Examples:**
  - `"Jane Smith"` - Display name
  - `"jsmith@redhat.com"` - Email address

- **$4 – new_qa_contacts_name** *(required only in 3-argument mode)*
  New QA contact name to update to.
  Can be display name or email address.
  Will be validated against JIRA users before update.
  
  **Examples:**
  - `"Jane Smith"` - Display name
  - `"jsmith@redhat.com"` - Email address

- **--dry-run** *(optional flag)*
  Preview the change without applying it.
  Shows what would be updated.
  Can be provided as $5 or anywhere in arguments.
  
  **Example:**
```bash
  /jira:update-qa-contact --issue-key OCPBUGS-78997 "Old" "New" --dry-run
```bash

## Return Value

- **Exit Code 0**: All updates successful (or dry-run completed)
- **Exit Code 1**: Some updates failed (partial success)
- **Exit Code 2**: No issues found matching criteria
- **Exit Code 3**: Authentication or permission error
- **Exit Code 4**: Invalid arguments or missing mandatory parameters
- **Exit Code 5**: New QA contact not found in JIRA
- **Summary Report**: Detailed report of all changes made

## Configuration

### Environment Variables

**Required:**
- **JIRA_USERNAME**: Your Atlassian account email address
  - Example: `jdoe@redhat.com`
  - Obtain from: Your Atlassian account profile

- **JIRA_API_TOKEN**: Atlassian API token for authentication
  - Obtain from: [Atlassian API Token Management](https://id.atlassian.com/manage-profile/security/api-tokens)
  - Store securely (never commit to version control)

**Optional:**
- **JIRA_QA_CONTACT_FIELD**: Custom field ID for QA Contact
  - Default: `customfield_10470` (OCPBUGS standard)
  - Override if different for your project
  - Find field ID: `curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" "https://redhat.atlassian.net/rest/api/3/field" | jq '.[] | select(.name | contains("QA Contact"))'`

**Setup Example (add to ~/.bashrc or project .env):**
```bash
export JIRA_USERNAME="your-email@redhat.com"
export JIRA_API_TOKEN="your-api-token-here"
export JIRA_QA_CONTACT_FIELD="customfield_10470"  # Optional, has default
```bash

**MCP Configuration (if using MCP server):**

Add to `~/.config/claude-code/mcp.json`:
```json
{
  "mcpServers": {
    "atlassian": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-atlassian"],
      "env": {
        "JIRA_USERNAME": "your-email@redhat.com",
        "JIRA_API_TOKEN": "your-atlassian-api-token-here"
      }
    }
  }
}
```bash

## Best Practices

1. **Always use --dry-run first**: Preview changes before applying them to avoid mistakes
```bash
   /jira:update-qa-contact on_qa,new,assigned "Old" "New" --dry-run
```bash

2. **Verify new QA contact exists**: The command validates this automatically, but double-check spelling

3. **Start with specific project**: Test with one project before running across all projects
```bash
   /jira:update-qa-contact on_qa "Old" "New" OCPBUGS --dry-run
```bash

4. **Use exact status names**: Match status names as they appear in JIRA (command normalizes common variations)

5. **Check user permissions**: Verify you have edit permissions for target issues before running

6. **Run during low-activity periods**: Avoid peak hours to reduce API load and contention

7. **Review logs after execution**: Check `.work/jira/update-qa-contact-<timestamp>.log` for details

8. **Communicate with team**: Notify affected team members about QA contact changes

9. **Use email addresses for disambiguation**: When names are common, use email addresses:
```bash
   /jira:update-qa-contact on_qa "jdoe@redhat.com" "jsmith@redhat.com"
```

10. **Optimize for large datasets**: For 10+ bugs, implement parallel fetching and account ID caching
   - Sequential processing: ~80 seconds for 100 bugs
   - Optimized processing: ~8 seconds for 100 bugs (10x faster)
   - See "Performance Optimizations" section for implementation details
   - Use reference implementation: `.work/jira/update-qa-optimized.sh`

## Anti-Patterns to Avoid

❌ **Running without dry-run on large datasets**
```bash
/jira:update-qa-contact on_qa,new,assigned "Old Name" "New Name"  # Updates immediately
```bash
✅ Always preview first with --dry-run:
```bash
/jira:update-qa-contact on_qa,new,assigned "Old Name" "New Name" --dry-run
```bash

❌ **Using partial or ambiguous names**
```bash
/jira:update-qa-contact on_qa "John" "Jane"  # May match multiple users
```bash
✅ Use full names or email addresses:
```bash
/jira:update-qa-contact on_qa "John Doe" "Jane Smith"
/jira:update-qa-contact on_qa "jdoe@redhat.com" "jsmith@redhat.com"
```bash

❌ **Ignoring error messages**
```bash
# Proceeding despite authentication errors
```bash
✅ Address errors before continuing:
```bash
# Fix authentication, verify permissions, then retry
```bash

❌ **Not verifying new QA contact exists**
```bash
/jira:update-qa-contact on_qa "Old Name" "Typo Namee"  # New name has typo
```bash
✅ Command validates automatically, but double-check your input:
```bash
/jira:update-qa-contact on_qa "Old Name" "Jane Smith" --dry-run
```bash

❌ **Using wrong status names**
```bash
/jira:update-qa-contact qa,triaged "Old" "New"  # Invalid status names
```bash
✅ Use correct JIRA status names:
```bash
/jira:update-qa-contact on_qa,new "Old" "New"
```bash

❌ **Not specifying status filter in bulk mode**
```bash
/jira:update-qa-contact "Old Name" "New Name"  # Missing $1 (bug_status)
```bash
✅ Always provide status filter as first argument for bulk mode:
```bash
/jira:update-qa-contact on_qa,new,assigned "Old Name" "New Name"
```bash
✅ Or use single issue mode for specific issues:
```bash
/jira:update-qa-contact --issue-key OCPBUGS-78997 "Old Name" "New Name"
```bash

❌ **Using wrong issue key format in single issue mode**
```bash
/jira:update-qa-contact --issue-key 78997 "New QA"  # Missing project prefix
```bash
✅ Use full issue key with project:
```bash
/jira:update-qa-contact --issue-key OCPBUGS-78997 "New QA"
```bash

❌ **Wanting validation but using 2-argument mode**
```bash
/jira:update-qa-contact --issue-key OCPBUGS-78997 "New QA"
# No validation - updates regardless of current value
```bash
✅ Use 3-argument mode for validation:
```bash
/jira:update-qa-contact --issue-key OCPBUGS-78997 "Current QA" "New QA"
# Validates current QA matches "Current QA" before updating
```bash

❌ **Providing wrong current QA in 3-argument mode**
```bash
/jira:update-qa-contact --issue-key OCPBUGS-78997 "Wrong Name" "New QA"
# Fails because issue has different QA contact
```bash
✅ Either verify current name or use 2-argument mode:
```bash
# Option 1: 2-argument mode (no validation)
/jira:update-qa-contact --issue-key OCPBUGS-78997 "New QA"

# Option 2: 3-argument mode with correct current name
/jira:update-qa-contact --issue-key OCPBUGS-78997 "Correct Current" "New QA"
```bash

## Troubleshooting

### Issue: No issues found

**Possible causes:**
- Old QA name doesn't match exactly (case-sensitive for display names)
- Issues are not in specified statuses
- Project-key filter is too restrictive
- QA Contact field is empty on those issues

**Solutions:**
- Verify exact QA contact name in JIRA UI (check an actual issue)
- Check issue statuses match criteria (use dry-run to debug)
- Try without project-key filter to search all projects
- Check if QA Contact field is actually populated

**Debug command:**
```bash
/jira:update-qa-contact on_qa,new,assigned "Exact Name" "New Name" --dry-run
```bash

### Issue: Updates fail with "Field not editable"

**Possible causes:**
- Issue workflow doesn't allow QA contact changes in current status
- Issue is closed or resolved (but shouldn't match NEW/ON_QA/Assigned filter)
- Field is locked by project configuration
- User doesn't have edit permission

**Solutions:**
- Skip closed/resolved issues (command should filter these out)
- Contact project admin to unlock field configuration
- Verify you have "Edit Issues" permission for the project
- Check individual issue to see if QA Contact field is editable

### Issue: Rate limit exceeded

**Possible causes:**
- Too many API calls in short time (large batch updates)
- Concurrent JIRA operations running (other scripts/users)
- API quotas exhausted

**Solutions:**
- Command automatically implements retry with backoff - just wait
- Reduce batch size in code (currently 50, can lower to 25)
- Run during off-peak hours
- Contact JIRA admin if rate limits are too restrictive

### Issue: Authentication errors despite valid token

**Possible causes:**
- Token expired (tokens don't expire but can be revoked)
- Username/email mismatch with token owner
- VPN or network connectivity issues
- Token lacks required permissions

**Solutions:**
- Regenerate token at [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
- Verify JIRA_USERNAME matches the email of token owner
- Check VPN connection to Red Hat network
- Verify token has not been revoked in Atlassian settings

**Test authentication:**
```bash
curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
  "https://redhat.atlassian.net/rest/api/3/myself" | jq .
```bash

### Issue: Multiple users found for new QA contact

**Possible causes:**
- Name is ambiguous (multiple "Jane Smith")
- Email domain differs (contractor vs employee)

**Solutions:**
- Command will prompt you to select the correct user:
```bash
  Multiple users found for "Jane Smith":
  1. Jane Smith (jsmith@redhat.com)
  2. Jane Smith-Anderson (jsmithanderson@redhat.com)
  
  Select user (1-2):
```bash
- Use email address instead of name to avoid ambiguity:
```bash
  /jira:update-qa-contact on_qa "old@redhat.com" "new@redhat.com"
```bash

### Issue: Command hangs or times out

**Possible causes:**
- Very large result set (thousands of issues)
- Network connectivity issues
- JIRA API slow response

**Solutions:**
- Add project filter to reduce scope:
```bash
  /jira:update-qa-contact on_qa "Old" "New" OCPBUGS
```bash
- Check network connectivity and VPN
- Try again during off-peak hours
- Check `.work/jira/update-qa-contact-<timestamp>.log` for last successful operation

### Issue: Single issue mode - current QA contact doesn't match

**Scenario:** Trying to update OCPBUGS-78997 but command says current QA contact doesn't match.

**Possible causes:**
- Issue has different QA contact than expected
- QA contact field is empty on the issue
- Name format doesn't match (display name vs email)

**Solutions:**
- Check the issue in JIRA UI to see actual current QA contact
- Use dry-run to see what the mismatch is:
```bash
  /jira:update-qa-contact --issue-key OCPBUGS-78997 "Expected" "New" --dry-run
```bash
- Try using email address instead of display name:
```bash
  /jira:update-qa-contact --issue-key OCPBUGS-78997 "current@redhat.com" "new@redhat.com"
```bash
- If QA contact is empty, the old_qa_contacts_name should be empty string or actual current value

## Verified Test Cases

The following test cases have been verified and confirmed working:

### Single Issue Mode - 2-Argument (Quick Update)

**Test 1: Update using email address**
```bash
/jira:update-qa-contact --issue-key OCPBUGS-78997 "skundu@redhat.com"
```bash
**Result**: ✅ PASS
- Successfully updated OCPBUGS-78997 QA contact to Sandeep Kundu
- No validation of current QA contact (quick mode)
- User resolution worked correctly with email address

### Single Issue Mode - 3-Argument (Safe Update with Validation)

**Test 2: Update with validation using email addresses**
```bash
/jira:update-qa-contact --issue-key OCPBUGS-78997 "skundu@redhat.com" "ropatil@redhat.com"
```bash
**Result**: ✅ PASS
- Successfully validated current QA contact is skundu@redhat.com
- Updated to Rohit Patil (ropatil@redhat.com)
- Proper validation before update

### Bulk Mode - Using Display Names

**Test 3: Bulk update with user selection**
```bash
/jira:update-qa-contact NEW "Yingzhao Zhou" "Rohit Patil" OCPBUGS
```bash
**Result**: ✅ PASS  
- Found multiple users named "Yingzhao Zhou" (5 matches)
- Prompted user to select correct match (option 1 selected)
- Found multiple users named "Rohit Patil" (5 matches)
- Prompted user to select correct match (option 1 selected)
- Successfully found 2 matching issues:
  - OCPBUGS-78326
  - OCPBUGS-8755
- Updated both issues from Yingzhao Zhou to Rohit Patil
- Progress indicator worked correctly (50%, 100%)
- Exit code: 0 (full success)

### Bulk Mode - Using Email Addresses (Recommended)

**Test 4: Bulk update with email addresses**
```bash
/jira:update-qa-contact NEW "yingzhou@redhat.com" "ropatil@redhat.com" OCPBUGS
```bash
**Result**: ✅ PASS
- Email addresses provided unambiguous user identification
- No user selection prompts needed
- Successfully found 1 remaining issue (OCPBUGS-8755)
  - Note: OCPBUGS-78326 was already updated in Test 3
- Updated OCPBUGS-8755 from Yingzhao Zhou to Rohit Patil
- Exit code: 0 (full success)

### Key Findings

1. **Email addresses vs display names**:
   - ✅ Email addresses: Direct match, no user selection needed
   - ⚠️ Display names: May require user selection if ambiguous

2. **JQL Query Requirements**:
   - Must use account IDs in JQL queries, not display names
   - Implementation correctly resolves names → account IDs → JQL query

3. **Issue Count Parsing**:
   - Fixed bug where `.total` field was null in API response
   - Changed to `.issues | length` for accurate count

4. **API Response Format**:
   - POST endpoint `/rest/api/3/search/jql` returns `.issues[]`
   - GET endpoint is deprecated (not used in implementation)

### Performance Notes

- User search: ~500ms per query
- JQL search: ~800ms for 100 issues
- Issue update: ~200ms per issue
- Progress indicator updates every issue
- No rate limiting encountered with 2 issues

## See Also

- `jira:solve` - Analyze and solve JIRA issues
- `jira:create` - Create JIRA issues with proper formatting
- `jira:grooming` - Generate grooming meeting agendas
- `jira:status-rollup` - Create status rollup reports
- `jira:backlog` - Manage backlog items

## Security Considerations

**IMPORTANT**: This command handles user assignments and requires appropriate permissions.

**Permissions required:**
- **Edit Issues** permission for target projects
- **Browse Projects** permission for target projects
- **Assignable User** permission (to assign QA contacts)

**Data handling:**
- Never log or display JIRA_API_TOKEN values
- Sanitize log files before sharing (remove any tokens)
- Use HTTPS for all API calls (default in implementation)
- Respect JIRA's rate limits to avoid service disruption

**Audit trail:**
- JIRA automatically logs all field changes in issue history
- Changes are attributed to the API token owner (JIRA_USERNAME)
- Reviewers can see who made QA contact changes and when
- Log files in `.work/jira/` contain operation details for troubleshooting

**Best practices:**
- Rotate API tokens regularly (every 90 days recommended)
- Store tokens in environment variables, not in code
- Never commit API tokens to git repositories
- Use project-specific tokens with minimal permissions when possible
- Review audit logs periodically to verify expected changes
