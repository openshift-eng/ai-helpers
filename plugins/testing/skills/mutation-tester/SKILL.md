---
name: Mutation Testing Executor
description: Execute tests against generated mutants and analyze results to validate test suite quality for Kubernetes operators
---

# Mutation Testing Executor

This skill executes the test suite against each generated mutant and analyzes the results to determine test suite effectiveness. A killed mutant (test fails) indicates good test coverage; a survived mutant (test passes) indicates a gap in testing.

## When to Use This Skill

Use this skill when:
- You have generated mutants and need to test them
- You want to calculate mutation score for operator controllers
- You're analyzing test suite quality
- You need to identify missing test cases

## Prerequisites

1. **Generated mutants** from mutation-generator skill
2. **Working test suite** that passes on original code
3. **Go toolchain** installed (go test)
4. **Sufficient time** - mutation testing is computationally expensive

## Implementation Steps

### Step 1: Validate Baseline Tests

Before testing mutants, ensure original tests pass:

**1.1 Run Baseline Tests**

```bash
echo "Running baseline tests against original code..."
cd "${OPERATOR_PATH}"

go test ./controllers/... -v -timeout 10m \
  > "${WORK_DIR}/baseline-test-output.txt" 2>&1

BASELINE_EXIT=$?

if [ $BASELINE_EXIT -ne 0 ]; then
  echo "❌ ERROR: Baseline tests failed"
  echo "Fix failing tests before running mutation testing"
  cat "${WORK_DIR}/baseline-test-output.txt"
  exit 1
fi

echo "✓ Baseline tests passed"
```

**1.2 Record Baseline Metrics**

```bash
# Count tests
TOTAL_TESTS=$(grep -c "^=== RUN" "${WORK_DIR}/baseline-test-output.txt" || echo "0")

# Execution time
TEST_DURATION=$(grep "^PASS" "${WORK_DIR}/baseline-test-output.txt" | \
                awk '{print $NF}' | sed 's/[^0-9.]//g' | head -1)

echo "Baseline: $TOTAL_TESTS tests in ${TEST_DURATION}s"
```

---

### Step 2: Test Each Mutant

**2.1 Iterate Through Mutants**

```bash
MUTANTS_DIR="${WORK_DIR}/mutants"
RESULTS_DIR="${WORK_DIR}/results"
mkdir -p "$RESULTS_DIR"

# Initialize counters
TOTAL_MUTANTS=$(find "$MUTANTS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
KILLED_MUTANTS=0
SURVIVED_MUTANTS=0
TIMEOUT_MUTANTS=0
ERROR_MUTANTS=0

echo ""
echo "Testing $TOTAL_MUTANTS mutants..."
echo "This may take a while (estimated: $((TOTAL_MUTANTS * TEST_DURATION / 60)) minutes)"
echo ""

CURRENT=0

for mutant_dir in "$MUTANTS_DIR"/mutant-*; do
  CURRENT=$((CURRENT + 1))
  MUTANT_ID=$(basename "$mutant_dir")
  
  # Load mutation metadata
  MUTATION_FILE="$mutant_dir/MUTATION.json"
  if [ ! -f "$MUTATION_FILE" ]; then
    echo "[$CURRENT/$TOTAL_MUTANTS] ⚠️  $MUTANT_ID: No metadata"
    continue
  fi
  
  MUTATION_DESC=$(jq -r '.description' "$MUTATION_FILE")
  MUTATION_TYPE=$(jq -r '.type' "$MUTATION_FILE")
  
  # Progress indicator
  echo -n "[$CURRENT/$TOTAL_MUTANTS] Testing $MUTANT_ID ($MUTATION_TYPE)... "
  
  # Test mutant (with timeout)
  cd "$mutant_dir"
  
  # Use timeout to prevent hanging tests
  timeout 300s go test ./controllers/... -v \
    > "$RESULTS_DIR/${MUTANT_ID}-output.txt" 2>&1
  
  TEST_EXIT=$?
  cd - > /dev/null
  
  # Analyze result
  if [ $TEST_EXIT -eq 124 ]; then
    # Timeout occurred
    echo "⏱️  KILLED (timeout)"
    KILLED_MUTANTS=$((KILLED_MUTANTS + 1))
    TIMEOUT_MUTANTS=$((TIMEOUT_MUTANTS + 1))
    STATUS="killed-timeout"
    
  elif [ $TEST_EXIT -ne 0 ]; then
    # Tests failed - mutant killed (GOOD!)
    echo "✓ KILLED"
    KILLED_MUTANTS=$((KILLED_MUTANTS + 1))
    STATUS="killed"
    
  else
    # Tests passed - mutant survived (BAD - indicates missing test)
    echo "⚠️  SURVIVED"
    SURVIVED_MUTANTS=$((SURVIVED_MUTANTS + 1))
    STATUS="survived"
  fi
  
  # Save result metadata
  cat > "$RESULTS_DIR/${MUTANT_ID}-result.json" << EOF
{
  "mutant_id": "$MUTANT_ID",
  "status": "$STATUS",
  "exit_code": $TEST_EXIT,
  "mutation": $(cat "$MUTATION_FILE"),
  "output_file": "$RESULTS_DIR/${MUTANT_ID}-output.txt"
}
EOF
  
done

cd "$OPERATOR_PATH"
```

**2.2 Display Progress**

For long-running mutation testing, show periodic updates:

```bash
# Every 10 mutants, show summary
if [ $((CURRENT % 10)) -eq 0 ]; then
  MUTATION_SCORE=$(awk "BEGIN {printf \"%.1f\", ($KILLED_MUTANTS / $CURRENT) * 100}")
  echo ""
  echo "   Progress: $CURRENT/$TOTAL_MUTANTS ($MUTATION_SCORE% killed so far)"
  echo ""
fi
```

---

### Step 3: Calculate Mutation Score

**3.1 Compute Overall Score**

```bash
# Mutation Score = (Killed / Total) * 100
MUTATION_SCORE=$(awk "BEGIN {printf \"%.2f\", ($KILLED_MUTANTS / $TOTAL_MUTANTS) * 100}")

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
echo "Mutation Score:       ${MUTATION_SCORE}%"
echo ""
```

**3.2 Interpret Score**

```bash
if (( $(echo "$MUTATION_SCORE >= 90" | bc -l) )); then
  echo "✓✓ EXCELLENT - Strong test suite!"
  VERDICT="excellent"
elif (( $(echo "$MUTATION_SCORE >= 80" | bc -l) )); then
  echo "✓  GOOD - Solid test coverage"
  VERDICT="good"
elif (( $(echo "$MUTATION_SCORE >= 70" | bc -l) )); then
  echo "⚠️  FAIR - Room for improvement"
  VERDICT="fair"
else
  echo "❌ POOR - Significant gaps in test coverage"
  VERDICT="poor"
fi

echo "════════════════════════════════════════════════════════════"
echo ""
```

**3.3 Calculate Score by Mutation Type**

```bash
# Analyze by mutation type
echo "Mutation Score by Type:"
echo ""

for mut_type in conditionals error-handling returns requeue status api-calls; do
  TYPE_TOTAL=$(jq -r "select(.mutation.type == \"$mut_type\") | .mutant_id" \
    "$RESULTS_DIR"/*-result.json 2>/dev/null | wc -l)
  
  if [ "$TYPE_TOTAL" -gt 0 ]; then
    TYPE_KILLED=$(jq -r "select(.mutation.type == \"$mut_type\" and .status == \"killed\") | .mutant_id" \
      "$RESULTS_DIR"/*-result.json 2>/dev/null | wc -l)
    
    TYPE_SCORE=$(awk "BEGIN {printf \"%.1f\", ($TYPE_KILLED / $TYPE_TOTAL) * 100}")
    
    printf "  %-20s: %5.1f%% (%d/%d)\n" "$mut_type" "$TYPE_SCORE" "$TYPE_KILLED" "$TYPE_TOTAL"
  fi
done

echo ""
```

---

### Step 4: Analyze Survived Mutants

**4.1 Identify High-Priority Survived Mutants**

```bash
echo "Analyzing survived mutants..."
echo ""

# Critical types that should not survive
CRITICAL_TYPES=("error-handling" "conditionals")

# List survived mutants
SURVIVED_MUTANTS_LIST=()

for result_file in "$RESULTS_DIR"/*-result.json; do
  STATUS=$(jq -r '.status' "$result_file")
  
  if [ "$STATUS" == "survived" ]; then
    MUTANT_ID=$(jq -r '.mutant_id' "$result_file")
    SURVIVED_MUTANTS_LIST+=("$MUTANT_ID")
  fi
done

if [ ${#SURVIVED_MUTANTS_LIST[@]} -eq 0 ]; then
  echo "✓ No survived mutants - all mutations were caught by tests!"
else
  echo "⚠️  ${#SURVIVED_MUTANTS_LIST[@]} survived mutants need attention:"
  echo ""
  
  # Show top 10 most critical
  COUNT=0
  for mutant_id in "${SURVIVED_MUTANTS_LIST[@]}"; do
    if [ $COUNT -ge 10 ]; then
      echo "  ... and $((${#SURVIVED_MUTANTS_LIST[@]} - 10)) more"
      break
    fi
    
    RESULT_FILE="$RESULTS_DIR/${mutant_id}-result.json"
    
    TYPE=$(jq -r '.mutation.type' "$RESULT_FILE")
    DESC=$(jq -r '.mutation.description' "$RESULT_FILE")
    FILE=$(jq -r '.mutation.file' "$RESULT_FILE")
    LINE=$(jq -r '.mutation.line' "$RESULT_FILE")
    
    echo "  $mutant_id:"
    echo "    Type:        $TYPE"
    echo "    Location:    $FILE:$LINE"
    echo "    Mutation:    $DESC"
    echo ""
    
    COUNT=$((COUNT + 1))
  done
fi
```

**4.2 Generate Recommendations**

For each survived mutant, suggest what test to add:

```bash
echo "Recommendations:"
echo ""

for mutant_id in "${SURVIVED_MUTANTS_LIST[@]:0:5}"; do  # Top 5
  RESULT_FILE="$RESULTS_DIR/${mutant_id}-result.json"
  
  TYPE=$(jq -r '.mutation.type' "$RESULT_FILE")
  FILE=$(jq -r '.mutation.file' "$RESULT_FILE")
  PATTERN=$(jq -r '.mutation.pattern' "$RESULT_FILE")
  
  case "$TYPE" in
    "error-handling")
      echo "→ $mutant_id: Add test case for error handling in $FILE"
      echo "   Suggestion: Test what happens when API call fails"
      ;;
    "conditionals")
      echo "→ $mutant_id: Add test for opposite condition in $FILE"
      echo "   Suggestion: Test both true and false branches"
      ;;
    "requeue")
      echo "→ $mutant_id: Validate requeue behavior in $FILE"
      echo "   Suggestion: Assert Result.Requeue value in test"
      ;;
    "status")
      echo "→ $mutant_id: Verify status updates in $FILE"
      echo "   Suggestion: Assert object status after reconciliation"
      ;;
  esac
  echo ""
done
```

---

### Step 5: Generate Reports

**5.1 Create JSON Report**

```bash
# Compile all results into single JSON
cat > "$RESULTS_DIR/mutation-report.json" << EOF
{
  "summary": {
    "total_mutants": $TOTAL_MUTANTS,
    "killed": $KILLED_MUTANTS,
    "survived": $SURVIVED_MUTANTS,
    "timeout": $TIMEOUT_MUTANTS,
    "mutation_score": $MUTATION_SCORE,
    "verdict": "$VERDICT",
    "test_duration_seconds": $TEST_DURATION,
    "timestamp": "$(date -Iseconds)"
  },
  "survived_mutants": [
$(
  for mutant_id in "${SURVIVED_MUTANTS_LIST[@]}"; do
    cat "$RESULTS_DIR/${mutant_id}-result.json"
    if [ "$mutant_id" != "${SURVIVED_MUTANTS_LIST[-1]}" ]; then
      echo ","
    fi
  done
)
  ]
}
EOF
```

**5.2 Generate HTML Report**

Create visual HTML report (simplified version):

```bash
cat > "$RESULTS_DIR/mutation-report.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
  <title>Mutation Testing Report</title>
  <style>
    body { font-family: sans-serif; margin: 40px; background: #f5f5f5; }
    .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }
    h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
    .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 30px 0; }
    .metric { background: #f9f9f9; padding: 20px; border-radius: 5px; text-align: center; }
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
    <table>
      <tr>
        <th>ID</th>
        <th>Type</th>
        <th>Location</th>
        <th>Description</th>
      </tr>
EOF

# Add survived mutants to table
for mutant_id in "${SURVIVED_MUTANTS_LIST[@]}"; do
  RESULT_FILE="$RESULTS_DIR/${mutant_id}-result.json"
  TYPE=$(jq -r '.mutation.type' "$RESULT_FILE")
  FILE=$(jq -r '.mutation.file' "$RESULT_FILE")
  LINE=$(jq -r '.mutation.line' "$RESULT_FILE")
  DESC=$(jq -r '.mutation.description' "$RESULT_FILE")
  
  cat >> "$RESULTS_DIR/mutation-report.html" << EOF
      <tr class="survived">
        <td>$mutant_id</td>
        <td>$TYPE</td>
        <td>$FILE:$LINE</td>
        <td>$DESC</td>
      </tr>
EOF
done

cat >> "$RESULTS_DIR/mutation-report.html" << 'EOF'
    </table>
  </div>
</body>
</html>
EOF

echo "📊 HTML Report: file://$(realpath "$RESULTS_DIR/mutation-report.html")"
```

**5.3 Generate Markdown Report**

```bash
cat > "$RESULTS_DIR/mutation-report.md" << EOF
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

## Mutation Score by Type

EOF

# Add score by type table
for mut_type in conditionals error-handling returns requeue status api-calls; do
  TYPE_TOTAL=$(jq -r "select(.mutation.type == \"$mut_type\") | .mutant_id" \
    "$RESULTS_DIR"/*-result.json 2>/dev/null | wc -l)
  
  if [ "$TYPE_TOTAL" -gt 0 ]; then
    TYPE_KILLED=$(jq -r "select(.mutation.type == \"$mut_type\" and .status == \"killed\") | .mutant_id" \
      "$RESULTS_DIR"/*-result.json 2>/dev/null | wc -l)
    TYPE_SCORE=$(awk "BEGIN {printf \"%.1f\", ($TYPE_KILLED / $TYPE_TOTAL) * 100}")
    
    echo "| $mut_type | ${TYPE_SCORE}% | $TYPE_KILLED/$TYPE_TOTAL |" >> "$RESULTS_DIR/mutation-report.md"
  fi
done

cat >> "$RESULTS_DIR/mutation-report.md" << 'EOF'

## Survived Mutants

The following mutants survived, indicating gaps in test coverage:

| Mutant ID | Type | Location | Description |
|-----------|------|----------|-------------|
EOF

for mutant_id in "${SURVIVED_MUTANTS_LIST[@]}"; do
  RESULT_FILE="$RESULTS_DIR/${mutant_id}-result.json"
  TYPE=$(jq -r '.mutation.type' "$RESULT_FILE")
  FILE=$(jq -r '.mutation.file' "$RESULT_FILE")
  LINE=$(jq -r '.mutation.line' "$RESULT_FILE")
  DESC=$(jq -r '.mutation.description' "$RESULT_FILE")
  
  echo "| $mutant_id | $TYPE | $FILE:$LINE | $DESC |" >> "$RESULTS_DIR/mutation-report.md"
done

echo "" >> "$RESULTS_DIR/mutation-report.md"
```

---

## Performance Optimization

**Parallel Testing**

For faster mutation testing, test mutants in parallel:

```bash
# Use GNU parallel if available
if command -v parallel &> /dev/null; then
  export -f test_single_mutant
  
  ls "$MUTANTS_DIR"/mutant-* | \
    parallel -j 4 --bar test_single_mutant {}
fi
```

**Incremental Testing**

Only test new mutants if running repeatedly:

```bash
# Skip already-tested mutants
for mutant_dir in "$MUTANTS_DIR"/mutant-*; do
  MUTANT_ID=$(basename "$mutant_dir")
  RESULT_FILE="$RESULTS_DIR/${MUTANT_ID}-result.json"
  
  if [ -f "$RESULT_FILE" ]; then
    echo "Skipping $MUTANT_ID (already tested)"
    continue
  fi
  
  # Test mutant...
done
```

## Output Files

- `mutation-report.json` - Complete results in JSON format
- `mutation-report.html` - Visual HTML report (default)
- `mutation-report.md` - Markdown report for PRs
- `{mutant-id}-output.txt` - Test output for each mutant
- `{mutant-id}-result.json` - Result metadata for each mutant

## See Also

- [mutation-generator skill](../mutation-generator/SKILL.md)
- [Mutation Testing Best Practices](https://pedrorijo.com/blog/intro-mutation/)

