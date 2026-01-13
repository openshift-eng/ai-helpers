---
name: Analyze Pprof
description: Aggregate and analyze CPU profiles from pprof files with comparative analysis support
---

# Analyze Pprof

This skill provides detailed implementation guidance for aggregating and analyzing CPU profile data from pprof files, with support for comparative analysis across multiple datasets.

## When to Use This Skill

Use this skill when the user wants to:
- Analyze CPU performance profiles from Go applications
- Aggregate multiple pprof files from load testing or production sampling
- Compare CPU usage patterns between different builds, configurations, or time periods
- Identify performance regressions or improvements
- Generate comprehensive performance reports with visualizations

## Prerequisites

Before starting, verify these prerequisites:

1. **Go Toolchain**
   - Check if installed: `which go`
   - Version check: `go version`
   - If not installed, provide instructions for the user's platform
   - Installation guide: https://go.dev/doc/install
   - Minimum version: Go 1.16+ (for modern pprof support)

2. **Python 3**
   - Check if installed: `which python3`
   - Version check: `python3 --version`
   - Minimum version: Python 3.7+

3. **Pprof Files**
   - User should provide one or more directories containing pprof CPU profile files
   - Common file patterns: `*.pprof`, `*.prof`, `*.pb.gz`, or files named `profile`

## Input Format

The user will provide:

1. **One or more directories** containing pprof CPU profile files
   - Each directory represents a dataset to analyze
   - Multiple directories enable comparative analysis
   - Examples:
     - Single: `./profiles/baseline`
     - Multiple: `./profiles/before ./profiles/after`
     - Multiple configs: `./profiles/config-a ./profiles/config-b ./profiles/config-c`

2. **Optional parameters** (if user requests):
   - Top N functions to report (default: 20)
   - Minimum percentage threshold for inclusion (default: 1%)
   - Output format preference (text, JSON, HTML)

## Implementation Steps

### Step 1: Validate Prerequisites and Input

1. **Check for Go toolchain**

```bash
if ! command -v go &> /dev/null; then
    echo "Error: Go toolchain is required for pprof analysis"
    echo "Please install Go from: https://go.dev/doc/install"
    exit 1
fi

# Verify go tool pprof is available
if ! go tool pprof -help &> /dev/null; then
    echo "Error: go tool pprof is not available"
    exit 1
fi

echo "✓ Go toolchain found: $(go version)"
```

2. **Check for Python 3**

```bash
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required for analysis aggregation"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
```

3. **Validate input directories**

```bash
# Store directories in array
directories=("$@")

if [ ${#directories[@]} -eq 0 ]; then
    echo "Error: No directories provided"
    echo "Usage: /utils:analyze-pprof <dir1> [dir2 ...]"
    exit 1
fi

echo ""
echo "Validating input directories..."

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Error: Directory not found: $dir"
        exit 1
    fi

    # Count pprof files
    pprof_count=$(find "$dir" -type f \( -name "*.pprof" -o -name "*.prof" -o -name "*.pb.gz" -o -name "profile" \) 2>/dev/null | wc -l)

    if [ "$pprof_count" -eq 0 ]; then
        echo "⚠ Warning: No pprof files found in $dir"
        echo "  Expected file patterns: *.pprof, *.prof, *.pb.gz, or 'profile'"
    else
        echo "✓ Found $pprof_count pprof file(s) in $dir"
    fi
done
```

### Step 2: Create Working Directory

1. **Set up workspace**

```bash
# Use basename of first directory as identifier
dir_name=$(basename "${directories[0]}")
timestamp=$(date +%Y%m%d_%H%M%S)
work_dir=".work/analyze-pprof/${dir_name}_${timestamp}"

mkdir -p "$work_dir"

echo ""
echo "Working directory: $work_dir"
echo ""
```

2. **Copy helper script to working directory (for reference)**

```bash
# The helper script is located at:
script_path="plugins/utils/skills/analyze-pprof/analyze_pprof.py"

if [ ! -f "$script_path" ]; then
    echo "Error: Helper script not found at $script_path"
    exit 1
fi

# Create a local copy for this analysis
cp "$script_path" "$work_dir/"
```

### Step 3: Process Each Directory

For each directory provided, perform the following steps:

1. **Find and list pprof files**

```bash
for i in "${!directories[@]}"; do
    dir="${directories[$i]}"
    label="dataset_$((i+1))"

    echo "==============================================="
    echo "PROCESSING: $dir (Label: $label)"
    echo "==============================================="
    echo ""

    # Find all pprof files
    pprof_files=()
    while IFS= read -r -d '' file; do
        pprof_files+=("$file")
    done < <(find "$dir" -type f \( -name "*.pprof" -o -name "*.prof" -o -name "*.pb.gz" -o -name "profile" \) -print0 2>/dev/null)

    if [ ${#pprof_files[@]} -eq 0 ]; then
        echo "No pprof files found, skipping..."
        continue
    fi

    echo "Found ${#pprof_files[@]} pprof file(s):"
    for file in "${pprof_files[@]}"; do
        size=$(du -h "$file" | cut -f1)
        echo "  - $(basename "$file") ($size)"
    done
    echo ""
done
```

2. **Merge pprof files using go tool pprof**

```bash
    # Merge all pprof files in the directory
    merged_profile="$work_dir/${label}_merged.pprof"

    echo "Merging ${#pprof_files[@]} pprof files..."

    # Use go tool pprof to merge profiles
    # The -proto flag outputs in pprof format
    go tool pprof -proto -output="$merged_profile" "${pprof_files[@]}" 2>/dev/null

    if [ $? -ne 0 ]; then
        echo "Warning: Failed to merge profiles for $dir"
        continue
    fi

    merged_size=$(du -h "$merged_profile" | cut -f1)
    echo "✓ Created merged profile: ${label}_merged.pprof ($merged_size)"
    echo ""
```

3. **Extract top functions using go tool pprof**

```bash
    # Generate text summary
    summary_file="$work_dir/${label}_summary.txt"

    echo "Generating analysis report..."
    {
        echo "PPROF ANALYSIS REPORT"
        echo "====================="
        echo "Dataset: $dir"
        echo "Label: $label"
        echo "Files merged: ${#pprof_files[@]}"
        echo "Generated: $(date)"
        echo ""

        echo "TOP 20 FUNCTIONS BY CUMULATIVE CPU TIME"
        echo "========================================"
        go tool pprof -top -cum "$merged_profile" 2>/dev/null | head -25

        echo ""
        echo "TOP 20 FUNCTIONS BY FLAT CPU TIME"
        echo "=================================="
        go tool pprof -top "$merged_profile" 2>/dev/null | head -25

        echo ""
        echo "CALL GRAPH (Top 10 by cumulative time)"
        echo "======================================="
        go tool pprof -tree -cum "$merged_profile" 2>/dev/null | head -50

    } > "$summary_file"

    echo "✓ Created text report: ${label}_summary.txt"
```

4. **Generate JSON data for programmatic access**

```bash
    # Extract structured data using the Python helper
    json_file="$work_dir/${label}_summary.json"

    python3 "$script_path" \
        --extract-top \
        --pprof-file "$merged_profile" \
        --output "$json_file" \
        --top-n 50 \
        2>/dev/null

    if [ -f "$json_file" ]; then
        echo "✓ Created JSON data: ${label}_summary.json"
    fi
```

5. **Generate flamegraph SVG**

```bash
    # Generate flamegraph
    flamegraph_file="$work_dir/${label}_flamegraph.svg"

    go tool pprof -output="$flamegraph_file" -svg "$merged_profile" 2>/dev/null

    if [ -f "$flamegraph_file" ]; then
        svg_size=$(du -h "$flamegraph_file" | cut -f1)
        echo "✓ Created flamegraph: ${label}_flamegraph.svg ($svg_size)"
    fi

    echo ""
```

### Step 4: Perform Comparative Analysis (if multiple directories)

If the user provided multiple directories, perform comparative analysis:

1. **Check if comparison is needed**

```bash
if [ ${#directories[@]} -gt 1 ]; then
    echo "==============================================="
    echo "COMPARATIVE ANALYSIS"
    echo "==============================================="
    echo ""
    echo "Comparing ${#directories[@]} datasets..."
    echo ""
fi
```

2. **Use Python helper to compare JSON data**

```bash
    # Run comparison
    comparison_file="$work_dir/comparison_report.txt"

    python3 "$script_path" \
        --compare \
        --input-dir "$work_dir" \
        --output "$comparison_file" \
        --threshold 20.0 \
        2>/dev/null

    if [ -f "$comparison_file" ]; then
        echo "✓ Created comparison report: comparison_report.txt"
        echo ""

        # Display comparison report
        cat "$comparison_file"
    fi
```

### Step 5: Generate Summary and Final Output

1. **Create comprehensive summary**

```bash
echo ""
echo "==============================================="
echo "ANALYSIS COMPLETE"
echo "==============================================="
echo ""

echo "Output directory: $work_dir"
echo ""

echo "Generated files:"
for i in "${!directories[@]}"; do
    label="dataset_$((i+1))"
    echo ""
    echo "Dataset $((i+1)): ${directories[$i]}"

    if [ -f "$work_dir/${label}_summary.txt" ]; then
        echo "  ✓ Text report: ${label}_summary.txt"
    fi

    if [ -f "$work_dir/${label}_summary.json" ]; then
        echo "  ✓ JSON data: ${label}_summary.json"
    fi

    if [ -f "$work_dir/${label}_merged.pprof" ]; then
        echo "  ✓ Merged profile: ${label}_merged.pprof"
        echo "    (Use: go tool pprof -http=:8080 $work_dir/${label}_merged.pprof)"
    fi

    if [ -f "$work_dir/${label}_flamegraph.svg" ]; then
        echo "  ✓ Flamegraph: ${label}_flamegraph.svg"
    fi
done

if [ ${#directories[@]} -gt 1 ] && [ -f "$work_dir/comparison_report.txt" ]; then
    echo ""
    echo "Comparative Analysis:"
    echo "  ✓ Comparison report: comparison_report.txt"
fi

echo ""
echo "You can view the flamegraphs in a web browser or use go tool pprof for interactive analysis."
```

2. **Provide usage recommendations**

```bash
echo ""
echo "Next steps:"
echo "  1. Review text reports for top CPU consumers"
echo "  2. Open flamegraphs in browser for visual analysis"
echo "  3. For interactive analysis: go tool pprof -http=:8080 <merged.pprof>"

if [ ${#directories[@]} -gt 1 ]; then
    echo "  4. Review comparison report for performance changes"
fi

echo ""
```

## Return Value

- **Exit 0**: Analysis completed successfully
- **Exit 1**: Error (missing prerequisites, no valid pprof files, etc.)

**Output Files**:
- `dataset_N_summary.txt`: Human-readable text report
- `dataset_N_summary.json`: Structured JSON data
- `dataset_N_merged.pprof`: Merged profile for further analysis
- `dataset_N_flamegraph.svg`: Visual flamegraph
- `comparison_report.txt`: Comparative analysis (if multiple datasets)

## Error Handling

### Missing Go Toolchain

**Error**: `go: command not found`

**Resolution**:
- Inform user that Go is required
- Provide installation instructions for their platform
- Link to: https://go.dev/doc/install

### Invalid Pprof Files

**Error**: pprof parsing errors during merge

**Resolution**:
1. Verify files are valid pprof CPU profiles
2. Check file corruption (try opening individual files)
3. Ensure all files are from the same architecture (amd64, arm64, etc.)
4. Skip corrupted files and continue with valid ones

### No Pprof Files Found

**Error**: Empty directory or no matching files

**Resolution**:
1. List directory contents to help user
2. Ask user to confirm file naming patterns
3. Provide examples of expected file names
4. Suggest checking file extensions

### Memory Issues

**Error**: Out of memory during large profile processing

**Resolution**:
1. Process files in smaller batches
2. Suggest using `go tool pprof` directly for very large files
3. Recommend increasing available memory
4. Use sampling or filtering if available

## Examples

### Example 1: Single Directory Analysis

**User request**: "Analyze the CPU profiles in ./profiles/production"

**Expected workflow**:
1. Validate Go and Python are installed
2. Find pprof files in ./profiles/production
3. Merge all files into single profile
4. Generate text report with top functions
5. Create flamegraph
6. Output results to .work/analyze-pprof/production_TIMESTAMP/

### Example 2: Before/After Comparison

**User request**: "Compare CPU profiles before and after optimization"

**Expected workflow**:
1. Process ./profiles/before directory
2. Process ./profiles/after directory
3. Generate individual reports for each
4. Create comparison report showing:
   - Functions with increased CPU usage (regressions)
   - Functions with decreased CPU usage (improvements)
   - New functions not in before
   - Removed functions not in after
5. Highlight significant changes (>20% difference)

### Example 3: Multi-Configuration Comparison

**User request**: "Compare three different database configurations"

**Expected workflow**:
1. Process ./profiles/config-postgres
2. Process ./profiles/config-mysql
3. Process ./profiles/config-mongodb
4. Generate comparative analysis showing relative CPU consumption
5. Identify which configuration is most efficient

## Advanced Usage

### Interactive Analysis

After running the command, users can perform interactive analysis:

```bash
# Open interactive web UI
go tool pprof -http=:8080 .work/analyze-pprof/*/dataset_1_merged.pprof

# Generate specific views
go tool pprof -web .work/analyze-pprof/*/dataset_1_merged.pprof  # Graph view
go tool pprof -list='myFunction' merged.pprof  # Source code view
go tool pprof -peek='myPackage' merged.pprof   # Package-level view
```

### Custom Filtering

Users can filter analysis by package or function:

```bash
# Focus on specific package
go tool pprof -focus='github.com/myorg/mypackage' merged.pprof -top

# Ignore runtime functions
go tool pprof -ignore='runtime\.' merged.pprof -top

# Show only functions above threshold
go tool pprof -nodecount=10 merged.pprof -top
```

## Performance Considerations

- Merging large profiles (>500MB) may require significant memory
- Processing time scales with number of samples in profiles
- Flamegraph generation can be slow for complex call stacks
- JSON extraction is faster than full pprof analysis
- Consider processing files in parallel for very large datasets

## Security Considerations

- Pprof files may reveal internal implementation details
- Function names and package paths are visible in reports
- Stack traces may contain sensitive business logic
- Treat profiles from production systems as confidential
- Sanitize reports before sharing externally

## See Also

- **Go pprof documentation**: https://pkg.go.dev/runtime/pprof
- **Go blog on profiling**: https://go.dev/blog/pprof
- **Flamegraph documentation**: https://www.brendangregg.com/flamegraphs.html
- **pprof GitHub**: https://github.com/google/pprof

## Notes

- This skill focuses on CPU profiles; memory profiles use different analysis techniques
- Profiles should be collected under similar conditions for meaningful comparison
- Short profiles (<10s) may not have enough samples for accurate analysis
- Consider using `-cpuprofile` flag when running Go programs to generate profiles
- For continuous profiling, consider using tools like Google Cloud Profiler or Datadog
- The merge operation is additive: all samples from all files are combined
- Timestamps are not preserved during merging; only aggregate data is retained
