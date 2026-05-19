#!/usr/bin/env python3
"""
Parses make generate output and identifies error patterns.
Returns JSON with error classification and suggested fixes.
"""

import sys
import json
import re
from pathlib import Path

# Error pattern definitions
ERROR_PATTERNS = [
    {
        "name": "missing_deepcopy_markers",
        "signatures": [
            r"Types need DeepCopy methods",
            r"missing deepcopy-gen markers",
            r"DeepCopy.*not found",
            r"must have deepcopy",
        ],
        "error_type": "missing_markers",
        "suggested_fix": "Add // +k8s:deepcopy-gen=true comment above type definitions",
        "auto_fixable": True,
    },
    {
        "name": "missing_genclient_markers",
        "signatures": [
            r"does not have genclient marker",
            r"genclient.*required",
            r"missing.*genclient",
        ],
        "error_type": "missing_markers",
        "suggested_fix": "Add // +genclient comment above resource type definitions (not lists or subresources)",
        "auto_fixable": True,
    },
    {
        "name": "import_path_resolution",
        "signatures": [
            r"cannot resolve import path",
            r"package.*not found",
            r"no such package",
            r"cannot find package",
        ],
        "error_type": "import_error",
        "suggested_fix": "Run 'go mod tidy' or verify GOPATH is correctly set",
        "auto_fixable": True,
    },
    {
        "name": "tool_not_found",
        "signatures": [
            r"deepcopy-gen.*command not found",
            r"client-gen.*not found",
            r"informer-gen.*not found",
            r"lister-gen.*not found",
            r"openapi-gen.*not found",
            r"controller-gen.*not found",
            r"protoc.*command not found",
            r"protobuf requires protoc",
        ],
        "error_type": "missing_tool",
        "suggested_fix": "Install missing code-generator tools or run tool installation make target",
        "auto_fixable": True,
    },
    {
        "name": "gopath_not_set",
        "signatures": [
            r"GOPATH.*not set",
            r"GOPATH.*to be set",
            r"requires GOPATH",
            r"cannot find package in any of.*GOPATH",
            r"GOROOT.*not found",
        ],
        "error_type": "environment",
        "suggested_fix": "Verify GOPATH is set and repository is in correct location ($GOPATH/src/github.com/openshift/api)",
        "auto_fixable": False,
    },
    {
        "name": "permission_denied",
        "signatures": [
            r"permission denied",
            r"cannot create.*Permission denied",
        ],
        "error_type": "permissions",
        "suggested_fix": "Check file permissions and ownership in the repository directory",
        "auto_fixable": False,
    },
    {
        "name": "stale_generated_code",
        "signatures": [
            r"conflict.*generated",
            r"generated.*out of date",
            r"Please run.*update-codegen",
        ],
        "error_type": "stale_code",
        "suggested_fix": "Remove old generated files (find . -name 'zz_generated.*.go' -delete) and retry",
        "auto_fixable": True,
    },
    {
        "name": "vendor_out_of_sync",
        "signatures": [
            r"inconsistent vendoring",
            r"not marked as replaced in vendor/modules\.txt",
            r"To sync the vendor directory, run:\s+go mod vendor",
        ],
        "error_type": "dependency",
        "suggested_fix": "Run 'go mod vendor' to sync vendor directory with go.mod",
        "auto_fixable": True,
    },
    {
        "name": "go_mod_issues",
        "signatures": [
            r"go.mod.*malformed",
            r"go.sum.*mismatch",
            r"missing go.sum entry",
        ],
        "error_type": "dependency",
        "suggested_fix": "Run 'go mod tidy' to fix go.mod and go.sum",
        "auto_fixable": True,
    },
    {
        "name": "compilation_error",
        "signatures": [
            r"syntax error",
            r"undefined:",
            r"type.*not defined",
        ],
        "error_type": "compilation",
        "suggested_fix": "Fix syntax or type errors in source files before generating",
        "auto_fixable": False,
    },
]


def extract_file_references(output):
    """Extract file paths mentioned in error output."""
    file_patterns = [
        r"([a-zA-Z0-9_/.-]+\.go):\d+:\d+:",  # file.go:line:col:
        r"([a-zA-Z0-9_/.-]+\.go):",  # file.go:
        r"in\s+([a-zA-Z0-9_/.-]+\.go)",  # in file.go
    ]

    files = set()
    for pattern in file_patterns:
        matches = re.finditer(pattern, output)
        for match in matches:
            files.add(match.group(1))

    return sorted(list(files))


def extract_type_references(output):
    """Extract type names mentioned in errors."""
    type_patterns = [
        r"type\s+([A-Z][a-zA-Z0-9_]*)",
        r"struct\s+([A-Z][a-zA-Z0-9_]*)",
    ]

    types = set()
    for pattern in type_patterns:
        matches = re.finditer(pattern, output)
        for match in matches:
            types.add(match.group(1))

    return sorted(list(types))


def detect_error_pattern(output):
    """Detect which error pattern matches the output."""
    for pattern in ERROR_PATTERNS:
        for signature in pattern["signatures"]:
            if re.search(signature, output, re.IGNORECASE):
                return pattern

    return None


def analyze_output(output):
    """Analyze make generate output and return error classification."""
    # Check if generation was successful
    if "Exit code: 0" in output or re.search(r"generated.*successfully", output, re.IGNORECASE):
        return {
            "status": "success",
            "error_type": None,
            "error_pattern": None,
            "suggested_fix": None,
            "auto_fixable": False,
            "files_to_check": [],
            "types_mentioned": [],
        }

    # Detect error pattern
    pattern = detect_error_pattern(output)

    if pattern:
        return {
            "status": "error",
            "error_type": pattern["error_type"],
            "error_pattern": pattern["name"],
            "suggested_fix": pattern["suggested_fix"],
            "auto_fixable": pattern["auto_fixable"],
            "files_to_check": extract_file_references(output),
            "types_mentioned": extract_type_references(output),
        }
    else:
        # Unknown error pattern
        return {
            "status": "error",
            "error_type": "unknown",
            "error_pattern": "unrecognized",
            "suggested_fix": "Unknown error - manual review required",
            "auto_fixable": False,
            "files_to_check": extract_file_references(output),
            "types_mentioned": extract_type_references(output),
            "error_sample": output[:500] if len(output) > 500 else output,
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: detect_generation_errors.py <output_file>", file=sys.stderr)
        print("   or: cat output.log | detect_generation_errors.py -", file=sys.stderr)
        sys.exit(1)

    # Read input
    if sys.argv[1] == "-":
        output = sys.stdin.read()
    else:
        output_file = Path(sys.argv[1])
        if not output_file.exists():
            print(f"Error: File not found: {output_file}", file=sys.stderr)
            sys.exit(1)
        output = output_file.read_text()

    # Analyze
    result = analyze_output(output)

    # Output JSON
    print(json.dumps(result, indent=2))

    # Exit code based on status
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
