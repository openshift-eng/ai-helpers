---
name: Pattern Analyzer
description: Analyze design pattern implementations across OpenShift/Kubernetes repositories using AI
---

# Pattern Analyzer Skill

**Architecture:** Data (Python) + Intelligence (Claude AI)

## Overview

This skill uses a minimal data gathering approach followed by intelligent AI analysis:

1. **Python script** searches GitHub and clones repos (fast, automated)
2. **Claude AI** analyzes everything and generates recommendations (intelligent, adaptive)

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

**User executes (or you execute via terminal):**

```bash
/home/manpilla/Documents/pillaimanish/ai-helpers/plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh \
  "<pattern>" \
  [--orgs "openshift,kubernetes"] \
  [--repos 50] \
  [--refresh] \
  [--skip-clone]
```

**What this does:**
- Searches GitHub for repos implementing the pattern
- Clones up to 50 repositories (shallow clone)
- Creates `.work/design-patterns/<pattern>/` in user's current directory
- Generates `repos.json` with repository metadata
- Logs everything to `analysis.log`

**Output files:**
- `.work/design-patterns/<pattern>/repos.json` - Repository list with metadata
- `.work/design-patterns/<pattern>/repos/` - Cloned repositories
- `.work/design-patterns/<pattern>/analysis.log` - Execution log

**Time:** 15-20 minutes first run, 2-3 minutes with `--skip-clone`

### Step 2: Read the Repository Data

**CRITICAL: Read this file to understand what was found**

```bash
cat .work/design-patterns/<pattern>/repos.json
```

**Extract:**
- How many repos were found
- Which repos have highest quality (stars, activity)
- Repository descriptions (understand what each does)
- URLs for reference

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

**Your task:** Explore these repos to understand how the pattern is implemented.

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
User: /openshift:analyze-pattern NetworkPolicy

1. Script searches GitHub → 50 repos found
2. Script clones repos → 50 repos in .work/repos/
3. YOU (Claude) take over:
   - Read repos.json
   - Explore cluster-network-operator (similar to user)
   - Extract NetworkPolicy struct definition
   - See validation logic
   - Understand user has api/controllers/ structure
   - Generate specific guide for their operator
   - Create ANALYSIS.md with everything
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
