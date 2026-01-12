---
name: Gerrit Review
description: Fetch and analyze review comments from Gerrit changes to help address code review feedback systematically
---

# Gerrit Review

This skill enables AI agents to fetch, parse, and understand review comments from Gerrit code review systems. It bridges the gap where AI agents cannot directly read Gerrit URLs, providing structured comment data that can be used to address reviewer feedback.

## When to Use This Skill

Use this skill when the user wants to:
- Fetch review comments from a Gerrit change URL
- Understand what feedback reviewers have left on a patch
- Address unresolved comments systematically
- Get a summary of all comments on a Gerrit change
- Filter comments by patchset or resolution status

## Prerequisites

Before starting, verify these prerequisites:

1. **Python 3 Installation**
   - Check if installed: `which python3`
   - Python 3.6+ is required for f-string support and type hints

2. **Network Access**
   - The script uses Gerrit's public REST API
   - No authentication required for public Gerrit instances (e.g., review.opendev.org)
   - For private Gerrit instances, authentication may be required (not yet supported)

3. **Skill Script Location**
   - Script path: `plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py`
   - Ensure the script is executable or run with `python3`

## Input Format

The user will provide:

1. **Gerrit Change URL** - URL to a Gerrit change in any of these formats:
   - New-style: `https://review.example.com/c/org/project/+/123456`
   - With patchset: `https://review.example.com/c/org/project/+/123456/3`
   - Old-style: `https://review.example.com/#/c/123456/`
   - Direct: `https://review.example.com/123456`

2. **Optional filters**:
   - Specific patchset number to filter comments
   - Whether to show only unresolved comments

## Implementation Steps

### Step 1: Validate URL and Extract Components

1. **Run the fetch script**
   ```bash
   python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py "<gerrit_url>"
   ```

2. **The script automatically:**
   - Parses the Gerrit URL to extract base URL, project, and change number
   - Handles various URL formats (new-style, old-style, direct)
   - Constructs proper API endpoints

### Step 2: Fetch Comments

1. **Basic usage** (all comments):
   ```bash
   python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
     "https://review.example.com/c/org/project/+/123456"
   ```

2. **Filter by patchset**:
   ```bash
   python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
     -p 3 \
     "https://review.example.com/c/org/project/+/123456"
   ```

3. **Show only unresolved comments**:
   ```bash
   python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
     --unresolved-only \
     "https://review.example.com/c/org/project/+/123456"
   ```

4. **Get raw JSON output** (for programmatic use):
   ```bash
   python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
     --json \
     "https://review.example.com/c/org/project/+/123456"
   ```

### Step 3: Parse Output

The script outputs a structured text format:

```
======================================================================
GERRIT CHANGE: 123456
Project: org/project
Branch: main
Status: NEW
Subject: Example change subject
Owner: John Doe
======================================================================

Total comments: 15
  - Unresolved: 3
  - Resolved: 12
  - Patchsets with comments: 1, 2, 3

======================================================================
COMMENTS
======================================================================

### PATCHSET-LEVEL COMMENTS ###

---
Author: Jane Smith (UNRESOLVED)
Location: [Patchset 3 - General Comment]
Patchset: 3

Please add unit tests for the new functionality.

### FILE: sushy/resources/updateservice/updateservice.py ###

---
Author: Bob Johnson
Location: [sushy/resources/updateservice/updateservice.py:45]
Patchset: 3

Consider using a constant for this magic string.

======================================================================
ACTION ITEMS
======================================================================

3 unresolved comment(s) require attention.
Review each unresolved comment above and address the feedback.
```

### Step 4: Analyze and Categorize Comments

When processing comments for the `address-gerrit-reviews` command:

1. **Categorize by priority**:
   - **BLOCKING**: Critical issues (security, bugs, breaking changes)
   - **CHANGE_REQUEST**: Code improvements, refactoring
   - **QUESTION**: Clarification requests
   - **SUGGESTION**: Optional improvements, nits

2. **Group by file**: Comments on the same file should be addressed together

3. **Focus on unresolved**: Resolved comments typically don't need action

## Output Format

### Text Output (default)

The default text output is optimized for AI consumption:
- Clear headers and separators
- Comment metadata (author, location, patchset, resolution status)
- Organized by file for easy navigation
- Summary of action items at the end

### JSON Output (--json flag)

```json
{
  "change": {
    "_number": 123456,
    "project": "org/project",
    "branch": "master",
    "subject": "Add support for UpdateService actions",
    "status": "NEW",
    "owner": {
      "name": "John Doe",
      "_account_id": 12345
    }
  },
  "comments": {
    "/PATCHSET_LEVEL": [
      {
        "author": {"name": "Jane Smith"},
        "message": "Please add unit tests",
        "patch_set": 3,
        "unresolved": true
      }
    ],
    "sushy/resources/updateservice.py": [
      {
        "author": {"name": "Bob Johnson"},
        "message": "Consider using a constant",
        "line": 45,
        "patch_set": 3,
        "unresolved": false
      }
    ]
  }
}
```

## Error Handling

Handle these error scenarios gracefully:

1. **Invalid URL format**
   - Error: "Could not parse Gerrit URL: {url}"
   - Provide examples of valid URL formats

2. **Change not found (404)**
   - Error: "Change not found: {url}"
   - Verify the change number exists and is accessible

3. **Network error**
   - Error: "Network error: {reason}"
   - Check network connectivity
   - Verify Gerrit instance is accessible

4. **HTTP errors**
   - Error: "HTTP error {code}: {reason}"
   - May indicate authentication required for private instances

5. **No comments found**
   - Display: "No comments found on this change."
   - Or for filtered: "No comments found for patchset {N}."

## Supported Gerrit Instances

The script works with any Gerrit instance that has REST API enabled:

| Instance | URL Pattern | Notes |
|----------|-------------|-------|
| OpenDev (OpenStack) | `review.opendev.org` | Public, no auth required |
| Gerrit Code Review | `gerrit-review.googlesource.com` | Public projects |
| Android | `android-review.googlesource.com` | Public projects |
| Custom | Any Gerrit server | May require auth |

## Examples

### Example 1: Fetch all comments from a Gerrit change

```bash
python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
  "https://review.example.com/c/org/project/+/123456"
```

### Example 2: Get only unresolved comments from latest patchset

```bash
python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
  --unresolved-only \
  "https://review.example.com/c/org/project/+/123456/5"
```

### Example 3: Get JSON for programmatic processing

```bash
python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
  --json \
  "https://review.example.com/c/org/project/+/123456" \
  | jq '.comments | keys'
```

## Tips

- **Patchset filtering**: Use `-p N` or include patchset in URL to focus on specific patchset
- **Unresolved focus**: Use `--unresolved-only` when addressing review feedback
- **JSON for automation**: Use `--json` when integrating with other tools
- **URL flexibility**: The script handles various Gerrit URL formats automatically
- **No authentication**: Works out-of-the-box for public Gerrit instances

## Integration with address-reviews Command

This skill powers the `/utils:address-reviews` slash command when a Gerrit URL is detected:

1. The command auto-detects Gerrit from the URL pattern
2. Uses this script to fetch comments
3. Parses and categorizes the output
4. Systematically addresses each comment
5. Handles Gerrit-specific workflows (amend commits, `git review`)

See the `address-reviews.md` command for the full implementation.

## Limitations

1. **Authentication**: Currently only supports public Gerrit instances
2. **Inline diffs**: Does not fetch the actual code diff context
3. **Comment threads**: Shows flat list, doesn't reconstruct reply threads
4. **Draft comments**: Only shows published comments

## Future Enhancements

- Add authentication support for private Gerrit instances
- Fetch inline diff context for better code understanding
- Reconstruct comment reply threads
- Support for draft comments (authenticated users)
- Integration with `git review` for pushing amended changes

