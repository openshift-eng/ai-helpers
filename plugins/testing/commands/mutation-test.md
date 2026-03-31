---
description: Test operator controller quality through mutation testing - validates test suite catches code mutations
argument-hint: "[operator-path] [--controllers <controller1,controller2>] [--mutation-types <types>] [--report-format <format>]"
---

## Name
testing:mutation-test

## Synopsis

```
/testing:mutation-test [operator-path] [--controllers <controller1,controller2>] [--mutation-types <types>] [--report-format <format>]
```

## Description

The `testing:mutation-test` command performs mutation testing on Kubernetes operator controllers to validate the quality and effectiveness of the test suite. Unlike traditional code coverage which only measures if code is executed, mutation testing validates whether tests actually verify the correctness of the code.

**Mutation testing works by:**
1. Creating small, deliberate bugs (mutations) in the controller code
2. Running the test suite against each mutation
3. Checking if tests fail (killing the mutant) or pass (surviving mutant)
4. Surviving mutants indicate weak or missing tests

This command is specifically designed for operator controllers written in Go using controller-runtime, focusing on reconciliation logic, error handling, and state management patterns common in Kubernetes operators.

**Use cases:**
- Validate test suite quality beyond coverage percentages
- Identify missing test cases for edge conditions
- Find untested error handling paths
- Ensure reconciliation logic is properly validated
- Improve operator reliability and test confidence

**What makes this operator-focused:**
- Understands controller-runtime patterns (reconciliation, requeueing, finalizers)
- Focuses on mutations relevant to operators (condition checks, API calls, status updates)
- Identifies untested error scenarios in Kubernetes API interactions
- Validates watch/list/get patterns are tested correctly

## Arguments

- `operator-path` [optional]: Path to the operator repository. Defaults to current directory.
- `--controllers <names>` [optional]: Comma-separated list of controller names to test. If not specified, discovers all controllers automatically.
- `--mutation-types <types>` [optional]: Comma-separated mutation types to apply. Defaults to all. Options: `conditionals`, `returns`, `arithmetic`, `error-handling`, `requeue`, `status`, `api-calls`
- `--report-format <format>` [optional]: Output format. Options: `html`, `markdown`, `json`, `terminal`. Defaults to `html`.

## Implementation

### Workflow Overview

```
- [ ] Step 1: Setup and validate baseline
- [ ] Step 2: Generate mutation metadata (no copies!)
- [ ] Step 3: Test each mutation in-place
- [ ] Step 4: Analyze results and generate report
```

**Key Optimization**: Mutations are applied in-place, not by copying the entire repository. This makes mutation testing:
- **100x faster** - No time wasted copying files
- **99% smaller** - Uses only a few KB instead of GBs
- **Practical** - Can test large repositories quickly

**Important**: The mutation testing automatically **excludes the `vendor/` directory** from analysis, as third-party dependencies should not be mutated.

---

### Step 1: Setup and Validate Baseline

**1.1 Initialize Work Directory**

```bash
OPERATOR_PATH="${1:-.}"
WORK_DIR=".work/mutation-testing"
MUTATIONS_JSON="$WORK_DIR/mutations.json"
RESULTS_DIR="$WORK_DIR/results"

mkdir -p "$WORK_DIR" "$RESULTS_DIR"

cd "$OPERATOR_PATH"
echo "Testing operator at: $(pwd)"
```

**1.2 Run Baseline Tests**

Ensure tests pass before mutation testing:

```bash
echo "Running baseline tests..."

# Test all controller files (controller/controllers dirs and *controller.go files)
go test ./... -v -timeout 10m > "$WORK_DIR/baseline-output.txt" 2>&1
BASELINE_EXIT=$?

if [ $BASELINE_EXIT -ne 0 ]; then
  echo "❌ ERROR: Baseline tests failed"
  echo "Fix failing tests before running mutation testing"
  cat "$WORK_DIR/baseline-output.txt"
  exit 1
fi

echo "✓ Baseline tests passed"

# Record test count and duration for progress estimation
TOTAL_TESTS=$(grep -c "^=== RUN" "$WORK_DIR/baseline-output.txt" || echo "0")
TEST_DURATION=$(grep "^PASS" "$WORK_DIR/baseline-output.txt" | awk '{print $NF}' | sed 's/s//g' | head -1)

echo "Baseline: $TOTAL_TESTS tests in ${TEST_DURATION}s"
```

---

### Step 2: Generate Mutation Metadata

**2.1 Invoke Efficient Mutation Generator**

Generate mutation definitions WITHOUT copying files:

```bash
echo ""
echo "Generating mutations..."

python3 ${CLAUDE_PLUGIN_ROOT}/skills/mutation-generator/generate_mutations_efficient.py \
  --operator-path "$OPERATOR_PATH" \
  --mutation-types "${MUTATION_TYPES:-all}" \
  --output "$MUTATIONS_JSON"

if [ $? -ne 0 ]; then
  echo "❌ Mutation generation failed"
  exit 1
fi

# Load mutations
TOTAL_MUTANTS=$(jq -r '.total_mutations' "$MUTATIONS_JSON")

if [ "$TOTAL_MUTANTS" -eq 0 ]; then
  echo "❌ No mutations generated"
  exit 1
fi

echo "✓ Generated $TOTAL_MUTANTS mutation definitions"
echo ""
```

**Note**: The mutation generator automatically **excludes `vendor/` directories** to avoid mutating third-party dependencies. It analyzes all controller files including:
- Files under `controller/` or `controllers/` directories
- Files matching `*controller.go` pattern anywhere in the codebase (e.g., `operator_controller.go`)
- Related reconciliation logic and helper functions

**2.2 Filter by Controllers (Optional)**

If `--controllers` flag is provided, filter mutations:

```bash
if [ -n "$CONTROLLERS" ]; then
  echo "Filtering to controllers: $CONTROLLERS"
  
  # Filter mutations JSON
  jq --arg controllers "$CONTROLLERS" '
    .mutations |= map(select(.file | test($controllers)))
  ' "$MUTATIONS_JSON" > "$MUTATIONS_JSON.tmp"
  
  mv "$MUTATIONS_JSON.tmp" "$MUTATIONS_JSON"
  
  TOTAL_MUTANTS=$(jq -r '.total_mutations' "$MUTATIONS_JSON")
  echo "Filtered to $TOTAL_MUTANTS mutations"
fi
```

---

### Step 3: Test Each Mutation In-Place

**3.1 Initialize Counters**

```bash
KILLED_MUTANTS=0
SURVIVED_MUTANTS=0
TIMEOUT_MUTANTS=0

echo "Testing $TOTAL_MUTANTS mutations..."
echo "Estimated time: $((TOTAL_MUTANTS * TEST_DURATION / 60)) minutes"
echo ""
```

**3.2 Test Each Mutation**

Apply mutation → Test → Revert (no copying!):

```bash
# Extract mutations array (using process substitution to preserve variable scope)
while IFS= read -r mutation; do
  MUTANT_ID=$(echo "$mutation" | jq -r '.id')
  MUTATION_TYPE=$(echo "$mutation" | jq -r '.type')
  MUTATION_DESC=$(echo "$mutation" | jq -r '.description')
  
  # Save individual mutation
  MUTATION_FILE="$WORK_DIR/${MUTANT_ID}.json"
  echo "$mutation" > "$MUTATION_FILE"
  
  echo -n "[$((KILLED_MUTANTS + SURVIVED_MUTANTS + 1))/$TOTAL_MUTANTS] Testing $MUTANT_ID ($MUTATION_TYPE)... "
  
  # Apply mutation IN-PLACE
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/mutation-generator/apply_mutation.py \
    --mutation-json "$MUTATION_FILE" \
    --operator-path "$OPERATOR_PATH" \
    --action apply > /dev/null 2>&1
  
  if [ $? -ne 0 ]; then
    echo "⚠️  ERROR applying mutation"
    continue
  fi
  
  # Run tests with timeout (test all controller-related code)
  timeout 300s go test ./... > "$RESULTS_DIR/${MUTANT_ID}-output.txt" 2>&1
  TEST_EXIT=$?
  
  # REVERT mutation (restore original code)
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/mutation-generator/apply_mutation.py \
    --mutation-json "$MUTATION_FILE" \
    --operator-path "$OPERATOR_PATH" \
    --action revert > /dev/null 2>&1
  
  # Analyze result
  if [ $TEST_EXIT -eq 124 ]; then
    echo "⏱️  KILLED (timeout)"
    KILLED_MUTANTS=$((KILLED_MUTANTS + 1))
    TIMEOUT_MUTANTS=$((TIMEOUT_MUTANTS + 1))
    STATUS="killed-timeout"
  elif [ $TEST_EXIT -ne 0 ]; then
    echo "✓ KILLED"
    KILLED_MUTANTS=$((KILLED_MUTANTS + 1))
    STATUS="killed"
  else
    echo "⚠️  SURVIVED"
    SURVIVED_MUTANTS=$((SURVIVED_MUTANTS + 1))
    STATUS="survived"
  fi
  
  # Save result
  echo "$mutation" | jq --arg status "$STATUS" --arg exit "$TEST_EXIT" \
    '. + {status: $status, exit_code: ($exit | tonumber)}' \
    > "$RESULTS_DIR/${MUTANT_ID}-result.json"
  
done < <(jq -c '.mutations[]' "$MUTATIONS_JSON")
```

**3.3 Calculate Mutation Score**

```bash
echo ""
echo "════════════════════════════════════════════════════════════"
echo "                 MUTATION TESTING RESULTS"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Total Mutants:        $TOTAL_MUTANTS"
echo "Killed (Good):        $KILLED_MUTANTS"
echo "  - By tests:         $((KILLED_MUTANTS - TIMEOUT_MUTANTS))"
echo "  - By timeout:       $TIMEOUT_MUTANTS"
echo "Survived (Bad):       $SURVIVED_MUTANTS"
echo ""

MUTATION_SCORE=$(awk "BEGIN {printf \"%.2f\", ($KILLED_MUTANTS / $TOTAL_MUTANTS) * 100}")

echo "Mutation Score:       ${MUTATION_SCORE}%"
echo ""

# Interpret score using integer comparison (no bc dependency)
SCORE_INT=$(awk "BEGIN {printf \"%.0f\", ($KILLED_MUTANTS * 100 / $TOTAL_MUTANTS)}")

if [ "$SCORE_INT" -ge 90 ]; then
  echo "✓✓ EXCELLENT - Strong test suite!"
  VERDICT="excellent"
elif [ "$SCORE_INT" -ge 80 ]; then
  echo "✓  GOOD - Solid test coverage"
  VERDICT="good"
elif [ "$SCORE_INT" -ge 70 ]; then
  echo "⚠️  FAIR - Room for improvement"
  VERDICT="fair"
else
  echo "❌ POOR - Significant gaps in test coverage"
  VERDICT="poor"
fi

echo "════════════════════════════════════════════════════════════"
echo ""
```

---

### Step 4: Analyze Results and Generate Report

**4.1 Identify Survived Mutants**

```bash
echo "Analyzing survived mutants..."
echo ""

# Find survived mutants
SURVIVED_LIST=$(find "$RESULTS_DIR" -name "*-result.json" -exec jq -r 'select(.status == "survived") | .id' {} \;)

if [ -z "$SURVIVED_LIST" ]; then
  echo "✓ No survived mutants - all mutations were caught by tests!"
else
  SURVIVED_COUNT=$(echo "$SURVIVED_LIST" | wc -l)
  echo "⚠️  $SURVIVED_COUNT survived mutants need attention:"
  echo ""
  
  # Show top 10
  echo "$SURVIVED_LIST" | head -10 | while read mutant_id; do
    RESULT_FILE="$RESULTS_DIR/${mutant_id}-result.json"
    
    TYPE=$(jq -r '.type' "$RESULT_FILE")
    DESC=$(jq -r '.description' "$RESULT_FILE")
    FILE=$(jq -r '.file' "$RESULT_FILE")
    LINE=$(jq -r '.line' "$RESULT_FILE")
    
    echo "  $mutant_id:"
    echo "    Type:        $TYPE"
    echo "    Location:    $FILE:$LINE"
    echo "    Mutation:    $DESC"
    echo ""
  done
  
  if [ "$SURVIVED_COUNT" -gt 10 ]; then
    echo "  ... and $((SURVIVED_COUNT - 10)) more"
    echo ""
  fi
fi
```

**4.2 Generate Reports**

Create reports based on `--report-format`:

```bash
REPORT_FORMAT="${REPORT_FORMAT:-html}"

case "$REPORT_FORMAT" in
  html)
    # Generate HTML report
    cat > "$WORK_DIR/mutation-report.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
  <title>Mutation Testing Report</title>
  <style>
    body { font-family: sans-serif; margin: 40px; background: #f5f5f5; }
    .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
    .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 30px 0; }
    .metric { background: #f9f9f9; padding: 20px; border-radius: 5px; text-align: center; border: 1px solid #ddd; }
    .metric .value { font-size: 36px; font-weight: bold; color: #4CAF50; }
    .metric .label { color: #666; margin-top: 10px; }
    .excellent { color: #4CAF50; }
    .good { color: #8BC34A; }
    .fair { color: #FF9800; }
    .poor { color: #F44336; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
    th { background: #4CAF50; color: white; }
    .survived { background: #ffebee; }
    .killed { background: #e8f5e9; }
    code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🧬 Mutation Testing Report</h1>
    
    <div class="summary">
      <div class="metric">
        <div class="value">$MUTATION_SCORE%</div>
        <div class="label">Mutation Score</div>
      </div>
      <div class="metric">
        <div class="value">$KILLED_MUTANTS</div>
        <div class="label">Killed (Good)</div>
      </div>
      <div class="metric">
        <div class="value">$SURVIVED_MUTANTS</div>
        <div class="label">Survived (Bad)</div>
      </div>
      <div class="metric">
        <div class="value">$TOTAL_MUTANTS</div>
        <div class="label">Total Mutants</div>
      </div>
    </div>
    
    <h2>Verdict: <span class="$VERDICT">$(echo $VERDICT | tr '[:lower:]' '[:upper:]')</span></h2>
    
    <h2>Survived Mutants (Need Attention)</h2>
EOF

    if [ -z "$SURVIVED_LIST" ]; then
      echo "    <p><strong>✓ Excellent!</strong> All mutations were caught by tests.</p>" >> "$WORK_DIR/mutation-report.html"
    else
      cat >> "$WORK_DIR/mutation-report.html" << 'EOF'
    <table>
      <tr>
        <th>ID</th>
        <th>Type</th>
        <th>Location</th>
        <th>Description</th>
      </tr>
EOF

      echo "$SURVIVED_LIST" | while read mutant_id; do
        RESULT_FILE="$RESULTS_DIR/${mutant_id}-result.json"
        TYPE=$(jq -r '.type' "$RESULT_FILE")
        FILE=$(jq -r '.file' "$RESULT_FILE")
        LINE=$(jq -r '.line' "$RESULT_FILE")
        DESC=$(jq -r '.description' "$RESULT_FILE")
        
        cat >> "$WORK_DIR/mutation-report.html" << EOF
      <tr class="survived">
        <td><code>$mutant_id</code></td>
        <td>$TYPE</td>
        <td><code>$FILE:$LINE</code></td>
        <td>$DESC</td>
      </tr>
EOF
      done
      
      echo "    </table>" >> "$WORK_DIR/mutation-report.html"
    fi
    
    cat >> "$WORK_DIR/mutation-report.html" << 'EOF'
    
    <h2>💡 Performance Note</h2>
    <p>This mutation testing used an <strong>in-place mutation strategy</strong> - no repository copies were created! This makes mutation testing practical even for large repositories.</p>
  </div>
</body>
</html>
EOF

    echo "📊 HTML Report: file://$(pwd)/$WORK_DIR/mutation-report.html"
    ;;
    
  markdown)
    # Generate Markdown report
    cat > "$WORK_DIR/mutation-report.md" << EOF
# Mutation Testing Report

**Date:** $(date '+%Y-%m-%d %H:%M:%S')

## Summary

| Metric | Value |
|--------|-------|
| **Mutation Score** | **${MUTATION_SCORE}%** |
| Total Mutants | $TOTAL_MUTANTS |
| Killed (Good) | $KILLED_MUTANTS |
| Survived (Bad) | $SURVIVED_MUTANTS |
| Verdict | ${VERDICT^^} |

## Survived Mutants

EOF

    if [ -z "$SURVIVED_LIST" ]; then
      echo "✓ **Excellent!** All mutations were caught by tests." >> "$WORK_DIR/mutation-report.md"
    else
      cat >> "$WORK_DIR/mutation-report.md" << 'EOF'
| Mutant ID | Type | Location | Description |
|-----------|------|----------|-------------|
EOF

      echo "$SURVIVED_LIST" | while read mutant_id; do
        RESULT_FILE="$RESULTS_DIR/${mutant_id}-result.json"
        TYPE=$(jq -r '.type' "$RESULT_FILE")
        FILE=$(jq -r '.file' "$RESULT_FILE")
        LINE=$(jq -r '.line' "$RESULT_FILE")
        DESC=$(jq -r '.description' "$RESULT_FILE")
        
        echo "| \`$mutant_id\` | $TYPE | \`$FILE:$LINE\` | $DESC |" >> "$WORK_DIR/mutation-report.md"
      done
    fi
    
    echo "" >> "$WORK_DIR/mutation-report.md"
    echo "---" >> "$WORK_DIR/mutation-report.md"
    echo "*Generated using in-place mutation testing - no repository copies created!*" >> "$WORK_DIR/mutation-report.md"
    
    echo "📊 Markdown Report: $(pwd)/$WORK_DIR/mutation-report.md"
    ;;
    
  json)
    # JSON report from all result files
    jq -n -s \
      --arg score "$MUTATION_SCORE" \
      --arg verdict "$VERDICT" \
      --argjson killed "$KILLED_MUTANTS" \
      --argjson survived "$SURVIVED_MUTANTS" \
      --argjson total "$TOTAL_MUTANTS" \
      '{
        summary: {
          mutation_score: ($score | tonumber),
          verdict: $verdict,
          killed: $killed,
          survived: $survived,
          total: $total
        },
        results: .
      }' "$RESULTS_DIR"/*-result.json > "$WORK_DIR/mutation-report.json"
    
    echo "📊 JSON Report: $(pwd)/$WORK_DIR/mutation-report.json"
    ;;
esac

echo ""
```

---

## Return Value

**Format**: Mutation testing report with the following sections:

1. **Summary Statistics:**
   - Total mutants generated
   - Mutants killed (tests caught the bug)
   - Mutants survived (tests missed the bug)
   - Mutation score percentage

2. **Detailed Results Per Controller:**
   - Mutation breakdown by controller
   - Mutation score per controller
   - Areas with weak test coverage

3. **Survived Mutants Analysis:**
   - List of all survived mutants
   - Code location of each mutation
   - Type of mutation applied
   - Recommended test cases to add

4. **Actionable Recommendations:**
   - Priority order for adding tests
   - Example test cases for survived mutants
   - Patterns of weak coverage

5. **File Locations:**
   - HTML/Markdown report path
   - JSON analysis data path
   - Individual mutation result files in `.work/mutation-testing/results/`

**Exit Codes:**
- `0`: Mutation testing completed successfully
- `1`: Baseline tests failed (fix tests first)
- `2`: No controllers found
- `3`: Mutation generation failed

## Examples

### Example 1: Basic Mutation Testing

Test all controllers with default settings:

```
/testing:mutation-test
```

Output:
```
Discovering controllers...
Found 3 controllers: PodController, ServiceController, DeploymentController

Generating mutations...
✓ Generated 145 mutants

Running baseline tests...
✓ Baseline tests passed

Testing mutants... [145/145]
  ✓ Killed: 124
  ⚠️  Survived: 21

Mutation Score: 85.5%

📊 Report: .work/mutation-testing/mutation-report.html
```

---

### Example 2: Test Specific Controllers

Test only specific controllers:

```
/testing:mutation-test --controllers PodController,ServiceController
```

---

### Example 3: Focus on Error Handling

Test only error handling mutations:

```
/testing:mutation-test --mutation-types error-handling,returns
```

Use case: After adding error handling code, validate it's properly tested.

---

### Example 4: Generate Markdown Report

Generate markdown report for PR comments:

```
/testing:mutation-test --report-format markdown
```

Can paste the markdown report into PR comments to show test quality improvements.

---

### Example 5: Operator with Custom Path

Test operator in different directory:

```
/testing:mutation-test ~/git/my-operator
```

---

## Notes

### Mutation Score Interpretation

- **90%+**: Excellent - Strong test suite with comprehensive edge case coverage
- **80-90%**: Good - Solid test coverage, minor gaps in edge cases
- **70-80%**: Fair - Adequate coverage but notable gaps in error handling
- **< 70%**: Poor - Significant gaps in test coverage, high risk of bugs

### Performance Considerations

- Mutation testing is computationally expensive (runs tests N times for N mutants)
- Typical operator with 2000 LOC controller code generates 100-200 mutants
- With 30-second test suite, expect 50-100 minutes for full mutation testing
- Consider running on CI with parallelization, or locally with filtered mutation types

### Best Practices

1. **Start Small**: Test one controller at a time initially
2. **Fix Baseline First**: Ensure all tests pass before mutation testing
3. **Iterate**: Focus on high-value mutations (error handling, conditionals)
4. **Integrate into CI**: Run mutation testing weekly or per release
5. **Track Progress**: Measure mutation score improvement over time

### Limitations

- Cannot detect equivalent mutants (mutations that don't change behavior)
- Test suite runtime directly impacts mutation testing time
- May generate false positives if tests are non-deterministic
- Requires Go toolchain and controller-runtime setup

### Scope and Exclusions

**Included Files:**
- All files matching `*controller.go` pattern anywhere in the codebase (e.g., `operator_controller.go`, `pod_controller.go`)
- Controller files under `controller/` or `controllers/` directories (singular or plural)
- Related reconciliation logic and helper functions

**Excluded Files:**
- **Vendor directories**: The `vendor/` folder is automatically excluded from mutation testing as it contains third-party dependencies that should not be mutated
- Generated code and third-party packages

### Common Survived Mutants

**Patterns that often indicate missing tests:**
- Error handling not tested (`if err != nil` removed)
- Requeue logic not validated (changed requeue timing)
- Status updates not verified (skipped status updates)
- Finalizer logic not tested (removed finalizer checks)
- Condition transitions not validated (changed condition states)

## See Also

- Go mutation testing tools: `go-mutesting`, `gremlins`
- Operator testing patterns: controller-runtime testing docs
- `/openshift:new-e2e-test` - Generate E2E tests for operators
- `/utils:generate-test-plan` - Create test plans for PRs

## References

- [Mutation Testing: A Comprehensive Survey](https://ieeexplore.ieee.org/document/5487526)
- [controller-runtime Testing Guide](https://book.kubebuilder.io/cronjob-tutorial/writing-tests.html)
- [Google Testing Blog: Mutation Testing](https://testing.googleblog.com/2021/04/mutation-testing.html)

