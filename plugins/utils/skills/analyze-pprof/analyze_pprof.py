#!/usr/bin/env python3
"""
Helper script for analyzing and comparing pprof CPU profiles.

This script provides functionality to:
- Extract top functions from pprof files into structured JSON
- Compare multiple pprof datasets
- Generate comparative analysis reports
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any


def parse_pprof_top_output(output: str) -> List[Dict[str, Any]]:
    """
    Parse the output of 'go tool pprof -top' command.

    Expected format:
      flat  flat%   sum%        cum   cum%
      2.5s  5.2%  5.2%     25.3s 52.8%  runtime.mallocgc
      1.8s  3.8%  9.0%     18.7s 39.0%  encoding/json.Unmarshal
    """
    functions = []

    # Skip header lines
    lines = output.strip().split('\n')
    header_found = False

    for line in lines:
        # Skip until we find the header
        if not header_found:
            if 'flat' in line and 'cum' in line:
                header_found = True
            continue

        # Parse data lines
        # Format: flat flat% sum% cum cum% function_name
        parts = line.split()
        if len(parts) < 6:
            continue

        try:
            flat_time = parts[0]
            flat_pct = parts[1].rstrip('%')
            sum_pct = parts[2].rstrip('%')
            cum_time = parts[3]
            cum_pct = parts[4].rstrip('%')
            function_name = ' '.join(parts[5:])  # Function name may contain spaces

            # Convert time strings to seconds (handle formats like "2.5s", "250ms", "2500µs")
            flat_seconds = parse_time_to_seconds(flat_time)
            cum_seconds = parse_time_to_seconds(cum_time)

            functions.append({
                'function': function_name,
                'flat_time': flat_time,
                'flat_seconds': flat_seconds,
                'flat_percent': float(flat_pct),
                'cumulative_time': cum_time,
                'cumulative_seconds': cum_seconds,
                'cumulative_percent': float(cum_pct),
                'sum_percent': float(sum_pct)
            })
        except (ValueError, IndexError) as e:
            # Skip malformed lines
            continue

    return functions


def parse_time_to_seconds(time_str: str) -> float:
    """
    Convert time string to seconds.
    Handles: "2.5s", "250ms", "2500µs", "2500us"
    """
    time_str = time_str.lower().strip()

    # Match patterns: number followed by unit
    match = re.match(r'([\d.]+)\s*([a-zµ]+)', time_str)
    if not match:
        return 0.0

    value = float(match.group(1))
    unit = match.group(2)

    # Convert to seconds
    if unit == 's':
        return value
    elif unit == 'ms':
        return value / 1000.0
    elif unit in ['µs', 'us']:
        return value / 1000000.0
    elif unit == 'ns':
        return value / 1000000000.0
    else:
        return value  # Assume seconds if unknown


def extract_top_functions(pprof_file: str, top_n: int = 50) -> List[Dict[str, Any]]:
    """
    Extract top N functions from a pprof file using 'go tool pprof'.

    Args:
        pprof_file: Path to the pprof file
        top_n: Number of top functions to extract

    Returns:
        List of function data dictionaries
    """
    try:
        # Run go tool pprof -top to get top functions by cumulative time
        result = subprocess.run(
            ['go', 'tool', 'pprof', '-top', '-cum', pprof_file],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"Error running pprof: {result.stderr}", file=sys.stderr)
            return []

        # Parse the output
        functions = parse_pprof_top_output(result.stdout)

        # Return top N
        return functions[:top_n]

    except subprocess.TimeoutExpired:
        print(f"Error: pprof command timed out for {pprof_file}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error extracting functions from {pprof_file}: {e}", file=sys.stderr)
        return []


def load_dataset_json(json_file: Path) -> Dict[str, Any]:
    """Load a dataset JSON file."""
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {json_file}: {e}", file=sys.stderr)
        return {}


def compare_datasets(datasets: List[Tuple[str, List[Dict[str, Any]]]], threshold: float = 20.0) -> str:
    """
    Compare multiple datasets and generate a comparison report.

    Args:
        datasets: List of (label, functions) tuples
        threshold: Percentage threshold for highlighting changes

    Returns:
        Formatted comparison report as string
    """
    if len(datasets) < 2:
        return "Error: Need at least 2 datasets for comparison"

    report_lines = []

    # Compare first dataset with others
    baseline_label, baseline_funcs = datasets[0]

    # Create lookup by function name for baseline
    baseline_map = {f['function']: f for f in baseline_funcs}

    for i in range(1, len(datasets)):
        compare_label, compare_funcs = datasets[i]

        report_lines.append(f"Comparison: {baseline_label} vs {compare_label}")
        report_lines.append("=" * 80)
        report_lines.append("")

        # Create lookup for comparison dataset
        compare_map = {f['function']: f for f in compare_funcs}

        # Track changes
        regressions = []  # Functions with increased CPU usage
        improvements = []  # Functions with decreased CPU usage
        new_hotspots = []  # Functions only in comparison
        removed_hotspots = []  # Functions only in baseline

        # Analyze all functions from both datasets
        all_functions = set(baseline_map.keys()) | set(compare_map.keys())

        for func_name in all_functions:
            baseline_func = baseline_map.get(func_name)
            compare_func = compare_map.get(func_name)

            if baseline_func and compare_func:
                # Function exists in both - calculate change
                baseline_time = baseline_func['cumulative_seconds']
                compare_time = compare_func['cumulative_seconds']

                if baseline_time > 0:
                    change_pct = ((compare_time - baseline_time) / baseline_time) * 100
                    change_abs = compare_time - baseline_time

                    if abs(change_pct) >= threshold:
                        change_data = {
                            'function': func_name,
                            'baseline_time': baseline_time,
                            'compare_time': compare_time,
                            'change_pct': change_pct,
                            'change_abs': change_abs,
                            'baseline_pct': baseline_func['cumulative_percent'],
                            'compare_pct': compare_func['cumulative_percent']
                        }

                        if change_pct > 0:
                            regressions.append(change_data)
                        else:
                            improvements.append(change_data)

            elif compare_func and not baseline_func:
                # New hotspot
                new_hotspots.append({
                    'function': func_name,
                    'time': compare_func['cumulative_seconds'],
                    'percent': compare_func['cumulative_percent']
                })

            elif baseline_func and not compare_func:
                # Removed hotspot
                removed_hotspots.append({
                    'function': func_name,
                    'time': baseline_func['cumulative_seconds'],
                    'percent': baseline_func['cumulative_percent']
                })

        # Sort by magnitude of change
        regressions.sort(key=lambda x: x['change_abs'], reverse=True)
        improvements.sort(key=lambda x: abs(x['change_abs']), reverse=True)
        new_hotspots.sort(key=lambda x: x['time'], reverse=True)
        removed_hotspots.sort(key=lambda x: x['time'], reverse=True)

        # Generate report sections

        # Significant regressions
        if regressions:
            report_lines.append(f"SIGNIFICANT REGRESSIONS (>{threshold}% increase):")
            report_lines.append("-" * 80)
            for reg in regressions[:10]:  # Top 10
                report_lines.append(
                    f"  {reg['function']}\n"
                    f"    {baseline_label}: {format_time(reg['baseline_time'])} ({reg['baseline_pct']:.1f}%)\n"
                    f"    {compare_label}: {format_time(reg['compare_time'])} ({reg['compare_pct']:.1f}%)\n"
                    f"    Change: +{reg['change_pct']:.1f}% (+{format_time(reg['change_abs'])}) ▲"
                )
            report_lines.append("")

        # Significant improvements
        if improvements:
            report_lines.append(f"SIGNIFICANT IMPROVEMENTS (>{threshold}% decrease):")
            report_lines.append("-" * 80)
            for imp in improvements[:10]:  # Top 10
                report_lines.append(
                    f"  {imp['function']}\n"
                    f"    {baseline_label}: {format_time(imp['baseline_time'])} ({imp['baseline_pct']:.1f}%)\n"
                    f"    {compare_label}: {format_time(imp['compare_time'])} ({imp['compare_pct']:.1f}%)\n"
                    f"    Change: {imp['change_pct']:.1f}% ({format_time(imp['change_abs'])}) ▼"
                )
            report_lines.append("")

        # New hotspots
        if new_hotspots:
            report_lines.append(f"NEW HOTSPOTS (present in {compare_label}, not in {baseline_label}):")
            report_lines.append("-" * 80)
            for new in new_hotspots[:5]:  # Top 5
                report_lines.append(
                    f"  {new['function']}\n"
                    f"    Time: {format_time(new['time'])} ({new['percent']:.1f}%)"
                )
            report_lines.append("")

        # Removed hotspots
        if removed_hotspots:
            report_lines.append(f"REMOVED HOTSPOTS (present in {baseline_label}, not in {compare_label}):")
            report_lines.append("-" * 80)
            for removed in removed_hotspots[:5]:  # Top 5
                report_lines.append(
                    f"  {removed['function']}\n"
                    f"    Time: {format_time(removed['time'])} ({removed['percent']:.1f}%)"
                )
            report_lines.append("")

        # Summary
        report_lines.append("SUMMARY:")
        report_lines.append("-" * 80)
        report_lines.append(f"  Regressions (>{threshold}%): {len(regressions)}")
        report_lines.append(f"  Improvements (>{threshold}%): {len(improvements)}")
        report_lines.append(f"  New hotspots: {len(new_hotspots)}")
        report_lines.append(f"  Removed hotspots: {len(removed_hotspots)}")
        report_lines.append("")

    return '\n'.join(report_lines)


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time string."""
    if seconds >= 1.0:
        return f"{seconds:.2f}s"
    elif seconds >= 0.001:
        return f"{seconds * 1000:.2f}ms"
    elif seconds >= 0.000001:
        return f"{seconds * 1000000:.2f}µs"
    else:
        return f"{seconds * 1000000000:.2f}ns"


def main():
    parser = argparse.ArgumentParser(
        description='Analyze and compare pprof CPU profiles'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract top functions to JSON')
    extract_parser.add_argument('--pprof-file', required=True, help='Path to pprof file')
    extract_parser.add_argument('--output', required=True, help='Output JSON file')
    extract_parser.add_argument('--top-n', type=int, default=50, help='Number of top functions')

    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare multiple datasets')
    compare_parser.add_argument('--input-dir', required=True, help='Directory with dataset JSON files')
    compare_parser.add_argument('--output', required=True, help='Output comparison report file')
    compare_parser.add_argument('--threshold', type=float, default=20.0,
                               help='Percentage threshold for highlighting changes')

    # Legacy argument support (for backward compatibility)
    parser.add_argument('--extract-top', action='store_true',
                       help='Extract top functions (legacy)')
    parser.add_argument('--compare', action='store_true',
                       help='Compare datasets (legacy)')
    parser.add_argument('--pprof-file', help='Path to pprof file (legacy)')
    parser.add_argument('--input-dir', help='Input directory (legacy)')
    parser.add_argument('--output', help='Output file (legacy)')
    parser.add_argument('--top-n', type=int, default=50, help='Top N functions (legacy)')
    parser.add_argument('--threshold', type=float, default=20.0,
                       help='Comparison threshold (legacy)')

    args = parser.parse_args()

    # Handle legacy arguments
    if args.extract_top or (args.pprof_file and not args.command):
        # Extract mode
        if not args.pprof_file or not args.output:
            print("Error: --pprof-file and --output are required", file=sys.stderr)
            return 1

        print(f"Extracting top {args.top_n} functions from {args.pprof_file}...")

        functions = extract_top_functions(args.pprof_file, args.top_n)

        if not functions:
            print("Error: No functions extracted", file=sys.stderr)
            return 1

        # Write to JSON
        output_data = {
            'pprof_file': args.pprof_file,
            'top_n': args.top_n,
            'functions': functions
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"✓ Extracted {len(functions)} functions to {args.output}")
        return 0

    elif args.compare or (args.input_dir and not args.command):
        # Compare mode
        if not args.input_dir or not args.output:
            print("Error: --input-dir and --output are required", file=sys.stderr)
            return 1

        input_dir = Path(args.input_dir)

        # Find all dataset JSON files
        json_files = sorted(input_dir.glob('dataset_*_summary.json'))

        if len(json_files) < 2:
            print(f"Error: Need at least 2 dataset JSON files in {input_dir}", file=sys.stderr)
            print(f"Found: {len(json_files)} file(s)", file=sys.stderr)
            return 1

        print(f"Comparing {len(json_files)} datasets...")

        # Load datasets
        datasets = []
        for json_file in json_files:
            label = json_file.stem  # e.g., "dataset_1_summary"
            data = load_dataset_json(json_file)

            if 'functions' in data:
                datasets.append((label, data['functions']))
                print(f"  Loaded {label}: {len(data['functions'])} functions")

        if len(datasets) < 2:
            print("Error: Failed to load valid datasets", file=sys.stderr)
            return 1

        # Generate comparison report
        report = compare_datasets(datasets, args.threshold)

        # Write report
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(report)

        print(f"✓ Comparison report written to {args.output}")
        return 0

    elif args.command == 'extract':
        # Extract mode (new style)
        print(f"Extracting top {args.top_n} functions from {args.pprof_file}...")

        functions = extract_top_functions(args.pprof_file, args.top_n)

        if not functions:
            print("Error: No functions extracted", file=sys.stderr)
            return 1

        output_data = {
            'pprof_file': args.pprof_file,
            'top_n': args.top_n,
            'functions': functions
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"✓ Extracted {len(functions)} functions to {args.output}")
        return 0

    elif args.command == 'compare':
        # Compare mode (new style)
        input_dir = Path(args.input_dir)

        json_files = sorted(input_dir.glob('dataset_*_summary.json'))

        if len(json_files) < 2:
            print(f"Error: Need at least 2 dataset JSON files in {input_dir}", file=sys.stderr)
            return 1

        print(f"Comparing {len(json_files)} datasets...")

        datasets = []
        for json_file in json_files:
            label = json_file.stem
            data = load_dataset_json(json_file)

            if 'functions' in data:
                datasets.append((label, data['functions']))
                print(f"  Loaded {label}: {len(data['functions'])} functions")

        if len(datasets) < 2:
            print("Error: Failed to load valid datasets", file=sys.stderr)
            return 1

        report = compare_datasets(datasets, args.threshold)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(report)

        print(f"✓ Comparison report written to {args.output}")
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
