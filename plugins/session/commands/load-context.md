---
description: Load and learn from recent conversation history to maintain context across sessions
argument-hint: [days] [project:name] [keyword:term]
---

## Name
session:load-context

## Synopsis

```
/session:load-context
/session:load-context [days]
/session:load-context project:<project-name>
/session:load-context keyword:<search-term>
/session:load-context [days] project:<project-name>
/session:load-context [days] keyword:<search-term>
/session:load-context project:<project-name> keyword:<search-term>
```

## Description

The `session:load-context` command loads and analyzes recent conversation history from Claude Code's history file (`~/.claude/history.jsonl`), allowing Claude to understand previous discussions and maintain continuity across multiple sessions.

This command solves the problem of Claude "forgetting" context after you close and reopen Claude Code. By reading recent conversation history, Claude can:
- Recall previous questions and answers
- Understand ongoing work and decisions
- Continue discussions without repetition
- Build upon earlier technical context
- Remember which files you've been working on
- Know what problems you've already solved

**Key Benefits:**
- ✅ **Automatic context recovery** - No need to manually save sessions
- ✅ **Cross-session continuity** - Seamlessly resume work after closing Claude Code
- ✅ **Project awareness** - Understands your recent work across all projects
- ✅ **No repetition** - Avoid re-explaining the same concepts every day
- ✅ **Smart filtering** - Filter by time, project, or keywords
- ✅ **Flexible search** - Combine multiple filters for precise context loading

## Implementation

The command follows a five-phase process:

### Phase 1: Read Claude Code History File

1. **Locate history file**:
   - Path: `~/.claude/history.jsonl`
   - This file contains all conversation history in JSON Lines format

2. **Read and parse the file**:
   ```bash
   cat ~/.claude/history.jsonl
   ```
   - Each line is a JSON object representing one user message
   - Format: `{"display": "user message", "project": "/path/to/project", "timestamp": 1234567890, "sessionId": "uuid"}`

3. **Determine time range**:
   - Default: Last 7 days if no argument provided
   - Custom: Use the `days` argument (e.g., 3 for last 3 days)
   - Calculate timestamp threshold: `current_time - (days * 24 * 60 * 60 * 1000)`

### Phase 2: Parse Filter Arguments

1. **Parse command arguments**:
   - Detect numeric argument as `days` (e.g., `3`, `7`, `30`)
   - Detect `project:` prefix for project filtering (e.g., `project:ai-helpers`)
   - Detect `keyword:` prefix for keyword search (e.g., `keyword:loadbalancer`)
   - Support multiple filters in any order

2. **Extract filter values**:
   ```bash
   # Examples of argument parsing:
   # "3" → days=3
   # "project:ai-helpers" → project="ai-helpers"
   # "keyword:aws" → keyword="aws"
   # "7 project:ai-helpers" → days=7, project="ai-helpers"
   # "keyword:loadbalancer project:huali-test" → keyword="loadbalancer", project="huali-test"
   ```

### Phase 3: Filter and Extract Relevant Conversations

1. **Filter by timestamp** (if days specified):
   - Only include messages within the specified time range
   - Parse `timestamp` field (milliseconds since epoch)
   - Default: 7 days if no time filter specified
   - Filter out messages older than the threshold

2. **Filter by project** (if project: specified):
   - Extract project name from `project` path field
   - Match against specified project name
   - Case-insensitive matching
   - Example: `project:ai-helpers` matches `/Users/user/project/ai-helpers`

3. **Filter by keyword** (if keyword: specified):
   - Search in `display` field (user message text)
   - Case-insensitive search
   - Match partial words (e.g., `keyword:load` matches "loadbalancer", "loading")
   - Boolean OR if multiple keywords

4. **Group and organize**:
   - Group filtered messages by `project` path
   - Group by `sessionId` to reconstruct conversation threads
   - Maintain chronological order

5. **Extract message content**:
   - Parse `display` field for the user's question/message
   - Handle pasted content references if present
   - Clean up formatting (remove extra whitespace, newlines)

### Phase 4: Organize and Summarize Conversations

1. **Categorize by project**:
   - Organize messages by the project they relate to
   - Identify which project(s) have the most activity
   - Note project paths for context

2. **Identify key topics**:
   - Extract technical topics from messages (e.g., "build image", "push to quay", "write tests")
   - Group related questions together
   - Identify recurring themes or problems

3. **Build chronological narrative**:
   - Create a timeline of your work
   - Show progression from earlier to recent questions
   - Highlight unresolved questions or ongoing work

### Phase 5: Present Context Summary

Display a comprehensive summary in this format:

```
📚 Loaded conversation history from the last [N] days

**Time range**: [Start Date] to [End Date]
**Total messages**: [X] messages across [Y] sessions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂 **Projects you've been working on:**

1. /path/to/project1 ([X] messages)
2. /path/to/project2 ([Y] messages)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 **Key topics and questions:**

**Project: machine-api-provider-aws**
- Building and pushing Docker images to Quay
- Testing synchronized conditions in controllers
- Image size differences between local and remote

**Project: cluster-capi-operator**
- Writing E2E tests for label/annotation synchronization
- Verifying MAPI generation and synchronized time changes
- Code refactoring to reduce duplication

**Project: cloud-provider-aws**
- Load balancer issues with AWS
- Client IP preservation for NLB
- Hairpin connection debugging

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **Recent technical context:**

- You've been working on Kubernetes controllers across multiple projects
- Focus on AWS infrastructure (load balancers, images, IAM)
- Writing E2E tests with Ginkgo framework
- Docker image building and registry operations
- Debugging AWS NLB target group attributes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Context loaded! I now understand your recent work across these projects.

**How can I help you today?**
```

### Phase 6: Internalize Context

After displaying the summary:

1. **Store context mentally**:
   - Claude has now read all the conversation history
   - Can reference specific past questions
   - Understands the technical background

2. **Be ready to answer**:
   - If user asks about previous work, recall details
   - Don't ask for information that was already discussed
   - Build on previous conversations naturally

3. **Handle follow-up questions**:
   - User might ask: "What did we discuss about X?"
   - Claude can reference specific past messages
   - Provide continuity without repetition

## Return Value

**Terminal output**: Comprehensive summary of loaded conversations (see Phase 4 format above)

**Internal state**: Claude has full context from recent history

## Examples

### Example 1: Load default 7 days of history

```
/session:load-context
```

**Output:**
```
📚 Loaded conversation history from the last 7 days

**Time range**: Nov 21, 2025 to Nov 28, 2025
**Total messages**: 45 messages across 8 sessions

[... detailed summary as shown in Phase 4 ...]
```

### Example 2: Load last 3 days only

```
/session:load-context 3
```

Focuses on very recent work - good for daily continuity.

### Example 3: Load last 30 days for comprehensive context

```
/session:load-context 30
```

Useful when returning to a project after a break.

### Example 4: Filter by project only

```
/session:load-context project:ai-helpers
```

Loads all conversations related to the `ai-helpers` project (no time limit). Useful when you want to focus on a specific project regardless of when the conversations happened.

**Output:**
```
📚 Loaded conversation history for project: ai-helpers

**Total messages**: 45 messages across 6 sessions
**Projects**: ai-helpers only

[Shows only ai-helpers related conversations...]
```

### Example 5: Filter by keyword

```
/session:load-context keyword:loadbalancer
```

Searches all history for conversations containing "loadbalancer". Useful for finding specific technical discussions.

**Output:**
```
📚 Loaded conversations matching keyword: loadbalancer

**Total messages**: 12 messages across 3 sessions
**Keyword matches**: loadbalancer (case-insensitive)

[Shows only messages mentioning loadbalancer...]
```

### Example 6: Combine filters - Time + Project

```
/session:load-context 7 project:ai-helpers
```

Loads last 7 days of conversations, but only from the `ai-helpers` project.

**Use case:** Focus on recent work in a specific project while filtering out noise from other projects.

### Example 7: Combine filters - Time + Keyword

```
/session:load-context 3 keyword:aws
```

Loads last 3 days, but only messages containing "aws".

**Use case:** "What did I discuss about AWS in the last 3 days?"

### Example 8: Combine filters - Project + Keyword

```
/session:load-context project:huali-test keyword:nlb
```

Loads all conversations from `huali-test` project that mention "nlb".

**Use case:** "Show me all NLB-related discussions in my test project."

### Example 9: Triple filter - Time + Project + Keyword

```
/session:load-context 7 project:cloud-provider-aws keyword:security
```

Loads last 7 days from `cloud-provider-aws` project, only messages mentioning "security".

**Use case:** Very specific context - recent security-related work in a specific project.

### Example 10: Daily workflow

**Monday morning:**
```
/session:load-context 3
```
Loads last 3 days across all projects.

**Work on tasks...**

**When switching to specific project:**
```
/session:load-context project:ai-helpers
```
Focus only on ai-helpers context.

**When debugging specific issue:**
```
/session:load-context 7 keyword:error
```
Find recent error discussions.

### Example 11: After a vacation

**After 2 weeks off:**
```
/session:load-context 21
```
Loads the last 3 weeks to catch up on what happened.

## Arguments

All arguments are optional and can be combined in any order.

### **days** (numeric, optional)
- Number of days to look back in conversation history
- Default: `7` (last week) if no filters specified, or unlimited if project/keyword specified
- Valid range: `1` to `90`
- Examples:
  - `1` - just today
  - `3` - last 3 days (recommended for daily use)
  - `7` - last week (default)
  - `14` - last 2 weeks
  - `30` - last month

### **project:<name>** (optional)
- Filter conversations by project name
- Matches the last component of the project path
- Case-insensitive matching
- Examples:
  - `project:ai-helpers` - matches `/Users/user/project/ai-helpers`
  - `project:huali-test` - matches `/Users/user/project/huali-test`
  - `project:cloud-provider-aws` - matches any path ending in `cloud-provider-aws`

### **keyword:<term>** (optional)
- Search for specific keywords in conversation messages
- Searches in the user's message text (`display` field)
- Case-insensitive search
- Partial matching (e.g., `keyword:load` matches "loadbalancer", "loading", "upload")
- Examples:
  - `keyword:aws` - finds all AWS-related discussions
  - `keyword:loadbalancer` - finds load balancer discussions
  - `keyword:error` - finds error-related conversations
  - `keyword:nlb` - finds NLB-specific discussions

### **Combining Arguments**

Arguments can be combined in any order:

```bash
# Time + Project
/session:load-context 7 project:ai-helpers
/session:load-context project:ai-helpers 7        # Same as above

# Time + Keyword
/session:load-context 3 keyword:aws
/session:load-context keyword:aws 3              # Same as above

# Project + Keyword
/session:load-context project:huali-test keyword:nlb
/session:load-context keyword:nlb project:huali-test  # Same as above

# All three
/session:load-context 7 project:cloud-provider-aws keyword:security
```

**Filter behavior:**
- If **only days** specified: Load all conversations from that time period
- If **only project** specified: Load all conversations from that project (no time limit)
- If **only keyword** specified: Search all history for that keyword (no time limit)
- If **multiple filters**: Apply all filters (AND logic)

## Edge Cases and Error Handling

### No history file found

```
❌ Error: Could not find Claude Code history file at ~/.claude/history.jsonl

This might mean:
- You haven't had any conversations yet
- The history file location has changed
- File permissions issue

Try starting a new conversation first.
```

### No messages in time range

```
ℹ️  No conversation history found in the last [N] days.

You might want to:
- Try a longer time range: /session:load-context 14
- Check if you've been using Claude Code recently
```

### Very large history (>1000 messages)

```
⚠️  Found 1523 messages in the last [N] days. This is a lot of context.

Loading all messages might be overwhelming. Consider:
- Narrowing the time range (e.g., /session:load-context 3)
- Focusing on a specific project

Do you want to proceed? (yes/no)
```

If user says yes, load all. If no, suggest alternatives.

### Corrupted JSON lines

- Skip invalid JSON lines
- Log warning: "Skipped X invalid entries in history file"
- Continue processing valid entries

## Best Practices

### Daily Workflow

**Start of day:**
```bash
/session:load-context 3  # Load last 3 days
```

This gives you continuity without overload.

**End of day (optional):**
```bash
/session:save-session [description]  # Save structured notes if needed
```

### Weekly Workflow

**Monday morning:**
```bash
/session:load-context 7  # Load last week including Friday
```

### After Extended Break

**After vacation/weekend:**
```bash
/session:load-context 14  # Load 2 weeks to catch up
```

### Project-Specific Work

If working on multiple projects, the command automatically categorizes by project, so you can see which project has recent activity.

## Technical Details

### History File Format

Each line in `~/.claude/history.jsonl`:

```json
{
  "display": "User's message text",
  "pastedContents": {},
  "timestamp": 1762235844741,
  "project": "/Users/username/project/repo-name",
  "sessionId": "fb013359-809b-4b01-82e4-3a338a76aa57"
}
```

### Timestamp Calculation

```javascript
// Current time in milliseconds
const now = Date.now()

// Days ago in milliseconds
const daysAgo = days * 24 * 60 * 60 * 1000

// Threshold timestamp
const threshold = now - daysAgo

// Filter messages
messages.filter(msg => msg.timestamp >= threshold)
```

### Privacy Note

- This command only reads from your local `~/.claude/history.jsonl` file
- No data is sent anywhere
- All processing happens locally
- Only you and Claude see this history

## Differences from /session:save-session

| Feature | `/session:save-session` | `/session:load-context` |
|---------|------------------------|-------------------------|
| **Purpose** | Save current conversation | Load past conversations |
| **Manual?** | Yes - you decide when | Automatic reading |
| **Format** | Structured markdown | Parses JSONL history |
| **Content** | Current session only | Multiple past sessions |
| **Use case** | Document important work | Daily continuity |
| **Output** | Creates new file | Reads existing history |

**Recommended usage**: Use both together
- `/session:load-context` at start of day (automatic memory)
- `/session:save-session` for important milestones (structured docs)

## See Also

- `/session:save-session` - Save current conversation to structured markdown file
- Claude Code's native history file: `~/.claude/history.jsonl`
