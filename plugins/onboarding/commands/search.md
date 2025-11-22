---
description: Search documentation across ai-helpers and enhancements repositories
argument-hint: <search-term>
---

## Name

onboarding:search

## Synopsis

```
/onboarding:search <search-term>
```

## Description

The `onboarding:search` command searches for **general OpenShift documentation** across the `ai-helpers` (automation tools) and `openshift/enhancements` (architecture/design knowledge) repositories.

**Important Context:**
- This searches GENERAL OpenShift knowledge, not team-specific repos
- Useful for understanding OpenShift architecture, features, and processes
- Does NOT search your team's component repositories
- For team-specific documentation, search within your team's repos

This command is especially useful for:
- Finding enhancement proposals (KEPs) about OpenShift features
- Understanding how general OpenShift components work
- Learning OpenShift architecture and design decisions
- Finding general automation tools available to all teams
- Discovering general process documentation

The search prioritizes:
1. Enhancement proposals (KEPs) - General OpenShift design docs
2. General automation tools and commands
3. README files and general documentation
4. Process documentation applicable to all teams

## Implementation

1. **Validate Search Term**

   - Ensure search term is provided
   - Clean and normalize the search term

2. **Detect Repository Locations**

   ```bash
   # Check for enhancements repo
   ENHANCEMENTS_PATHS=(
     "../enhancements"
     "../openshift-enhancements"
     "../../enhancements"
     "../../openshift/enhancements"
     "$HOME/go/src/github.com/openshift/enhancements"
     "$HOME/src/openshift/enhancements"
   )

   ENHANCEMENTS_PATH=""
   for path in "${ENHANCEMENTS_PATHS[@]}"; do
     if [ -d "$path" ]; then
       ENHANCEMENTS_PATH=$(cd "$path" && pwd)
       break
     fi
   done

   # ai-helpers is current directory
   AI_HELPERS_PATH=$(pwd)
   ```

3. **Search ai-helpers Repository**

   Search markdown files in the current repo:

   ```bash
   echo "🔍 Searching ai-helpers (automation)..." >&2

   # Search with grep, prioritizing documentation
   AI_HELPERS_RESULTS=$(grep -r -i "$SEARCH_TERM" \
     --include="*.md" \
     --include="README.md" \
     --exclude-dir=".git" \
     --exclude-dir="node_modules" \
     -n -H \
     . 2>/dev/null)
   ```

4. **Search enhancements Repository (if available)**

   Search enhancement proposals and documentation:

   ```bash
   if [ -n "$ENHANCEMENTS_PATH" ]; then
     echo "🔍 Searching enhancements (technical knowledge)..." >&2

     # Search enhancements repo
     ENHANCEMENTS_RESULTS=$(grep -r -i "$SEARCH_TERM" \
       --include="*.md" \
       --exclude-dir=".git" \
       -n -H \
       "$ENHANCEMENTS_PATH" 2>/dev/null)
   fi
   ```

5. **Categorize and Prioritize Results**

   Group results by type:

   - **Enhancement Proposals**: Files in `enhancements/enhancements/` directory
   - **Documentation**: README files and docs directories
   - **Commands**: Command definition files
   - **Skills**: Implementation guides
   - **Other**: Additional relevant files

6. **Present Results**

   **If enhancements repo available:**

   ```
   ═══════════════════════════════════════════════════════════════
   🔍 SEARCH RESULTS FOR: "<search-term>"
   ═══════════════════════════════════════════════════════════════

   📚 ENHANCEMENT PROPOSALS (enhancements repo)

   Found 3 enhancement proposals:

   1. Network Observability
      File: enhancements/enhancements/network/network-observability.md
      Match: "network observability provides insights into..."
      Open: cd /path/to/enhancements && code enhancements/enhancements/network/network-observability.md

   2. Cluster Network Operator
      File: enhancements/enhancements/network/cluster-network-operator.md
      Match: "CNO manages the network configuration..."
      Open: cd /path/to/enhancements && code enhancements/enhancements/network/cluster-network-operator.md

   ─────────────────────────────────────────────────────────────

   🤖 AUTOMATION & TOOLS (ai-helpers repo)

   Found 2 relevant automation tools:

   1. Component Health Analysis
      File: plugins/component-health/README.md
      Match: "Track component health across releases..."
      Command: /component-health:summarize-jiras

   2. Prow Job Analysis
      File: plugins/prow-job/commands/analyze-test-failure.md
      Match: "Analyze test failures in CI jobs..."
      Command: /prow-job:analyze-test-failure

   ─────────────────────────────────────────────────────────────

   💡 SUGGESTIONS

   📖 Deep Dive (enhancements):
      Open enhancements repo to read full KEPs:
      cd /path/to/enhancements && code . --new-window

   🤖 Try Commands (ai-helpers):
      /component-health:summarize-jiras OCPBUGS --component "your-component"
      /prow-job:analyze-test-failure <prowjob-url> <test-name>

   🔍 Refine Search:
      /onboarding:search "<more-specific-term>"

   ═══════════════════════════════════════════════════════════════
   ```

   **If enhancements repo NOT available:**

   ```
   ═══════════════════════════════════════════════════════════════
   🔍 SEARCH RESULTS FOR: "<search-term>"
   ═══════════════════════════════════════════════════════════════

   🤖 AUTOMATION & TOOLS (ai-helpers repo only)

   Found 2 results:

   1. Component Health Analysis
      File: plugins/component-health/README.md
      Match: "Track component health across releases..."

   2. JIRA Automation
      File: plugins/jira/commands/create.md
      Match: "Create JIRA issues with proper formatting..."

   ─────────────────────────────────────────────────────────────

   ⚠️  LIMITED SEARCH - MISSING ENHANCEMENTS REPO

   You're only searching ai-helpers (automation).
   For complete results including technical documentation and KEPs:

   1. Clone the enhancements repo:
      cd .. && git clone https://github.com/openshift/enhancements.git

   2. Run search again:
      /onboarding:search "<search-term>"

   The enhancements repo contains:
   - Enhancement proposals (KEPs) for all features
   - Architecture documentation
   - Design decisions and rationale
   - Process documentation

   ═══════════════════════════════════════════════════════════════
   ```

7. **Handle No Results**

   ```
   ═══════════════════════════════════════════════════════════════
   🔍 SEARCH RESULTS FOR: "<search-term>"
   ═══════════════════════════════════════════════════════════════

   ❌ No results found in ai-helpers

   💡 SUGGESTIONS

   1. Try a different search term:
      /onboarding:search "<alternative-term>"

   2. Try broader terms:
      - Component name instead of full feature name
      - Technology instead of implementation detail

   3. If looking for technical specs:
      Clone enhancements repo for complete documentation:
      cd .. && git clone https://github.com/openshift/enhancements.git

   4. Ask Claude directly:
      "Explain how <search-term> works in OpenShift"

   ═══════════════════════════════════════════════════════════════
   ```

## Return Value

The command outputs **Search Results** organized by repository and document type:

### Enhancement Proposals Section
- Lists matching KEPs from the enhancements repo
- Shows file path and relevant excerpt
- Provides command to open the file

### Automation Tools Section
- Lists matching commands and tools from ai-helpers
- Shows relevant slash commands
- Provides usage examples

### Suggestions Section
- Next steps based on results
- Commands to try
- Ways to refine the search

## Examples

1. **Search for networking documentation**:

   ```
   /onboarding:search networking
   ```

   Finds all enhancement proposals, commands, and docs related to networking.

2. **Find authentication information**:

   ```
   /onboarding:search authentication
   ```

   Searches for auth-related KEPs and automation tools.

3. **Look up a specific component**:

   ```
   /onboarding:search kube-apiserver
   ```

   Finds KEPs and tools related to kube-apiserver.

4. **Search for process documentation**:

   ```
   /onboarding:search "code review"
   ```

   Finds process docs (quote multi-word terms).

## Arguments

- `$1` (required): Search term
  - Can be a single word or quoted phrase
  - Case-insensitive
  - Searches file content, not just filenames
  - Examples: `networking`, `"code review"`, `kube-apiserver`

## Prerequisites

1. **ai-helpers repo**: You're already in it (current directory)

2. **enhancements repo** (optional but recommended):
   - Provides access to KEPs and technical documentation
   - If missing, only searches ai-helpers
   - Clone with: `git clone https://github.com/openshift/enhancements.git ../enhancements`

3. **grep**: Should be available on all Unix-like systems

## Notes

- The search is case-insensitive for better results
- Results are prioritized by relevance and document type
- Only searches markdown files to focus on documentation
- The enhancements repo is optional but highly recommended
- Search results show context excerpts for quick scanning
- For deep exploration, the command suggests opening files in Claude Code
- Multi-word search terms should be quoted

## See Also

- Skill Documentation: `plugins/onboarding/skills/search/SKILL.md`
- Related Command: `/onboarding:start` (for setup verification)
- Enhancements repo: https://github.com/openshift/enhancements
