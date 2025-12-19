#!/bin/bash
#
# Pattern Analyzer - Data Gathering Only
# Claude AI handles all analysis and synthesis
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
PATTERN=""
ORGS="openshift,kubernetes"
MAX_REPOS=50
LANGUAGE=""
REFRESH=false
SKIP_CLONE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --pattern) PATTERN="$2"; shift 2 ;;
        --orgs) ORGS="$2"; shift 2 ;;
        --repos) MAX_REPOS="$2"; shift 2 ;;
        --language) LANGUAGE="$2"; shift 2 ;;
        --refresh) REFRESH=true; shift ;;
        --skip-clone) SKIP_CLONE=true; shift ;;
        *) PATTERN="$1"; shift ;;
    esac
done

# Validate
if [ -z "$PATTERN" ]; then
    echo "❌ ERROR: Pattern name is required"
    echo ""
    echo "Usage: $0 <pattern> [--orgs org1,org2] [--repos N] [--language LANG] [--refresh] [--skip-clone]"
    echo ""
    echo "Arguments:"
    echo "  --orgs        Comma-separated GitHub orgs (default: openshift,kubernetes)"
    echo "  --repos       Maximum repos to analyze (default: 50)"
    echo "  --language    Filter by language (e.g., go, python, shell). Default: all languages"
    echo "  --refresh     Force refresh (ignore cache)"
    echo "  --skip-clone  Skip cloning, use existing repos"
    echo ""
    echo "Examples:"
    echo "  $0 NetworkPolicy"
    echo "  $0 ValidatingWebhook --repos 30"
    echo "  $0 '/usr/bin/gather' --language shell"
    echo "  $0 ProxyConfig --skip-clone"
    exit 1
fi

# Setup
WORK_DIR=".work/design-patterns/$PATTERN"
LOG_FILE="$WORK_DIR/analysis.log"
mkdir -p "$WORK_DIR"

# Start logging
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  📊 PATTERN ANALYZER: $PATTERN"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "  Current directory: $(pwd)"
echo "  Repository: $(basename $(pwd))"
echo "  Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Check cache (using analysis.log as marker)
CACHE_FLAG="$WORK_DIR/analysis.log"
if [ -f "$CACHE_FLAG" ] && [ "$REFRESH" = false ]; then
    FILE_AGE=$(($(date +%s) - $(stat -c %Y "$CACHE_FLAG" 2>/dev/null || stat -f %m "$CACHE_FLAG")))
    DAYS_OLD=$((FILE_AGE / 86400))
    
    if [ $FILE_AGE -lt 604800 ]; then  # 7 days
        echo "✓ Cached analysis found (age: $DAYS_OLD days)"
        echo ""
        echo "📁 Cached data available in: $WORK_DIR/"
        echo ""
        echo "Files:"
        ls -lh "$WORK_DIR"/*.json 2>/dev/null | awk '{print "  •", $9, "-", $5}' || true
        echo ""
        echo "Cloned repositories: $(ls -1 $WORK_DIR/repos 2>/dev/null | wc -l) repos"
        echo ""
        echo "────────────────────────────────────────────────────────────────────────────────"
        echo "💡 TIP: Run with --refresh to force re-analysis"
        echo "────────────────────────────────────────────────────────────────────────────────"
        echo ""
        echo "🤖 Claude: Please read the data files above and provide detailed recommendations."
        echo ""
        exit 0
    fi
    
    echo "⚠️  Cache expired (>7 days old), running fresh analysis..."
    echo ""
fi

# STEP 1: Search GitHub
echo "────────────────────────────────────────────────────────────────────────────────"
echo "STEP 1/2: Searching GitHub for '$PATTERN' implementations"
echo "────────────────────────────────────────────────────────────────────────────────"
echo ""
echo "  Organizations: $ORGS"
echo "  Max repositories: $MAX_REPOS"
if [ -n "$LANGUAGE" ]; then
    echo "  Language filter: $LANGUAGE"
else
    echo "  Language filter: all languages"
fi
echo ""

if [ "$SKIP_CLONE" = true ] && [ -f "$WORK_DIR/repos.json" ]; then
    echo "⏩ Skipping GitHub search (using cached repos.json)"
    REPO_COUNT=$(python3 -c "import json; print(json.load(open('$WORK_DIR/repos.json'))['repos_selected'])" 2>/dev/null || echo "0")
else
    # Build search command
    SEARCH_CMD="python3 \"$SCRIPT_DIR/search_repos.py\" --pattern \"$PATTERN\" --orgs \"$ORGS\" --max-repos \"$MAX_REPOS\" --output \"$WORK_DIR/repos.json\""
    
    # Add language filter if specified
    if [ -n "$LANGUAGE" ]; then
        SEARCH_CMD="$SEARCH_CMD --language \"$LANGUAGE\""
    fi
    
    eval $SEARCH_CMD
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ ERROR: GitHub search failed"
        echo ""
        echo "Common issues:"
        echo "  • Network connectivity"
        echo "  • GitHub API rate limit (set GITHUB_TOKEN)"
        echo "  • Invalid pattern name"
        exit 2
    fi
    
    REPO_COUNT=$(python3 -c "import json; print(json.load(open('$WORK_DIR/repos.json'))['repos_selected'])")
fi

echo ""
echo "✅ Found $REPO_COUNT repositories to analyze"
echo ""

# Show top repos
echo "Top repositories:"
python3 -c "
import json
with open('$WORK_DIR/repos.json') as f:
    data = json.load(f)
for i, repo in enumerate(data['repos'][:5], 1):
    print(f\"  {i}. {repo['full_name']} (⭐ {repo['stars']})\")
if len(data['repos']) > 5:
    print(f\"  ... and {len(data['repos']) - 5} more\")
"
echo ""

# STEP 2: Clone Repositories
echo "────────────────────────────────────────────────────────────────────────────────"
echo "STEP 2/2: Cloning repositories"
echo "────────────────────────────────────────────────────────────────────────────────"
echo ""

if [ "$SKIP_CLONE" = true ]; then
    echo "⏩ Skipping clone (--skip-clone specified)"
    echo "   Using existing repositories in $WORK_DIR/repos/"
    CLONED_COUNT=$(ls -1 "$WORK_DIR/repos" 2>/dev/null | wc -l)
    echo "   Found: $CLONED_COUNT repos"
else
    echo "Cloning repositories (8 parallel workers, shallow clone)..."
    echo ""
    
    python3 -c "
import json
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def clone_repo(repo_info):
    \"\"\"Clone a single repository (designed for parallel execution)\"\"\"
    idx, total, repo = repo_info
    repo_name = repo['name']
    clone_url = repo['clone_url']
    full_name = repo.get('full_name', repo_name)
    repo_path = Path('$WORK_DIR/repos') / repo_name
    
    # Check if already exists
    if repo_path.exists():
        return (idx, total, repo_name, full_name, 'cached', None)
    
    # Clone the repo
    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', '--filter=blob:none', '--quiet', clone_url, str(repo_path)],
            capture_output=True,
            timeout=120
        )
        if result.returncode == 0:
            return (idx, total, repo_name, full_name, 'success', None)
        else:
            error_msg = result.stderr.decode()[:50] if result.stderr else 'git error'
            return (idx, total, repo_name, full_name, 'error', error_msg)
    except subprocess.TimeoutExpired:
        return (idx, total, repo_name, full_name, 'error', 'timeout (>120s)')
    except Exception as e:
        return (idx, total, repo_name, full_name, 'error', str(e)[:30])

# Load repos
with open('$WORK_DIR/repos.json') as f:
    data = json.load(f)

repos_dir = Path('$WORK_DIR/repos')
repos_dir.mkdir(parents=True, exist_ok=True)

total = len(data['repos'])
cloned = 0
skipped = 0
failed = []

# Prepare repo info with indices
repo_tasks = [(i+1, total, repo) for i, repo in enumerate(data['repos'])]

# Use ThreadPoolExecutor for parallel cloning (max 8 concurrent clones)
max_workers = min(8, total)
print_lock = threading.Lock()

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit all clone tasks
    futures = {executor.submit(clone_repo, task): task for task in repo_tasks}
    
    # Process results as they complete
    for future in as_completed(futures):
        idx, total, repo_name, full_name, status, error = future.result()
        
        with print_lock:
            if status == 'cached':
                print(f'  [{idx:2d}/{total}] ✓ {repo_name:40s} (already cloned)', flush=True)
                cloned += 1
                skipped += 1
            elif status == 'success':
                print(f'  [{idx:2d}/{total}] ✓ {repo_name:40s} (cloned)', flush=True)
                cloned += 1
            else:
                print(f'  [{idx:2d}/{total}] ✗ {repo_name:40s} ({error})', flush=True)
                failed.append({'name': repo_name, 'full_name': full_name, 'error': error})

print()
print(f'Summary:')
print(f'  • Successfully cloned: {cloned - skipped} new repos')
print(f'  • Already cached: {skipped} repos')
print(f'  • Total available: {cloned} repos')

# Report and save failed repos for user visibility
if failed:
    print(f'  • Failed: {len(failed)} repos')
    print()
    print('Failed repositories:')
    for f in failed:
        print(f'    - {f[\"full_name\"]}: {f[\"error\"]}')
    
    # Save failed repos to a file for reference
    failed_file = Path('$WORK_DIR/clone_failures.json')
    with open(failed_file, 'w') as ff:
        json.dump({'failed_count': len(failed), 'failures': failed}, ff, indent=2)
    print()
    print(f'  ℹ️  Failed repos saved to: $WORK_DIR/clone_failures.json')

if cloned < 3:
    print()
    print('❌ ERROR: Too few repos cloned (minimum 3 required)')
    sys.exit(3)
"
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ ERROR: Repository cloning failed"
        exit 3
    fi
    
    CLONED_COUNT=$(ls -1 "$WORK_DIR/repos" 2>/dev/null | wc -l)
fi

echo ""
echo "✅ $CLONED_COUNT repositories available for analysis"
echo ""

# Note: analysis.log is automatically created by the logging redirection at the top

# Summary
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  ✅ DATA GATHERING COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "📁 Analysis workspace: $WORK_DIR/"
echo ""
echo "Generated data:"
echo "  • repos.json          - $REPO_COUNT repositories metadata (stars, URLs, descriptions)"
echo "  • repos/              - $CLONED_COUNT cloned repositories ready for analysis"
echo "  • analysis.log        - This execution log"
echo ""
echo "────────────────────────────────────────────────────────────────────────────────"
echo "🤖 NEXT: Claude AI Analysis"
echo "────────────────────────────────────────────────────────────────────────────────"
echo ""
echo "Claude should now:"
echo ""
echo "  1. READ repos.json to see which repositories were found"
echo ""
echo "  2. EXPLORE the cloned repos in $WORK_DIR/repos/"
echo "     • Read actual code (types, controllers, webhooks)"
echo "     • Find struct definitions for $PATTERN"
echo "     • Understand implementation approaches"
echo "     • Extract validation/logic examples"
echo ""
echo "  3. ANALYZE your current repository:"
echo "     • Explore directory structure"
echo "     • Read go.mod for dependencies"
echo "     • Find existing patterns (CRDs, controllers, webhooks)"
echo "     • Understand what your project does"
echo ""
echo "  4. GENERATE detailed recommendations:"
echo "     • Statistical insights (X% of repos use Y)"
echo "     • Code examples from similar repos"
echo "     • Specific file paths for YOUR project"
echo "     • Complete, working implementation code"
echo "     • Step-by-step integration guide"
echo ""
echo "  5. CREATE summary file:"
echo "     • Save as: $WORK_DIR/ANALYSIS.md"
echo "     • Include: Statistics, examples, recommendations, code"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "🔍 Quick start for Claude:"
echo ""
echo "  cat $WORK_DIR/repos.json"
echo "  ls $WORK_DIR/repos/"
echo "  # Explore repos, analyze code, generate ANALYSIS.md"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
