---
description: Analyze how OpenShift repos implement a design pattern and get custom recommendations
argument-hint: <pattern-name> [--orgs org1,org2] [--repos N]
---

## Name

openshift:analyze-pattern

## Synopsis

```
/openshift:analyze-pattern <pattern> [--orgs org1,org2] [--repos N] [--refresh] [--skip-clone]
```

## Description

The `openshift:analyze-pattern` command analyzes how OpenShift and Kubernetes repositories implement a specific design pattern and provides intelligent, context-aware recommendations tailored to your repository.

**What makes this powerful:**
- Analyzes up to 50 real-world implementations
- Statistically identifies common approaches
- Understands YOUR project structure and purpose
- Provides complete, copy-paste-ready code examples
- Explains WHY certain approaches are recommended

**Use cases:**
- Learning how to implement NetworkPolicy, ValidatingWebhook, etc.
- Understanding ecosystem-wide best practices
- Getting started with unfamiliar patterns
- Finding high-quality reference implementations

## Implementation

**Architecture: Data + Intelligence**

This command uses a two-layer approach:
1. **Python scripts** gather data (fast, reliable)
2. **Claude AI** analyzes and synthesizes (intelligent, adaptive)

### Data Gathering (Automated)

Execute the analysis script:

```bash
/home/manpilla/Documents/pillaimanish/ai-helpers/plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh \
  "<pattern>" \
  --orgs "openshift,kubernetes" \
  --repos 50
```

This script:
1. Searches GitHub Code Search API for pattern usage
2. Ranks and filters repos by quality (stars, activity, relevance)
3. Shallow clones top repos (~50 repos)
4. Analyzes pattern implementations statistically
5. Detects user's repository structure
6. Performs deep analysis of user's project purpose

**Output (in `.work/design-patterns/<pattern>/`):**
- `repos.json` - Repository metadata
- `pattern_analysis.json` - Statistical analysis
- `user_context.json` - User's project context
- `repos/` - Cloned repositories for exploration

### Analysis and Synthesis (Claude AI)

After data gathering completes, Claude should:

1. **Read all JSON files** to understand the landscape

2. **Explore cloned repositories:**
   - Find the most similar repos to user's project
   - Read actual struct definitions
   - Extract real implementation code
   - Review test examples

3. **Analyze user's project:**
   - Understand what they're building (from dependencies, CRDs, controllers)
   - Identify where pattern fits in their architecture
   - Determine specific files to create/modify

4. **Generate intelligent recommendations:**
   - Statistical insights ("X% of repos use approach Y")
   - Code examples from actual repos (not templates!)
   - Specific file paths for user's project structure
   - Complete, working code samples
   - Detailed implementation steps
   - Testing guidance

5. **Provide context-aware guidance:**
   - Explain WHY this pattern is relevant to their project
   - Show HOW it integrates with their existing code
   - Reference similar implementations they can learn from

### Key Principles

- **Data-driven:** All recommendations based on analyzed repos
- **Context-aware:** Tailored to user's specific project
- **Complete:** Full working code, not snippets
- **Explainable:** Every recommendation backed by data

## Return Value

**Terminal Output:**
- Progress indicators during data gathering
- Path to generated data files
- Instructions for Claude to analyze

**Files Created:**
- `.work/design-patterns/<pattern>/repos.json`
- `.work/design-patterns/<pattern>/pattern_analysis.json`
- `.work/design-patterns/<pattern>/user_context.json`
- `.work/design-patterns/<pattern>/repos/` - Cloned repositories

**Claude's Analysis:**
- Statistical summary of implementations
- Code examples from actual repos
- Context-specific recommendations
- Complete implementation guide
- References to similar repos

## Examples

### Example 1: Basic Pattern Analysis

```
/openshift:analyze-pattern NetworkPolicy
```

Analyzes 50 NetworkPolicy implementations, then Claude provides:
- Statistical breakdown of approaches
- Real code examples
- Specific recommendations for your project

### Example 2: Quick Analysis

```
/openshift:analyze-pattern ValidatingWebhook --repos 10
```

Analyzes fewer repos for faster results.

### Example 3: Multi-org Search

```
/openshift:analyze-pattern CustomResourceDefinition --orgs openshift,kubernetes,kubernetes-sigs
```

Searches across multiple organizations.

### Example 4: Use Cached Repos

```
/openshift:analyze-pattern ProxyConfig --skip-clone
```

Reuses already-cloned repos, only re-analyzes.

## Arguments

- `$1` (required): **Pattern name**
  - Examples: "NetworkPolicy", "ValidatingWebhook", "ProxyConfig"
  - Use exact Kubernetes/Go type names

- `--orgs <org1,org2>` (optional): **GitHub organizations**
  - Default: "openshift,kubernetes"
  - Comma-separated, no spaces

- `--repos <N>` (optional): **Maximum repos to analyze**
  - Default: 50 (comprehensive)
  - Range: 3-50
  - More repos = better statistics, slower analysis

- `--refresh` (optional): **Force refresh**
  - Ignores cache
  - Re-runs entire analysis

- `--skip-clone` (optional): **Skip cloning**
  - Uses existing cloned repos
  - Re-runs analysis only
  - Saves 10-15 minutes

## Prerequisites

1. **Python 3.6+**
2. **Git**
3. **GitHub Token** (optional but recommended):
   ```bash
   export GITHUB_TOKEN="ghp_..."
   ```
4. **Disk space**: ~500MB per analysis

## Notes

- **Run from your target project directory** for best results
- First run: ~15-20 minutes (cloning)
- Cached runs: ~2-3 minutes (analysis only)
- With `--skip-clone`: ~2-3 minutes
- Cache expires after 7 days

**Critical:** This command generates data. Claude AI performs the intelligent analysis and recommendations.

## See Also

- Skill Documentation: `plugins/openshift/skills/pattern-analyzer/SKILL.md`
- Python Scripts: `plugins/openshift/skills/pattern-analyzer/*.py`
