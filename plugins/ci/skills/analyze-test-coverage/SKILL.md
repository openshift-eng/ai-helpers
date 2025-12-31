---
name: Analyze Test Coverage
description: Determine which OpenShift CI jobs will execute specific tests based on test labels
---

# Analyze Test Coverage Skill

This skill helps developers and QE engineers determine which OpenShift CI jobs their tests will be executed in by analyzing test labels (tags). It provides actionable recommendations when tests won't run in expected jobs.

## Goal

**Primary Purpose:** Determine if tests will run in OpenShift CI jobs based on their Ginkgo test labels.

**Key Principles:**
1. Tests need explicit conformance suite tags to run in blocking jobs
2. For new tests, it is **NOT recommended** to add them to blocking jobs initially
3. Tests should earn their way into blocking jobs through stability and importance
4. The analysis helps developers understand test coverage BEFORE submitting PRs

## When to Use This Skill

Use this skill when:
- **Reviewing PRs** to discover which jobs will run the new/modified tests
- Adding new tests to openshift/origin
- Debugging why tests aren't running in expected CI jobs
- Understanding which jobs will run existing tests
- Planning test suite coverage strategy
- Verifying test coverage before submitting changes

## Prerequisites

### Required Repositories

Both repositories must be locally available:

1. **openshift/origin** - Contains test files and suite definitions
2. **openshift/release** - Contains CI job configurations

### Required Tools

- `gh` (GitHub CLI)
- `jq` (JSON processor)
- `yq` (YAML processor)
- `python3` (for helper scripts)
- `grep`/`ripgrep`

### Repository Auto-Detection

The skill will automatically search for repositories in common locations:
- `~/github-go/openshift/{origin,release}`
- `~/go/src/github.com/openshift/{origin,release}`
- `~/src/github.com/openshift/{origin,release}`

If not found, prompt the user to set environment variables:
```bash
export ORIGIN_REPO=/path/to/openshift/origin
export RELEASE_REPO=/path/to/openshift/release
```

## Implementation Steps

### Step 1: Validate Prerequisites

Check all required tools and repositories are available:

```bash
#!/bin/bash

# Function to check command exists
check_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: Required command '$1' not found"
    echo "Install with: brew install $1"
    return 1
  fi
  return 0
}

# Check required commands
MISSING=()
for cmd in gh jq yq python3 grep; do
  check_command "$cmd" || MISSING+=("$cmd")
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "Missing required tools: ${MISSING[*]}"
  echo "Please install them before continuing"
  exit 1
fi

echo "✓ All required tools are available"
```

### Step 2: Locate Required Repositories

Auto-detect or prompt for repository locations:

```bash
#!/bin/bash

# Function to find repository
find_repo() {
  local repo_name=$1
  local env_var=$2

  # Check environment variable first
  if [[ -n "${!env_var}" && -d "${!env_var}/.git" ]]; then
    echo "${!env_var}"
    return 0
  fi

  # Search common locations
  local search_paths=(
    "$HOME/github-go/openshift/$repo_name"
    "$HOME/go/src/github.com/openshift/$repo_name"
    "$HOME/src/github.com/openshift/$repo_name"
  )

  for path in "${search_paths[@]}"; do
    if [[ -d "$path/.git" ]]; then
      echo "$path"
      return 0
    fi
  done

  return 1
}

# Locate origin repository
ORIGIN_REPO=$(find_repo "origin" "ORIGIN_REPO")
if [[ -z "$ORIGIN_REPO" ]]; then
  echo "Error: openshift/origin repository not found"
  echo "Please set: export ORIGIN_REPO=/path/to/openshift/origin"
  exit 1
fi

# Locate release repository
RELEASE_REPO=$(find_repo "release" "RELEASE_REPO")
if [[ -z "$RELEASE_REPO" ]]; then
  echo "Error: openshift/release repository not found"
  echo "Please set: export RELEASE_REPO=/path/to/openshift/release"
  exit 1
fi

echo "Using repositories:"
echo "  Origin:  $ORIGIN_REPO"
echo "  Release: $RELEASE_REPO"
```

### Step 3: Parse Input Arguments

Handle test input (required) and job filter (optional):

```bash
#!/bin/bash

TEST_INPUT="$1"   # Required: file path, labels string, or PR URL/number
JOB_FILTER="$2"   # Optional: version, job pattern, specific job, or file

# Determine if test input is a PR, file, or labels
if [[ "$TEST_INPUT" =~ ^https://github\.com/([^/]+)/([^/]+)/pull/([0-9]+) ]]; then
  # PR URL format: https://github.com/openshift/origin/pull/12345
  PR_OWNER="${BASH_REMATCH[1]}"
  PR_REPO="${BASH_REMATCH[2]}"
  PR_NUMBER="${BASH_REMATCH[3]}"
  echo "Analyzing PR: $PR_OWNER/$PR_REPO#$PR_NUMBER"
  INPUT_TYPE="pr"
elif [[ "$TEST_INPUT" =~ ^([^/]+)/([^#]+)#([0-9]+)$ ]]; then
  # Repo#PR format: openshift/origin#12345
  PR_OWNER="${BASH_REMATCH[1]}"
  PR_REPO="${BASH_REMATCH[2]}"
  PR_NUMBER="${BASH_REMATCH[3]}"
  echo "Analyzing PR: $PR_OWNER/$PR_REPO#$PR_NUMBER"
  INPUT_TYPE="pr"
elif [[ "$TEST_INPUT" =~ ^#?([0-9]+)$ ]]; then
  # Just PR number (assume openshift/origin)
  PR_OWNER="openshift"
  PR_REPO="origin"
  PR_NUMBER="${BASH_REMATCH[1]}"
  echo "Analyzing PR: $PR_OWNER/$PR_REPO#$PR_NUMBER (assumed repository)"
  INPUT_TYPE="pr"
elif [[ -f "$TEST_INPUT" ]]; then
  echo "Analyzing test file: $TEST_INPUT"
  TEST_FILE="$TEST_INPUT"
  TEST_LABELS=""  # Will extract from file
  INPUT_TYPE="file"
elif [[ -f "$ORIGIN_REPO/$TEST_INPUT" ]]; then
  echo "Analyzing test file: $ORIGIN_REPO/$TEST_INPUT"
  TEST_FILE="$ORIGIN_REPO/$TEST_INPUT"
  TEST_LABELS=""
  INPUT_TYPE="file"
else
  echo "Analyzing test labels: $TEST_INPUT"
  TEST_FILE=""
  TEST_LABELS="$TEST_INPUT"
  INPUT_TYPE="labels"
fi

# Parse job filter (optional)
if [[ -z "$JOB_FILTER" ]]; then
  echo "No filter specified - will analyze all blocking jobs"
  FILTER_MODE="all-blocking"
elif [[ -f "$JOB_FILTER" ]]; then
  echo "Loading jobs from file: $JOB_FILTER"
  mapfile -t JOBS < "$JOB_FILTER"
  FILTER_MODE="explicit-list"
elif [[ "$JOB_FILTER" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "Filtering jobs for version: $JOB_FILTER"
  FILTER_MODE="version"
  VERSION="$JOB_FILTER"
elif [[ "$JOB_FILTER" == *"periodic-ci"* ]]; then
  echo "Analyzing specific job: $JOB_FILTER"
  JOBS=("$JOB_FILTER")
  FILTER_MODE="explicit-list"
else
  echo "Filtering jobs by pattern: $JOB_FILTER"
  FILTER_MODE="pattern"
  PATTERN="$JOB_FILTER"
fi
```

### Step 3a: Handle PR Input

If input is a PR, fetch changed test files and extract labels:

```bash
#!/bin/bash

if [[ "$INPUT_TYPE" == "pr" ]]; then
  echo "Fetching PR files from $PR_OWNER/$PR_REPO#$PR_NUMBER..."

  # Get list of changed files in the PR
  PR_FILES=$(gh pr view "$PR_NUMBER" \
    --repo "$PR_OWNER/$PR_REPO" \
    --json files \
    --jq '.files[].path' 2>/dev/null)

  if [[ -z "$PR_FILES" ]]; then
    echo "Error: Failed to fetch PR files. Make sure:"
    echo "  1. PR number is correct"
    echo "  2. You have access to the repository"
    echo "  3. gh CLI is authenticated (run: gh auth status)"
    exit 1
  fi

  # Filter for test files (*_test.go)
  TEST_FILES_IN_PR=$(echo "$PR_FILES" | grep '_test\.go$')

  if [[ -z "$TEST_FILES_IN_PR" ]]; then
    echo "No test files found in PR #$PR_NUMBER"
    echo ""
    echo "Changed files:"
    echo "$PR_FILES" | sed 's/^/  - /'
    echo ""
    echo "This PR does not add or modify any test files."
    exit 0
  fi

  echo "Found test files in PR:"
  echo "$TEST_FILES_IN_PR" | sed 's/^/  - /'
  echo ""

  # Determine repository path to use
  if [[ "$PR_REPO" == "origin" ]]; then
    REPO_PATH="$ORIGIN_REPO"
  elif [[ "$PR_REPO" == "release" ]]; then
    REPO_PATH="$RELEASE_REPO"
  else
    echo "Warning: Unsupported repository: $PR_REPO"
    echo "Only openshift/origin and openshift/release are supported"
    exit 1
  fi

  # Extract labels from all test files
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  EXTRACT_SCRIPT="$SCRIPT_DIR/extract_test_labels.py"

  if [[ ! -f "$EXTRACT_SCRIPT" ]]; then
    echo "Error: Helper script not found: $EXTRACT_SCRIPT"
    exit 1
  fi

  ALL_LABELS=()
  while IFS= read -r test_file; do
    full_path="$REPO_PATH/$test_file"

    if [[ ! -f "$full_path" ]]; then
      echo "Warning: File not found locally: $full_path"
      echo "Make sure your local repository is up to date with the PR branch"
      continue
    fi

    echo "Extracting labels from: $test_file"
    labels=$(python3 "$EXTRACT_SCRIPT" "$full_path" 2>/dev/null)

    if [[ -n "$labels" ]]; then
      while IFS= read -r label; do
        ALL_LABELS+=("$label")
      done <<< "$labels"
    fi
  done <<< "$TEST_FILES_IN_PR"

  # Remove duplicates and sort
  TEST_LABELS=$(printf '%s\n' "${ALL_LABELS[@]}" | sort -u)

  if [[ -z "$TEST_LABELS" ]]; then
    echo ""
    echo "⚠️  No test labels found in any test files"
    echo ""
    echo "Test files analyzed:"
    echo "$TEST_FILES_IN_PR" | sed 's/^/  - /'
    echo ""
    echo "Make sure test descriptions include labels like:"
    echo '  g.It("test description [sig-cli][Feature:Example]", func() {'
    echo ""
    exit 0
  fi

  echo ""
  echo "Extracted labels from PR:"
  echo "$TEST_LABELS" | sed 's/^/  - [/; s/$/]/'
  echo ""
fi
```

### Step 3b: Discover Jobs Based on Filter

Discover which jobs to analyze based on the filter:

```bash
#!/bin/bash

function discover_jobs() {
  local filter_mode="$1"
  local filter_value="$2"
  local release_repo="$3"

  local jobs_dir="$release_repo/ci-operator/jobs/openshift/release"
  local discovered_jobs=()

  case "$filter_mode" in
    "all-blocking")
      # Find all blocking jobs (jobs in release-blocking-* files)
      for yaml_file in "$jobs_dir"/*-periodics.yaml; do
        # Extract job names, filter for blocking patterns
        discovered_jobs+=($(yq eval '.periodics[].name' "$yaml_file" 2>/dev/null | \
          grep -E "(nightly|ci).*-4\.[0-9]+" | \
          grep -v "optional"))
      done
      ;;

    "version")
      # Filter jobs for specific version (e.g., 4.21)
      for yaml_file in "$jobs_dir"/*-periodics.yaml; do
        discovered_jobs+=($(yq eval '.periodics[].name' "$yaml_file" 2>/dev/null | \
          grep "$filter_value"))
      done
      ;;

    "pattern")
      # Filter jobs matching pattern (e.g., "nightly-blocking")
      for yaml_file in "$jobs_dir"/*-periodics.yaml; do
        discovered_jobs+=($(yq eval '.periodics[].name' "$yaml_file" 2>/dev/null | \
          grep "$filter_value"))
      done
      ;;

    "explicit-list")
      # Jobs already provided
      discovered_jobs=("${JOBS[@]}")
      ;;
  esac

  printf '%s\n' "${discovered_jobs[@]}"
}

# Discover jobs
case "$FILTER_MODE" in
  "explicit-list")
    echo "Using ${#JOBS[@]} explicitly provided job(s)"
    ;;
  *)
    mapfile -t JOBS < <(discover_jobs "$FILTER_MODE" "${VERSION:-$PATTERN}" "$RELEASE_REPO")
    echo "Discovered ${#JOBS[@]} jobs matching filter"
    ;;
esac

if [[ ${#JOBS[@]} -eq 0 ]]; then
  echo "Error: No jobs found matching filter"
  exit 1
fi
```

### Step 4: Extract Test Labels

Use the helper script to parse Go test files and extract Ginkgo labels:

**Create:** `plugins/ci/skills/analyze-test-coverage/extract_test_labels.py`

```python
#!/usr/bin/env python3
"""
Extract Ginkgo test labels from Go test files.
Handles various Ginkgo test description formats.
"""

import re
import sys
from pathlib import Path

def extract_labels_from_line(line):
    """Extract all [Label] tags from a test description."""
    # Match patterns like: [sig-cli], [Suite:openshift/conformance/parallel]
    pattern = r'\[([^\]]+)\]'
    matches = re.findall(pattern, line)
    return matches

def extract_from_file(filepath):
    """Extract all unique labels from a test file."""
    labels = set()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                # Look for Ginkgo test descriptions
                # Patterns: g.It("...", ...), It("...", ...), g.Describe("...", ...)
                if re.search(r'\b(It|g\.It|Describe|g\.Describe|Context|g\.Context)\s*\(', line):
                    found_labels = extract_labels_from_line(line)
                    labels.update(found_labels)
    except Exception as e:
        print(f"Error reading file {filepath}: {e}", file=sys.stderr)
        return set()

    return labels

def main():
    if len(sys.argv) != 2:
        print("Usage: extract_test_labels.py <test-file.go>", file=sys.stderr)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    labels = extract_from_file(filepath)

    # Output one label per line, sorted
    for label in sorted(labels):
        print(label)

if __name__ == '__main__':
    main()
```

**Usage in skill:**

```bash
# Extract labels from test file
if [[ -n "$TEST_FILE" ]]; then
  echo "Extracting labels from test file..."

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  EXTRACT_SCRIPT="$SCRIPT_DIR/extract_test_labels.py"

  if [[ ! -f "$EXTRACT_SCRIPT" ]]; then
    echo "Error: Helper script not found: $EXTRACT_SCRIPT"
    exit 1
  fi

  TEST_LABELS=$(python3 "$EXTRACT_SCRIPT" "$TEST_FILE")

  if [[ -z "$TEST_LABELS" ]]; then
    echo "Warning: No test labels found in file"
    echo "Make sure test descriptions include labels like [sig-cli]"
  else
    echo "Found labels:"
    echo "$TEST_LABELS" | sed 's/^/  - /'
  fi
fi
```

### Step 5: Analyze Test Suite Definitions

Load suite definitions from `pkg/testsuites/standard_suites.go`:

**Create:** `plugins/ci/skills/analyze-test-coverage/parse_suites.py`

```python
#!/usr/bin/env python3
"""
Parse test suite definitions from standard_suites.go
Extracts suite names and their filter qualifiers.
"""

import re
import sys
import json
from pathlib import Path

def parse_suites(filepath):
    """
    Parse standard_suites.go and extract suite definitions.

    Returns: dict mapping suite names to their qualifiers
    Example: {
        "openshift/conformance/parallel": ["name.contains('[Suite:openshift/conformance/parallel')"],
        "openshift/conformance/serial": ["name.contains('[Suite:openshift/conformance/serial')"],
        "all": ["true"]
    }
    """
    suites = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match suite definitions
    # Looks for: Name: "suite-name", followed by Qualifiers: []string{...}
    suite_pattern = r'Name:\s*"([^"]+)"[\s\S]*?Qualifiers:\s*\[\]string\{([^}]+)\}'

    for match in re.finditer(suite_pattern, content):
        suite_name = match.group(1)
        qualifiers_block = match.group(2)

        # Extract individual qualifier strings
        qualifier_pattern = r'"([^"]+)"'
        qualifiers = re.findall(qualifier_pattern, qualifiers_block)

        suites[suite_name] = qualifiers

    return suites

def main():
    if len(sys.argv) != 2:
        print("Usage: parse_suites.py <origin-repo-path>", file=sys.stderr)
        sys.exit(1)

    origin_path = Path(sys.argv[1])
    suites_file = origin_path / "pkg/testsuites/standard_suites.go"

    if not suites_file.exists():
        print(f"Error: Suite definitions not found: {suites_file}", file=sys.stderr)
        sys.exit(1)

    suites = parse_suites(suites_file)

    # Output as JSON
    print(json.dumps(suites, indent=2))

if __name__ == '__main__':
    main()
```

**Usage in skill:**

```bash
# Parse suite definitions
echo "Loading test suite definitions..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARSE_SUITES_SCRIPT="$SCRIPT_DIR/parse_suites.py"

SUITES_JSON=$(python3 "$PARSE_SUITES_SCRIPT" "$ORIGIN_REPO")

if [[ -z "$SUITES_JSON" ]]; then
  echo "Error: Failed to parse suite definitions"
  exit 1
fi

echo "Loaded suite definitions"
```

### Step 6: Analyze CI Job Configurations

For each job, extract the test suite and workflow configuration:

**Create:** `plugins/ci/skills/analyze-test-coverage/analyze_job.py`

```python
#!/usr/bin/env python3
"""
Analyze a CI job configuration to determine which test suite it uses.
"""

import sys
import json
import yaml
from pathlib import Path

def find_job_config(release_repo, job_name):
    """Find the job configuration file for a given job name."""
    # Jobs are typically in ci-operator/jobs/openshift/release/
    jobs_dir = release_repo / "ci-operator/jobs/openshift/release"

    if not jobs_dir.exists():
        return None

    # Search for job in periodics files
    for yaml_file in jobs_dir.glob("*-periodics.yaml"):
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            if not data or 'periodics' not in data:
                continue

            for job in data['periodics']:
                if job.get('name') == job_name:
                    return {'file': str(yaml_file), 'job': job}
        except Exception as e:
            print(f"Warning: Error parsing {yaml_file}: {e}", file=sys.stderr)

    return None

def extract_test_suite(job_config, release_repo):
    """
    Extract TEST_SUITE from job configuration.

    Looks in:
    1. Job spec.env directly
    2. Workflow steps (from step-registry)
    """
    test_suite = None
    workflow_name = None

    # Check job env vars directly
    spec = job_config.get('spec', {})
    env_vars = spec.get('env', [])

    for env in env_vars:
        if env.get('name') == 'TEST_SUITE':
            test_suite = env.get('value')
            break

    # If not in job, check workflow
    if not test_suite:
        # Extract workflow name from job steps
        if 'steps' in spec:
            workflow_name = spec['steps'].get('workflow')

        if workflow_name:
            # Load workflow definition
            workflow_path = release_repo / f"ci-operator/step-registry/{workflow_name.replace('-', '/')}/{workflow_name}-workflow.yaml"

            if workflow_path.exists():
                with open(workflow_path, 'r') as f:
                    workflow = yaml.safe_load(f)

                # Check workflow env
                env_vars = workflow.get('env', [])
                for env in env_vars:
                    if env.get('name') == 'TEST_SUITE':
                        test_suite = env.get('value')
                        break

    return {
        'test_suite': test_suite,
        'workflow': workflow_name
    }

def main():
    if len(sys.argv) != 3:
        print("Usage: analyze_job.py <release-repo-path> <job-name>", file=sys.stderr)
        sys.exit(1)

    release_repo = Path(sys.argv[1])
    job_name = sys.argv[2]

    # Find job configuration
    job_data = find_job_config(release_repo, job_name)

    if not job_data:
        print(json.dumps({'error': f'Job not found: {job_name}'}))
        sys.exit(1)

    # Extract test suite information
    suite_info = extract_test_suite(job_data['job'], release_repo)

    result = {
        'job_name': job_name,
        'config_file': job_data['file'],
        'test_suite': suite_info['test_suite'],
        'workflow': suite_info['workflow']
    }

    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
```

**Usage in skill:**

```bash
# Analyze each job
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYZE_JOB_SCRIPT="$SCRIPT_DIR/analyze_job.py"

for job in "${JOBS[@]}"; do
  echo "Analyzing job: $job"

  JOB_INFO=$(python3 "$ANALYZE_JOB_SCRIPT" "$RELEASE_REPO" "$job")

  if echo "$JOB_INFO" | jq -e '.error' >/dev/null 2>&1; then
    echo "  ⚠️  Job not found: $job"
    continue
  fi

  TEST_SUITE=$(echo "$JOB_INFO" | jq -r '.test_suite // "unknown"')
  WORKFLOW=$(echo "$JOB_INFO" | jq -r '.workflow // "unknown"')

  echo "  Suite: $TEST_SUITE"
  echo "  Workflow: $WORKFLOW"
done
```

### Step 7: Match Tests Against Suite Filters

Determine if test labels match the suite's filter qualifiers:

```bash
#!/bin/bash

# Function to check if test labels match suite filter
test_matches_suite() {
  local test_labels="$1"      # Newline-separated list of labels
  local suite_qualifiers="$2" # JSON array of qualifiers

  # Extract qualifier count
  local qualifier_count=$(echo "$suite_qualifiers" | jq 'length')

  if [[ $qualifier_count -eq 0 ]]; then
    return 0  # No filters = matches everything
  fi

  # Check each qualifier
  for ((i=0; i<qualifier_count; i++)); do
    local qualifier=$(echo "$suite_qualifiers" | jq -r ".[$i]")

    # Handle special case: "true" matches everything
    if [[ "$qualifier" == "true" ]]; then
      return 0
    fi

    # Parse CEL expression: name.contains('[Tag]')
    # Simplification: Extract the tag requirement from the contains() call
    if [[ "$qualifier" =~ name\.contains\([\'\"]\[([^\]]+)\] ]]; then
      local required_tag="${BASH_REMATCH[1]}"

      # Check if test has this tag
      if echo "$test_labels" | grep -q "^${required_tag}$"; then
        return 0  # Match found
      fi
    fi
  done

  return 1  # No match
}

# Example usage
SUITE_QUALIFIERS=$(echo "$SUITES_JSON" | jq '.["openshift/conformance/parallel"]')

if test_matches_suite "$TEST_LABELS" "$SUITE_QUALIFIERS"; then
  echo "✅ Tests WILL run in this job"
else
  echo "❌ Tests WILL NOT run in this job"
fi
```

### Step 8: Generate Recommendations

Based on the analysis, provide actionable recommendations:

```bash
#!/bin/bash

generate_recommendations() {
  local test_labels="$1"
  local matching_jobs_count="$2"
  local total_jobs_count="$3"

  echo ""
  echo "## Recommendations"
  echo ""

  if [[ $matching_jobs_count -eq 0 ]]; then
    echo "### ⚠️  Tests Will Not Run in Any Analyzed Jobs"
    echo ""
    echo "**Analysis:** Your tests lack the conformance suite tags required by blocking CI jobs."
    echo ""
    echo "**Recommended Action:**"
    echo ""
    echo "**For new tests, it is NOT recommended to add them to blocking jobs immediately.**"
    echo "New tests should:"
    echo "1. Start in optional/informing jobs"
    echo "2. Prove stability over time (2-4 weeks)"
    echo "3. Demonstrate value and importance"
    echo "4. Only then be promoted to blocking jobs"
    echo ""
    echo "**Option 1: Run in Optional Jobs (Recommended for New Tests)**"
    echo ""
    echo "Create or use existing optional CI jobs with \`TEST_SUITE: all\` or specific sig filters:"
    echo ""
    echo "\`\`\`yaml"
    echo "- as: e2e-aws-sig-cli-optional"
    echo "  interval: 168h  # Weekly"
    echo "  steps:"
    echo "    cluster_profile: aws"
    echo "    workflow: openshift-e2e-aws"
    echo "    env:"
    echo "      TEST_SUITE: all"
    echo "      TEST_ARGS: '--ginkgo.focus=\\[sig-cli\\]'"
    echo "\`\`\`"
    echo ""
    echo "**Option 2: Add Conformance Tags (Only for Established Tests)**"
    echo ""
    echo "If your tests have proven stable and are critical for cluster health:"
    echo ""

    # Check which conformance tags are missing
    if ! echo "$test_labels" | grep -q "Suite:openshift/conformance/parallel"; then
      echo "For parallel execution:"
      echo "\`\`\`go"
      echo "g.It(\"test description [Suite:openshift/conformance/parallel][sig-cli]\", func() {"
      echo "    // Test implementation"
      echo "})"
      echo "\`\`\`"
      echo ""
    fi

    if ! echo "$test_labels" | grep -q "Suite:openshift/conformance/serial"; then
      echo "For serial execution (tests that modify cluster-wide state):"
      echo "\`\`\`go"
      echo "g.It(\"test description [Suite:openshift/conformance/serial][sig-cli]\", func() {"
      echo "    // Test implementation"
      echo "})"
      echo "\`\`\`"
      echo ""
    fi

    echo "**Important:** Adding conformance tags makes tests run in blocking jobs."
    echo "Blocking jobs prevent merges and releases if they fail."
    echo "Only add conformance tags if:"
    echo "- Test has proven stable (>98% pass rate over 2+ weeks)"
    echo "- Test validates critical cluster functionality"
    echo "- Team commits to maintaining and fixing flakes promptly"
    echo ""

  elif [[ $matching_jobs_count -lt $total_jobs_count ]]; then
    echo "### ✅ Tests Run in Some Jobs ($matching_jobs_count/$total_jobs_count)"
    echo ""
    echo "Your tests will run in $matching_jobs_count out of $total_jobs_count analyzed jobs."
    echo ""
    echo "If you expected tests to run in more jobs, verify:"
    echo "1. Jobs use compatible test suites"
    echo "2. Tests have appropriate conformance tags"
    echo "3. Jobs aren't upgrade-only (which run limited test sets)"
    echo ""

  else
    echo "### ✅ Tests Run in All Analyzed Jobs"
    echo ""
    echo "Your tests are properly tagged and will run in all $total_jobs_count analyzed jobs."
    echo ""
  fi
}
```

### Step 9: Generate Analysis Report

Create a comprehensive markdown report:

```bash
#!/bin/bash

generate_report() {
  local test_file="$1"
  local test_labels="$2"
  local jobs_analyzed="$3"
  local jobs_matched="$4"
  local jobs_not_matched="$5"

  cat << 'EOF'
# Test Coverage Analysis Report

**Generated:** $(date -u '+%Y-%m-%d %H:%M:%S UTC')

---

## Summary

EOF

  echo "- **Test File:** ${test_file:-N/A}"
  echo "- **Jobs Analyzed:** $jobs_analyzed"
  echo "- **✅ Tests WILL run in:** $jobs_matched jobs"
  echo "- **❌ Tests WILL NOT run in:** $jobs_not_matched jobs"
  echo ""
  echo "## Test Labels Found"
  echo ""
  if [[ -n "$test_labels" ]]; then
    echo "$test_labels" | while read -r label; do
      echo "- \`[$label]\`"
    done
  else
    echo "*No labels found*"
  fi

  echo ""
  echo "---"
  echo ""
  echo "## Detailed Job Analysis"
  echo ""

  # Job-specific analysis follows...
}
```

## Error Handling

### Common Error Scenarios

1. **Repository Not Found**
   ```
   Error: openshift/origin repository not found

   Searched locations:
   - ~/github-go/openshift/origin
   - ~/go/src/github.com/openshift/origin
   - ~/src/github.com/openshift/origin

   Please set: export ORIGIN_REPO=/path/to/openshift/origin
   ```

2. **Job Not Found**
   ```
   Warning: Job 'e2e-aws-ovn-4.21' not found

   Possible matches:
   - periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn
   - periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn

   Tip: Use full job name from 'gh pr checks' or job logs
   ```

3. **No Labels Found**
   ```
   Warning: No test labels found in test/extended/cli/example.go

   Make sure test descriptions include labels:
   g.It("test name [sig-cli][Feature:Example]", func() {
   ```

4. **Missing Helper Scripts**
   ```
   Error: Helper script not found: plugins/ci/skills/analyze-test-coverage/extract_test_labels.py

   Please ensure all helper scripts are present in:
   plugins/ci/skills/analyze-test-coverage/
   ```

## Testing the Implementation

### Test Case 1: Analyze PR to discover which jobs will run its tests

```bash
/ci:analyze-test-coverage https://github.com/openshift/origin/pull/12345
```

**Expected:**
- Fetches PR files using gh CLI
- Identifies test files in PR (e.g., 2 _test.go files found)
- Extracts labels from all test files
- Discovers all blocking jobs (40-50 jobs)
- Shows which jobs will/won't run the PR's tests
- Provides recommendations for new tests

### Test Case 2: Analyze PR with shorthand syntax

```bash
/ci:analyze-test-coverage openshift/origin#12345
# or just:
/ci:analyze-test-coverage #12345
```

**Expected:**
- Same as Test Case 1
- Works with repo#PR or just #PR format (assumes openshift/origin)

### Test Case 3: Analyze PR for specific version jobs

```bash
/ci:analyze-test-coverage https://github.com/openshift/origin/pull/12345 4.21
```

**Expected:**
- Fetches PR files
- Extracts labels from test files
- Analyzes only 4.21 jobs (20-30 jobs)
- Shows coverage for that release version

### Test Case 4: Discover which jobs will run a test file (default behavior)

```bash
/ci:analyze-test-coverage test/extended/cli/mustgather.go
```

**Expected:**
- Extracts labels from mustgather.go
- Discovers all blocking jobs (40-50 jobs)
- Shows 0 jobs will run (missing conformance tags)
- Lists all jobs that won't run with reasons
- Recommends starting in optional jobs

### Test Case 5: Discover jobs for specific version using labels

```bash
/ci:analyze-test-coverage "[sig-cli][Feature:CLI]" 4.21
```

**Expected:**
- Uses labels directly
- Discovers all 4.21 jobs (20-30 jobs)
- Shows which jobs will/won't run
- Explains missing tags

### Test Case 6: Check if specific job will run test

```bash
/ci:analyze-test-coverage "[sig-network][Suite:openshift/conformance/parallel]" periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn
```

**Expected:**
- Analyzes only that one job
- Shows tests WILL run (has required tag)
- Confirms label match

### Test Case 7: Discover jobs matching pattern

```bash
/ci:analyze-test-coverage test/extended/builds/build.go nightly-blocking
```

**Expected:**
- Discovers all nightly blocking jobs
- Shows build tests coverage across nightly jobs

## Best Practices

1. **Run analysis before submitting PRs**
   - Understand test coverage impact
   - Add appropriate labels upfront

2. **Start new tests in optional jobs**
   - Let tests prove stability
   - Avoid blocking CI/CD pipeline

3. **Use parallel tags when possible**
   - Faster feedback (30x parallelism)
   - More jobs run parallel suites

4. **Reserve serial tags for disruptive tests**
   - Tests modifying cluster-wide config
   - Tests with shared resource dependencies

5. **Don't over-tag**
   - Only add conformance tags when truly needed
   - More blocking jobs = more maintenance burden

## Performance Characteristics

- **Single job:** ~2-5 seconds
- **10 jobs:** ~10-20 seconds
- **50+ jobs:** ~60-120 seconds

Performance depends on:
- Repository size
- Network access to files
- Number of test labels to analyze

## Related Commands

- `/ci:ask-sippy` - Query test history and stability
- `/ci:list-unstable-tests` - Find flaky tests
- `/ci:query-test-result` - Check specific test results
- `/git:summary` - Show current branch status

## Notes

- Analysis is based on current main branch configurations
- Some jobs may have dynamic TEST_SUITE overrides not captured
- Upgrade jobs typically run only conformance-tagged tests
- Hypershift and other specialized jobs may have different behaviors
