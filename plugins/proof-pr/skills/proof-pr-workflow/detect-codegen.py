#!/usr/bin/env python3
"""
Detect if a repository requires code generation after dependency updates.

This script analyzes a repository to determine if it has code generation
requirements and executes the appropriate generation commands.

Returns:
    0: No code generation needed or generation successful
    1: Code generation needed but failed
    2: Detection error
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, asdict


@dataclass
class CodegenResult:
    """Results from codegen detection and execution"""
    repo_path: str
    needs_codegen: bool
    detection_method: str  # "known-repo", "makefile", "go-generate", "zz-files", "none"
    command: Optional[str] = None
    files_changed: List[str] = None
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON output"""
        d = asdict(self)
        if d['files_changed'] is None:
            d['files_changed'] = []
        return d


class CodegenDetector:
    """Detects and runs code generation for OpenShift repositories"""

    # Known repositories with standard codegen commands
    KNOWN_REPOS = {
        'client-go': 'make update-codegen',
        'api': 'make update-codegen-crds',
        'apiserver-library-go': 'make update-codegen',
        'library-go': 'make update-codegen',
        'openshift-apiserver': 'make update-codegen',
        'kube-apiserver': 'make update-codegen',
    }

    # Common Makefile targets for codegen
    CODEGEN_TARGETS = [
        'update-codegen',
        'update-codegen-crds',
        'update',
        'generate',
        'generate-code',
    ]

    # Patterns indicating generated files
    GENERATED_FILE_PATTERNS = [
        '**/zz_generated.*.go',
        '**/*_generated.go',
        '**/generated/**/*.go',
        '**/listers/**/*.go',
        '**/informers/**/*.go',
        '**/clientset/**/*.go',
    ]

    def __init__(self, repo_path: str, verbose: bool = True):
        self.repo_path = Path(repo_path).resolve()
        self.verbose = verbose
        self.repo_name = self._get_repo_name()

    def _get_repo_name(self) -> str:
        """Extract repository name from path or git remote"""
        # Try to get from git remote
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            url = result.stdout.strip()
            # Extract repo name from URL (e.g., github.com/openshift/client-go -> client-go)
            repo_name = url.rstrip('/').split('/')[-1].replace('.git', '')
            return repo_name
        except subprocess.CalledProcessError:
            # Fallback to directory name
            return self.repo_path.name

    def _log(self, message: str):
        """Print verbose logging"""
        if self.verbose:
            print(f"[detect-codegen] {message}", file=sys.stderr)

    def _check_known_repo(self) -> Optional[str]:
        """Check if this is a known repository with standard codegen"""
        if self.repo_name in self.KNOWN_REPOS:
            cmd = self.KNOWN_REPOS[self.repo_name]
            self._log(f"Detected known repository '{self.repo_name}' with command: {cmd}")
            return cmd
        return None

    def _check_makefile_targets(self) -> Optional[str]:
        """Check Makefile for codegen targets"""
        makefile = self.repo_path / 'Makefile'
        if not makefile.exists():
            self._log("No Makefile found")
            return None

        self._log(f"Checking Makefile for codegen targets")

        # Read Makefile and look for codegen targets
        try:
            content = makefile.read_text()

            # Look for our known targets
            for target in self.CODEGEN_TARGETS:
                # Match target definitions (target: or .PHONY: target)
                if f"{target}:" in content or f".PHONY: {target}" in content:
                    cmd = f"make {target}"
                    self._log(f"Found Makefile target '{target}': {cmd}")
                    return cmd

            self._log("No known codegen targets found in Makefile")
        except Exception as e:
            self._log(f"Error reading Makefile: {e}")

        return None

    def _check_go_generate(self) -> Optional[str]:
        """Check for //go:generate directives in Go files"""
        self._log("Checking for //go:generate directives")

        try:
            # Find all .go files
            result = subprocess.run(
                ['find', '.', '-name', '*.go', '-type', 'f'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            go_files = [f for f in result.stdout.split('\n') if f]

            # Check first 100 files for //go:generate
            for go_file in go_files[:100]:
                try:
                    path = self.repo_path / go_file.lstrip('./')
                    content = path.read_text()
                    if '//go:generate' in content:
                        self._log(f"Found //go:generate directive in {go_file}")
                        return "go generate ./..."
                except Exception:
                    continue

            self._log("No //go:generate directives found")
        except Exception as e:
            self._log(f"Error checking for go:generate: {e}")

        return None

    def _check_generated_files(self) -> bool:
        """Check if repository contains generated files"""
        self._log("Checking for generated file patterns")

        for pattern in self.GENERATED_FILE_PATTERNS:
            try:
                # Use find to check for pattern
                result = subprocess.run(
                    ['find', '.', '-path', pattern, '-type', 'f'],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                files = [f for f in result.stdout.split('\n') if f]
                if files:
                    self._log(f"Found {len(files)} files matching pattern '{pattern}'")
                    self._log(f"Examples: {files[:3]}")
                    return True
            except Exception as e:
                self._log(f"Error checking pattern {pattern}: {e}")
                continue

        self._log("No generated file patterns found")
        return False

    def detect(self) -> CodegenResult:
        """
        Detect if repository needs code generation.

        Returns CodegenResult with detection details.
        """
        self._log(f"Detecting codegen requirements for {self.repo_path}")

        # 1. Check known repositories first
        cmd = self._check_known_repo()
        if cmd:
            return CodegenResult(
                repo_path=str(self.repo_path),
                needs_codegen=True,
                detection_method="known-repo",
                command=cmd
            )

        # 2. Check Makefile targets
        cmd = self._check_makefile_targets()
        if cmd:
            return CodegenResult(
                repo_path=str(self.repo_path),
                needs_codegen=True,
                detection_method="makefile",
                command=cmd
            )

        # 3. Check for //go:generate directives
        cmd = self._check_go_generate()
        if cmd:
            return CodegenResult(
                repo_path=str(self.repo_path),
                needs_codegen=True,
                detection_method="go-generate",
                command=cmd
            )

        # 4. Check for existing generated files (suggests codegen but no clear command)
        has_generated_files = self._check_generated_files()
        if has_generated_files:
            self._log("WARNING: Found generated files but no clear codegen command")
            self._log("Repository likely needs codegen but detection failed")
            return CodegenResult(
                repo_path=str(self.repo_path),
                needs_codegen=True,
                detection_method="zz-files",
                command=None,
                error="Generated files found but no codegen command detected"
            )

        # No codegen needed
        self._log("No code generation requirements detected")
        return CodegenResult(
            repo_path=str(self.repo_path),
            needs_codegen=False,
            detection_method="none"
        )

    def run_codegen(self, command: str) -> Tuple[bool, List[str], Optional[str]]:
        """
        Execute the code generation command.

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (success, changed_files, error_message)
        """
        self._log(f"Running codegen command: {command}")

        # Get current git status
        try:
            subprocess.run(
                ['git', 'diff', '--quiet'],
                cwd=self.repo_path,
                check=False  # Don't fail if there are changes
            )
        except Exception as e:
            return False, [], f"Failed to check git status: {e}"

        # Run the command
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                error_msg = f"Command failed with exit code {result.returncode}\n"
                error_msg += f"stdout: {result.stdout}\n"
                error_msg += f"stderr: {result.stderr}"
                self._log(f"Codegen failed: {error_msg}")
                return False, [], error_msg

            self._log("Codegen command completed successfully")

        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after 300 seconds"
            self._log(error_msg)
            return False, [], error_msg
        except Exception as e:
            error_msg = f"Failed to run command: {e}"
            self._log(error_msg)
            return False, [], error_msg

        # Check what files changed
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            changed_files = [f for f in result.stdout.split('\n') if f]

            if changed_files:
                self._log(f"Codegen modified {len(changed_files)} files")
                self._log(f"Examples: {changed_files[:5]}")
            else:
                self._log("No files were modified by codegen")

            return True, changed_files, None

        except Exception as e:
            error_msg = f"Failed to check changed files: {e}"
            self._log(error_msg)
            # Don't fail if we can't check changes - codegen succeeded
            return True, [], None

    def detect_and_run(self) -> CodegenResult:
        """
        Detect and run code generation if needed.

        Returns complete CodegenResult with execution details.
        """
        # Detect requirements
        result = self.detect()

        # If no codegen needed, return early
        if not result.needs_codegen:
            result.success = True
            return result

        # If detection failed (has generated files but no command), fail
        if result.command is None:
            result.success = False
            return result

        # Run the codegen command
        success, changed_files, error = self.run_codegen(result.command)

        result.success = success
        result.files_changed = changed_files
        result.error = error

        return result


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect and run code generation for OpenShift repositories"
    )
    parser.add_argument(
        'repo_path',
        nargs='?',
        default='.',
        help='Path to repository (default: current directory)'
    )
    parser.add_argument(
        '--detect-only',
        action='store_true',
        help='Only detect, do not run codegen'
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

    detector = CodegenDetector(args.repo_path, verbose=not args.quiet)

    try:
        if args.detect_only:
            result = detector.detect()
        else:
            result = detector.detect_and_run()

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\nResults:")
            print(f"  Needs codegen: {result.needs_codegen}")
            print(f"  Detection method: {result.detection_method}")
            if result.command:
                print(f"  Command: {result.command}")
            if result.files_changed:
                print(f"  Files changed: {len(result.files_changed)}")
            if result.error:
                print(f"  Error: {result.error}")
            print(f"  Success: {result.success}")

        # Exit codes:
        # 0 = success (no codegen needed or codegen succeeded)
        # 1 = codegen failed
        # 2 = detection error
        if not result.success and result.needs_codegen:
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
