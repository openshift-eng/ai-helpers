# Pattern Analyzer

**Ultra-minimal data gathering + Claude AI intelligence**

## Architecture

```
┌─────────────────────────────────┐
│  Python: search_repos.py        │
│  Bash: git clone                │
│  ↓                               │
│  Output: repos.json + repos/    │
└─────────────────────────────────┘
              ↓
┌─────────────────────────────────┐
│  Claude AI:                     │
│  • Read repos.json              │
│  • Explore cloned repos         │
│  • Analyze user's project       │
│  • Generate ANALYSIS.md         │
└─────────────────────────────────┘
```

**That's it!** No detection scripts, no templates, just data + AI.

## Quick Usage

```bash
# Navigate to YOUR project first!
cd /home/manpilla/Documents/pillaimanish/your-operator-project

# Run data gathering
/home/manpilla/Documents/pillaimanish/ai-helpers/plugins/openshift/skills/pattern-analyzer/analyze_pattern.sh \
  "NetworkPolicy" \
  --repos 50
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

| Script | Purpose | What It Does |
|--------|---------|--------------|
| `analyze_pattern.sh` | Orchestration | Runs search + clone, guides Claude |
| `search_repos.py` | GitHub search | Finds repos implementing pattern |

**Only 2 scripts!** Everything else is Claude AI.

## Arguments

```bash
./analyze_pattern.sh <pattern> [options]
```

- `<pattern>` - Pattern name (NetworkPolicy, ValidatingWebhook, etc.)
- `--orgs <orgs>` - GitHub orgs (default: openshift,kubernetes)
- `--repos <N>` - Max repos (default: 50, range: 3-50)
- `--refresh` - Force refresh (ignore cache)
- `--skip-clone` - Use existing cloned repos

## Example

```bash
# 1. Go to your project
cd ~/my-operator

# 2. Run analysis
/path/to/analyze_pattern.sh "ProxyConfig" --repos 50

# 3. Claude analyzes and creates:
.work/design-patterns/ProxyConfig/ANALYSIS.md

# 4. Read the guide
cat .work/design-patterns/ProxyConfig/ANALYSIS.md
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
- ~2GB disk space for 50 repos
- (Optional) GITHUB_TOKEN for higher API limits
