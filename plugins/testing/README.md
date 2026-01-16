# Testing Plugin

Comprehensive testing utilities for operators and applications. Currently includes advanced mutation testing for Kubernetes operators.

## What is Mutation Testing?

Mutation testing validates the **quality** of your test suite by introducing deliberate bugs (mutations) into your code and checking if your tests catch them:

- **Killed Mutant** ✓: Tests failed → Good! Your tests caught the bug
- **Survived Mutant** ⚠️: Tests passed → Bad! Your tests missed the bug

Unlike traditional code coverage which only measures if code is *executed*, mutation testing measures if tests *validate correctness*.

## Why Mutation Testing for Operators?

Kubernetes operators have critical reconciliation logic that must be thoroughly tested:

- **Error handling**: Does your test catch when API calls fail?
- **Requeue logic**: Are requeue conditions properly validated?
- **Status updates**: Do tests verify status changes?
- **Finalizers**: Is cleanup logic tested?
- **Edge cases**: Are conditional branches fully tested?

A mutation score of 80%+ indicates a robust test suite that catches bugs before they reach production.

## Available Commands

### `/testing:mutation-test` - Mutation Testing for Operators

Advanced mutation testing for Kubernetes operator controllers. Validates test suite quality by introducing deliberate bugs and checking if tests catch them.

**Coming Soon:**
- `/testing:unit-test` - Unit test generation and scaffolding
- `/testing:e2e-test` - End-to-end test helpers and validation
- `/testing:regression-test` - Regression test suite management
- `/testing:integration-test` - Integration test orchestration

## Installation

### From Claude Code Plugin Marketplace

```bash
# Add the marketplace (if not already added)
/plugin marketplace add openshift-eng/ai-helpers

# Install the testing plugin
/plugin install testing@ai-helpers
```

### Manual Installation (Cursor)

```bash
# Clone the repository (if not already cloned)
git clone git@github.com:openshift-eng/ai-helpers.git

# Link to Cursor commands
ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Usage

### Basic Usage

Run mutation testing on your operator:

```bash
/testing:mutation-test
```

This will:
1. Discover all controller files
2. Generate mutations (typically 100-200 mutants)
3. Run your test suite against each mutant
4. Generate an HTML report with results

### Test Specific Controllers

```bash
/testing:mutation-test --controllers PodController,ServiceController
```

### Focus on Specific Mutation Types

```bash
# Test only error handling
/testing:mutation-test --mutation-types error-handling

# Test multiple types
/testing:mutation-test --mutation-types error-handling,conditionals,requeue
```

Available mutation types:
- `conditionals` - Change comparison operators, negate booleans
- `error-handling` - Remove error checks, change error types
- `returns` - Modify return statements and error returns
- `requeue` - Change requeue behavior and timing
- `status` - Skip status updates, change conditions
- `api-calls` - Change API operation types

### Generate Different Report Formats

```bash
# HTML report (default)
/testing:mutation-test --report-format html

# Markdown report (good for PRs)
/testing:mutation-test --report-format markdown

# JSON report (for automation)
/testing:mutation-test --report-format json
```

## Example Output

```
🔍 Scanning operator at: /home/user/my-operator
📄 Found 2 controller files
   Analyzing: controllers/pod_controller.go
   Analyzing: controllers/service_controller.go

🧬 Creating 145 mutants...
   Created 10/145 mutants...
   Created 20/145 mutants...
   ...
✓ Generated 145 mutations

Running baseline tests...
✓ Baseline tests passed

Testing 145 mutants...
This may take a while (estimated: 45 minutes)

[1/145] Testing mutant-001 (error-handling)... ✓ KILLED
[2/145] Testing mutant-002 (conditional)... ⚠️  SURVIVED
[3/145] Testing mutant-003 (requeue)... ✓ KILLED
...

════════════════════════════════════════════════════════════
                 MUTATION TESTING RESULTS
════════════════════════════════════════════════════════════

Total Mutants:        145
Killed (Good):        124
  - By tests:         121
  - By timeout:       3
Survived (Bad):       21

Mutation Score:       85.52%

✓  GOOD - Solid test coverage

Mutation Score by Type:

  conditionals        : 88.1% (37/42)
  error-handling      : 81.6% (31/38)
  returns             : 85.7% (6/7)
  requeue             : 83.3% (15/18)
  status              : 92.0% (23/25)
  api-calls           : 80.0% (12/15)

════════════════════════════════════════════════════════════

⚠️  21 survived mutants need attention:

  mutant-002:
    Type:        conditional
    Location:    controllers/pod_controller.go:87
    Mutation:    Change == to !=

  mutant-015:
    Type:        error-handling
    Location:    controllers/pod_controller.go:156
    Mutation:    Remove error check

  ... and 19 more

Recommendations:

→ mutant-015: Add test case for error handling in controllers/pod_controller.go
   Suggestion: Test what happens when API call fails

→ mutant-002: Add test for opposite condition in controllers/pod_controller.go
   Suggestion: Test both true and false branches

📊 HTML Report: file:///path/.work/mutation-testing/mutation-report.html
```

## Understanding Mutation Score

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| **90%+** | ✓✓ Excellent | Maintain quality, minor tweaks |
| **80-90%** | ✓ Good | Address critical survived mutants |
| **70-80%** | ⚠️ Fair | Focus on error handling gaps |
| **< 70%** | ❌ Poor | Significant test improvements needed |

## What Gets Tested

### Conditionals
```go
// Original
if obj.Status.Ready == true {
    // do something
}

// Mutated
if obj.Status.Ready != true {  // Changed == to !=
    // do something
}
```

If tests still pass, you need a test that validates behavior in both cases.

### Error Handling
```go
// Original
err := r.Get(ctx, key, obj)
if err != nil {
    return ctrl.Result{}, err
}

// Mutated
err := r.Get(ctx, key, obj)
// MUTANT: Removed error check

// If tests pass, you're missing error scenario test
```

### Requeue Behavior
```go
// Original
return ctrl.Result{}, nil

// Mutated
return ctrl.Result{Requeue: true}, nil

// If tests pass, you're not validating requeue behavior
```

### Status Updates
```go
// Original
obj.Status.Conditions = []Condition{
    {Type: "Ready", Status: "True"},
}
r.Status().Update(ctx, obj)

// Mutated (skipped status update)
// MUTANT: Skipped status update

// If tests pass, you're not checking status was updated
```

## Performance Considerations

Mutation testing is computationally expensive:

- **Small operator** (500 LOC): ~50 mutants, ~15-20 minutes
- **Medium operator** (2000 LOC): ~150 mutants, ~45-60 minutes
- **Large operator** (5000 LOC): ~300+ mutants, ~2-3 hours

**Tips for faster testing:**
1. Focus on specific controllers with `--controllers`
2. Run only high-value mutations: `--mutation-types error-handling,conditionals`
3. Run on CI with multiple parallel workers
4. Use incremental testing (only new mutations)

## Integration with CI

Add mutation testing to your CI pipeline:

```yaml
# .github/workflows/mutation-testing.yml
name: Mutation Testing
on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday
  workflow_dispatch:
  pull_request:
    branches: [main]

jobs:
  mutation-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      
      - name: Install mutation testing tools
        run: |
          # Install your mutation testing script/binary
          # Example: go install github.com/your-org/mutation-tester@latest
          # Or use the Python scripts from this plugin
          pip install -r plugins/testing/skills/mutation-generator/requirements.txt
      
      - name: Run Mutation Testing
        run: |
          # Run the actual mutation testing script
          python3 plugins/testing/skills/mutation-generator/generate_mutations_efficient.py \
            --operator-path . \
            --mutation-types error-handling,conditionals \
            --output .work/mutations.json
          
          # Execute tests for each mutation
          bash plugins/testing/skills/mutation-tester/run_mutations.sh \
            --mutations .work/mutations.json \
            --report-format markdown > mutation-report.md
      
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('mutation-report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '## Mutation Testing Results\n\n' + report
            });
      
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: mutation-report
          path: |
            mutation-report.md
            .work/mutation-testing/
```

**Note**: The `/testing:mutation-test` command is a Claude Code slash command meant for interactive development. For CI/CD, use the underlying scripts directly as shown above, or create a wrapper script that implements the mutation testing workflow.

## Best Practices

### 1. Start Small
Begin with one controller to understand the process:
```bash
/testing:mutation-test --controllers MyController
```

### 2. Fix High-Value Gaps First
Prioritize:
1. Error handling mutations (most critical)
2. Conditional mutations (logic bugs)
3. Status update mutations (correctness)

### 3. Iterate and Improve
- Run mutation testing weekly
- Track mutation score over time
- Aim for 80%+ before major releases

### 4. Don't Chase 100%
- Some equivalent mutants can't be detected
- Focus on meaningful gaps, not perfection
- 90%+ is excellent in practice

### 5. Use in Code Reviews
Add mutation testing results to PRs:
```bash
/testing:mutation-test \
  --report-format markdown > mutation-results.md
```

## Example: Improving Test Suite

**Before** (Mutation Score: 65%):
```go
func TestReconcile(t *testing.T) {
    // Only tests happy path
    result, err := reconciler.Reconcile(ctx, req)
    assert.NoError(t, err)
    assert.Equal(t, ctrl.Result{}, result)
}
```

**Mutation testing reveals**: 35% of error handling mutations survived

**After** (Mutation Score: 92%):
```go
func TestReconcile_Success(t *testing.T) {
    result, err := reconciler.Reconcile(ctx, req)
    assert.NoError(t, err)
    assert.Equal(t, ctrl.Result{}, result)
}

func TestReconcile_GetError(t *testing.T) {
    // Test error handling
    client := fake.NewClientBuilder().
        WithInterceptorFuncs(interceptor.Funcs{
            Get: func(ctx context.Context, client client.WithWatch, 
                     key client.ObjectKey, obj client.Object, 
                     opts ...client.GetOption) error {
                return errors.NewNotFound(schema.GroupResource{}, "test")
            },
        }).Build()
    
    reconciler := &MyReconciler{Client: client}
    result, err := reconciler.Reconcile(ctx, req)
    
    // Verify error handling
    assert.NoError(t, err)
    assert.False(t, result.Requeue)
}

func TestReconcile_UpdateError(t *testing.T) {
    // Test status update error handling
    // ...
}

func TestReconcile_RequeueBehavior(t *testing.T) {
    // Test requeue conditions
    // ...
}
```

## Troubleshooting

### "Baseline tests failed"
Fix your tests before running mutation testing:
```bash
go test ./controllers/... -v
```

### "No controllers found"
Ensure your operator uses standard structure:
- `controllers/` or `pkg/controller/` directories
- Files named `*controller*.go` or `*reconciler*.go`

### "Mutation testing too slow"
- Reduce scope: `--controllers` or `--mutation-types`
- Run on faster machine or CI with parallelization
- Consider sampling strategy for very large operators

### "Too many survived mutants"
This indicates test gaps:
1. Review survived mutants in report
2. Add tests for untested scenarios
3. Focus on error handling first
4. Iterate and rerun

## Advanced Usage

### Custom Operator Path
```bash
/testing:mutation-test ~/git/my-operator
```

### Combine with Coverage Analysis
```bash
# Get both coverage and mutation score
go test ./controllers/... -coverprofile=coverage.out
go tool cover -func=coverage.out

/testing:mutation-test
```

Good operators have: **High coverage (>80%) AND high mutation score (>80%)**

## References

- [Mutation Testing: A Comprehensive Survey](https://ieeexplore.ieee.org/document/5487526)
- [controller-runtime Testing Guide](https://book.kubebuilder.io/cronjob-tutorial/writing-tests.html)
- [Google Testing Blog: Mutation Testing](https://testing.googleblog.com/2021/04/mutation-testing.html)
- [PITest (Java mutation testing)](https://pitest.org/) - Inspiration for this tool

## Contributing

Found a bug or want to add mutation types? Contributions welcome!

See [AGENTS.md](../../AGENTS.md) for contribution guidelines.

## License

See [LICENSE](../../LICENSE) for details.

