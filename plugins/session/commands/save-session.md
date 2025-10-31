---
description: Save current conversation session to markdown file for future continuation
argument-hint: [-i] [description]
---

## Name
session:save-session

## Synopsis

```
/save-session
/save-session [description]
/save-session --incremental <description>
/save-session -i <description>
```

## Description

Saves the current conversation session to a comprehensive markdown file that enables seamless resumption of work after extended time intervals (days, weeks, or months).

**🚨 CRITICAL SECURITY REQUIREMENT 🚨**

**YOU MUST NEVER write sensitive information to session files. This is an absolute, non-negotiable requirement.**

Before writing ANY content to a session file, you MUST:
1. Scan ALL content for sensitive information
2. Redact ALL sensitive data (API keys, tokens, passwords, webhook URLs, usernames, etc.)
3. Verify redaction is complete
4. Only then write to file

**Failure to redact sensitive information is a critical security violation.**

This command addresses limitations of Claude Code's built-in session management by capturing:
- Complete conversation context and technical rationale
- Detailed file modification tracking with line numbers
- Key technical decisions and alternatives considered
- Commands executed during the session
- Clear resumption instructions
- **REDACTED sensitive information for security**

The generated session file is designed for engineers working across multiple projects with long gaps between sessions, providing all necessary context to continue work without losing momentum while maintaining security.

**Save Modes:**
- **Default mode**: Saves content from the beginning of the conversation to now
- **Incremental mode** (with `--incremental` or `-i` flag): Saves only content since the last session save, enabling multiple topic saves in one conversation

## Implementation

**⚠️ MANDATORY SECURITY PRINCIPLE ⚠️**

**BEFORE IMPLEMENTING ANY PHASE: You MUST commit to NEVER writing sensitive information to session files.**

This is not optional. This is not a suggestion. This is an absolute requirement.
- API keys → MUST be redacted
- Tokens → MUST be redacted
- Passwords → MUST be redacted
- Webhook URLs → MUST be redacted
- Private keys → MUST be redacted
- Usernames in paths → MUST be redacted
- ANY sensitive data → MUST be redacted

If you are uncertain whether something is sensitive: **REDACT IT**.
When in doubt: **ASK THE USER** before including it.

The command follows a six-phase process with intelligent session tracking and **mandatory sensitive information redaction**:

### Phase 0: Session Detection and Mode Selection

**Core Principle:** A session is considered "saved" if Claude has read or created a session file in the current conversation, regardless of how the user phrased their request.

**🚨 CRITICAL EXECUTION ORDER - MANDATORY 🚨**

**YOU MUST EXECUTE ALL 3 STEPS IN THIS EXACT ORDER. SKIPPING ANY STEP WILL CAUSE ERRORS.**

1. **STEP 1**: Parse command arguments and validate flags
2. **STEP 2**: Determine save scope (if incremental mode)
3. **STEP 3**: 🔴 **MANDATORY** - Check conversation tool history to determine CREATE vs UPDATE mode
   - **THIS IS NOT OPTIONAL**
   - **YOU MUST CHECK Read AND Write TOOL HISTORY**
   - **FAILURE TO CHECK WILL CREATE DUPLICATE FILES**

**Before proceeding to Phase 1**: You MUST have completed STEP 3 and determined mode (CREATE or UPDATE).

**Common failure**: Skipping directly to "get current time" without checking tool history → This is WRONG!

---

**STEP 1: Parse command arguments and validate**

Check for flags and arguments:
- `--incremental` or `-i` flag present? → Set incremental_mode = true
- Description provided? → Extract description
- Neither? → description = null, incremental_mode = false

**IMPORTANT VALIDATION:**
- If `incremental_mode = true` AND `description = null`:
  - **ERROR**: Display error message to user
  - Message: "❌ The --incremental (-i) flag requires a description. Usage: /save-session -i <description>"
  - **STOP**: Do not proceed with save operation
  - Explanation: Incremental mode is only for creating new session files with specific topics, not for updating existing sessions

- If `incremental_mode = true` AND `description` is provided:
  - **VALID**: Proceed to STEP 2

**STEP 2: Determine save scope (only applies when description is provided)**

**Note**: This step only executes when a description is provided. The `--incremental` flag is invalid without a description.

**IF incremental_mode is true** (description must be provided):
1. Find the timestamp of the most recent session save in conversation history
   - Search all Write tool calls to `session-*.md` files
   - Get the timestamp of the most recent Write operation
   - This is the "last save point"

2. Set content scope:
   - **save_from** = timestamp of last session save
   - **save_to** = current time
   - Only conversation content between these timestamps will be saved

3. If no previous session save found:
   - Treat as default mode (save from beginning)
   - Warn user: "⚠️ No previous save found, saving from conversation start"

**IF incremental_mode is false (default):**
- **save_from** = conversation start
- **save_to** = current time
- Save all conversation content

**STEP 3: Determine CREATE or UPDATE mode**

**⚠️ CRITICAL: This step determines whether to create a new session file or update an existing one. Execute this check BEFORE proceeding.**

**IF description argument is provided:**
- Set mode to "CREATE"
- Skip to Phase 0.5 (sanitization) and create a new session file
- Use the content scope determined in STEP 2

**IF no description argument is provided:**

**YOU MUST perform this detection check:**

1. **Search conversation history for session file operations (MANDATORY CHECK):**

   **Step 3a: Check Read tool history**
   - Scan ALL Read tool invocations in current conversation (from conversation start to now)
   - For each Read tool call, examine the `file_path` parameter
   - Look for file_path matching regex pattern: `.*session-.*\.md$`
   - If found: Extract the FULL file path (e.g., `/path/to/session-2025-10-22-topic.md`)
   - Result: If any match found → `session_file_read = <file_path>`, otherwise → `session_file_read = null`

   **Step 3b: Check Write tool history**
   - Scan ALL Write tool invocations in current conversation (from conversation start to now)
   - For each Write tool call, examine the `file_path` parameter
   - Look for file_path matching regex pattern: `.*session-.*\.md$`
   - If found: Extract the FULL file path
   - Result: If any match found → `session_file_written = <file_path>`, otherwise → `session_file_written = null`

2. **Determine mode based on detection results (MANDATORY DECISION TREE):**

   ```
   IF session_file_read != null OR session_file_written != null:
       mode = "UPDATE"
       target_file = session_file_written if session_file_written != null else session_file_read
       Inform user: "Updating existing session: {basename(target_file)}"
       Proceed to Phase 3 UPDATE mode with target_file
   ELSE:
       mode = "CREATE"
       Inform user: "Creating new session file"
       Proceed to Phase 0.5 and Phase 3 CREATE mode
   ```

3. **Verification output (MANDATORY):**

   Before proceeding to Phase 1, you MUST internally verify and log:
   - ✓ Checked Read tool history: [Found/Not found] session file
   - ✓ Checked Write tool history: [Found/Not found] session file
   - ✓ Mode determined: [CREATE/UPDATE]
   - ✓ Target file: [file path or "new file"]

**Detection is tool-based, not phrase-based:**
- User says "please read session-xxx.md" → Claude uses Read tool → UPDATE mode
- User says "open session-xxx.md" → Claude uses Read tool → UPDATE mode
- User says "show me session-xxx.md" → Claude uses Read tool → UPDATE mode
- User says "/path/to/session-xxx.md" → Claude uses Read tool → UPDATE mode
- Any phrasing that causes Claude to read a session-*.md file → UPDATE mode

**Common Mistakes to Avoid:**
- ❌ Don't create a new file when a session file was already read in this conversation
- ❌ Don't assume CREATE mode without checking tool history first
- ❌ Don't rely on user phrasing; only check actual Read/Write tool calls
- ❌ Don't forget to check BOTH Read and Write tool histories

### Phase 0.5: Input Sanitization
If a description argument is provided, sanitize it for safe filename usage:
- Convert all spaces to hyphens
- Convert to lowercase
- Remove or replace special characters (keep only alphanumeric, hyphens, and underscores)
- Truncate to 100 characters maximum if longer
- Example: "investigating OCPBUGS-12345 regarding routes" → "investigating-ocpbugs-12345-regarding-routes"

---

## 🛑 CHECKPOINT: Before Proceeding to Phase 1

**STOP! DO NOT PROCEED UNTIL YOU HAVE COMPLETED PHASE 0.**

**MANDATORY VERIFICATION - YOU MUST ANSWER ALL THESE QUESTIONS:**

1. ✅ **Have you executed Phase 0 STEP 1?**
   - Did you parse command arguments?
   - Did you determine if description is provided?
   - Did you check for --incremental flag?

2. ✅ **Have you executed Phase 0 STEP 2?** (if applicable)
   - If incremental mode, did you determine save scope?
   - If not incremental, did you confirm save_from = conversation start?

3. ✅ **Have you executed Phase 0 STEP 3?** 🔴 **THIS IS MANDATORY**
   - Did you check Read tool history for session-*.md files?
   - Did you check Write tool history for session-*.md files?
   - Did you determine mode (CREATE or UPDATE)?
   - If UPDATE mode: Do you know the target file path?
   - Did you output verification results to confirm?

**IF YOU CANNOT ANSWER "YES" TO ALL QUESTIONS ABOVE:**
- **GO BACK TO PHASE 0**
- **DO NOT PROCEED**
- **EXECUTE ALL MISSING STEPS**

**IF YOU CAN ANSWER "YES" TO ALL QUESTIONS:**
- Proceed to Phase 1
- Your mode is: [CREATE/UPDATE]
- Your target file is: [file path or "new file with timestamp"]

---

### Phase 1: Context Analysis
- Summarizes main topics and goals discussed
- Lists all accomplishments and completed tasks
- Identifies all files that were read, modified, or created
- Extracts important technical decisions and their rationale
- Captures any error messages encountered and how they were resolved
- Notes any commands that were run (make, linter, tests, etc.)

### Phase 1.5: Sensitive Information Redaction

**🚨 CRITICAL SECURITY REQUIREMENT - ABSOLUTE AND NON-NEGOTIABLE 🚨**

**YOU MUST NEVER WRITE SENSITIVE INFORMATION TO SESSION FILES.**

This phase is **NOT OPTIONAL**. This is a **MANDATORY SECURITY GATE**.

Before writing ANY content to the session file, ALL sensitive information MUST be redacted to prevent security leaks.

**Consequences of failure:**
- Security breach
- Credential exposure
- Potential system compromise
- User trust violation

**This is your responsibility. You MUST enforce this.**

**Mandatory Redaction Process:**

1. **Scan all content** (conversation text, code snippets, commands, file paths, URLs) for sensitive patterns
2. **Apply redaction rules** to replace sensitive data with safe placeholders
3. **Verify redaction** before proceeding to file write
4. **Triple-check**: Scan again to ensure nothing was missed

**Sensitive Information Categories and Redaction Rules:**

**1. API Keys and Tokens**
- **Pattern**: Strings matching common API key formats
  - Google API keys: `AIza[0-9A-Za-z_-]{35}`
  - AWS keys: `AKIA[0-9A-Z]{16}`
  - Generic long alphanumeric: `[a-zA-Z0-9_-]{32,}`
  - Bearer tokens: `Bearer [a-zA-Z0-9._-]+`
- **Redaction**: Replace with `[REDACTED_API_KEY]` or `[REDACTED_TOKEN]`
- **Example**:
  - Before: `AIzaFakeExampleKey1234567890abcdefg`
  - After: `[REDACTED_API_KEY]`

**2. Webhook URLs**
- **Pattern**: URLs containing `hooks.slack.com`, `webhook`, `hooks`, or similar
  - Slack: `https://hooks.slack.com/services/[A-Z0-9/]+`
  - Generic: `https?://[^/]*webhook[^/]*/[^\s]+`
- **Redaction**: Replace with `[REDACTED_WEBHOOK_URL]`
- **Example**:
  - Before: `https://hooks.slack.com/services/T12FAKE34/B56FAKE78/fakeWebhookToken123456`
  - After: `[REDACTED_WEBHOOK_URL]`

**3. Passwords and Secrets**
- **Pattern**: Strings following `password=`, `secret=`, `key=`, `token=`, `pwd=`
  - Regex: `(password|secret|pwd|key|token)\s*[=:]\s*[^\s,;]+`
- **Redaction**: Replace with `[REDACTED_SECRET]`
- **Example**:
  - Before: `password=FakeP@ssw0rd123`
  - After: `password=[REDACTED_SECRET]`

**4. Private Keys and Certificates**
- **Pattern**: PEM-format keys and certificates
  - SSH: `-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----`
  - Certificates: `-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----`
- **Redaction**: Replace with `[REDACTED_PRIVATE_KEY]` or `[REDACTED_CERTIFICATE]`

**5. Database Connection Strings**
- **Pattern**: Connection strings with credentials
  - PostgreSQL: `postgresql://[^:]+:[^@]+@`
  - MySQL: `mysql://[^:]+:[^@]+@`
  - MongoDB: `mongodb://[^:]+:[^@]+@`
- **Redaction**: Replace credentials portion with `[REDACTED_USER]:[REDACTED_PASSWORD]`

**6. JWT Tokens**
- **Pattern**: Three base64 segments separated by dots
  - Regex: `eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+`
- **Redaction**: Replace with `[REDACTED_JWT_TOKEN]`

**7. Email Addresses (Optional - Context-Dependent)**
- **Pattern**: Standard email format `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- **Redaction Policy**:
  - **Redact personal emails**: `user@gmail.com` → `[REDACTED_EMAIL]`
  - **Keep corporate/public emails**: `support@company.com` → Keep as-is
  - **Redact in sensitive contexts**: If part of authentication/credentials

**8. IP Addresses (Context-Dependent)**
- **Pattern**: IPv4: `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b`
- **Redaction Policy**:
  - **Redact private IPs**: `192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`
  - **Redact in connection strings**: When part of database URLs or credentials
  - **Keep public IPs**: If documenting public services (context-dependent)

**9. File Paths with Sensitive Information**
- **Pattern**: Paths containing usernames or sensitive directories
  - Home directories: `/Users/[username]/`, `/home/[username]/`
  - Credential files: Paths ending in `*-token.json`, `*-key.json`, `credentials.json`, `secrets.yaml`
- **Redaction Policy**:
  - **Redact username**: `/Users/jdoe/` → `/Users/[USERNAME]/`
  - **Keep relative structure**: Keep directory structure after username
  - **Example**:
    - Before: `/Users/jdoe/work/config/myapp-credentials.json`
    - After: `/Users/[USERNAME]/work/config/[PROJECT]-credentials.json`

**10. JSON/YAML Credential Files**
- **Pattern**: File contents showing keys
  ```json
  {
    "key": "AIzaFakeExampleKey1234567890abcdefg"
  }
  ```
- **Redaction**: Replace actual key value with placeholder
  ```json
  {
    "key": "[REDACTED_API_KEY]"
  }
  ```

**Implementation Guidelines:**

1. **Process content in order**:
   - First redact most specific patterns (API keys, tokens)
   - Then general patterns (passwords, secrets)
   - Finally contextual patterns (emails, IPs, paths)

2. **Preserve context**:
   - Keep file structure and format visible
   - Maintain code readability
   - Show WHAT was configured, not the actual values

3. **Document redactions**:
   - **REQUIRED**: Add a note at the beginning of session file (immediately after date/metadata):
     ```markdown
     > **Security Note**: Sensitive information (API keys, tokens, passwords, webhook URLs, usernames)
     > has been automatically redacted from this session for security purposes.
     ```
   - This note is **MANDATORY** - it alerts readers that redaction has occurred
   - It also serves as a reminder to you that you MUST have performed redaction

4. **Verification checklist** (before writing file):
   - ✓ No API keys visible
   - ✓ No webhook URLs with tokens
   - ✓ No passwords or secrets
   - ✓ No private keys or certificates
   - ✓ No JWT tokens
   - ✓ Usernames in paths redacted
   - ✓ Credential file contents redacted
   - ✓ No database connection strings with credentials
   - ✓ No email addresses in sensitive contexts
   - ✓ No private IP addresses in credentials

**MANDATORY Error Handling:**
- If uncertain whether to redact: **ALWAYS ERR ON THE SIDE OF CAUTION** - redact it
- If pattern might contain sensitive data: **REDACT IT**
- When in doubt: **ASK USER** before including in session file
- **NEVER** make assumptions that something is "probably safe"
- **NEVER** skip redaction because "it seems like test data"
- **ALWAYS** treat all potential credentials as real credentials

**Example Redaction Results:**

```markdown
# Before Redaction:
API_KEY=AIzaFakeExampleKey1234567890abcdefg
SLACK_WEBHOOK=https://hooks.slack.com/services/T12FAKE34/B56FAKE78/fakeWebhookToken123456
config_path=/Users/jdoe/work/config/myapp-credentials.json

# After Redaction:
API_KEY=[REDACTED_API_KEY]
SLACK_WEBHOOK=[REDACTED_WEBHOOK_URL]
config_path=/Users/[USERNAME]/work/config/[PROJECT]-credentials.json
```

### Phase 2: File Modification Tracking
- Reads and verifies current state of modified files
- Lists specific line numbers and code changes
- Includes before/after comparisons for critical changes
- Notes which files were created vs modified vs deleted
- Tracks any generated files (like bindata)

### Phase 3: Session File Creation or Update

**🔒 SECURITY CHECKPOINT: Before proceeding to file write**

**STOP AND VERIFY:**
1. ✅ Have you scanned ALL content for sensitive information?
2. ✅ Have you applied redaction rules to ALL sensitive data?
3. ✅ Have you verified the verification checklist?
4. ✅ Are you absolutely certain no sensitive information remains?

**If you cannot answer YES to all four questions: DO NOT PROCEED.**
**Go back to Phase 1.5 and redo the redaction process.**

---

**🔴 CRITICAL CHECKPOINT: Phase 0 Completion Verification**

**BEFORE PROCEEDING WITH FILE WRITE, VERIFY PHASE 0 WAS COMPLETED:**

**Question 1**: What mode did Phase 0 STEP 3 determine?
- If you cannot answer this question → **GO BACK TO PHASE 0 STEP 3**
- Your answer must be either: "CREATE" or "UPDATE"

**Question 2**: If mode is UPDATE, what is the target file path?
- If mode is UPDATE and you don't know the file path → **GO BACK TO PHASE 0 STEP 3**
- Your answer must be a full file path (e.g., `/path/to/session-2025-10-22-topic.md`)

**Question 3**: Did you check Read tool history for session-*.md files?
- If you did not check → **GO BACK TO PHASE 0 STEP 3a**
- Your answer must explicitly state: "Checked Read tool history, found: [path] or found: none"

**Question 4**: Did you check Write tool history for session-*.md files?
- If you did not check → **GO BACK TO PHASE 0 STEP 3b**
- Your answer must explicitly state: "Checked Write tool history, found: [path] or found: none"

**ENFORCEMENT RULE:**
- If Phase 0 STEP 3 was skipped → You are now in **ERROR STATE**
- **STOP IMMEDIATELY**
- **GO BACK** to Phase 0 STEP 3
- **EXECUTE the tool history check**
- **DETERMINE the correct mode**
- **THEN return to Phase 3**

**If you have completed Phase 0 STEP 3 correctly:**
- State your mode: [CREATE/UPDATE]
- State your target file: [path or "new file"]
- Proceed to the appropriate mode section below

---

**Mode: CREATE (new session file)**

**⚠️ CRITICAL: Time Generation Instructions**
- **ALWAYS use the current actual time** when generating session files
- **NEVER use placeholder values** like "YYYY-MM-DD HH:MM:SS" or hardcoded times
- Get the current time at the moment of file creation (both local and UTC)
- Format timestamps correctly:
  - `session_id`: Format as `YYYY-MM-DD-HHMMSS` using local time (e.g., "2025-10-22-143000")
  - `started_at` and `last_updated`: Format as `YYYY-MM-DD HH:MM:SS TIMEZONE (YYYY-MM-DD HH:MM:SS UTC)`
    - Example: "2025-10-22 14:30:00 EST (2025-10-22 19:30:00 UTC)"
    - Example: "2025-10-22 22:30:00 CST (2025-10-22 14:30:00 UTC)"
    - Local time comes first (primary), UTC in parentheses (reference)
  - `Date`: Format as `YYYY-MM-DD` using local date (e.g., "2025-10-22")
  - `Last Updated`: Format as `YYYY-MM-DD HH:MM:SS TIMEZONE` using local time only (e.g., "2025-10-22 14:30:00 EST")
  - All other timestamps in the document: Use local time only for readability

Creates a comprehensive markdown document with session tracking metadata:

```markdown
<!--
SESSION_METADATA (Do not edit manually)
session_id: YYYY-MM-DD-HHMMSS
started_at: YYYY-MM-DD HH:MM:SS TIMEZONE (YYYY-MM-DD HH:MM:SS UTC)
last_updated: YYYY-MM-DD HH:MM:SS TIMEZONE (YYYY-MM-DD HH:MM:SS UTC)
update_count: 1
-->

# Session: [Title]
**Date**: YYYY-MM-DD
**Last Updated**: YYYY-MM-DD HH:MM:SS TIMEZONE
```

**Note:** The placeholders above (YYYY-MM-DD, etc.) are FORMAT EXAMPLES ONLY. Replace them with actual current time values. Use user's local time as primary time, with UTC in parentheses for metadata fields.

Followed by these sections:
1. **Session Summary** - Brief 1-2 paragraph overview
2. **Current State** - Status of work and modifications
3. **Accomplishments** - Detailed completion checklist
4. **Files Modified** - Organized by Created/Modified/Deleted
5. **Key Technical Decisions** - Rationale and implications
6. **Pending Tasks** - Unfinished work (checkbox format)
7. **Commands Used** - All executed commands
8. **Context for Resumption** - Critical continuation information
9. **Full Conversation Summary** - Key discussion points
10. **Next Steps** - Clear action items
11. **How to Resume This Session** - Step-by-step guide

**Mode: UPDATE (existing session file)**

**⚠️ CRITICAL: Time Update Instructions**
- **ALWAYS use the current actual time** when updating timestamps
- **NEVER use placeholder values** or copy old timestamps
- Get the current time (both local and UTC) at the moment of file update
- Format for metadata fields: `YYYY-MM-DD HH:MM:SS TIMEZONE (YYYY-MM-DD HH:MM:SS UTC)`
  - Example: "2025-10-22 16:45:00 EST (2025-10-22 21:45:00 UTC)"
  - Local time first (primary), UTC in parentheses (reference)
- Format for header and body timestamps: Use local time only (e.g., "2025-10-22 16:45:00 EST")

1. **Update metadata section:**
   - Increment `update_count`
   - Update `last_updated` timestamp **to current actual time**
   - Keep original `session_id` and `started_at` (DO NOT modify these)

2. **Update header:**
   - Update "Last Updated" timestamp **to current actual time**

3. **Append new content sections:**
   - Add "## Update {N}: YYYY-MM-DD HH:MM" section separator (use current actual time)
   - Add "### New Accomplishments Since Last Save"
   - Add "### Additional Files Modified"
   - Add "### New Technical Decisions"
   - Add "### Updated Pending Tasks" (replace old pending tasks section)
   - Add "### Recent Commands"
   - Add "### Continuation Context" (what happened since last save)

4. **Update summary sections:**
   - Keep original Session Summary
   - Update Current State section with latest status
   - Merge accomplishments (keep completed, add new)
   - Update Next Steps with current priorities

### Phase 4: Verification and Output

**For CREATE mode:**
- Confirms new session file was created successfully
- Displays file path and size
- Shows session_id for tracking
- Provides resumption instructions

**For UPDATE mode:**
- Confirms existing session file was updated successfully
- Displays file path and updated size
- Shows update count (e.g., "Update #3")
- Summarizes what was added in this update
- Provides resumption instructions

## Return Value

**CREATE mode** creates a markdown file in the repository root directory with filename:
- `session-YYYY-MM-DD-HHMMSS.md` (without description)
- `session-YYYY-MM-DD-<description>.md` (with custom description)

Terminal output for CREATE:
```
✅ New session created successfully!

File: session-YYYY-MM-DD-description.md (XX KB)
Location: /full/path/to/file
Session ID: YYYY-MM-DD-HHMMSS

📖 To resume this session:
   Please read `/full/path/to/session-YYYY-MM-DD-description.md` and continue from where we left off
```

**UPDATE mode** updates the existing session file found in current directory.

Terminal output for UPDATE:
```
✅ Session updated successfully! (Update #3)

File: session-YYYY-MM-DD-description.md (XX KB → YY KB)
Location: /full/path/to/file
Original session started: YYYY-MM-DD HH:MM

📝 Added in this update:
   - X new accomplishments
   - Y additional files modified
   - Z new commands executed

📖 To resume this session:
   Please read `/full/path/to/session-YYYY-MM-DD-description.md` and continue from where we left off
```

## Examples

### Example 1: Creating a New Session (First Save)
```
/save-session
```
**Result:** Creates `session-2025-10-22-143000.md` with metadata tracking

### Example 2: Continuing Work and Updating (No Description)
```
# Work for 30 minutes, then save progress
/save-session

# Continue working for another hour
/save-session
```
**Result:**
- First call creates `session-2025-10-22-143000.md` (Write tool called)
- Second call detects Write tool was used to create session file → updates the same file (adds Update #2 section)

### Example 3: Starting a New Branch (With Description)
```
# Working on feature A
/save-session

# Decide to work on feature B
/save-session feature-b-implementation
```
**Result:**
- First call creates `session-2025-10-22-143000.md`
- Second call creates NEW file `session-2025-10-22-feature-b-implementation.md` (description provided = new session)

### Example 4: Multiple Save Points in One Session
```
/save-session                    # Create: session-2025-10-22-143000.md
# ... work for 1 hour ...
/save-session                    # Update: session-2025-10-22-143000.md (Update #2)
# ... work for 2 hours ...
/save-session                    # Update: session-2025-10-22-143000.md (Update #3)
```

### Example 5: Named Session with Updates
```
/save-session bug-fix-ocpbugs-12345    # Create new named session
# ... fix part 1 ...
/save-session                          # Update same session
# ... fix part 2 ...
/save-session                          # Update same session again
```
**Result:** `session-2025-10-22-bug-fix-ocpbugs-12345.md` with 3 update sections

### Example 6: With Spaces and Special Characters
```
/save-session investigating OCPBUGS-12345 regarding routes
```
**Result:** Creates `session-2025-10-22-investigating-ocpbugs-12345-regarding-routes.md`

### Example 7: Resuming a Saved Session (Different Phrasings)
All these phrasings work the same way - they trigger Read tool:

```bash
# Phrasing 1: "please read"
User: please read /path/to/session-2025-10-22-bug-fix.md
Claude: [Uses Read tool] ✓

# Phrasing 2: "open"
User: open session-2025-10-22-bug-fix.md
Claude: [Uses Read tool] ✓

# Phrasing 3: "show me"
User: show me session-2025-10-22-bug-fix.md
Claude: [Uses Read tool] ✓

# Phrasing 4: Direct path
User: /path/to/session-2025-10-22-bug-fix.md
Claude: [Uses Read tool] ✓

# Later in conversation, save progress
/save-session
```
**Result:** Updates `session-2025-10-22-bug-fix.md` (because Read tool was used)

### Example 8: Cross-Day Work - Resume Previous Session
```bash
# Day 1 - Create and save
/save-session → Creates session-2025-10-22-170000.md
# Close Claude Code

# Day 2 - Resume yesterday's work (new conversation)
User: Open session-2025-10-22-170000.md and continue yesterday's work
Claude: [Uses Read tool to read the file]

# Continue working...
/save-session
```
**Result:** Updates `session-2025-10-22-170000.md` (Read tool detected in conversation history)

### Example 9: Cross-Day Work - Start Fresh
```bash
# Day 1 - Create and save
/save-session → Creates session-2025-10-22-170000.md
# Close Claude Code

# Day 2 - New conversation, new task (don't read yesterday's file)
User: Let's work on something new today

# Work on new task...
/save-session
```
**Result:** Creates `session-2025-10-23-090000.md` (no Read tool calls in conversation history)

### Example 10: Incremental Save - Multiple Topics in One Conversation
```bash
# Start working on Topic A
User: Let's discuss Topic A...
Claude: [Discussion about Topic A]

# Save Topic A progress (first save)
/save-session
→ Creates session-2025-10-22-143000.md (contains Topic A)

# Continue Topic A
Claude: [More discussion about Topic A]

# Save Topic A again
/save-session
→ Updates session-2025-10-22-143000.md (Update #2, more Topic A content)

# Save complete Topic A to dedicated file (all content from start)
/save-session topicA
→ Creates session-2025-10-22-topicA.md
→ Contains ALL content from conversation start (entire Topic A discussion)

# Start working on Topic B (different topic)
User: Now let's discuss Topic B...
Claude: [Discussion about Topic B]

# Save ONLY Topic B to new file (incremental mode)
/save-session --incremental topicB
# or
/save-session -i topicB
→ Creates session-2025-10-22-topicB.md
→ Contains ONLY content since last save (only Topic B, no Topic A)

# Continue Topic B
Claude: [More discussion about Topic B]

# Update Topic B file
/save-session
→ Updates session-2025-10-22-topicB.md (most recent session)
→ Adds more Topic B content

# Start Topic C
User: Let's move to Topic C...
Claude: [Discussion about Topic C]

# Save ONLY Topic C incrementally
/save-session -i topicC
→ Creates session-2025-10-22-topicC.md
→ Contains ONLY content since last save (only Topic C)
```

**Final Result:**
- `session-2025-10-22-143000.md` - Initial saves with Topic A progress
- `session-2025-10-22-topicA.md` - Complete Topic A (from conversation start)
- `session-2025-10-22-topicB.md` - Only Topic B discussion
- `session-2025-10-22-topicC.md` - Only Topic C discussion

**Key Benefit:** One long conversation can be cleanly separated into multiple focused session files, each containing only relevant content.

## Arguments

**--incremental, -i** (optional flag)
- **Purpose**: Save only content since the last session save (incremental mode)
- **⚠️ IMPORTANT**: **MUST** be used with a description argument
  - ✅ Valid: `/save-session -i topicB`
  - ❌ Invalid: `/save-session -i` (will show error)
- **Use case**: Saving multiple separate topics in one conversation
- **Behavior**:
  - Finds the timestamp of the most recent session save (Write to session-*.md)
  - Saves only conversation content from that timestamp to now
  - If no previous save found: saves from beginning (with warning)
- **Error handling**: If used without description, displays:
  - "❌ The --incremental (-i) flag requires a description. Usage: /save-session -i <description>"
- **Example**: `/save-session -i topicB` or `/save-session --incremental topicB`
- **Rationale**: Incremental mode is for creating new session files with specific topics, not for updating existing sessions (which use different logic)

**description** (optional)
- **When provided WITHOUT --incremental flag (default)**:
  - Creates a NEW session file with custom identifier
  - Saves content from **conversation beginning to now**
  - Allows explicit session branching (e.g., switching to different feature/bug)
  - Filename: `session-YYYY-MM-DD-<description>.md`
  - **Input handling**: Automatically sanitized for safe filename usage (spaces → hyphens, special chars removed, max 100 chars)
  - **Good examples**: `feature-name`, `bug-fix`, `refactoring`, `investigating-ocpbugs-12345`

- **When provided WITH --incremental flag**:
  - Creates a NEW session file with custom identifier
  - Saves content from **last session save to now** (incremental)
  - Enables saving multiple independent topics in one conversation
  - Each topic gets its own clean session file

- **When omitted**: Intelligent session tracking based on conversation history
  - **First save**: Creates new timestamped file `session-YYYY-MM-DD-HHMMSS.md`
  - **Subsequent saves**: Automatically detects and updates the existing session file
  - Detection method: Checks if Claude has read or created a session-*.md file in current conversation
  - Works regardless of time elapsed (1 hour or 10 hours in same conversation)
  - Metadata tracking: Uses hidden HTML comments to track session ID

**Behavior Summary:**
```
/save-session                    → First call: CREATE (all content from start)
/save-session                    → Later calls: UPDATE same session
/save-session topicA             → CREATE new session (all content from start)
/save-session -i topicB          → CREATE new session (only content since last save)
```

**Note**: You can use spaces and special characters in your description - they will be automatically sanitized. For example, "investigating OCPBUGS-12345 regarding routes" becomes "investigating-ocpbugs-12345-regarding-routes".

## Session Metadata Format

Session files include hidden metadata for intelligent tracking:

```html
<!--
SESSION_METADATA (Do not edit manually)
session_id: 2025-10-22-143000
started_at: 2025-10-22 14:30:00 EST (2025-10-22 19:30:00 UTC)
last_updated: 2025-10-22 16:45:00 EST (2025-10-22 21:45:00 UTC)
update_count: 3
-->
```

**⚠️ IMPORTANT:** The timestamps shown above are EXAMPLES ONLY. When creating or updating session files, ALWAYS use the **current actual time** at the moment of file creation/update, not these example values. Use user's local time as primary (with timezone), and include UTC in parentheses for reference.

This metadata enables:
- Automatic detection of existing sessions
- Update count tracking
- Session timeline reconstruction
- Multiple update sections in one file
