#!/usr/bin/env python3
"""
Test Structure Analyzer - Analyze test coverage without running tests (Go only)

This script analyzes the structure of Go test and source files to identify
coverage gaps without actually executing tests.

Language Support: Go only
"""

import argparse
import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

# Add skills directory to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.dirname(SCRIPT_DIR)
if SKILLS_DIR not in sys.path:
    sys.path.insert(0, SKILLS_DIR)

# Go language configuration
GO_CONFIG = {
    'source_patterns': ['*.go'],
    'test_patterns': ['*_test.go'],
    'e2e_test_patterns': ['*e2e*_test.go', '*_e2e_test.go', '*integration*_test.go', '*_integration_test.go'],
    'e2e_test_dirs': ['test/e2e', 'test/integration', 'e2e', 'integration', 'tests/e2e', 'tests/integration'],
    'e2e_test_markers': [r'\[Serial\]', r'\[Disruptive\]', r'\[Longduration\]', r'\[ConnectedOnly\]', r'\[NonPreRelease\]', r'\.Describe\(', r'g\.Context\(', r'g\.It\('],
    'unit_test_dirs': ['test/unit', 'unit', 'tests/unit'],
    'util_patterns': ['*_util.go', '*_utils.go', '*_helper.go', '*_helpers.go', 'util.go', 'utils.go', 'helpers.go', 'helper.go'],
    'test_function_pattern': r'func\s+(Test\w+|Benchmark\w+|Example\w*)\s*\(',
    'function_pattern': r'func\s+(\([^)]+\)\s+)?(\w+)\s*\(',
    'exclude_dirs': ['vendor', 'testdata', '.git'],
}


@dataclass
class TestFunction:
    """Represents a test function"""
    name: str
    line_start: int
    line_end: int
    targets: List[str]  # Functions/methods this test calls


@dataclass
class SourceFunction:
    """Represents a source function"""
    name: str
    line_start: int
    line_end: int
    visibility: str  # 'public', 'private', 'exported'
    complexity: int = 1


@dataclass
class TestFile:
    """Represents a test file"""
    path: str
    tests: List[TestFunction]
    imports: List[str]
    target_file: Optional[str] = None


@dataclass
class SourceFile:
    """Represents a source file"""
    path: str
    functions: List[SourceFunction]
    classes: List[str]


def matches_pattern(filename: str, patterns: List[str]) -> bool:
    """Check if filename matches any of the patterns"""
    from fnmatch import fnmatch
    return any(fnmatch(filename, pattern) for pattern in patterns)


def is_util_file(filename: str, language: str = 'go') -> bool:
    """Check if file is a utility/helper file"""
    util_patterns = GO_CONFIG.get('util_patterns', [])
    return matches_pattern(filename, util_patterns)


def is_e2e_test_file(file_path: str, language: str = 'go', content: str = None) -> bool:
    """
    Determine if a test file is an e2e/integration test based on:
    1. File naming patterns (e.g., *e2e*_test.go, *integration*_test.go)
    2. Directory location (e.g., test/e2e/, integration/)
    3. Content markers (e.g., [Serial], [Disruptive], g.It(), g.Describe())

    Returns True if the file is identified as an e2e test, False otherwise.
    """
    config = GO_CONFIG

    # Check 1: E2E file naming patterns
    e2e_patterns = config.get('e2e_test_patterns', [])
    filename = os.path.basename(file_path)
    if matches_pattern(filename, e2e_patterns):
        return True

    # Check 2: E2E directory location
    e2e_dirs = config.get('e2e_test_dirs', [])
    normalized_path = file_path.replace('\\', '/')
    for e2e_dir in e2e_dirs:
        if f'/{e2e_dir}/' in normalized_path or normalized_path.startswith(f'{e2e_dir}/'):
            return True

    # Check 3: Unit test directory (if in unit test dir, it's NOT e2e)
    unit_dirs = config.get('unit_test_dirs', [])
    for unit_dir in unit_dirs:
        if f'/{unit_dir}/' in normalized_path or normalized_path.startswith(f'{unit_dir}/'):
            return False

    # Check 4: E2E markers in content (if content provided)
    if content:
        e2e_markers = config.get('e2e_test_markers', [])
        for marker in e2e_markers:
            if re.search(marker, content):
                return True

    # Default: treat as unit unless we positively identify e2e markers
    return False


def is_unit_test_file(file_path: str, language: str = 'go') -> bool:
    """
    Determine if a test file is a unit test based on:
    1. Directory location (e.g., test/unit/)
    2. NOT matching e2e patterns

    Returns True if the file is identified as a unit test, False otherwise.
    """
    config = GO_CONFIG

    # Check if in unit test directory
    unit_dirs = config.get('unit_test_dirs', [])
    normalized_path = file_path.replace('\\', '/')
    for unit_dir in unit_dirs:
        if f'/{unit_dir}/' in normalized_path or normalized_path.startswith(f'{unit_dir}/'):
            return True

    # Check if it matches e2e patterns - if yes, it's NOT a unit test
    e2e_patterns = config.get('e2e_test_patterns', [])
    filename = os.path.basename(file_path)
    if matches_pattern(filename, e2e_patterns):
        return False

    # Check if in e2e directory - if yes, it's NOT a unit test
    e2e_dirs = config.get('e2e_test_dirs', [])
    for e2e_dir in e2e_dirs:
        if f'/{e2e_dir}/' in normalized_path or normalized_path.startswith(f'{e2e_dir}/'):
            return False

    return False


def discover_files(source_dir: str, language: str = 'go', e2e_only: bool = True) -> Tuple[List[str], List[str]]:
    """
    Discover test and source files in a Go project.

    Args:
        source_dir: Directory to search
        language: Programming language (always 'go', kept for compatibility)
        e2e_only: If True, only include e2e/integration tests (default: True).
                  If False, include all tests.

    Returns:
        Tuple of (test_files, source_files)
    """
    config = GO_CONFIG
    test_patterns = config['test_patterns']
    source_patterns = config['source_patterns']
    exclude_dirs = config['exclude_dirs']

    # Also exclude unit test directories if e2e_only is True
    if e2e_only:
        unit_dirs = config.get('unit_test_dirs', [])
        exclude_dirs = exclude_dirs + [os.path.basename(d) for d in unit_dirs]

    test_files = []
    source_files = []

    for root, dirs, files in os.walk(source_dir):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            file_path = os.path.join(root, file)

            if matches_pattern(file, test_patterns):
                # If e2e_only is True, filter out unit tests
                if e2e_only:
                    # Read file content to check for e2e markers
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                        # Only include if it's identified as an e2e test
                        if is_e2e_test_file(file_path, language, content):
                            test_files.append(file_path)
                    except (OSError, UnicodeDecodeError):
                        # If we can't read the file, use filename/path heuristics only
                        if is_e2e_test_file(file_path, language):
                            test_files.append(file_path)
                else:
                    # Include all test files
                    test_files.append(file_path)

            elif matches_pattern(file, source_patterns):
                # Don't include test files as source files
                if not matches_pattern(file, test_patterns):
                    source_files.append(file_path)

    return test_files, source_files


def parse_test_file(file_path: str, language: str = 'go') -> TestFile:
    """Parse a Go test file to extract test functions"""
    config = GO_CONFIG
    test_pattern = config['test_function_pattern']

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        lines = content.split('\n')

    tests = []
    imports = []

    # Extract test functions - standard Go test functions
    for i, line in enumerate(lines):
        match = re.search(test_pattern, line)
        if match:
            # Extract test name - use the last captured group
            if match.lastindex:
                test_name = match.group(match.lastindex)
            else:
                test_name = match.group(0)

            # Find end of test function by tracking brace depth
            line_end = i
            brace_depth = 0
            for j in range(i, len(lines)):
                brace_depth += lines[j].count('{') - lines[j].count('}')
                if brace_depth <= 0 and j > i:
                    line_end = j
                    break
            else:
                line_end = len(lines) - 1

            # Extract function calls (potential test targets)
            test_block = '\n'.join(lines[i:line_end])
            targets = extract_function_calls(test_block, language)

            tests.append(TestFunction(
                name=test_name,
                line_start=i + 1,
                line_end=line_end + 1,
                targets=targets
            ))

    # For Go: Also extract Ginkgo/BDD-style tests (g.It, It, g.Context, etc.)
    if language == 'go':
        ginkgo_it_pattern = r'(?:g\.|o\.)?It\(\s*["\']([^"\']+)["\']'
        ginkgo_describe_pattern = r'(?:g\.|o\.)?(?:Describe|Context)\(\s*["\']([^"\']+)["\']'

        for i, line in enumerate(lines):
            # Match g.It(...) or It(...)
            it_match = re.search(ginkgo_it_pattern, line)
            if it_match:
                test_name = it_match.group(1)

                # Find end of It block (look for closing brace at same or lower indent)
                line_end = i + 1
                base_indent = len(line) - len(line.lstrip())
                brace_count = line.count('{') - line.count('}')

                for j in range(i + 1, len(lines)):
                    brace_count += lines[j].count('{') - lines[j].count('}')
                    if brace_count <= 0:
                        line_end = j
                        break
                    if j + 1 == len(lines):
                        line_end = j

                # Extract function calls
                test_block = '\n'.join(lines[i:line_end + 1])
                targets = extract_function_calls(test_block, language)

                tests.append(TestFunction(
                    name=f"It: {test_name}",
                    line_start=i + 1,
                    line_end=line_end + 1,
                    targets=targets
                ))

            # Also track Describe/Context blocks for context
            describe_match = re.search(ginkgo_describe_pattern, line)
            if describe_match and not it_match:  # Don't count lines that are both
                context_name = describe_match.group(1)
                # Note: We're not adding these as tests, just tracking them
                # Could be enhanced to show test hierarchy

    # Extract imports from Go files
    in_import_block = False
    for line in lines:
        if 'import (' in line:
            in_import_block = True
        elif in_import_block and ')' in line:
            in_import_block = False
        elif in_import_block or 'import' in line:
            imports.extend(re.findall(r'"([^"]+)"', line))

    # Infer target source file
    target_file = infer_target_file(file_path, language)

    return TestFile(
        path=file_path,
        tests=tests,
        imports=imports,
        target_file=target_file
    )


def parse_source_file(file_path: str, language: str = 'go') -> SourceFile:
    """Parse a Go source file to extract functions"""
    config = GO_CONFIG
    function_pattern = config['function_pattern']

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        lines = content.split('\n')

    functions = []

    for i, line in enumerate(lines):
        match = re.search(function_pattern, line)
        if match:
            # Extract function name and determine visibility for Go
            func_name = match.group(2)
            # In Go, exported functions start with uppercase, private with lowercase
            visibility = 'exported' if func_name[0].isupper() else 'private'

            # Find end of function (simplified)
            line_end = i + 1
            indent_level = len(line) - len(line.lstrip())

            for j in range(i + 1, len(lines)):
                if lines[j].strip() == '':
                    continue
                curr_indent = len(lines[j]) - len(lines[j].lstrip())
                if curr_indent <= indent_level and lines[j].strip():
                    line_end = j
                    break
                if j + 1 == len(lines):
                    line_end = j + 1

            # Calculate basic complexity (count decision points)
            func_block = '\n'.join(lines[i:line_end])
            complexity = calculate_complexity(func_block)

            functions.append(SourceFunction(
                name=func_name,
                line_start=i + 1,
                line_end=line_end + 1,
                visibility=visibility,
                complexity=complexity
            ))

    return SourceFile(
        path=file_path,
        functions=functions,
        classes=[]  # Simplified - not extracting classes
    )


def extract_function_calls(code_block: str, language: str = 'go') -> List[str]:
    """Extract function calls from Go code block (simplified)"""
    # Extract function call patterns - capture final identifier after any dotted qualifiers
    # This ensures pkg.DoThing() captures "DoThing" instead of "pkg"
    call_pattern = r'(?:(?:\b\w+\.)+)?(\b\w+)\s*\('
    calls = [match.group(1) for match in re.finditer(call_pattern, code_block)]

    # Filter out Go keywords
    keywords = {'if', 'for', 'switch', 'return', 'func', 'range', 'select', 'go', 'defer'}
    return list(set([c for c in calls if c not in keywords]))


def calculate_complexity(code_block: str) -> int:
    """Calculate cyclomatic complexity (simplified)"""
    # Count decision points
    decision_keywords = ['if', 'for', 'while', 'switch', 'case', '&&', '||']
    complexity = 1  # Base complexity

    for keyword in decision_keywords:
        complexity += code_block.count(keyword)

    return complexity


def infer_target_file(test_file_path: str, language: str = 'go') -> Optional[str]:
    """Infer the source file that a Go test file tests"""
    test_file = os.path.basename(test_file_path)
    test_dir = os.path.dirname(test_file_path)

    # handler_test.go -> handler.go
    if test_file.endswith('_test.go'):
        source_file = test_file.replace('_test.go', '.go')
        source_path = os.path.join(test_dir, source_file)
        if os.path.exists(source_path):
            return source_path

    return None


def map_tests_to_source(test_files: List[TestFile], source_files: List[SourceFile]) -> Dict:
    """Map tests to source files and functions"""
    mapping = {}

    # Create lookup for source files
    source_by_path = {sf.path: sf for sf in source_files}

    # Map each source file
    for source_file in source_files:
        # Find test files that target this source file
        related_tests = [tf for tf in test_files if tf.target_file == source_file.path]
        candidate_tests = related_tests if related_tests else test_files
        tests_covering_file: Set[str] = set()

        # Map functions to tests
        function_mapping = {}
        for func in source_file.functions:
            # Find tests that call this function
            tests_for_func = []
            for test_file in candidate_tests:
                for test in test_file.tests:
                    if func.name in test.targets:
                        tests_for_func.append(test.name)
                        tests_covering_file.add(test_file.path)

            function_mapping[func.name] = {
                'tested': len(tests_for_func) > 0,
                'tests': tests_for_func,
                'test_count': len(tests_for_func),
                'visibility': func.visibility,
                'complexity': func.complexity,
                'lines': [func.line_start, func.line_end]
            }

        mapped_test_files = sorted(tests_covering_file) if tests_covering_file else [tf.path for tf in related_tests]

        mapping[source_file.path] = {
            'test_files': mapped_test_files,
            'functions': function_mapping,
            'tested_functions': sum(1 for f in function_mapping.values() if f['tested']),
            'untested_functions': sum(1 for f in function_mapping.values() if not f['tested']),
            'total_functions': len(function_mapping)
        }

    return mapping


def calculate_priority(file_path: str, file_data: Dict) -> str:
    """Calculate priority for testing a file/function"""
    # High priority: No tests at all, or many exported/public functions
    if len(file_data['test_files']) == 0:
        # Check if it has exported/public functions
        exported_count = sum(
            1 for f in file_data['functions'].values()
            if f['visibility'] in ['exported', 'public']
        )
        if exported_count >= 3:
            return 'high'
        elif exported_count >= 1:
            return 'medium'
        else:
            return 'low'

    # Medium priority: Partially tested
    if file_data['untested_functions'] > 0:
        ratio = file_data['untested_functions'] / file_data['total_functions']
        if ratio > 0.5:
            return 'medium'
        else:
            return 'low'

    return 'low'


def identify_gaps(mapping: Dict, priority_filter: str = 'all') -> Dict:
    """Identify coverage gaps"""
    gaps = {
        'untested_files': [],
        'untested_functions': [],
        'partially_tested_files': [],
    }

    for source_file, data in mapping.items():
        file_priority = calculate_priority(source_file, data)
        include_file_level = priority_filter == 'all' or file_priority == priority_filter

        if len(data['test_files']) == 0 and include_file_level:
            # Completely untested file
            exported_count = sum(
                1 for f in data['functions'].values()
                if f['visibility'] in ['exported', 'public']
            )
            gaps['untested_files'].append({
                'file': source_file,
                'total_functions': data['total_functions'],
                'exported_functions': exported_count,
                'priority': file_priority
            })

        elif data['untested_functions'] > 0 and include_file_level:
            # Partially tested file
            gaps['partially_tested_files'].append({
                'file': source_file,
                'test_files': data['test_files'],
                'tested_functions': data['tested_functions'],
                'untested_functions': data['untested_functions'],
                'total_functions': data['total_functions'],
                'coverage': (data['tested_functions'] / data['total_functions'] * 100) if data['total_functions'] > 0 else 0,
                'priority': file_priority
            })

        # Collect untested functions (always iterate, apply function-level priority filter)
        for func_name, func_data in data['functions'].items():
            if not func_data['tested']:
                func_priority = 'high' if func_data['visibility'] in ['exported', 'public'] else 'low'
                if priority_filter == 'all' or func_priority == priority_filter:
                    gaps['untested_functions'].append({
                        'file': source_file,
                        'function': func_name,
                        'lines': func_data['lines'],
                        'visibility': func_data['visibility'],
                        'complexity': func_data['complexity'],
                        'priority': func_priority
                    })

    return gaps


def generate_test_only_summary(test_files: List[TestFile]) -> str:
    """Generate text summary for test-only mode (single test file analysis)"""
    if not test_files:
        return "No test files found."

    test_file = test_files[0]
    report = []
    report.append("Test Structure Analysis (Test-Only Mode)")
    report.append("=" * 55)
    report.append("")
    report.append(f"File: {os.path.basename(test_file.path)}")
    report.append(f"Path: {test_file.path}")
    report.append("")
    report.append("Summary:")
    report.append(f"  Total Tests:        {len(test_file.tests)}")
    report.append(f"  Total Imports:      {len(test_file.imports)}")
    report.append("")

    if test_file.tests:
        report.append("Test Functions:")
        for i, test in enumerate(test_file.tests[:10], 1):  # Show first 10 tests
            target_str = f" (calls: {', '.join(test.targets[:5])})" if test.targets else ""
            report.append(f"  {i}. {test.name} (lines {test.line_start}-{test.line_end}){target_str}")
        if len(test_file.tests) > 10:
            report.append(f"  ... and {len(test_file.tests) - 10} more tests")
        report.append("")

    if test_file.imports:
        report.append("Imports:")
        for imp in test_file.imports[:5]:  # Show first 5 imports
            report.append(f"  - {imp}")
        if len(test_file.imports) > 5:
            report.append(f"  ... and {len(test_file.imports) - 5} more imports")
        report.append("")

    report.append("Note:")
    report.append("  This is a test-structure-only analysis.")
    report.append("  No source files were analyzed or mapped.")
    report.append("  For full coverage gap analysis, run on a directory.")

    return '\n'.join(report)


def generate_summary_report(gaps: Dict, mapping: Dict) -> str:
    """Generate text summary report"""
    total_files = len(mapping)
    files_with_tests = sum(1 for data in mapping.values() if len(data['test_files']) > 0)
    files_without_tests = total_files - files_with_tests

    total_functions = sum(data['total_functions'] for data in mapping.values())
    tested_functions = sum(data['tested_functions'] for data in mapping.values())
    untested_functions = total_functions - tested_functions

    coverage_pct = (tested_functions / total_functions * 100) if total_functions > 0 else 0

    report = []
    report.append("Test Structure Analysis")
    report.append("=" * 55)
    report.append("")
    report.append("Summary:")
    report.append(f"  Total Source Files:    {total_files}")

    files_with_pct = (files_with_tests / total_files * 100) if total_files > 0 else 0
    files_without_pct = (files_without_tests / total_files * 100) if total_files > 0 else 0

    report.append(f"  Files With Tests:      {files_with_tests} ({files_with_pct:.1f}%)")
    report.append(f"  Files Without Tests:   {files_without_tests} ({files_without_pct:.1f}%)")
    report.append("")
    report.append(f"  Total Functions:       {total_functions}")
    report.append(f"  Tested Functions:      {tested_functions} ({coverage_pct:.1f}%)")
    report.append(f"  Untested Functions:    {untested_functions} ({100 - coverage_pct:.1f}%)")
    report.append("")

    # High priority gaps
    high_priority_untested = [g for g in gaps['untested_files'] if g['priority'] == 'high']
    if high_priority_untested:
        report.append("High Priority Gaps (need tests):")
        for i, gap in enumerate(high_priority_untested[:5], 1):
            report.append(f"  {i}. {gap['file']} - No test file ({gap['exported_functions']} exported functions)")
        report.append("")

    # Medium priority gaps
    medium_priority = [g for g in gaps['partially_tested_files'] if g['priority'] == 'medium']
    if medium_priority:
        report.append("Medium Priority Gaps:")
        for i, gap in enumerate(medium_priority[:5], 1):
            report.append(f"  {i}. {gap['file']} - Partially tested ({gap['tested_functions']}/{gap['total_functions']} functions, {gap['coverage']:.1f}%)")
        report.append("")

    # Recommendations
    report.append("Recommendations:")
    report.append(f"  ✓ Create test files for {len(gaps['untested_files'])} untested source files")
    report.append(f"  ✓ Add tests for {len(gaps['untested_functions'])} untested functions")
    if gaps['partially_tested_files']:
        report.append(f"  ✓ Strengthen test coverage for {len(gaps['partially_tested_files'])} partially tested files")
    if high_priority_untested:
        report.append(f"  ⚠ Focus on high-priority gaps first ({len(high_priority_untested)} items)")

    return '\n'.join(report)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze Go test structure without running tests (Go only)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('source_dir', help='Go source directory to analyze')
    parser.add_argument('--priority', choices=['all', 'high', 'medium', 'low'], default='all',
                        help='Filter gaps by priority level')
    parser.add_argument('--output', default='.work/test-coverage/analyze',
                        help='Output directory for reports')
    parser.add_argument('--include-test-utils', action='store_true',
                        help='Include test utility/helper files in analysis (excluded by default)')
    parser.add_argument('--include-unit-tests', action='store_true',
                        help='Include unit tests in analysis (by default, only e2e/integration tests are analyzed)')
    parser.add_argument('--test-structure-only', action='store_true',
                        help='Analyze only test file structure, skip source file analysis and gap detection')

    args = parser.parse_args()

    try:
        # Validate path and detect if it's a file or directory
        single_file_mode = False
        test_only_mode = args.test_structure_only  # Enable test-only mode if flag is set
        single_file_path = None
        source_dir = args.source_dir

        if os.path.isfile(args.source_dir):
            # Single file mode
            single_file_mode = True
            single_file_path = os.path.abspath(args.source_dir)
            source_dir = os.path.dirname(args.source_dir)
            print(f"Analyzing single file: {os.path.basename(single_file_path)}")
        elif os.path.isdir(args.source_dir):
            # Directory mode
            source_dir = args.source_dir
        else:
            print(f"Error: Path not found: {args.source_dir}", file=sys.stderr)
            return 1

        # This analyzer only supports Go language
        language = 'go'
        print(f"Language: Go")
        print()

        # Discover files
        if single_file_mode:
            # Check if the single file is a test file
            test_patterns = GO_CONFIG['test_patterns']
            filename = os.path.basename(single_file_path)

            is_test = False

            # Check 1: Does filename match test patterns?
            if matches_pattern(filename, test_patterns):
                is_test = True

            # Check 2: Is it in a test directory or has test markers in content?
            if not is_test:
                try:
                    with open(single_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    # Check if file has e2e test characteristics
                    if is_e2e_test_file(single_file_path, language, content):
                        is_test = True
                except (OSError, UnicodeDecodeError):
                    # If we can't read the file, just use filename/path heuristics
                    if is_e2e_test_file(single_file_path, language):
                        is_test = True

            if is_test:
                # It's a test file - analyze test structure only
                print("Test file detected - analyzing test structure only (no source file mapping)")
                test_only_mode = True
                test_files_paths = [single_file_path]
                source_files_paths = []
            else:
                # It's a source file - analyze as source
                print("Source file detected - analyzing as source file")
                test_files_paths = []
                source_files_paths = [single_file_path]
        else:
            # By default, analyze only e2e/integration tests (not unit tests)
            e2e_only = not args.include_unit_tests
            if test_only_mode:
                print("Discovering test files only (test-structure-only mode)...")
                if e2e_only:
                    print("(Analyzing e2e/integration tests only)")
            elif e2e_only:
                print("Discovering e2e/integration test files and source files...")
                print("(Use --include-unit-tests to include unit tests)")
            else:
                print("Discovering all test and source files...")
            test_files_paths, source_files_paths = discover_files(
                source_dir, language, e2e_only=e2e_only
            )

            # If test-structure-only mode, ignore discovered source files
            if test_only_mode:
                source_files_paths = []

        # Filter out utility files unless flag is set (but not in single file mode)
        if not args.include_test_utils and not single_file_mode:
            util_files = [f for f in source_files_paths if is_util_file(os.path.basename(f), language)]
            source_files_paths = [f for f in source_files_paths if not is_util_file(os.path.basename(f), language)]
            if util_files:
                print(f"Excluding {len(util_files)} test utility/helper files (use --include-test-utils to include them)")

        print(f"Found {len(source_files_paths)} source files")
        print(f"Found {len(test_files_paths)} test files")
        print()

        # Parse test files
        print("Parsing test files...")
        test_files = []
        for path in test_files_paths:
            try:
                test_file = parse_test_file(path, language)
                test_files.append(test_file)
            except (OSError, UnicodeDecodeError) as e:
                print(f"Warning: Failed to parse {path}: {e}", file=sys.stderr)

        # Parse source files (skip in test-only mode)
        if not test_only_mode:
            print("Parsing source files...")
            source_files = []
            for path in source_files_paths:
                try:
                    source_file = parse_source_file(path, language)
                    source_files.append(source_file)
                except (OSError, UnicodeDecodeError) as e:
                    print(f"Warning: Failed to parse {path}: {e}", file=sys.stderr)

            # Map tests to source
            print("Mapping tests to source code...")
            mapping = map_tests_to_source(test_files, source_files)

            # Identify gaps
            print("Identifying coverage gaps...")
            gaps = identify_gaps(mapping, args.priority)
        else:
            # Test-only mode: no source files, no mapping, no gaps
            source_files = []
            mapping = {}
            gaps = {'untested_files': [], 'untested_functions': [], 'partially_tested_files': []}

        # Create output directory
        os.makedirs(args.output, exist_ok=True)

        # Generate reports
        print("Generating reports...")

        # JSON report
        json_path = os.path.join(args.output, 'test-structure-gaps.json')
        report_data = {
            'language': language,
            'source_dir': args.source_dir,
            'test_only_mode': test_only_mode,
            'gaps': gaps,
            'summary': {
                'total_source_files': len(source_files),
                'total_test_files': len(test_files),
                'untested_files_count': len(gaps['untested_files']),
                'untested_functions_count': len(gaps['untested_functions']),
            }
        }
        if single_file_mode:
            report_data['analysis_mode'] = 'single_file'
            report_data['analyzed_file'] = single_file_path

        # In test-only mode, include test file details
        if test_only_mode and test_files:
            test_file = test_files[0]
            report_data['test_file_details'] = {
                'path': test_file.path,
                'test_count': len(test_file.tests),
                'tests': [
                    {
                        'name': t.name,
                        'line_start': t.line_start,
                        'line_end': t.line_end,
                        'targets': t.targets
                    }
                    for t in test_file.tests
                ],
                'imports': test_file.imports
            }

        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        # Text summary
        text_path = os.path.join(args.output, 'test-structure-summary.txt')
        if test_only_mode:
            summary = generate_test_only_summary(test_files)
        else:
            summary = generate_summary_report(gaps, mapping)
        with open(text_path, 'w') as f:
            f.write(summary)

        # HTML report
        html_path = os.path.join(args.output, 'test-structure-report.html')
        try:
            # Try relative import first (when run as module)
            try:
                from .test_structure_reports import generate_test_structure_html
            except ImportError:
                # Fallback to absolute import (when run as script)
                from skills.analyze.test_structure_reports import generate_test_structure_html

            with open(json_path, 'r') as f:
                json_data = json.load(f)
            generate_test_structure_html(json_data, html_path)
        except ImportError as e:
            print(f"Warning: Could not import HTML report generator: {e}")
            print("Skipping HTML report generation")
        except Exception as e:
            print(f"Warning: Failed to generate HTML report: {e}")
            import traceback
            traceback.print_exc()

        # Print summary to console
        print()
        print(summary)
        print()
        print("Reports Generated:")
        print(f"  JSON Report:   {json_path}")
        print(f"  Text Summary:  {text_path}")
        if os.path.exists(html_path):
            print(f"  HTML Report:   {html_path}")
        print()

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
