# Analyze Pprof Skill

This skill provides tools for aggregating and analyzing CPU profiles from pprof files, with support for comparative analysis across multiple datasets.

## Overview

The analyze-pprof skill helps you:
- Aggregate multiple pprof CPU profile files
- Identify CPU hotspots and performance bottlenecks
- Compare performance across different builds or configurations
- Generate comprehensive reports with visualizations

## Files

- **SKILL.md**: Detailed implementation guide for the AI agent
- **analyze_pprof.py**: Python helper script for data extraction and comparison
- **README.md**: This file

## Usage

This skill is invoked through the `/utils:analyze-pprof` command. See the command documentation for usage details.

### Command Syntax

```bash
/utils:analyze-pprof <directory1> [directory2 ...]
```

### Examples

1. **Analyze single directory**:
   ```
   /utils:analyze-pprof ./profiles/baseline
   ```

2. **Compare before/after**:
   ```
   /utils:analyze-pprof ./profiles/before ./profiles/after
   ```

3. **Compare multiple configurations**:
   ```
   /utils:analyze-pprof ./profiles/config-a ./profiles/config-b ./profiles/config-c
   ```

## Helper Script

The `analyze_pprof.py` script can be used independently:

### Extract top functions to JSON

```bash
python3 analyze_pprof.py extract \
  --pprof-file merged.pprof \
  --output functions.json \
  --top-n 50
```

### Compare datasets

```bash
python3 analyze_pprof.py compare \
  --input-dir .work/analyze-pprof/results/ \
  --output comparison.txt \
  --threshold 20.0
```

## Requirements

- Go toolchain (for `go tool pprof`)
- Python 3.7+
- pprof CPU profile files

## Output

The analysis generates:
- **Text reports**: Human-readable summaries with top CPU consumers
- **JSON data**: Structured data for programmatic access
- **Merged profiles**: Combined pprof files for further analysis
- **Flamegraphs**: SVG visualizations of call stacks
- **Comparison reports**: Detailed diff between datasets (when comparing)

## See Also

- [Command documentation](../../commands/analyze-pprof.md)
- [Go pprof documentation](https://pkg.go.dev/runtime/pprof)
- [Flamegraph visualization](https://www.brendangregg.com/flamegraphs.html)
