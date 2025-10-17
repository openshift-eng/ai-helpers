# Changelog

## 2025-10-16 - Regex Pattern Support, Resource List Display, and Glog Severity Detection

### Changes

1. **Regex Pattern Support** (parse_all_logs.py)
2. **Show Searched Resources in HTML Report** (generate_html_report.py)
3. **Glog Severity Level Detection** (parse_all_logs.py)

---

## 2025-10-16 - Glog Severity Level Detection

### Problem
Pod logs were all marked as "info" level, even when they contained errors or warnings. Glog format logs (used by many Kubernetes components) have severity indicators at the start of each line:
- `E` = Error
- `W` = Warning
- `I` = Info
- `F` = Fatal

Example error line:
```
E0910 11:43:41.153414       1 service_account_controller.go:368] "Unhandled Error" err="e2e-test-..."
```

This made it impossible to filter pod logs by severity level in the HTML report.

### Solution
Updated `parse_pod_logs()` function to:
1. Detect glog format at the start of each line
2. Extract the severity character (E, W, I, F) and timestamp components
3. Map severity to our level scheme:
   - E (Error) and F (Fatal) → `error`
   - W (Warning) → `warn`
   - I (Info) → `info`
4. Parse glog timestamp (MMDD HH:MM:SS.microseconds) into ISO format
5. Infer year (2025) since glog doesn't include it
6. Default to `info` for non-glog formatted lines

### Changes Made

#### Code Changes
- **parse_all_logs.py**:
  - Updated glog pattern regex: `^([EIWF])(\d{2})(\d{2})\s+(\d{2}:\d{2}:\d{2}\.\d+)`
  - Capture severity, month, day, and time components
  - Construct ISO 8601 timestamp with inferred year
  - Extract severity character and map to level
  - Keep default "info" for non-glog lines

### Testing

Verified with real Prow job data:
- Pattern: `e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx`
- Pod log results:
  - 8 error-level entries (glog E and F lines)
  - 0 warning-level entries
  - 155 info-level entries
- Sample error correctly detected: `E0910 11:43:41.153414       1 service_account_controller.go:368] "Unhandled Error" err="e2e-test-...`
- **Timestamp parsing**: All 8 error entries now have timestamps (previously showed "No timestamp")
  - Example: `E0910 11:37:35.363241` → `2025-09-10T11:37:35.363241Z`

### Benefits
- Users can now filter pod logs by severity in the HTML report
- Error and warning pod logs are highlighted with red/yellow badges
- Timeline shows error events in red for quick identification
- More accurate representation of pod log severity

---

## 2025-10-16 - Regex Pattern Support

### Problem
The original `parse_all_logs.py` script used simple substring matching, which meant searching for multiple resources required:
1. Running the script multiple times (once per resource)
2. Manually merging the JSON outputs
3. More time and complexity

For example, searching for `e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx` would look for that literal string (including the pipe character), finding zero results.

### Solution
Updated `parse_all_logs.py` to support **regex pattern matching**:

1. **Regex compilation**: Compile the resource pattern as a regex for efficient matching
2. **Smart detection**: Use fast substring search for simple patterns, regex for complex patterns
3. **Flexible matching**: Match pattern against both `namespace` and `name` fields in audit logs
4. **Performance optimized**: Only use regex when needed (patterns containing `|`, `.*`, `[`, etc.)

### Changes Made

#### Code Changes
- **parse_all_logs.py**:
  - Added regex compilation for resource patterns
  - Smart detection of regex vs. simple string patterns
  - Updated both `parse_audit_logs()` and `parse_pod_logs()` functions
  - Added usage documentation for regex patterns

#### Documentation Changes
- **SKILL.md**:
  - Updated "Input Format" section with regex pattern examples
  - Added "Resource Pattern Parameter" section in Step 6
  - Updated "Filter matches" explanation to reflect regex matching
  - Added Example 4 showing multi-resource search using regex
  - Updated Tips and Important Notes sections

### Usage Examples

**Before** (required multiple runs + manual merge):
```bash
# Run 1: First resource
python3 parse_all_logs.py "e2e-test-project-api-pkjxf" ... > output1.json

# Run 2: Second resource
python3 parse_all_logs.py "e2e-test-project-api-7zdxx" ... > output2.json

# Manually merge JSON files with Python
```

**After** (single run):
```bash
# Single run for multiple resources
python3 parse_all_logs.py "e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx" ... > output.json
```

### Pattern Support

The script now supports all standard regex patterns:

- **Multiple resources**: `resource1|resource2|resource3`
- **Wildcards**: `e2e-test-project-api-.*`
- **Character classes**: `resource-[abc]-name`
- **Optional characters**: `resource-name-?`
- **Simple substrings**: `my-namespace` (backward compatible)

### Performance

- Simple patterns (no regex chars) use fast substring search
- Regex patterns are compiled once and reused
- No performance degradation for simple searches
- Minimal overhead for regex searches

### Testing

Verified with real Prow job data:
- Pattern: `e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx`
- Result: 1,047 entries (884 audit + 163 pod logs)
- Matches manual merge of individual searches: ✓

### Backward Compatibility

All existing simple substring patterns continue to work:
- `my-namespace` → still uses fast substring search
- `pod-name` → still uses fast substring search
- No breaking changes to existing functionality

---

## 2025-10-16 - Show Searched Resources in HTML Report

### Problem
The HTML report only displayed the single `resource_name` parameter in the "Resources:" section. When searching for multiple resources using a regex pattern like `e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx`, the header would only show:
```
Resources: e2e-test-project-api-pkjxf
```

This was misleading because the report actually contained data for both resources.

### Solution
Updated `generate_html_report.py` to:
1. Accept a `resource_pattern` parameter (the same pattern used in parse script)
2. Parse the pattern to extract the searched resources (split on `|` for regex patterns)
3. Display the searched resources as a comma-separated list
4. Use only the first resource name for the HTML filename (to avoid special chars like `|`)

### Changes Made

#### Code Changes
- **generate_html_report.py**:
  - Renamed parameter from `resource_name` to `resource_pattern`
  - Parse pattern by splitting on `|` to extract individual resources
  - Sort and display parsed resources in header
  - Sanitize filename by using only first resource and removing regex special chars

#### Skill Documentation
- **SKILL.md**:
  - Updated Step 7 to specify passing `resource_pattern` instead of `resource_name`
  - Added note that the pattern should be the same as used in parse script
  - Updated Example 4 to show the expected output

#### Display Examples

**Before**:
```
Resources: e2e-test-project-api-pkjxf
```

**After (searching with pattern "e2e-test-project-api-pkjxf|e2e-test-project-api-7zdxx")**:
```
Resources: e2e-test-project-api-7zdxx, e2e-test-project-api-pkjxf
```

### Benefits
- Users see **only** what they searched for, not all related resources
- Clear indication of which resources were analyzed
- More accurate and less cluttered
- Filename remains safe (no special characters)
