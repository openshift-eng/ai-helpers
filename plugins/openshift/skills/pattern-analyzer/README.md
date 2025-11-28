# Pattern Analyzer

**Minimal data gathering + Claude AI intelligence**

## Architecture

```
┌──────────────────────────────────────────┐
│  Python: search_repos.py                 │
│  • GitHub Code Search API (paginated)    │
│  • Deduplicates file matches             │
│  • Ranks repos by quality                │
│  ↓                                        │
│  Output: repos.json                      │
└──────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────┐
│  Python: Parallel git clone (8 workers)  │
│  • --depth 1 --filter=blob:none          │
│  ↓                                        │
│  Output: repos/ + analysis.log           │
└──────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────┐
│  Claude AI:                              │
│  • Read repos.json                       │
│  • Explore cloned repos                  │
│  • Analyze user's project                │
│  • Generate ANALYSIS.md                  │
└──────────────────────────────────────────┘
```

**Key Features:**
- ✅ **Parallel cloning:** Up to 8 concurrent clones (3-5x faster!)
- ✅ **Pagination:** Fetches ALL search results (up to 1000)
- ✅ **Deduplication:** Removes duplicate file matches
- ✅ **All file types:** Searches Dockerfiles, shell scripts, YAML, Go, etc.
- ✅ **Smart caching:** Uses `analysis.log` as 7-day cache marker

## Quick Usage

```bash
# Navigate to YOUR project first!
cd ~/your-operator-project

# Locate the analyzer script
ANALYZER_SCRIPT=$(find ~ -name "analyze_pattern.sh" -path "*/pattern-analyzer/*" 2>/dev/null | head -1)

# Run data gathering
$ANALYZER_SCRIPT \
  "NetworkPolicy" \
  --repos 50

# Or if ai-helpers is in workspace:
# plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh "NetworkPolicy" --repos 50
```

**Output:**
```
✅ DATA GATHERING COMPLETE

Generated data:
  • repos.json - 50 repositories metadata
  • repos/ - 50 cloned repositories
  • analysis.log - Execution log

🤖 NEXT: Claude AI Analysis

Claude should now:
  1. READ repos.json
  2. EXPLORE cloned repos
  3. ANALYZE your project
  4. GENERATE detailed recommendations
  5. CREATE ANALYSIS.md with complete guide
```

## What You Get

**Claude generates:** `.work/design-patterns/<pattern>/ANALYSIS.md`

Contains:
- Statistical insights from 50 repos
- Real code examples (extracted from repos)
- Specific recommendations for YOUR project
- Complete struct definitions
- Full implementation code
- Step-by-step integration guide
- Testing examples
- References to similar repos

## Scripts

| Script | Purpose | Key Features |
|--------|---------|--------------|
| `analyze_pattern.sh` | Orchestration | Cache management, clone coordination |
| `search_repos.py` | GitHub search | **Pagination**, deduplication, ranking |

**Only 2 scripts!** Everything else is Claude AI.

**What makes search_repos.py powerful:**
- Paginates through all GitHub search results (not just first 100)
- Deduplicates file matches across pages
- Searches all file types by default (optional language filter)
- Ranks repos by stars, activity, and relevance

## Arguments

```bash
./analyze_pattern.sh <pattern> [options]
```

- `<pattern>` - Pattern name or search term
  - Examples: "NetworkPolicy", "/usr/bin/gather", "must-gather"
- `--orgs <orgs>` - GitHub orgs (default: openshift,kubernetes)
- `--repos <N>` - Max repos (default: 50, range: 3-50)
- `--language <LANG>` - Language filter (default: all)
  - Examples: `go`, `python`, `shell`, `dockerfile`
  - Omit to search all file types
- `--refresh` - Force refresh (ignore cache)
- `--skip-clone` - Use existing cloned repos

## Examples

### Example 1: Go Type Pattern
```bash
cd ~/my-operator
./analyze_pattern.sh "NetworkPolicy" --language go --repos 50
```

### Example 2: Shell Script Pattern (all file types)
```bash
cd ~/must-gather-operator
./analyze_pattern.sh "/usr/bin/gather" --repos 50
# Searches: Dockerfiles, shell scripts, YAML, Makefiles, etc.
```

### Example 3: Quick Analysis
```bash
./analyze_pattern.sh "ValidatingWebhook" --repos 10
```

### Example 4: Use Cached Data
```bash
./analyze_pattern.sh "ProxyConfig" --skip-clone
# Uses existing repos/, re-runs search only
```

**After data gathering completes:**
```bash
# Claude creates comprehensive analysis
cat .work/design-patterns/<pattern>/ANALYSIS.md
```

## Why This Works

**Python is good at:**
- GitHub API calls
- git clone operations
- File system operations

**Claude is good at:**
- Reading and understanding code
- Finding patterns and similarities
- Generating context-specific recommendations
- Writing complete, working implementations
- Explaining reasoning

**Use the right tool for each job!** 🎯

## Output Structure

```
.work/design-patterns/<pattern>/
├── repos.json          # Metadata (from Python)
├── analysis.log        # Execution log (from bash)
├── ANALYSIS.md         # Complete guide (from Claude) ⭐
└── repos/              # Cloned repos (from git)
    ├── cluster-network-operator/
    ├── api/
    ├── sdn/
    └── ... (50 repos)
```

## Requirements

- Python 3.6+
- Git
- ~400-600MB disk space for 50 repos (optimized shallow clones with `--depth 1`)
- (Optional) GITHUB_TOKEN for higher API limits
