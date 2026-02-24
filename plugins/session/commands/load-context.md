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
- ✅ **Context-efficient** - Uses agent to generate compact summaries, preserving main thread context
- ✅ **Human-reviewed** - You approve the summary before it's ingested

## Implementation

The command uses an **agent-based approach** to efficiently process conversation history and generate a compact summary. This keeps the main thread's context clean while still providing helpful continuity.

**Why use an agent?**
- Heavy history parsing happens in **separate context** (doesn't bloat main thread)
- Agent generates a **compact summary** instead of loading full message history
- Main thread only ingests the summary after **human review**
- Preserves context window and maintains quality

### Phase 1: Launch History Analysis Agent

1. **Parse command arguments first** (in main thread):
   - Detect numeric argument as `days` (e.g., `3`, `7`, `30`)
   - Detect `project:` prefix for project filtering (e.g., `project:ai-helpers`)
   - Detect `keyword:` prefix for keyword search (e.g., `keyword:loadbalancer`)
   - Support multiple filters in any order

2. **Spawn a general-purpose agent** using the Task tool:
   ```
   Launch agent to analyze conversation history with filters:
   - Days: [N] (default: 7)
   - Project: [project-name] (optional)
   - Keyword: [search-term] (optional)
   ```

3. **Agent's mission**:
   - Read `~/.claude/history.jsonl`
   - Parse and filter based on provided arguments
   - Generate a **compact summary** (target: 300-500 tokens)
   - Return summary to main thread

### Phase 2: Agent Reads and Filters History

**Agent performs these steps in its own context:**

1. **Locate and read history file**:
   - Path: `~/.claude/history.jsonl`
   - Each line is a JSON object: `{"display": "user message", "project": "/path/to/project", "timestamp": 1234567890, "sessionId": "uuid"}`

2. **Apply filters**:
   - **Time filter** (if days specified):
     - Calculate threshold: `current_time - (days * 24 * 60 * 60 * 1000)`
     - Only include messages after threshold
   - **Project filter** (if project: specified):
     - Match last component of project path (case-insensitive)
     - Example: `project:ai-helpers` matches `/Users/user/project/ai-helpers`
   - **Keyword filter** (if keyword: specified):
     - Search in `display` field (case-insensitive)
     - Partial matching (e.g., `keyword:load` matches "loadbalancer", "loading")

3. **Organize filtered messages**:
   - Group by project path
   - Group by sessionId to understand conversation threads
   - Maintain chronological order

### Phase 3: Agent Generates Compact Summary

**The agent creates a HIGH-LEVEL summary** (NOT full message content):

**Target length**: 300-500 tokens maximum

**Summary structure**:

```
📊 Analysis of [N] messages from last [X] days

**Projects** (by activity):
- ai-helpers: 23 messages
  Topics: JIRA automation, plugin development, slash commands
- cloud-provider-aws: 15 messages
  Topics: NLB debugging, client IP preservation, target group attributes
- cluster-capi-operator: 12 messages
  Topics: E2E tests, label synchronization, MAPI generation

**Key Technical Areas**:
- AWS infrastructure (load balancers, IAM, networking)
- Kubernetes controllers and CRDs
- Testing (E2E with Ginkgo, unit tests)
- CI/CD (Docker builds, Quay registry)

**Recent Focus**:
- Debugging AWS NLB hairpin connection issues
- Writing E2E tests for annotation synchronization
- Building and pushing container images to Quay
```

**What NOT to include**:
- ❌ Full message text
- ❌ Detailed conversation history
- ❌ Specific file paths or code snippets
- ❌ Complete chronological narratives

**What TO include**:
- ✅ Project names and message counts
- ✅ High-level topic keywords
- ✅ Technical themes and patterns
- ✅ Recent focus areas

### Phase 4: Present Summary for Human Review

**After agent completes**, present the summary to the user:

```
📚 I've analyzed your conversation history from the last 7 days.

Here's a high-level summary:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Agent's compact summary displayed here]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Context Impact**:
- This summary is approximately [X] tokens
- Main thread context remains clean
- You can refine filters if needed

Would you like me to internalize this context?

Options:
- **yes** - I'll remember this high-level overview
- **no** - Discard summary, no context added
- **refine** - Adjust filters (e.g., "just ai-helpers project")
```

### Phase 5: User Reviews and Decides

**User responses:**

1. **User says "yes"**:
   - Main thread internalizes the compact summary
   - Can reference general topics and projects
   - Context window preserved

2. **User says "no"**:
   - Discard summary entirely
   - No context added to main thread
   - User maintains full control

3. **User requests refinement**:
   - User says "refine" or describes desired filter (e.g., "just show ai-helpers", "just ai-helpers project")
   - Claude presents available filter options based on the current summary:
     - Project filters from discovered projects
     - Time range suggestions
     - Keyword suggestions based on topics
   - User selects desired refinement
   - Re-run agent with updated filters
   - Present new refined summary for review
   - User can continue refining or approve/reject

### Phase 6: Internalize Summary (If Approved)

**If user approves:**

1. **Main thread context**:
   - Has high-level overview of recent work
   - Knows which projects are active
   - Understands general technical themes
   - Does NOT have full message history

2. **Answer follow-up questions**:
   - User: "What have I been working on with AWS?"
   - Claude: "Based on the summary, you've been working on NLB debugging, client IP preservation, and target group attributes in the cloud-provider-aws project."
   - Can reference general topics from summary
   - Cannot quote specific past messages (summary only)

3. **Benefits maintained**:
   - ✅ Context continuity across sessions
   - ✅ Project awareness
   - ✅ No context bloat
   - ✅ User control preserved

## Return Value

**Terminal output**:
- Compact summary generated by agent (300-500 tokens)
- Context impact assessment (token count)
- User approval prompt

**Internal state** (after user approval):
- High-level overview of recent work
- Project names and activity levels
- General technical themes
- Does NOT contain full message history

## Examples

### Example 1: Load default 7 days of history

```
/session:load-context
```

**Output:**
```
📚 I've analyzed your conversation history from the last 7 days.

Here's a high-level summary:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Analysis of 45 messages from last 7 days

**Projects** (by activity):
- ai-helpers: 23 messages
  Topics: JIRA automation, plugin development, slash commands
- cloud-provider-aws: 15 messages
  Topics: NLB debugging, client IP preservation, AWS networking
- cluster-capi-operator: 7 messages
  Topics: E2E tests, label synchronization

**Key Technical Areas**:
- AWS infrastructure (load balancers, target groups)
- Kubernetes controllers and CRDs
- Testing frameworks (Ginkgo, E2E)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Context Impact**:
- This summary is approximately 420 tokens
- Main thread context remains clean
- You can refine filters if needed

Would you like me to internalize this context?

Options:
- **yes** - I'll remember this high-level overview
- **no** - Discard summary, no context added
- **refine** - Adjust filters (e.g., "just ai-helpers project")
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
📚 I've analyzed conversation history for project: ai-helpers

Here's a high-level summary:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Analysis of 45 messages (ai-helpers project only)

**Topics Covered**:
- JIRA automation and integration
- Claude Code plugin development
- Slash command creation
- Marketplace registration
- Command documentation (man page format)

**Key Technical Areas**:
- Claude Code plugin architecture
- JIRA API integration
- Markdown frontmatter and formatting

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Context Impact**: ~380 tokens

Would you like me to internalize this context? (yes/no/refine)
```

### Example 5: Filter by keyword

```
/session:load-context keyword:loadbalancer
```

Searches all history for conversations containing "loadbalancer". Useful for finding specific technical discussions.

**Output:**
```
📚 I've analyzed conversations matching keyword: loadbalancer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Analysis of 12 messages (keyword: loadbalancer)

**Projects Involved**:
- cloud-provider-aws: 9 messages
- openshift-docs: 3 messages

**Topics**:
- AWS NLB target group configuration
- Client IP preservation settings
- Load balancer annotation syntax
- Hairpin connection debugging

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Context Impact**: ~280 tokens

Would you like me to internalize this context? (yes/no/refine)
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

### Context Management Philosophy

**The key principle**: Let the agent do the heavy lifting, keep your main thread clean.

- ✅ **Agent processes** large history files
- ✅ **You review** compact summaries before accepting
- ✅ **Main thread** only gets high-level overview
- ✅ **Quality preserved** by avoiding context bloat

### Daily Workflow

**Start of day:**
```bash
/session:load-context 3  # Agent analyzes last 3 days, presents summary
```

Review the summary, then choose:
- `yes` - Internalize the compact overview
- `no` - Skip if you don't need context today
- `refine` - Narrow down to specific project

**End of day (optional):**
```bash
/session:save-session [description]  # Save structured notes if needed
```

### Weekly Workflow

**Monday morning:**
```bash
/session:load-context 7  # Agent summarizes last week
```

Review summary to understand what happened over the weekend or last week.

### After Extended Break

**After vacation/weekend:**
```bash
/session:load-context 14  # Agent summarizes 2 weeks
```

The agent will extract high-level themes, not dump 2 weeks of full messages.

### Project-Specific Work

**When focusing on one project:**
```bash
/session:load-context project:ai-helpers  # Only ai-helpers context
```

**When debugging specific issue:**
```bash
/session:load-context 3 keyword:error  # Recent error discussions
```

### Managing Context Budget

**Good practice:**
1. Start with narrow filters (3 days, specific project)
2. Review summary before accepting
3. If summary is too broad, refine filters
4. Only accept summaries that are genuinely useful

**Avoid:**
- ❌ Loading 30+ days without project filter (too broad)
- ❌ Accepting summaries you don't actually need
- ❌ Re-loading context multiple times in same session

## Technical Details

### Agent-Based Architecture

**Why use an agent?**

Traditional approach (loading full history into main thread):
```
Main Thread: Read 1000 messages → Parse → Filter → Load all → CONTEXT BLOAT
```

Agent-based approach (current implementation):
```
Main Thread: Parse args → Launch agent
  ↓
Agent Context: Read 1000 messages → Parse → Filter → Summarize → Return 400 tokens
  ↓
Main Thread: Review summary → User approves → Internalize 400 tokens only
```

**Benefits:**
- Main thread context stays under 500 tokens (vs. potentially 10,000+)
- Agent context is discarded after summary generation
- User maintains control via approval step
- Quality preserved by avoiding context exhaustion

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

### Summary Generation Guidelines (for Agent)

**Target token count**: 300-500 tokens

**What to extract:**
- Project names and message counts
- High-level topic keywords (3-5 per project)
- Technical themes (languages, frameworks, tools)
- Recent focus areas (what's being worked on now)

**What to exclude:**
- Full message text or quotes
- Specific file paths or code snippets
- Detailed chronological narratives
- Implementation details

**Quality check:**
- Can a human read the summary in 30 seconds?
- Does it capture the "essence" without details?
- Would it help Claude understand context without full history?

### Privacy Note

- This command only reads from your local `~/.claude/history.jsonl` file
- No data is sent anywhere
- All processing happens locally (including agent execution)
- Only you and Claude see this history

## Differences from /session:save-session

| Feature | `/session:save-session` | `/session:load-context` |
|---------|------------------------|-------------------------|
| **Purpose** | Save current conversation | Load past conversations |
| **Manual?** | Yes - you decide when | Yes - you approve summary |
| **Format** | Structured markdown | Agent-generated summary |
| **Content** | Current session only | Multiple past sessions (summarized) |
| **Use case** | Document important work | Daily continuity via compact overview |
| **Output** | Creates new file | Generates in-memory summary (300-500 tokens) |
| **Context impact** | None (writes file) | Minimal (~400 tokens after approval) |
| **Agent usage** | No | Yes (parsing in separate context) |

**Recommended usage**: Use both together
- `/session:load-context` at start of day (compact context recovery)
- `/session:save-session` for important milestones (structured docs)

**Complementary workflows:**
- `/session:load-context` gives you high-level awareness of recent work
- `/session:save-session` creates permanent documentation of important sessions
- Together they provide both continuity and documentation

## See Also

- `/session:save-session` - Save current conversation to structured markdown file
- Claude Code's native history file: `~/.claude/history.jsonl`
