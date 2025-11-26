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

This is a non-negotiable, absolute requirement that must be followed without exception.
- API keys → MUST be redacted
- Tokens → MUST be redacted
- Passwords → MUST be redacted
- Webhook URLs → MUST be redacted
- Private keys → MUST be redacted
- Usernames in paths → MUST be redacted
- ANY sensitive data → MUST be redacted

If you are uncertain whether something is sensitive, **REDACT IT**. When in doubt, **ASK THE USER** before including it.

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

   ```text
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
   - Was the --incremental flag checked?

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

### Phase 1.5: Sensitive Information Redaction and Verification

**🚨 CRITICAL SECURITY REQUIREMENT - ABSOLUTE AND NON-NEGOTIABLE 🚨**

**YOU MUST NEVER WRITE SENSITIVE INFORMATION TO SESSION FILES.**

This phase is **NOT OPTIONAL**. This is a **MANDATORY SECURITY GATE** with **AUTOMATED VERIFICATION**.

Before writing ANY content to the session file, ALL sensitive information MUST be redacted AND verified with automated tooling.

**Consequences of failure:**
- Security breach
- Credential exposure
- Potential system compromise
- User trust violation

**This is your responsibility. You MUST enforce this.**

---

#### Step 0: Quick Pre-Scan (Workflow Optimization)

**Purpose**: Determine if manual redaction is needed, while still ensuring all sessions are verified with gitleaks.

**Quick scan for common sensitive patterns**:

Scan the conversation content for obvious sensitive information patterns:

1. **API Keys and Tokens**:
   - GitHub tokens: `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`
   - AWS keys: `AKIA`
   - Google API keys: `AIza`
   - Stripe keys: `sk_live`, `sk_test`
   - Generic long tokens: `[a-zA-Z0-9_-]{32,}` in suspicious contexts

2. **Authentication**:
   - Bearer tokens: `Bearer` followed by long strings
   - JWT tokens: `eyJ` (Base64 encoded JSON)
   - Basic auth in URLs: `https://user:pass@`

3. **Credentials**:
   - Patterns like: `password=`, `secret=`, `token=`, `api_key=`, `pwd=`
   - Private keys: `-----BEGIN PRIVATE KEY ...`, `-----BEGIN RSA PRIVATE KEY ...`

4. **Webhooks**:
   - Slack webhooks: `hooks.slack.com/services/`
   - Generic webhook URLs with tokens

5. **Database Connection Strings**:
   - `postgresql://user:pass@`, `mysql://user:pass@`, `mongodb://user:pass@`

**Decision Tree**:

```text
IF sensitive patterns detected:
    SENSITIVE_FOUND = true
    → Execute Step 1-2 (manual redaction required)
    → Then Step 3 (gitleaks verification of redacted content)
ELSE:
    SENSITIVE_FOUND = false
    → Skip Step 1-2 (no redaction needed)
    → Still proceed to Step 3 (gitleaks verification as safety check)
```

**Important Notes**:
- **This is an optimization step, not a security gate**
- **Gitleaks verification (Step 3) is ALWAYS executed** regardless of pre-scan results
- Pre-scan allows skipping manual redaction work when content is clean
- But gitleaks still validates to catch anything the pre-scan might miss
- **When in doubt, mark as SENSITIVE_FOUND = true**

**Why always run gitleaks**:
- **Defense in Depth**: Pre-scan might miss uncommon secret formats
- **Comprehensive Detection**: Gitleaks has extensive rule database
- **Regular Updates**: Gitleaks rules are maintained for new secret types
- **Low Cost, High Value**: Small performance overhead for significant security benefit

---

#### Step 1: Check for Comprehensive Redaction Skill (Optional but Recommended)

**Note**: This step is only executed if `SENSITIVE_FOUND = true` from Step 0.

First, check if the comprehensive `redact-sensitive-info` skill from the utils plugin is available:

**Detection Method**:

Use the Glob tool to search for the skill in common locations:

1. **Search in user's installed plugins** (most common):
   - Pattern: `~/.claude/plugins/**/redact-sensitive-info/SKILL.md`
   - This covers all installed plugin repositories

2. **Search in current project** (if working in ai-helpers repo):
   - Pattern: `**/redact-sensitive-info/SKILL.md`
   - Relative to current working directory

**If FOUND** (Glob returns at least one result):
- Read the found SKILL.md file to understand the comprehensive redaction workflow
- Follow that skill's detailed guidance (it includes 400+ lines of instructions)
- That skill includes detailed pattern matching and automated gitleaks verification
- After completing that skill's workflow, skip directly to Step 3 of this command

**If NOT_FOUND** (Glob returns no results):
- The utils plugin with redact-sensitive-info skill is not installed
- Proceed with Step 2 (simplified redaction below)

---

#### Step 2: Simplified Redaction (when utils plugin not available)

**Note**: This step is only executed if `SENSITIVE_FOUND = true` from Step 0.

**Mandatory Redaction Process:**

1. **Scan all content** (conversation text, code snippets, commands, file paths, URLs) for sensitive patterns
2. **Apply redaction rules** to replace sensitive data with safe placeholders
3. **Verify with gitleaks** (automated verification - see Step 3)

**Sensitive Information to Redact:**

**1. API Keys and Tokens**
- **Patterns**:
  - Google API keys: `AIza[0-9A-Za-z_-]{35}`
  - AWS keys: `AKIA[0-9A-Z]{16}`
  - GitHub tokens: `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`
  - Generic long alphanumeric: `[a-zA-Z0-9_-]{32,}`
  - Bearer tokens: `Bearer [a-zA-Z0-9._-]+`
- **Redaction**: Replace with `[REDACTED_API_KEY]` or `[REDACTED_TOKEN]`

**2. Passwords and Secrets**
- **Patterns**: `password=`, `secret=`, `key=`, `token=`, `pwd=`
- **Redaction**: Replace with `[REDACTED_SECRET]`

**3. Private Keys and Certificates**
- **Patterns**: `-----BEGIN PRIVATE KEY ...`, `-----BEGIN RSA PRIVATE KEY ...`
- **Redaction**: Replace entire key block with `[REDACTED_PRIVATE_KEY]`

**4. Database Connection Strings**
- **Patterns**: `postgresql://user:pass@`, `mysql://user:pass@`, `mongodb://user:pass@`
- **Redaction**: Replace credentials with `[REDACTED_USER]:[REDACTED_PASSWORD]`

**5. Webhook URLs**
- **Patterns**: `hooks.slack.com/services/`, URLs containing `webhook` with tokens
- **Redaction**: Replace with `[REDACTED_WEBHOOK_URL]`

**6. JWT Tokens**
- **Patterns**: `eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+`
- **Redaction**: Replace with `[REDACTED_JWT_TOKEN]`

**7. File Paths with Usernames**
- **Patterns**: `/Users/<username>/`, `/home/<username>/`
- **Redaction**: Replace username with `[USERNAME]`
- **Example**: `/Users/testuser/work/config.yaml` → `/Users/[USERNAME]/work/config.yaml`

**Quick Redaction Guidelines:**
- When uncertain whether to redact: **ALWAYS REDACT**
- If pattern might contain sensitive data: **REDACT IT**
- When in doubt: **ASK USER** before including
- **NEVER** assume something is "probably safe"

**Document Redactions:**
Add this note at the beginning of the session file (after metadata):
```markdown
> **Security Note**: Sensitive information (API keys, tokens, passwords, webhook URLs, usernames)
> has been automatically redacted and verified with gitleaks for security purposes.
```

---

#### Step 3: Automated Verification with Gitleaks (MANDATORY - ALWAYS EXECUTED)

**🔴 CRITICAL: This step is MANDATORY for ALL sessions and uses automated tooling to verify content safety.**

**This step ALWAYS executes regardless of Step 0 results:**
- **If `SENSITIVE_FOUND = true`**: Verify that redaction in Step 1-2 was successful
- **If `SENSITIVE_FOUND = false`**: Verify as safety check (pre-scan might have missed something)

You MUST verify the session file content with gitleaks before writing it to disk.

**Implementation:**

Run gitleaks verification using the first available tool (podman/docker/gitleaks binary).

**Important**: Regardless of the verification result, **the session file will ALWAYS be saved**. The verification result only determines what warnings are shown to the user.

**📝 Improving User Experience - Avoiding Repeated Permission Prompts:**

If you find that Claude Code asks for permission every time gitleaks verification runs, you can configure automatic approval by adding the verification commands to your project's `.claude/settings.local.json` file:

```json
{
  "permissions": {
    "allow": [
      "Bash(podman:*)",
      "Bash(docker:*)",
      "Bash(gitleaks:*)"
    ]
  }
}
```

**Why this helps:**
- Without this configuration, Claude Code will prompt for permission each time podman/docker/gitleaks runs
- With this configuration, these commands are automatically approved for the project
- You only need to add the tool(s) you have installed (e.g., just podman if that's what you use)

**How to configure:**
1. Create or edit `.claude/settings.local.json` in your project root
2. Add the verification tool commands to the `permissions.allow` array
3. Restart Claude Code or reload the configuration
4. Future gitleaks verifications will run without prompting

**Note:** This is optional. If you prefer to review each command execution, you can skip this configuration and approve manually each time.

```bash
# Try to run gitleaks verification (prefer containers over binary)
GITLEAKS_RESULT=""
GITLEAKS_OUTPUT=""

# Create temporary directory in user's home (avoids SELinux issues with /tmp)
GITLEAKS_TEMP_DIR="$HOME/.gitleaks-verify"
mkdir -p "$GITLEAKS_TEMP_DIR"

# Generate unique temporary filename (security: avoid fixed names to prevent race conditions)
# Use timestamp + random number for uniqueness (cross-platform, no external dependencies)
TEMP_FILE="$GITLEAKS_TEMP_DIR/session-verify-$(date +%s)-${RANDOM}.md"
TEMP_FILE_BASENAME=$(basename "$TEMP_FILE")

# Create temporary file with session content
cat > "$TEMP_FILE" << 'EOF'
[PASTE YOUR SESSION CONTENT HERE - REDACTED OR NOT]
EOF

# Option A: Try podman
if command -v podman &>/dev/null; then
  echo "✓ Using podman for gitleaks verification"
  GITLEAKS_OUTPUT=$(podman run --rm -v "$GITLEAKS_TEMP_DIR:/scan:Z" ghcr.io/gitleaks/gitleaks:latest \
    detect --no-git --source "/scan/$TEMP_FILE_BASENAME" --verbose 2>&1)
  GITLEAKS_RESULT=$?

# Option B: Try docker
elif command -v docker &>/dev/null; then
  echo "✓ Using docker for gitleaks verification"
  GITLEAKS_OUTPUT=$(docker run --rm -v "$GITLEAKS_TEMP_DIR:/scan:Z" ghcr.io/gitleaks/gitleaks:latest \
    detect --no-git --source "/scan/$TEMP_FILE_BASENAME" --verbose 2>&1)
  GITLEAKS_RESULT=$?

# Option C: Try gitleaks binary
elif command -v gitleaks &>/dev/null; then
  echo "✓ Using gitleaks binary for verification"
  GITLEAKS_OUTPUT=$(gitleaks detect --no-git --source "$TEMP_FILE" --verbose 2>&1)
  GITLEAKS_RESULT=$?

# Option D: No tool available
else
  GITLEAKS_RESULT="NO_TOOL"
fi

# Clean up temporary file
rm -f "$TEMP_FILE"

# Process results and set warning flags
SECURITY_WARNING_HEADER=""
SECURITY_WARNING_FOOTER=""

if [ "$GITLEAKS_RESULT" = "NO_TOOL" ]; then
  # No verification tool available
  echo ""
  echo "=========================================="
  echo "⚠️  WARNING: UNABLE TO VERIFY WITH GITLEAKS"
  echo "=========================================="
  echo ""
  echo "Reason: podman, docker, and gitleaks are not available"
  echo ""
  echo "⚠️  SESSION FILE WILL BE SAVED WITHOUT VERIFICATION"
  echo ""
  echo "This means potential secrets (API keys, tokens, passwords) cannot be detected automatically."
  echo ""
  echo "📝 RECOMMENDED ACTIONS:"
  echo "  1. Install verification tools:"
  echo "     Podman/Docker (preferred):"
  echo "       - macOS: brew install podman"
  echo "       - Linux (RHEL/Fedora): sudo dnf install podman"
  echo "       - Linux (Ubuntu/Debian): sudo apt-get install podman"
  echo "       - Or install Docker: https://docs.docker.com/get-docker/"
  echo "     Gitleaks:"
  echo "       - /utils:install-gitleaks (if utils plugin installed)"
  echo "       - Manual: https://github.com/gitleaks/gitleaks#installation"
  echo "  2. After install, manually run: gitleaks detect --no-git --source <session-file>"
  echo "  3. Manually review the session file for sensitive information"
  echo ""
  echo "Proceeding to save file WITHOUT verification..."
  echo "=========================================="
  echo ""

  SECURITY_WARNING_HEADER="<!--
⚠️ VERIFICATION WARNING ⚠️
This session file was saved WITHOUT gitleaks verification.
Gitleaks was not available at save time (podman/docker/gitleaks not found).
MANUALLY REVIEW this file for sensitive information before sharing or committing.
-->"

elif [ $GITLEAKS_RESULT -eq 0 ]; then
  # Verification passed - no secrets detected
  echo ""
  echo "=========================================="
  echo "✅ GITLEAKS VERIFICATION PASSED"
  echo "=========================================="
  echo ""
  echo "No secrets detected in session content."
  echo "Safe to proceed with saving the file."
  echo ""

else
  # Verification failed - secrets detected
  echo ""
  echo "=========================================="
  echo "⚠️⚠️⚠️  CRITICAL WARNING: SENSITIVE INFORMATION DETECTED  ⚠️⚠️⚠️"
  echo "=========================================="
  echo ""
  echo "Gitleaks found potential secrets in the session content:"
  echo ""
  echo "$GITLEAKS_OUTPUT"
  echo ""
  echo "=========================================="
  echo "🔴 THE SESSION FILE WILL STILL BE SAVED"
  echo "=========================================="
  echo ""
  echo "⚠️  SECURITY RISK: The saved file may contain:"
  echo "  - API keys, tokens, passwords"
  echo "  - Private keys or certificates"
  echo "  - Webhook URLs with tokens"
  echo "  - Database credentials"
  echo "  - Authentication tokens"
  echo ""
  echo "📝 REQUIRED ACTIONS AFTER SAVE:"
  echo "  1. Open the saved session file immediately"
  echo "  2. Locate and review the secrets identified above"
  echo "  3. Manually redact all sensitive information"
  echo "  4. Save the redacted version"
  echo "  5. Re-run gitleaks to verify: gitleaks detect --no-git --source <session-file>"
  echo ""
  echo "⚠️  DO NOT commit this file to git or share it until secrets are removed!"
  echo ""
  echo "Proceeding to save file WITH SECURITY WARNING markers..."
  echo "=========================================="
  echo ""

  SECURITY_WARNING_HEADER="<!--
⚠️⚠️⚠️ SECURITY WARNING ⚠️⚠️⚠️
This session file contains SENSITIVE INFORMATION detected by gitleaks.
DO NOT commit to git or share until you have manually reviewed and redacted all secrets.
Gitleaks detection results are included at the end of this file.
-->"

  SECURITY_WARNING_FOOTER="

---

## ⚠️ GITLEAKS DETECTION RESULTS ⚠️

The following sensitive information was detected in this session file:

\`\`\`
$GITLEAKS_OUTPUT
\`\`\`

**REQUIRED ACTIONS:**
1. Review each finding above
2. Locate the secrets in this file
3. Redact them with placeholders like [REDACTED_API_KEY]
4. Save the file
5. Re-run gitleaks to verify all secrets are removed:
   \`\`\`
   gitleaks detect --no-git --source <this-file>
   \`\`\`

**DO NOT ignore this warning. Exposing secrets can lead to security breaches.**
"
fi
```

**Result Handling:**

The verification result is stored in variables that will be used when writing the file:

- `SECURITY_WARNING_HEADER`: Added at the top of the file (after metadata) if secrets detected or verification unavailable
- `SECURITY_WARNING_FOOTER`: Added at the bottom of the file if secrets detected (includes full gitleaks output)

**Key Behavior:**
- ✅ **Exit code 0**: Clean file, no warnings added
- ⚠️ **Exit code 1**: Secrets detected, prominent warnings added to file, but file is still saved
- ⚠️ **No tool available**: Warning added to file about missing verification, file is still saved
- ⚠️ **Execution error**: Treated same as "no tool available", file is still saved

**The session file is ALWAYS saved regardless of gitleaks result.**

---

#### Step 4: Final Security Checklist and File Preparation

Before proceeding to Phase 3 (file write), verify and prepare:

**Mandatory checks for ALL sessions:**
- ✅ Step 0: Performed quick pre-scan to determine workflow
- ✅ Step 3: Executed gitleaks verification (result captured in variables)

**Conditional checks (if sensitive info detected):**
- ✅ Step 1-2: If `SENSITIVE_FOUND = true`, checked for comprehensive skill AND performed manual redaction
- ✅ Step 1-2: If `SENSITIVE_FOUND = false`, skipped Step 1-2 (no manual redaction needed)

**File preparation based on gitleaks result:**

1. **If gitleaks passed (exit code 0)**:
   - No security warnings will be added to file
   - Proceed to Phase 3 to write clean file

2. **If gitleaks detected secrets (exit code 1)**:
   - `SECURITY_WARNING_HEADER` will be inserted after metadata
   - `SECURITY_WARNING_FOOTER` will be appended at end of file
   - User will see prominent terminal warnings
   - File will still be saved with warning markers

3. **If gitleaks unavailable or failed**:
   - `SECURITY_WARNING_HEADER` will be inserted after metadata
   - Indicates file was saved without verification
   - File will still be saved with warning marker

**Workflow Summary**:
- **Clean content, verified**: Step 0 → Step 3 (exit 0) → Write clean file ✓
- **Clean content, unverified**: Step 0 → Step 3 (no tool) → Write file with verification warning ✓
- **Sensitive content, verified clean after redaction**: Step 0 → Step 1-2 → Step 3 (exit 0) → Write clean file ✓
- **Sensitive content, still contains secrets**: Step 0 → Step 1-2 → Step 3 (exit 1) → Write file with security warnings ✓

**Important**: Regardless of gitleaks result, Phase 3 will ALWAYS proceed to save the file. The only difference is whether security warning markers are included.

---

**Why This Approach:**

- **Optimized Workflow**: Pre-scan (Step 0) skips unnecessary manual work for clean content
- **Always Verified**: Gitleaks runs on ALL sessions regardless of pre-scan results (defense in depth)
- **Manual Redaction When Needed**: Only perform manual work when sensitive info detected
- **Progressive Enhancement**: Uses comprehensive skill if available, falls back to simplified version
- **No Hard Dependencies**: Works with podman/docker (no installation) or gitleaks binary
- **User Transparency**: Clear warnings when verification unavailable
- **Security First**: Blocks file write if secrets detected, comprehensive detection via gitleaks

### Phase 2: File Modification Tracking
- Reads and verifies current state of modified files
- Lists specific line numbers and code changes
- Includes before/after comparisons for critical changes
- Notes which files were created vs modified vs deleted
- Tracks any generated files (like bindata)

### Phase 3: Session File Creation or Update

**🔒 SECURITY CHECKPOINT: Before proceeding to file write**

**STOP AND VERIFY Phase 1.5 completion:**

**MANDATORY for ALL sessions:**
1. ✅ Phase 1.5 Step 0: Performed quick pre-scan
2. ✅ Phase 1.5 Step 3: Executed gitleaks verification (result captured)
3. ✅ Phase 1.5 Step 4: Security warnings prepared based on gitleaks result

**Conditional checks (if sensitive info was detected in Step 0):**
4. ✅ Phase 1.5 Step 1: Checked for comprehensive redaction skill
5. ✅ Phase 1.5 Step 2: Performed manual redaction

**File write preparation:**
- `SECURITY_WARNING_HEADER` variable is set (empty if clean, warning text if issues)
- `SECURITY_WARNING_FOOTER` variable is set (empty if clean, gitleaks results if secrets found)

**Proceed to file write:**
- **The file will ALWAYS be written**, regardless of gitleaks result
- Warning markers from Step 3 will be included in the file if needed
- User has already been shown terminal warnings during Step 3

**Key principle**: Never block the save operation. Let users save their work, but warn them about security risks.

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

Creates a comprehensive Markdown document with session tracking metadata:

```markdown
<!--
SESSION_METADATA (Do not edit manually)
session_id: YYYY-MM-DD-HHMMSS
started_at: YYYY-MM-DD HH:MM:SS TIMEZONE (YYYY-MM-DD HH:MM:SS UTC)
last_updated: YYYY-MM-DD HH:MM:SS TIMEZONE (YYYY-MM-DD HH:MM:SS UTC)
update_count: 1
-->

[INSERT $SECURITY_WARNING_HEADER HERE IF NOT EMPTY]

# Session: [Title]
**Date**: YYYY-MM-DD
**Last Updated**: YYYY-MM-DD HH:MM:SS TIMEZONE
```

**IMPORTANT: Security Warning Insertion**
- If `$SECURITY_WARNING_HEADER` is not empty, insert it immediately after the metadata comment block
- This header warns users if gitleaks detected secrets or if verification was unavailable
- Example placement:
  ```markdown
  <!--
  SESSION_METADATA (Do not edit manually)
  ...
  -->

  <!--
  ⚠️⚠️⚠️ SECURITY WARNING ⚠️⚠️⚠️
  This session file contains SENSITIVE INFORMATION detected by gitleaks.
  ...
  -->

  # Session: [Title]
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

**IMPORTANT: Security Warning Footer**
- At the END of the entire file, append `$SECURITY_WARNING_FOOTER` if not empty
- This footer contains the full gitleaks output when secrets were detected
- Provides users with specific locations and types of secrets found
- Example:
  ```markdown
  ... (end of regular content)

  ---

  ## ⚠️ GITLEAKS DETECTION RESULTS ⚠️

  The following sensitive information was detected in this session file:

  ```
  Finding: API_KEY = "sk_live_..."
  Secret: sk_live_...
  RuleID: generic-api-key
  Line: 142
  ```markdown

  **REQUIRED ACTIONS:**
  1. Review each finding above
  2. Locate the secrets in this file
  ...
  ```

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
```text
✅ New session created successfully!

File: session-YYYY-MM-DD-description.md (XX KB)
Location: /full/path/to/file
Session ID: YYYY-MM-DD-HHMMSS

📖 To resume this session:
   Please read `/full/path/to/session-YYYY-MM-DD-description.md` and continue from where we left off
```

**UPDATE mode** updates the existing session file found in current directory.

Terminal output for UPDATE:
```text
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
```bash
/save-session
```
**Result:** Creates `session-2025-10-22-143000.md` with metadata tracking

### Example 2: Continuing Work and Updating (No Description)
```bash
# Work for 30 minutes, then save progress
/save-session

# Continue working for another hour
/save-session
```
**Result:**
- First call creates `session-2025-10-22-143000.md` (Write tool called)
- Second call detects Write tool was used to create session file → updates the same file (adds Update #2 section)

### Example 3: Starting a New Branch (With Description)
```bash
# Working on feature A
/save-session

# Decide to work on feature B
/save-session feature-b-implementation
```
**Result:**
- First call creates `session-2025-10-22-143000.md`
- Second call creates NEW file `session-2025-10-22-feature-b-implementation.md` (description provided = new session)

### Example 4: Multiple Save Points in One Session
```bash
/save-session                    # Create: session-2025-10-22-143000.md
# ... work for 1 hour ...
/save-session                    # Update: session-2025-10-22-143000.md (Update #2)
# ... work for 2 hours ...
/save-session                    # Update: session-2025-10-22-143000.md (Update #3)
```

### Example 5: Named Session with Updates
```bash
/save-session bug-fix-ocpbugs-12345    # Create new named session
# ... fix part 1 ...
/save-session                          # Update same session
# ... fix part 2 ...
/save-session                          # Update same session again
```
**Result:** `session-2025-10-22-bug-fix-ocpbugs-12345.md` with 3 update sections

### Example 6: With Spaces and Special Characters
```bash
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
```json
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
