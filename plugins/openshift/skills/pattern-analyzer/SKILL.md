---
name: Pattern Analyzer
description: Analyze design pattern implementations across OpenShift/Kubernetes repositories using AI
---

# Pattern Analyzer Skill

**Architecture:** Data (Python) + Intelligence (Claude AI)

## Overview

This skill uses a minimal data gathering approach followed by intelligent AI analysis:

1. **Python script** searches GitHub (with pagination) and clones repos (fast, automated)
2. **Claude AI** analyzes everything and generates recommendations (intelligent, adaptive)

**Key capabilities:**
- ✅ **Complete search coverage:** Paginates through ALL GitHub results (up to 1000)
- ✅ **All file types:** Searches Dockerfiles, shell scripts, YAML, Go, Python, etc.
- ✅ **Deduplication:** Removes duplicate file matches across pages
- ✅ **Smart caching:** 7-day cache based on `analysis.log` timestamp

**No hardcoded templates. No rigid patterns. Just data + AI.**

## When to Use This Skill

Use when implementing `/openshift:analyze-pattern` command to help developers understand how to implement design patterns (NetworkPolicy, ValidatingWebhook, ProxyConfig, etc.) in their Kubernetes/OpenShift projects.

## Prerequisites

**For the user:**
- Python 3.6+
- Git
- GitHub token (optional): `export GITHUB_TOKEN="ghp_..."`
- Must run from their target project directory

**For you (Claude):**
- Read JSON data files
- Explore cloned repositories
- Analyze user's project structure
- Generate intelligent recommendations

## Implementation

### Step 1: Run Data Gathering Script

**Locate the script dynamically:**

```bash
# Find the analyze_pattern.sh script
ANALYZER_SCRIPT=$(find ~ -name "analyze_pattern.sh" -path "*/pattern-analyzer/*" 2>/dev/null | head -1)

if [ -z "$ANALYZER_SCRIPT" ]; then
    # Fallback: try relative path if in workspace
    if [ -f "plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh" ]; then
        ANALYZER_SCRIPT="plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh"
    else
        echo "ERROR: Pattern analyzer script not found"
        echo "Please ensure the openshift plugin from ai-helpers is properly installed"
        exit 1
    fi
fi
```

**Execute the analysis script:**

```bash
$ANALYZER_SCRIPT \
  "<pattern>" \
  [--orgs "openshift,kubernetes"] \
  [--repos 50] \
  [--language LANG] \
  [--refresh] \
  [--skip-clone]
```

**What this does:**
1. **Searches GitHub Code Search API** (with pagination)
   - Fetches ALL search results (up to 1000 matches across multiple pages)
   - Searches all file types by default (Dockerfiles, scripts, YAML, Go, etc.)
   - Optional `--language` filter for specific languages
2. **Deduplicates file matches** across pagination results
3. **Ranks repositories** by quality (stars, activity, relevance)
4. **Parallel clones repositories** (up to 8 concurrent shallow clones, ~50 repos max)
5. **Creates workspace** in `.work/design-patterns/<pattern>/`

**Output files:**
- `.work/design-patterns/<pattern>/repos.json` - Repository metadata with scores
- `.work/design-patterns/<pattern>/repos/` - Cloned repositories
- `.work/design-patterns/<pattern>/analysis.log` - Execution log (also cache marker)

**Time:** 
- First run: 5-8 minutes (search + parallel shallow clones with `--depth 1`)
- Cached: Instant (if analysis.log < 7 days old)
- With `--skip-clone`: 2-5 minutes (search only)

### Step 2: Read the Repository Data

**MANDATORY: Execute this exact command to read the data**

```bash
# REQUIRED: Read the repos.json file - DO NOT SKIP THIS STEP
python3 -c "
import json
with open('.work/design-patterns/<pattern>/repos.json') as f:
    data = json.load(f)
print(f'Pattern: {data[\"pattern\"]}')
print(f'Total repos found: {data[\"repos_found\"]}')
print(f'Repos selected: {data[\"repos_selected\"]}')
print()
print('Top 10 repositories:')
for i, repo in enumerate(data['repos'][:10], 1):
    print(f'  {i}. {repo[\"full_name\"]:40s} ⭐{repo[\"stars\"]:4d}  score:{repo[\"relevance_score\"]}')
print()
print('Repos most similar to your project (pick 3-5 for deep analysis):')
# TODO: Claude should identify which repos match user's project type
"
```

**After running this command, extract:**
- Total repos found (for statistics)
- Top 5 repos by score (candidates for deep analysis)
- Repos matching user's project type (operators → pick operators)

**Example data structure:**
```json
{
  "pattern": "NetworkPolicy",
  "repos_selected": 50,
  "repos": [
    {
      "name": "cluster-network-operator",
      "org": "openshift",
      "full_name": "openshift/cluster-network-operator",
      "stars": 107,
      "description": "...",
      "clone_url": "...",
      "relevance_score": 12.5
    }
  ]
}
```

### Step 3: Explore the Cloned Repositories

**The repos are cloned to:** `.work/design-patterns/<pattern>/repos/`

**IMPORTANT - Context Window Management:**
To avoid exhausting the context window when analyzing 50+ repos, use this tiered approach:

| Tier | Repos | Analysis Depth | Purpose |
|------|-------|----------------|---------|
| **Tier 1** | Top 3-5 (most similar) | Full code review | Deep understanding |
| **Tier 2** | Next 10 repos | Struct definitions only | Pattern extraction |
| **Tier 3** | Remaining repos | Count occurrences | Statistics only |

**NEVER load all 50 repos into context at once.** Instead:
1. Read `repos.json` to get the list (small file)
2. Identify top 3-5 repos similar to user's project
3. Deep-dive only into those 3-5 repos
4. For statistics, use grep/find commands to count patterns without reading full files

#### A. Find Similar Repos to User's Project

First, understand user's project:
```bash
# Check if it's an operator
ls api/ controllers/ config/

# Check go.mod
cat go.mod | grep -E 'operator-sdk|controller-runtime|module'

# Check for existing patterns
find . -name "*webhook*.go" -o -name "*controller*.go"
```

Then find repos with similar structure from the cloned set.

#### B. Identify Top 3-5 Repos for Deep Analysis

Based on user's project type, select 3-5 repos to analyze deeply:
```bash
# List all cloned repos with their characteristics
for repo in .work/design-patterns/<pattern>/repos/*/; do
  echo "=== $(basename $repo) ==="
  ls "$repo" | head -5
done
```

**Selection criteria:**
- Same project type (operator → pick operators)
- Similar directory structure
- Active/well-maintained (from repos.json scores)

#### B. Analyze Pattern Implementation

For each relevant repo (focus on top 5-7 similar ones):

```bash
# Find struct definition
grep -r "type <Pattern> struct" .work/design-patterns/<pattern>/repos/<repo-name>/ --include="*.go"

# Find implementation files
find .work/design-patterns/<pattern>/repos/<repo-name>/ -name "*<pattern>*.go" | grep -v vendor | grep -v generated

# Read the actual code
cat .work/design-patterns/<pattern>/repos/<repo-name>/<file>
```

**What to extract:**
- Complete struct definitions (with all fields and comments)
- Validation functions
- Controller/Reconciler implementations
- Webhook configurations (YAML)
- Test examples
- RBAC configurations

#### C. Statistical Analysis

Based on what you read from the repos:

- Count approaches: "How many use ValidatingWebhook vs AdmissionController?"
- Common fields: "What fields appear in most struct definitions?"
- Common patterns: "Do they all validate URLs? Handle nil values?"
- Testing practices: "What do tests check for?"

### Step 4: Analyze User's Project

**Explore their repository structure:**

```bash
# Check project type
ls -la  # See directory structure

# Operator?
cat go.mod | grep operator-sdk

# Read their CRDs
find api/ -name "*_types.go" 2>/dev/null | head -5

# Check existing controllers
ls controllers/ pkg/controller/ 2>/dev/null

# Check build system
cat Makefile | head -20
```

**Understand:**
- Project type (operator, application, library)
- Directory layout (standard operator, pkg-based, custom)
- Existing patterns (webhooks, CRDs, controllers)
- Dependencies (what APIs they already use)
- What components they manage (from controller names)

### Step 5: Generate Intelligent Recommendations

**Based on everything you learned, provide:**

#### A. Statistical Summary

```markdown
## Pattern Analysis: <Pattern>

Analyzed <N> repositories from <orgs>

### Implementation Approaches
- <X>/<N> (Y%) repos use <approach>
- <X>/<N> (Y%) repos use <approach>
...

### Common Fields (from struct definitions)
- Field1: appears in X/N repos (purpose: ...)
- Field2: appears in X/N repos (purpose: ...)
```

#### B. Code Examples from Actual Repos

**Show REAL code** (not templates):

```markdown
### Struct Definition (from <repo-name>)

\`\`\`go
// Complete struct from actual repo
type ProxyConfig struct {
    HTTPProxy *string `json:"httpProxy,omitempty"`
    // ... all fields with comments
}
\`\`\`
```

#### C. Context-Specific Recommendations

**For THEIR specific project:**

```markdown
## Recommendations for Your Project

### Your Project Context
- Type: Operator (controller-runtime v0.20.4)
- Manages: SpireServer, SpireAgent, OIDCDiscoveryProvider
- Structure: api/, controllers/, config/
- Existing patterns: Has webhooks, uses kustomize

### Implementation Plan

**File 1: api/v1alpha1/<pattern>_types.go**

Create this file with:

\`\`\`go
package v1alpha1

// <Pattern> - based on openshift/cluster-network-operator implementation
type <Pattern> struct {
    // Actual fields from analyzed repos
    Field1 string `json:"field1"`
    // ...
}
\`\`\`

**File 2: controllers/<pattern>_webhook.go**

\`\`\`go
// Complete webhook implementation
// Based on <similar-repo>
\`\`\`

... (continue with complete, working code for each file)
```

#### D. Integration Steps

**Specific commands for their setup:**

```markdown
1. Create api/v1alpha1/<pattern>_types.go
2. Run: make manifests
3. Create controllers/<pattern>_webhook.go
4. Update main.go: (exact lines to add)
5. Update config/rbac/role.yaml: (exact YAML to add)
6. Test: make test
```

### Step 6: Create Summary Markdown File

**CRITICAL: Save everything to a markdown file**

Create: `.work/design-patterns/<pattern>/ANALYSIS.md`

**Format:**

```markdown
# <Pattern> Implementation Analysis

Generated: <timestamp>
Analyzed: <N> repositories
Target project: <repo-name>

## Executive Summary

[Brief overview of findings]

## Statistical Insights

[Approaches, features, testing practices]

## Code Examples

[Complete struct definitions, functions, configs from actual repos]

## Recommendations for <repo-name>

[Specific guidance for their project]

## Files to Create/Modify

### File: api/v1alpha1/<pattern>_types.go
\`\`\`go
[complete code]
\`\`\`

### File: controllers/<pattern>_webhook.go
\`\`\`go
[complete code]
\`\`\`

[... all files with complete code]

## Implementation Steps

1. [Step-by-step with exact commands]

## Testing Guide

[How to test the implementation]

## References

- Similar repos to review: [list]
- Specific files to study: [list]
- Cloned repos location: .work/design-patterns/<pattern>/repos/

## Data Sources

- Analysis date: <date>
- Repositories analyzed: <N>
- GitHub organizations: <orgs>
- Data files: repos.json, analysis.log
```

**Save this file and inform the user:**
```
✅ Detailed analysis saved to:
   .work/design-patterns/<pattern>/ANALYSIS.md

📖 View with: cat .work/design-patterns/<pattern>/ANALYSIS.md
```

## Key Principles

### DO:
✅ Read ALL the cloned repositories  
✅ Extract REAL code examples  
✅ Understand user's SPECIFIC project  
✅ Provide COMPLETE, working code  
✅ Explain WHY (backed by statistics)  
✅ Generate ANALYSIS.md with everything  
✅ Be specific about file paths in THEIR repo  

### DON'T:
❌ Use generic templates  
❌ Make assumptions without data  
❌ Provide incomplete code snippets  
❌ Skip exploring the actual repos  
❌ Forget to create ANALYSIS.md  

## Error Handling

- If <3 repos cloned: Exit with error
- If pattern not found: Suggest alternatives
- If user's repo has unusual structure: Adapt recommendations

## Success Criteria

User should get:
1. ✅ Statistical insights from 50 repos
2. ✅ Real code examples (not templates)
3. ✅ Specific recommendations for their project
4. ✅ Complete implementation in ANALYSIS.md
5. ✅ Clear next steps

## Example Workflow

```
User: /openshift:analyze-pattern "/usr/bin/gather"

1. Script searches GitHub (ALL file types):
   → Fetches Page 1: 100 results
   → Fetches Page 2: 52 results
   → Total: 152 code matches
   → Deduplicates: 0 duplicates
   → Selects top 27 repos based on quality scores

2. Script clones repos:
   → Successfully clones 24 repos (3 failures due to permissions)
   → Saves to .work/design-patterns/usr/bin/gather/repos/

3. Claude executes the following MANDATORY steps (in order):

   **Step 3a: Read repos.json** (REQUIRED)
   ```bash
   cat .work/design-patterns/usr/bin/gather/repos.json | head -100
   ```
   
   **Step 3b: Identify top 3 similar repos** (REQUIRED)
   From repos.json, select the 3 repos most similar to user's project type.
   For this example: must-gather, oadp-operator, ocs-operator
   
   **Step 3c: Extract patterns from each** (REQUIRED for top 3 only)
   ```bash
   grep -r "gather" .work/design-patterns/usr/bin/gather/repos/must-gather/ --include="*.sh" | head -20
   ```
   
   **Step 3d: Generate ANALYSIS.md** (REQUIRED)
   Create `.work/design-patterns/usr/bin/gather/ANALYSIS.md` with findings
```

## Output Structure

```
.work/design-patterns/<pattern>/
├── repos.json              # Repo metadata (from Python)
├── analysis.log            # Execution log (from bash)
├── ANALYSIS.md             # Your comprehensive guide (CREATE THIS!)
└── repos/                  # Cloned repos (from bash)
    ├── cluster-network-operator/
    ├── api/
    └── ...
```

## See Also

- Command: `plugins/openshift/commands/analyze-pattern.md`
- Data script: `plugins/openshift/skills/pattern-analyzer/search_repos.py`
- Wrapper: `plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh`
