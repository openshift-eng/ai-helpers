---
description: Analyze how OpenShift repos implement a design pattern and get custom recommendations
argument-hint: <pattern-name> [--orgs org1,org2] [--repos N] [--language LANG]
---

## Name

openshift:analyze-pattern

## Synopsis

```
/openshift:analyze-pattern <pattern> [--orgs org1,org2] [--repos N] [--language LANG] [--refresh] [--skip-clone]
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

**Locate the script directory dynamically:**

```bash
# Find the analyze_pattern.sh script
ANALYZER_SCRIPT=$(find ~ -name "analyze_pattern.sh" -path "*/pattern-analyzer/*" 2>/dev/null | head -1)

if [ -z "$ANALYZER_SCRIPT" ]; then
    echo "ERROR: Pattern analyzer script not found"
    echo "Please ensure the openshift plugin from ai-helpers is properly installed"
    exit 1
fi
```

**Execute the analysis script:**

```bash
$ANALYZER_SCRIPT \
  "<pattern>" \
  --orgs "openshift,kubernetes" \
  --repos 50
```

**Or use relative path if plugin is in workspace:**

```bash
plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh \
  "<pattern>" \
  --orgs "openshift,kubernetes" \
  --repos 50
```

This script:
1. **Searches GitHub Code Search API** for pattern usage
   - Paginates through ALL results (up to 1000 matches)
   - Searches all file types by default (Dockerfiles, shell scripts, YAML, Go, etc.)
   - Optional `--language` filter for specific languages
2. **Deduplicates results** to avoid counting the same file twice
3. **Ranks and filters repos** by quality (stars, activity, relevance, recency)
4. **Parallel clones top repos** (~50 repos max, up to 8 concurrent clones)
5. **Creates analysis workspace** with all data for Claude AI

**Output (in `.work/design-patterns/<pattern>/`):**
- `repos.json` - Repository metadata (stars, URLs, descriptions, scores)
- `analysis.log` - Execution log (also serves as cache marker)
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
  - Pagination progress (Page 1, Page 2, etc.)
  - Repository ranking and scoring
  - Clone progress for each repository
- Path to generated data files
- Instructions for Claude to analyze

**Files Created:**
- `.work/design-patterns/<pattern>/repos.json` - Repository metadata with scores
- `.work/design-patterns/<pattern>/analysis.log` - Complete execution log
- `.work/design-patterns/<pattern>/repos/` - Cloned repositories (shallow)

**Claude AI Analysis (generated after data gathering):**
- `.work/design-patterns/<pattern>/ANALYSIS.md` - Complete analysis including:
  - Statistical summary of implementations
  - Code examples from actual repos
  - Context-specific recommendations for your project
  - Complete implementation guide
  - References to similar repos

## Examples

### Example 1: Basic Pattern Analysis (Go types)

```
/openshift:analyze-pattern NetworkPolicy --language go
```

Analyzes 50 NetworkPolicy implementations in Go code, then Claude provides:
- Statistical breakdown of approaches
- Real code examples
- Specific recommendations for your project

### Example 2: Shell Script Analysis

```
/openshift:analyze-pattern "/usr/bin/gather"
```

Searches all file types (Dockerfiles, shell scripts, YAML) for gather scripts.
Useful for analyzing operational patterns.

### Example 3: Quick Analysis

```
/openshift:analyze-pattern ValidatingWebhook --repos 10
```

Analyzes fewer repos for faster results.

### Example 4: Multi-org Search

```
/openshift:analyze-pattern CustomResourceDefinition --orgs openshift,kubernetes,kubernetes-sigs
```

Searches across multiple organizations.

### Example 5: Use Cached Repos

```
/openshift:analyze-pattern ProxyConfig --skip-clone
```

Reuses already-cloned repos, only re-analyzes.

### Example 6: Python Code Patterns

```
/openshift:analyze-pattern "must-gather" --language python --repos 20
```

Finds Python implementations of must-gather patterns.

## Arguments

- `$1` (required): **Pattern name**
  - Examples: "NetworkPolicy", "ValidatingWebhook", "/usr/bin/gather"
  - Can be Go types, file paths, or any search term
  - Use quotes if pattern contains spaces or special characters

- `--orgs <org1,org2>` (optional): **GitHub organizations**
  - Default: "openshift,kubernetes"
  - Comma-separated, no spaces
  - Example: `--orgs openshift,kubernetes,kubernetes-sigs`

- `--repos <N>` (optional): **Maximum repos to analyze**
  - Default: 50 (comprehensive)
  - Range: 3-50
  - More repos = better statistics, slower analysis

- `--language <LANG>` (optional): **Programming language filter**
  - Default: all languages (searches everything)
  - Examples: `go`, `python`, `shell`, `dockerfile`, `yaml`
  - When omitted, searches Dockerfiles, shell scripts, YAML, Go, etc.
  - Use for Go types: `--language go`

- `--refresh` (optional): **Force refresh**
  - Ignores cache (based on analysis.log age)
  - Re-runs entire analysis
  - Cache expires after 7 days automatically

- `--skip-clone` (optional): **Skip cloning**
  - Uses existing cloned repos
  - Re-runs search only
  - Saves 10-15 minutes

## Prerequisites

1. **Python 3.6+**
2. **Git**
3. **GitHub Token** (optional but recommended):
   ```bash
   export GITHUB_TOKEN="ghp_..."
   ```
4. **Disk space**: ~400-600MB per analysis (optimized shallow clones)

## Notes

- **Run from your target project directory** for best results
- First run: ~5-8 minutes (search + parallel cloning)
- Cached runs: Instant (if analysis.log < 7 days old)
- With `--skip-clone`: ~2-5 minutes (search only)
- Cache marker: `analysis.log` file (expires after 7 days)

**Performance:**
- **Parallel cloning:** Up to 8 concurrent git clones for maximum speed
- **Optimized cloning:** Uses `--depth 1` (single commit) + `--filter=blob:none` (deferred blobs)
- **GitHub API pagination:** Fetches ALL search results (up to 1000)
- **Deduplication:** Removes duplicate file matches across pages
- **Rate limiting:** 2-second delays between pagination requests
- **Token recommended:** Set `GITHUB_TOKEN` for higher API limits

**Critical:** This command generates data. Claude AI performs the intelligent analysis and recommendations.

## See Also

- Skill Documentation: `plugins/openshift/skills/pattern-analyzer/SKILL.md`
- Python Scripts: `plugins/openshift/skills/pattern-analyzer/*.py`
