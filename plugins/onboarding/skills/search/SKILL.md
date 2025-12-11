---
name: Onboarding Search
description: Search documentation across ai-helpers and enhancements repositories intelligently
---

# Onboarding Search

This skill provides intelligent cross-repository documentation search, helping users find information across both automation tools (ai-helpers) and technical knowledge (openshift/enhancements) repositories.

## When to Use This Skill

Use this skill when:
- A user asks "how does X work?"
- Looking for enhancement proposals (KEPs) about a feature
- Finding documentation about a component or system
- Locating examples or implementation details
- New hires exploring the codebase
- Routing users to the right documentation

## Prerequisites

1. **ai-helpers repo**: Always available (current directory)
2. **enhancements repo** (optional): Provides enhanced search results
3. **grep**: Standard Unix tool (should be available)

## Implementation Steps

### Step 1: Validate and Normalize Search Term

```bash
#!/bin/bash

SEARCH_TERM="$1"

if [ -z "$SEARCH_TERM" ]; then
  echo "Error: Please provide a search term" >&2
  echo "Usage: /onboarding:search <search-term>" >&2
  exit 1
fi

# Clean the search term (remove extra quotes if present)
SEARCH_TERM=$(echo "$SEARCH_TERM" | sed 's/^["'\'']*//;s/["'\'']*$//')

echo "🔍 Searching for: $SEARCH_TERM" >&2
```

### Step 2: Detect Enhancements Repository

```bash
#!/bin/bash

# Search common locations
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
    # Verify it looks like the enhancements repo
    if [ -d "$path/enhancements" ] || [ -f "$path/README.md" ]; then
      ENHANCEMENTS_FOUND=true
      ENHANCEMENTS_PATH=$(cd "$path" && pwd)
      echo "✅ Enhancements repo found: $ENHANCEMENTS_PATH" >&2
      break
    fi
  fi
done

if [ "$ENHANCEMENTS_FOUND" = false ]; then
  echo "⚠️  Enhancements repo not found - search limited to ai-helpers" >&2
fi
```

### Step 3: Search ai-helpers Repository

```bash
#!/bin/bash

echo "🔍 Searching ai-helpers..." >&2

# Search markdown files in current repo
# Prioritize certain directories for better results
AI_HELPERS_RESULTS=$(grep -r -i "$SEARCH_TERM" \
  --include="*.md" \
  --exclude-dir=".git" \
  --exclude-dir="node_modules" \
  --exclude-dir=".work" \
  -n -H -m 1 \
  . 2>/dev/null)

# Count results
AI_HELPERS_COUNT=$(echo "$AI_HELPERS_RESULTS" | grep -c ":" || echo "0")
echo "Found $AI_HELPERS_COUNT matches in ai-helpers" >&2
```

### Step 4: Search Enhancements Repository

```bash
#!/bin/bash

if [ "$ENHANCEMENTS_FOUND" = true ]; then
  echo "🔍 Searching enhancements..." >&2

  # Search for KEPs and documentation
  ENHANCEMENTS_RESULTS=$(grep -r -i "$SEARCH_TERM" \
    --include="*.md" \
    --exclude-dir=".git" \
    -n -H -m 1 \
    "$ENHANCEMENTS_PATH" 2>/dev/null)

  # Count results
  ENHANCEMENTS_COUNT=$(echo "$ENHANCEMENTS_RESULTS" | grep -c ":" || echo "0")
  echo "Found $ENHANCEMENTS_COUNT matches in enhancements" >&2
fi
```

### Step 5: Categorize Results

Group and prioritize search results:

**Enhancement Proposals (Highest Priority)**
```bash
#!/bin/bash

# Extract KEP matches (files in enhancements/enhancements/)
KEPS=$(echo "$ENHANCEMENTS_RESULTS" | grep "/enhancements/enhancements/")

# Extract file paths and excerpts
while IFS= read -r line; do
  if [ -n "$line" ]; then
    FILE_PATH=$(echo "$line" | cut -d: -f1)
    LINE_NUM=$(echo "$line" | cut -d: -f2)
    EXCERPT=$(echo "$line" | cut -d: -f3- | sed 's/^[ \t]*//')

    # Get relative path from enhancements root
    REL_PATH=$(echo "$FILE_PATH" | sed "s|$ENHANCEMENTS_PATH/||")

    # Store for display
    echo "KEP: $REL_PATH (line $LINE_NUM)"
    echo "  > $EXCERPT"
  fi
done <<< "$KEPS"
```

**Commands and Tools**
```bash
#!/bin/bash

# Extract command files from ai-helpers
COMMANDS=$(echo "$AI_HELPERS_RESULTS" | grep "/commands/.*\.md")

while IFS= read -r line; do
  if [ -n "$line" ]; then
    FILE_PATH=$(echo "$line" | cut -d: -f1)

    # Extract plugin and command name
    PLUGIN=$(echo "$FILE_PATH" | sed 's|^./plugins/||' | cut -d/ -f1)
    COMMAND=$(basename "$FILE_PATH" .md)

    echo "Command: /$PLUGIN:$COMMAND"
    echo "  File: $FILE_PATH"
  fi
done <<< "$COMMANDS"
```

**README Files and Documentation**
```bash
#!/bin/bash

# Extract README and doc files
DOCS=$(echo "$AI_HELPERS_RESULTS $ENHANCEMENTS_RESULTS" | grep -i "readme\|/doc")

# Process documentation matches
while IFS= read -r line; do
  if [ -n "$line" ]; then
    echo "Documentation: $line"
  fi
done <<< "$DOCS"
```

### Step 6: Format and Present Results

Create a well-organized output:

```
═══════════════════════════════════════════════════════════════
🔍 SEARCH RESULTS FOR: "kube-apiserver"
═══════════════════════════════════════════════════════════════

Found 8 matches across both repositories

📚 ENHANCEMENT PROPOSALS (3 matches)

1. API Server Network Policy
   Location: enhancements/enhancements/network/apiserver-network-policy.md
   Preview: "This enhancement proposes adding network policy support..."

   Open in Claude Code:
   cd /path/to/enhancements && code enhancements/enhancements/network/apiserver-network-policy.md

2. API Server Identity
   Location: enhancements/enhancements/authentication/apiserver-identity.md
   Preview: "Implement API server identity using bound service account tokens..."

   Open in Claude Code:
   cd /path/to/enhancements && code enhancements/enhancements/authentication/apiserver-identity.md

─────────────────────────────────────────────────────────────

🤖 AUTOMATION TOOLS (2 matches)

1. Component Health Analysis
   Command: /component-health:summarize-jiras
   File: plugins/component-health/README.md

   Try it:
   /component-health:summarize-jiras OCPBUGS --component "kube-apiserver"

2. JIRA Bug Analysis
   Command: /component-health:list-jiras
   File: plugins/component-health/commands/list-jiras.md

   Try it:
   /component-health:list-jiras OCPBUGS --component "kube-apiserver"

─────────────────────────────────────────────────────────────

📖 DOCUMENTATION (3 matches)

1. Component Health Plugin README
   Location: plugins/component-health/README.md
   Preview: "Analyze component health metrics for kube-apiserver..."

2. Testing Guide
   Location: docs/testing-guide.md
   Preview: "How to test kube-apiserver changes..."

─────────────────────────────────────────────────────────────

💡 NEXT STEPS

🎯 Quick Actions:
   • View bug summary: /component-health:summarize-jiras OCPBUGS --component "kube-apiserver"
   • Search more specifically: /onboarding:search "kube-apiserver authentication"

📚 Deep Dive:
   • Open enhancements repo to read full KEPs
   • Ask Claude: "Explain the kube-apiserver enhancement proposals"

═══════════════════════════════════════════════════════════════
```

### Step 7: Handle Edge Cases

**No Results Found:**
```
═══════════════════════════════════════════════════════════════
🔍 SEARCH RESULTS FOR: "nonexistent-thing"
═══════════════════════════════════════════════════════════════

❌ No matches found

💡 SUGGESTIONS

1. Check spelling and try again
2. Try broader search terms:
   - Use component name instead of specific feature
   - Search for technology rather than implementation

3. Try similar terms:
   /onboarding:search "related-term"

4. Ask Claude directly:
   "What do you know about nonexistent-thing in OpenShift?"

5. Missing enhancements repo?
   Clone it for complete technical documentation:
   cd .. && git clone https://github.com/openshift/enhancements.git

═══════════════════════════════════════════════════════════════
```

**Enhancements Repo Not Available:**
```
═══════════════════════════════════════════════════════════════
⚠️  LIMITED SEARCH - ENHANCEMENTS REPO NOT FOUND
═══════════════════════════════════════════════════════════════

Currently searching: ai-helpers only
Missing: openshift/enhancements (technical documentation)

To get complete search results:

1. Clone enhancements repo:
   cd .. && git clone https://github.com/openshift/enhancements.git

2. Re-run search:
   /onboarding:search "your-term"

What you're missing:
✗ Enhancement proposals (KEPs)
✗ Architecture documentation
✗ Design decisions and rationale
✗ Process documentation

═══════════════════════════════════════════════════════════════
```

## Error Handling

1. **Missing search term**: Provide usage help
2. **No results**: Suggest alternatives and broader terms
3. **Enhancements not found**: Explain limitation and provide clone instructions
4. **Grep errors**: Fall back gracefully, show partial results
5. **Malformed results**: Skip and continue processing

## Performance Considerations

- Limit grep to markdown files only
- Use `-m 1` to get first match per file (faster)
- Exclude hidden directories and common non-doc directories
- Cache repository locations to avoid repeated filesystem checks

## Output Format

The output is designed to be:
- **Scannable**: Clear sections with visual separators
- **Actionable**: Every result includes a way to use it or open it
- **Contextual**: Shows previews/excerpts for quick relevance check
- **Helpful**: Provides next steps and suggestions

## Integration Points

This skill integrates with:
- `onboarding:start` - Can be suggested after initial setup
- Other documentation commands - Can reference them
- JIRA commands - Can suggest related automation
- Component health commands - Can suggest analysis

## Notes

- Search is case-insensitive for better UX
- Results are limited per file to avoid overwhelming output
- Prioritizes KEPs and enhancement proposals as most valuable
- Gracefully degrades when enhancements repo is unavailable
- File paths are shown relative to repo root for clarity
- Commands to open files are ready-to-copy
