---
name: jira-writer
description: Update and modify JIRA issues on Red Hat Issue Tracker. Use this skill to push release notes, update custom fields (release note content, status), manage labels (add/remove), and modify issue properties. This skill performs write operations and will prompt for user approval before making changes. Requires jira and ratelimit Python packages. Only use when explicitly asked to update or modify JIRA issues.
author: Gabriel McGoldrick (gmcgoldr@redhat.com)
---

# JIRA Writer Skill

This skill provides write access to JIRA issues on Red Hat Issue Tracker (https://redhat.atlassian.net).

**WARNING: This skill modifies JIRA issues. Always verify the changes before confirming.**

## Capabilities

- **Push Release Notes**: Update the release note custom field with generated content
- **Update Status**: Set release note status to 'Proposed' or other values
- **Update Custom Fields**: Modify any custom field on a JIRA issue
- **Label Management**: Add or remove labels on JIRA issues
- **Batch Updates**: Update multiple issues with the same content

## Usage

The skill uses a Python script that connects to JIRA using an authentication token.

### Environment Variables Required

Set in `~/.env` (global) or `.env` in the project root (local override). See docs-tools README for setup:

```bash
JIRA_API_TOKEN=your-jira-api-token
JIRA_EMAIL=you@redhat.com           # required for Atlassian Cloud
JIRA_URL=https://redhat.atlassian.net  # optional, defaults to redhat.atlassian.net
```

The script loads `.env` files automatically — do **not** prepend `source ~/.env` to bash commands.

### Examples

**Push a release note:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue INFERENG-5233 --release-note "Fixed issue with..."
```

**Update release note status:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue INFERENG-5233 --status Proposed
```

**Update custom field:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue INFERENG-5233 --custom-field customfield_10783 --value "Release note content"
```

**Batch update multiple issues:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue INFERENG-5233 --issue INFERENG-5049 --status Approved
```

**Read release note from file:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue INFERENG-5233 --release-note-file /path/to/note.txt
```

**Add a label:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue PROJ-123 --labels-add docs-in-progress
```

**Swap labels (remove + add in one API call):**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue PROJ-123 --labels-remove docs-ready --labels-add docs-in-progress
```

**Batch label update:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_writer.py --issue PROJ-123 --issue PROJ-456 --labels-add docs-complete
```

## Output Format

The script outputs JSON with the following structure:

```json
{
  "success": true,
  "issue_key": "INFERENG-5233",
  "updated_fields": {
    "customfield_10783": "Release note content",
    "customfield_10807": "Proposed"
  },
  "url": "https://redhat.atlassian.net/browse/INFERENG-5233"
}
```

## Custom Fields

Common custom fields used:
- `customfield_10783`: Release Note Text
- `customfield_10807`: Release Note Status (values: Proposed, Approved, Rejected)
- `customfield_10785`: Release Note Type

## Rate Limiting

The skill respects JIRA API rate limits (2 calls per 5 seconds) to avoid overwhelming the server.

## Security

- Requires user approval before making changes (no allowed-tools restriction)
- Token stored in environment variable (not in code)
- All changes are logged with details

## Common Use Cases

1. **Publish release notes**: Push generated release note content to JIRA
2. **Update status**: Mark release notes as Proposed/Approved after review
3. **Batch updates**: Apply same status to multiple issues
4. **Field updates**: Modify any custom field on JIRA issues
5. **Label management**: Add or remove labels for workflow automation

## Best Practices

- Always review the content before pushing to JIRA
- Test with non-production issues first
- Verify the issue key is correct
- Back up existing content if overwriting
- Use descriptive commit messages when used with git workflows
