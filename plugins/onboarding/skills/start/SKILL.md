---
name: Onboarding Start
description: Verify multi-repo setup and guide new hires through environment configuration
---

# Onboarding Start

This skill provides a comprehensive environment check for new hires, detecting the presence of companion repositories and guiding users through proper setup of the OpenShift engineering toolchain.

## When to Use This Skill

Use this skill when:
- A new hire runs their first command in ai-helpers
- You need to verify the multi-repo setup
- Someone asks "how do I get started?"
- Checking if environment variables are properly configured
- Providing guidance on navigation between ai-helpers and enhancements

## Prerequisites

None - this is designed to be the first thing new hires run.

## Implementation Steps

### Step 1: Detect enhancements Repository

Search for the `openshift/enhancements` repository in common locations:

```bash
#!/bin/bash

# Define search paths
ENHANCEMENTS_PATHS=(
  "../enhancements"
  "../openshift-enhancements"
  "../../enhancements"
  "../../openshift/enhancements"
  "$HOME/go/src/github.com/openshift/enhancements"
  "$HOME/src/openshift/enhancements"
  "$HOME/openshift/enhancements"
)

ENHANCEMENTS_FOUND=false
ENHANCEMENTS_PATH=""

echo "🔍 Searching for openshift/enhancements repository..." >&2

for path in "${ENHANCEMENTS_PATHS[@]}"; do
  if [ -d "$path" ]; then
    # Verify it's actually the enhancements repo
    if [ -d "$path/enhancements" ] || [ -f "$path/README.md" ]; then
      ENHANCEMENTS_FOUND=true
      ENHANCEMENTS_PATH=$(cd "$path" && pwd)
      echo "✅ Found enhancements at: $ENHANCEMENTS_PATH" >&2
      break
    fi
  fi
done

if [ "$ENHANCEMENTS_FOUND" = false ]; then
  echo "❌ enhancements repository not found" >&2
fi
```

### Step 2: Check Environment Variables

Verify critical environment variables:

```bash
#!/bin/bash

echo "🔧 Checking environment configuration..." >&2

# Check JIRA configuration
ENV_STATUS="complete"

if [ -z "$JIRA_URL" ]; then
  echo "⚠️  JIRA_URL not set" >&2
  ENV_STATUS="incomplete"
else
  echo "✅ JIRA_URL: $JIRA_URL" >&2
fi

if [ -z "$JIRA_PERSONAL_TOKEN" ]; then
  echo "⚠️  JIRA_PERSONAL_TOKEN not set" >&2
  ENV_STATUS="incomplete"
else
  echo "✅ JIRA_PERSONAL_TOKEN: ***configured***" >&2
fi

# Could add more checks here for other env vars
```

### Step 3: Generate Setup Report

Create a comprehensive report based on findings:

**If Complete Setup (enhancements found + env vars set):**

```
═══════════════════════════════════════════════════════════════
🎉 COMPLETE SETUP DETECTED - YOU'RE READY TO GO!
═══════════════════════════════════════════════════════════════

📁 REPOSITORY STRUCTURE
├─ 🤖 ai-helpers (current)
│  └─ Location: /Users/you/go/src/github.com/openshift-eng/ai-helpers
│  └─ Purpose: Claude Code automation, workflows, slash commands
│
└─ 📚 enhancements (detected)
   └─ Location: /Users/you/go/src/github.com/openshift/enhancements
   └─ Purpose: Technical specs, KEPs, architecture docs, processes

═══════════════════════════════════════════════════════════════
💡 HOW TO USE THIS SETUP
═══════════════════════════════════════════════════════════════

📍 YOU ARE HERE (ai-helpers):
Use this repo for automation and quick tasks:

  🎫 JIRA Automation:
     /jira:create <type> <project> <summary>
     /jira:solve <issue-key>
     /jira:status-rollup <epic-key>

  🔍 Component Health:
     /component-health:summarize-jiras <project> --component <name>
     /component-health:analyze-regressions <release>

  🧪 CI Analysis:
     /prow-job:analyze-test-failure <prowjob-url> <test-name>
     /ci:ask-sippy <question>

📚 ENHANCEMENTS REPO (for deep learning):
When you need to understand HOW something works:

  1. Open in new Claude Code window:
     cd /Users/you/go/src/github.com/openshift/enhancements
     code . --new-window

  2. Ask Claude questions like:
     - "Explain the kube-apiserver enhancement proposals"
     - "What's the architecture of HyperShift?"
     - "Show me all enhancements related to networking"

  3. Search enhancements from here:
     /onboarding:search <topic>

═══════════════════════════════════════════════════════════════
🔧 ENVIRONMENT CONFIGURATION
═══════════════════════════════════════════════════════════════

✅ JIRA_URL: https://issues.redhat.com
✅ JIRA_PERSONAL_TOKEN: ***configured***

═══════════════════════════════════════════════════════════════
🚀 RECOMMENDED NEXT STEPS
═══════════════════════════════════════════════════════════════

1. Try your first automation command:
   /component-health:summarize-jiras OCPBUGS --component "<your-team-component>"

2. Explore available commands:
   Type / to see all available slash commands

3. Deep dive into a technical topic:
   Open enhancements repo and ask Claude about specific KEPs

4. Create your first JIRA:
   /jira:create task OCPBUGS "My first automated JIRA"

═══════════════════════════════════════════════════════════════
📖 HELPFUL RESOURCES
═══════════════════════════════════════════════════════════════

- ai-helpers README: ./README.md
- Plugin documentation: ./plugins/<plugin-name>/README.md
- Enhancements README: /path/to/enhancements/README.md
- Team-specific guides: Ask your manager or buddy

═══════════════════════════════════════════════════════════════
```

**If Incomplete Setup (missing enhancements):**

```
═══════════════════════════════════════════════════════════════
⚠️  INCOMPLETE SETUP - ACTION REQUIRED
═══════════════════════════════════════════════════════════════

📋 SETUP STATUS

✅ ai-helpers (current repo)
   Location: /Users/you/go/src/github.com/openshift-eng/ai-helpers

❌ enhancements (NOT FOUND)
   This repo is ESSENTIAL for understanding OpenShift internals

═══════════════════════════════════════════════════════════════
📚 WHY YOU NEED openshift/enhancements
═══════════════════════════════════════════════════════════════

The enhancements repository contains:

✅ Enhancement Proposals (KEPs): Detailed specs for every feature
✅ Architecture Documentation: How systems are designed
✅ Process Documentation: Team workflows and procedures
✅ Historical Context: Why decisions were made
✅ API Changes: Evolution of OpenShift APIs
✅ Feature Gates: Understanding feature maturity

Without it, you'll struggle to understand:
- How features are implemented
- Why code is structured a certain way
- What the intended behavior should be
- Historical context for debugging

═══════════════════════════════════════════════════════════════
🔧 FIX THIS NOW (30 seconds)
═══════════════════════════════════════════════════════════════

Choose ONE option:

OPTION 1: Clone as sibling (recommended for most users)
  cd ..
  git clone https://github.com/openshift/enhancements.git

OPTION 2: Clone to Go workspace
  mkdir -p ~/go/src/github.com/openshift
  cd ~/go/src/github.com/openshift
  git clone https://github.com/openshift/enhancements.git

OPTION 3: Clone anywhere and symlink
  cd /your/preferred/location
  git clone https://github.com/openshift/enhancements.git
  ln -s /your/preferred/location/enhancements ~/go/src/github.com/openshift/enhancements

═══════════════════════════════════════════════════════════════
✅ AFTER CLONING
═══════════════════════════════════════════════════════════════

Run this command again to verify:
  /onboarding:start

═══════════════════════════════════════════════════════════════
🎯 AVAILABLE NOW (without enhancements)
═══════════════════════════════════════════════════════════════

You can still use automation commands:
  /jira:create
  /component-health:summarize-jiras
  /prow-job:analyze-test-failure

But you'll have limited ability to understand the codebase.

═══════════════════════════════════════════════════════════════
```

**If Environment Variables Missing:**

```
═══════════════════════════════════════════════════════════════
🔧 ENVIRONMENT CONFIGURATION NEEDED
═══════════════════════════════════════════════════════════════

⚠️  JIRA CREDENTIALS NOT CONFIGURED

Many automation commands require JIRA access. Set these now:

1. Get your JIRA Personal Access Token:
   - Go to: https://issues.redhat.com
   - Click your profile → Personal Access Tokens
   - Create new token with appropriate permissions
   - Copy the token

2. Add to your shell configuration:

   # For bash (~/.bashrc):
   echo 'export JIRA_URL="https://issues.redhat.com"' >> ~/.bashrc
   echo 'export JIRA_PERSONAL_TOKEN="your-token-here"' >> ~/.bashrc
   source ~/.bashrc

   # For zsh (~/.zshrc):
   echo 'export JIRA_URL="https://issues.redhat.com"' >> ~/.zshrc
   echo 'export JIRA_PERSONAL_TOKEN="your-token-here"' >> ~/.zshrc
   source ~/.zshrc

3. Verify:
   echo $JIRA_URL
   echo $JIRA_PERSONAL_TOKEN

Commands that require JIRA:
  ❌ /jira:* (all JIRA commands)
  ❌ /component-health:summarize-jiras
  ❌ /component-health:list-jiras

═══════════════════════════════════════════════════════════════
```

### Step 4: List Available Commands

Group commands by plugin and show their purpose:

```
═══════════════════════════════════════════════════════════════
📝 AVAILABLE SLASH COMMANDS
═══════════════════════════════════════════════════════════════

🎫 JIRA AUTOMATION (requires JIRA credentials)
   /jira:create - Create JIRA issues with proper formatting
   /jira:solve - Analyze and solve JIRA issues automatically
   /jira:status-rollup - Generate status reports for epics
   /jira:grooming - Generate grooming meeting agendas

🔍 COMPONENT HEALTH
   /component-health:summarize-jiras - Summary statistics by component
   /component-health:list-jiras - Raw JIRA data export
   /component-health:analyze-regressions - Grade component health

🧪 CI & TESTING
   /prow-job:analyze-test-failure - Debug test failures
   /prow-job:analyze-install-failure - Debug installation failures
   /ci:ask-sippy - Query CI test data
   /ci:trigger-periodic - Trigger CI jobs

📚 DOCUMENTATION & ONBOARDING
   /onboarding:start - This command (environment check)
   /onboarding:search - Search across repos (coming soon)

🛠️ UTILITIES
   /utils:generate-test-plan - Generate test plans
   /git:summary - Git commit summaries

Type any command for detailed help!

═══════════════════════════════════════════════════════════════
```

## Error Handling

This skill is designed to never error - it always provides helpful guidance:

1. **Repository not found**: Provide clone instructions
2. **Environment variables missing**: Provide setup instructions
3. **Multiple issues**: Prioritize and list all fixes needed
4. **Partial setup**: Acknowledge what works, guide toward completion

## Output Format

The output is designed to be:
- **Visually clear**: Using ASCII art separators and emojis
- **Actionable**: Every problem has a solution with exact commands
- **Prioritized**: Most important issues listed first
- **Encouraging**: Positive tone, celebrates what's working

## Related Skills

- `onboarding:search` - Search documentation across multiple repos
- Session management skills - for persisting configuration

## Notes

- This skill is idempotent - safe to run many times
- It never modifies the system, only reports status
- The pretty formatting uses standard terminal characters
- Paths are detected dynamically, not hardcoded
- The skill assumes a Unix-like environment (Linux, macOS)
