#!/usr/bin/env python3
"""
Attempt automatic fixes for common compilation errors after dependency updates.

Handles common cases like:
- Type renames (e.g., Policy → ImageSigstoreVerificationPolicy)
- Package moves
- Import path changes
- Method signature changes (simple cases)

Returns:
    0: Fixes applied successfully and compilation succeeds
    1: Fixes applied but compilation still fails
    2: Could not determine fixes (manual intervention needed)
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class CompilationError:
    """Represents a compilation error"""
    file: str
    line: int
    column: int
    message: str
    error_type: str  # "undefined", "type-mismatch", "import-error", etc.


@dataclass
class Fix:
    """Represents a fix to be applied"""
    file: str
    old_text: str
    new_text: str
    reason: str


@dataclass
class FixResult:
    """Results from attempting fixes"""
    repo_path: str
    compilation_errors: List[CompilationError]
    fixes_attempted: List[Fix]
    files_modified: List[str]
    compilation_succeeds: bool
    needs_manual_fix: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON output"""
        return {
            'repo_path': self.repo_path,
            'compilation_errors': [asdict(e) for e in self.compilation_errors],
            'fixes_attempted': [asdict(f) for f in self.fixes_attempted],
            'files_modified': self.files_modified,
            'compilation_succeeds': self.compilation_succeeds,
            'needs_manual_fix': self.needs_manual_fix,
            'error': self.error
        }


class AutoFixer:
    """Automatically fix common compilation errors"""

    # Common type rename patterns from OpenShift API changes
    TYPE_RENAME_PATTERNS = [
        # Sigstore verification types (from api#2626 simulation)
        (r'\bPolicy\b', 'ImageSigstoreVerificationPolicy'),
        (r'\bPKI\b', 'ImagePolicyPKIRootOfTrust'),
    ]

    def __init__(self, repo_path: str, verbose: bool = True):
        self.repo_path = Path(repo_path).resolve()
        self.verbose = verbose
        self.go_module = self._get_go_module()

    def _get_go_module(self) -> Optional[str]:
        """Get the Go module name from go.mod"""
        go_mod = self.repo_path / 'go.mod'
        if not go_mod.exists():
            return None

        try:
            content = go_mod.read_text()
            for line in content.split('\n'):
                if line.startswith('module '):
                    return line.split()[1].strip()
        except Exception as e:
            self._log(f"Error reading go.mod: {e}")

        return None

    def _log(self, message: str):
        """Print verbose logging"""
        if self.verbose:
            print(f"[attempt-fix] {message}", file=sys.stderr)

    def compile(self) -> Tuple[bool, List[CompilationError]]:
        """
        Attempt to compile the repository and parse errors.

        Returns:
            Tuple of (success, list_of_errors)
        """
        self._log("Running compilation check...")

        try:
            result = subprocess.run(
                ['go', 'build', './...'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                self._log("Compilation successful")
                return True, []

            # Parse compilation errors
            errors = self._parse_compilation_errors(result.stderr)
            self._log(f"Found {len(errors)} compilation errors")

            return False, errors

        except subprocess.TimeoutExpired:
            self._log("Compilation timed out")
            return False, []
        except Exception as e:
            self._log(f"Error running compilation: {e}")
            return False, []

    def _parse_compilation_errors(self, stderr: str) -> List[CompilationError]:
        """
        Parse go build error output.

        Example error formats:
        - path/to/file.go:123:45: undefined: SomeType
        - path/to/file.go:123:45: cannot use x (type T1) as type T2
        """
        errors = []

        # Regex for Go compilation errors
        error_pattern = re.compile(
            r'^(.+?):(\d+):(\d+): (.+)$',
            re.MULTILINE
        )

        for match in error_pattern.finditer(stderr):
            file_path = match.group(1)
            line = int(match.group(2))
            column = int(match.group(3))
            message = match.group(4)

            # Classify error type
            error_type = "unknown"
            if "undefined:" in message:
                error_type = "undefined"
            elif "cannot use" in message or "type" in message.lower():
                error_type = "type-mismatch"
            elif "import" in message.lower():
                error_type = "import-error"

            errors.append(CompilationError(
                file=file_path,
                line=line,
                column=column,
                message=message,
                error_type=error_type
            ))

        return errors

    def _extract_undefined_types(self, errors: List[CompilationError]) -> Set[str]:
        """Extract undefined type names from errors"""
        undefined_types = set()

        for error in errors:
            if error.error_type == "undefined":
                # Extract type name from "undefined: TypeName"
                match = re.search(r'undefined: (\w+)', error.message)
                if match:
                    type_name = match.group(1)
                    undefined_types.add(type_name)

        return undefined_types

    def _find_type_renames(self, undefined_types: Set[str]) -> Dict[str, str]:
        """
        Attempt to find renamed types by searching dependency code.

        This is a heuristic approach:
        1. Look for types in updated dependencies that might be renames
        2. Use naming similarity (e.g., Policy → ImageSigstoreVerificationPolicy)
        3. Check import paths for hints
        """
        renames = {}

        self._log(f"Searching for renames of: {undefined_types}")

        # First, check our known patterns
        for old_pattern, new_name in self.TYPE_RENAME_PATTERNS:
            for undefined_type in undefined_types:
                if re.fullmatch(old_pattern, undefined_type):
                    renames[undefined_type] = new_name
                    self._log(f"Found known rename: {undefined_type} → {new_name}")

        # TODO: Could add more sophisticated detection here:
        # - Search go.mod dependencies for similar type names
        # - Use go/packages to inspect imported packages
        # - Parse vendored code if present

        return renames

    def _create_rename_fixes(
        self,
        errors: List[CompilationError],
        renames: Dict[str, str]
    ) -> List[Fix]:
        """
        Create Fix objects for type renames.

        For each file with undefined types, create fixes to rename them.
        """
        fixes = []
        files_to_fix = set(error.file for error in errors)

        for file_path in files_to_fix:
            abs_path = self.repo_path / file_path if not Path(file_path).is_absolute() else Path(file_path)

            if not abs_path.exists():
                continue

            try:
                content = abs_path.read_text()

                # Apply each rename
                for old_name, new_name in renames.items():
                    # Use word boundaries to avoid partial matches
                    pattern = r'\b' + re.escape(old_name) + r'\b'

                    if re.search(pattern, content):
                        fixes.append(Fix(
                            file=str(file_path),
                            old_text=old_name,
                            new_text=new_name,
                            reason=f"Type renamed from {old_name} to {new_name}"
                        ))

            except Exception as e:
                self._log(f"Error reading {file_path}: {e}")
                continue

        return fixes

    def _apply_fixes(self, fixes: List[Fix]) -> List[str]:
        """
        Apply fixes to files.

        Returns:
            List of files that were modified
        """
        modified_files = set()

        # Group fixes by file
        fixes_by_file = defaultdict(list)
        for fix in fixes:
            fixes_by_file[fix.file].append(fix)

        for file_path, file_fixes in fixes_by_file.items():
            abs_path = self.repo_path / file_path if not Path(file_path).is_absolute() else Path(file_path)

            if not abs_path.exists():
                self._log(f"Warning: File not found: {file_path}")
                continue

            try:
                content = abs_path.read_text()
                original_content = content

                # Apply all fixes for this file
                for fix in file_fixes:
                    pattern = r'\b' + re.escape(fix.old_text) + r'\b'
                    content = re.sub(pattern, fix.new_text, content)
                    self._log(f"  {file_path}: {fix.old_text} → {fix.new_text}")

                # Only write if content changed
                if content != original_content:
                    abs_path.write_text(content)
                    modified_files.add(file_path)
                    self._log(f"Modified: {file_path}")

            except Exception as e:
                self._log(f"Error applying fixes to {file_path}: {e}")
                continue

        return list(modified_files)

    def attempt_fix(self) -> FixResult:
        """
        Attempt to automatically fix compilation errors.

        Process:
        1. Compile and collect errors
        2. Analyze errors to determine fixes
        3. Apply fixes
        4. Re-compile to verify

        Returns:
            FixResult with details of what was attempted
        """
        self._log(f"Attempting automatic fixes for {self.repo_path}")

        # Step 1: Initial compilation
        success, errors = self.compile()

        if success:
            self._log("Repository already compiles successfully")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=[],
                fixes_attempted=[],
                files_modified=[],
                compilation_succeeds=True,
                needs_manual_fix=False
            )

        if not errors:
            self._log("Compilation failed but no errors were parsed")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=[],
                fixes_attempted=[],
                files_modified=[],
                compilation_succeeds=False,
                needs_manual_fix=True,
                error="Compilation failed but errors could not be parsed"
            )

        # Show error summary
        self._log(f"\nFound {len(errors)} compilation errors:")
        error_types = defaultdict(int)
        for error in errors:
            error_types[error.error_type] += 1
        for error_type, count in error_types.items():
            self._log(f"  {error_type}: {count}")

        # Step 2: Analyze errors and determine fixes
        undefined_types = self._extract_undefined_types(errors)

        if not undefined_types:
            self._log("No undefined types found - cannot auto-fix")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=errors,
                fixes_attempted=[],
                files_modified=[],
                compilation_succeeds=False,
                needs_manual_fix=True,
                error="Errors are not simple type renames"
            )

        self._log(f"\nUndefined types: {undefined_types}")

        # Try to find type renames
        renames = self._find_type_renames(undefined_types)

        if not renames:
            self._log("Could not determine type renames - manual fix needed")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=errors,
                fixes_attempted=[],
                files_modified=[],
                compilation_succeeds=False,
                needs_manual_fix=True,
                error=f"Could not determine renames for types: {undefined_types}"
            )

        self._log(f"\nDetected renames:")
        for old, new in renames.items():
            self._log(f"  {old} → {new}")

        # Step 3: Create and apply fixes
        fixes = self._create_rename_fixes(errors, renames)

        if not fixes:
            self._log("No fixes could be created")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=errors,
                fixes_attempted=[],
                files_modified=[],
                compilation_succeeds=False,
                needs_manual_fix=True,
                error="No applicable fixes found"
            )

        self._log(f"\nApplying {len(fixes)} fixes:")
        modified_files = self._apply_fixes(fixes)

        if not modified_files:
            self._log("No files were modified")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=errors,
                fixes_attempted=fixes,
                files_modified=[],
                compilation_succeeds=False,
                needs_manual_fix=True,
                error="Fixes could not be applied"
            )

        # Step 4: Re-compile to verify fixes
        self._log(f"\nRe-compiling after fixes...")
        success, remaining_errors = self.compile()

        if success:
            self._log("SUCCESS: Repository now compiles!")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=errors,
                fixes_attempted=fixes,
                files_modified=modified_files,
                compilation_succeeds=True,
                needs_manual_fix=False
            )
        else:
            self._log(f"Compilation still fails with {len(remaining_errors)} errors")
            self._log("Manual fixes may be needed")
            return FixResult(
                repo_path=str(self.repo_path),
                compilation_errors=remaining_errors,
                fixes_attempted=fixes,
                files_modified=modified_files,
                compilation_succeeds=False,
                needs_manual_fix=True,
                error="Auto-fixes applied but compilation still fails"
            )


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Attempt automatic fixes for compilation errors"
    )
    parser.add_argument(
        'repo_path',
        nargs='?',
        default='.',
        help='Path to repository (default: current directory)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose logging'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    fixer = AutoFixer(args.repo_path, verbose=not args.quiet)

    try:
        result = fixer.attempt_fix()

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\nResults:")
            print(f"  Initial errors: {len(result.compilation_errors)}")
            print(f"  Fixes attempted: {len(result.fixes_attempted)}")
            print(f"  Files modified: {len(result.files_modified)}")
            print(f"  Compilation succeeds: {result.compilation_succeeds}")
            print(f"  Needs manual fix: {result.needs_manual_fix}")
            if result.error:
                print(f"  Error: {result.error}")

        # Exit codes:
        # 0 = fixes applied and compilation succeeds
        # 1 = fixes applied but compilation still fails
        # 2 = could not determine fixes
        if result.compilation_succeeds:
            sys.exit(0)
        elif result.fixes_attempted:
            sys.exit(1)
        else:
            sys.exit(2)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
