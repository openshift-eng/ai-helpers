---
description: New hire onboarding - verify setup and get started
---

## Name

onboarding:start

## Synopsis

```
/onboarding:start
```

## Description

The `onboarding:start` command helps new hires in OpenShift engineering understand the **general OpenShift knowledge base** and automation tools available to all teams.

**Important Context:**
- OpenShift has dozens of teams, each with their own repositories
- This command focuses on **general OpenShift knowledge**, not team-specific repos
- Your team will have its own onboarding for team-specific repositories and workflows
- The repos checked here (ai-helpers, enhancements) are useful for **all teams**

This command helps you understand:
- How to use `ai-helpers` for general automation (JIRA, CI, component health)
- How to access `enhancements` for general OpenShift architecture and processes
- What general automation tools are available across all teams
- Where to find information about OpenShift design decisions and features

## Implementation

1. **Check Current Directory**

   - Verify we're in the ai-helpers repo
   - Get the absolute path to use as reference point

2. **Search for enhancements Repository**

   Check common locations where the `openshift/enhancements` repo might be:

   ```bash
   # Common sibling locations
   ENHANCEMENTS_PATHS=(
     "../enhancements"
     "../openshift-enhancements"
     "../../enhancements"
     "../../openshift/enhancements"
     "$HOME/go/src/github.com/openshift/enhancements"
     "$HOME/src/openshift/enhancements"
   )

   ENHANCEMENTS_FOUND=false
   ENHANCEMENTS_PATH=""

   for path in "${ENHANCEMENTS_PATHS[@]}"; do
     if [ -d "$path" ]; then
       ENHANCEMENTS_FOUND=true
       ENHANCEMENTS_PATH=$(cd "$path" && pwd)
       break
     fi
   done
   ```

3. **Check Environment Variables**

   Verify critical environment variables are set:

   ```bash
   # Check JIRA credentials
   if [ -z "$JIRA_URL" ]; then
     JIRA_CONFIGURED=false
   elif [ -z "$JIRA_PERSONAL_TOKEN" ]; then
     JIRA_CONFIGURED=false
   else
     JIRA_CONFIGURED=true
   fi
   ```

4. **Present Setup Status**

   **If enhancements repo found:**

   ```
   ═══════════════════════════════════════════════════════════════
   ✅ GENERAL OPENSHIFT RESOURCES DETECTED
   ═══════════════════════════════════════════════════════════════

   📁 General Repositories (for all OpenShift teams):

   🤖 ai-helpers (current)
      Purpose: General automation tools
      Use for: JIRA, CI analysis, component health tracking

   📚 enhancements (detected)
      Purpose: General OpenShift architecture knowledge
      Location: $ENHANCEMENTS_PATH
      Use for: Understanding features, design decisions, processes

   ═══════════════════════════════════════════════════════════════
   💡 GENERAL AUTOMATION TOOLS (all teams)
   ═══════════════════════════════════════════════════════════════

   /jira:create - Create JIRA issues
   /jira:solve - Auto-analyze and solve JIRA issues
   /component-health:summarize-jiras - View bug metrics
   /prow-job:analyze-test-failure - Debug CI failures
   /ci:ask-sippy - Query CI test data
   /onboarding:search <topic> - Search general OpenShift docs

   📚 To explore enhancements:
   cd $ENHANCEMENTS_PATH && code . --new-window

   ═══════════════════════════════════════════════════════════════
   ⚠️  TEAM-SPECIFIC ONBOARDING
   ═══════════════════════════════════════════════════════════════

   These are GENERAL resources for all teams. OpenShift has dozens
   of teams, each with their own repos and onboarding.

   Your team likely has:
   - Component-specific repos (operators, controllers, etc.)
   - Team documentation and runbooks
   - Team-specific tools

   👉 Ask your manager/team lead about team-specific repos!

   ═══════════════════════════════════════════════════════════════
   ```

   **If enhancements repo NOT found:**

   ```
   ═══════════════════════════════════════════════════════════════
   📚 GENERAL OPENSHIFT RESOURCES
   ═══════════════════════════════════════════════════════════════

   ✅ ai-helpers (current) - General automation tools
   📚 enhancements (optional) - General OpenShift knowledge

   ═══════════════════════════════════════════════════════════════
   💡 ABOUT THE ENHANCEMENTS REPO
   ═══════════════════════════════════════════════════════════════

   The openshift/enhancements repo contains GENERAL OpenShift
   knowledge useful for all teams:

   ✅ Enhancement proposals (KEPs): How features are designed
   ✅ Architecture docs: How components work together
   ✅ Process docs: How the project operates
   ✅ Historical context: Why decisions were made

   This helps you understand OpenShift as a whole, regardless
   of which team you're on.

   🔧 Add It For Enhanced Learning (optional):

   # Clone as sibling (recommended)
   cd .. && git clone https://github.com/openshift/enhancements.git

   # Or clone to go workspace
   mkdir -p ~/go/src/github.com/openshift
   cd ~/go/src/github.com/openshift
   git clone https://github.com/openshift/enhancements.git

   Then run /onboarding:start again!

   ═══════════════════════════════════════════════════════════════
   🤖 GENERAL AUTOMATION AVAILABLE NOW
   ═══════════════════════════════════════════════════════════════

   /jira:create - Create JIRA issues
   /component-health:summarize-jiras - View bug metrics
   /prow-job:analyze-test-failure - Debug CI failures
   /ci:ask-sippy - Query CI test data

   ═══════════════════════════════════════════════════════════════
   ⚠️  TEAM-SPECIFIC ONBOARDING
   ═══════════════════════════════════════════════════════════════

   Remember: This is just GENERAL OpenShift knowledge!

   OpenShift has dozens of teams, each with their own:
   - Component repositories
   - Team documentation
   - Specific onboarding processes

   👉 Ask your manager/team lead about team-specific repos!

   ═══════════════════════════════════════════════════════════════
   ```

5. **Check JIRA Configuration**

   If JIRA not configured:

   ```
   ⚠️  JIRA Not Configured

   Many commands require JIRA credentials. Set these:

   export JIRA_URL="https://issues.redhat.com"
   export JIRA_PERSONAL_TOKEN="your-token-here"

   Get your token:
   1. Go to https://issues.redhat.com
   2. Profile → Personal Access Tokens
   3. Generate new token
   4. Add to your ~/.bashrc or ~/.zshrc
   ```

6. **List Available Commands**

   Show all available slash commands by plugin:

   - JIRA automation: /jira:*
   - CI analysis: /ci:*, /prow-job:*
   - Component health: /component-health:*
   - Documentation: /doc:*, /onboarding:*
   - Utilities: /utils:*

7. **Provide Next Steps**

   ```
   🚀 Next Steps:

   📚 General OpenShift Learning:
   1. (Optional) Clone enhancements for general knowledge:
      cd .. && git clone https://github.com/openshift/enhancements.git

   2. Try general automation commands:
      /component-health:summarize-jiras OCPBUGS --component "kube-apiserver"
      /onboarding:search "topic you're learning about"
      /ci:ask-sippy "test failure trends"

   3. Configure JIRA credentials if needed:
      export JIRA_URL="https://issues.redhat.com"
      export JIRA_PERSONAL_TOKEN="your-token"

   4. Explore general OpenShift architecture (if enhancements cloned):
      cd $ENHANCEMENTS_PATH && code . --new-window

   ⚠️  IMPORTANT - Team-Specific Onboarding:
   👉 Ask your manager or team lead about:
      - Your team's specific repositories
      - Team onboarding documentation
      - Team-specific tools and workflows
      - Which components your team owns

   📖 General Documentation:
   - ai-helpers README: ./README.md
   - Plugin docs: ./plugins/*/README.md
   - Enhancements: https://github.com/openshift/enhancements
   ```

## Return Value

The command outputs a **Setup Status Report** including:

- ✅/❌ Repository detection status
- 📁 Repository locations if found
- ⚠️ Missing components with clone instructions
- 🔧 Environment variable status
- 📝 List of available commands
- 🚀 Recommended next steps

## Examples

1. **First time setup check**:

   ```
   /onboarding:start
   ```

   Checks your environment and provides personalized setup guidance.

2. **After cloning enhancements**:

   ```
   /onboarding:start
   ```

   Verifies the enhancements repo is now detected and shows full capabilities.

## Arguments

This command takes no arguments.

## Prerequisites

None - this command is designed to be the very first command a new hire runs.

## Notes

- This command is idempotent - safe to run multiple times
- It doesn't modify your system, only checks and reports
- The search paths are hardcoded but cover most common clone locations
- If enhancements repo is in an unusual location, consider symlinking it to a standard path

## See Also

- Skill Documentation: `plugins/onboarding/skills/start/SKILL.md`
- Related Command: `/onboarding:search` (for searching documentation across repos)
- Main README: `README.md` (for detailed setup instructions)
- Enhancements README: `../enhancements/README.md` (if cloned)
