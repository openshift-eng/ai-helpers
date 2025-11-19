#!/usr/bin/env python3
"""
Execute semgrep scan with proper .semgrepignore handling.

This script handles all deterministic tasks:
- Creating .semgrepignore file (if --include-deps flag is present)
- Running semgrep scan
- Cleaning up .semgrepignore
- Outputting results as JSON

Usage:
    python3 run_semgrep_scan.py --config <config-url> --output <output-file> [--include-deps]

Example:
    python3 run_semgrep_scan.py --config https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml --output semgrep-all.json
    python3 run_semgrep_scan.py --config https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml --output semgrep-all.json --include-deps
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


class ExitCode:
    """Exit code constants."""

    SUCCESS = 0
    ERROR = 1
    SEMGREP_ERROR = 2


class SemgrepIgnoreConfig:
    """Configuration for .semgrepignore file handling."""

    FILE_NAME = ".semgrepignore"
    BACKUP_SUFFIX = ".bak"
    EXPECTED_LINE_COUNT_EXCLUDE_DEPS = 13
    EXPECTED_LINE_COUNT_INCLUDE_DEPS = 7
    FORBIDDEN_PATTERNS = ("vendor/", "node_modules/", ".git/")
    DEPENDENCY_PATTERNS = (
        "vendor/",
        "node_modules/",
        "site-packages/",
        "thirdparty/",
        ".venv/",
        "venv/",
    )
    SCAN_DIRECTORY = "."

    CONTENT_EXCLUDE_DEPS = """/__pycache__/
*.pyc
/_test.
/test/
/build/
/dist/
/target/
vendor/
node_modules/
site-packages/
thirdparty/
.venv/
venv/
"""

    CONTENT_INCLUDE_DEPS = """/__pycache__/
*.pyc
/_test.
/test/
/build/
/dist/
/target/
"""


class SemgrepIgnoreManager:
    """Manages .semgrepignore file creation and cleanup."""

    def __init__(self, file_path: str = SemgrepIgnoreConfig.FILE_NAME):
        self.file_path = Path(file_path)
        self.backup_path = Path(str(self.file_path) + SemgrepIgnoreConfig.BACKUP_SUFFIX)

    def create(self, include_deps: bool = False) -> bool:
        """
        Create .semgrepignore file, backing up existing file if present.

        Args:
            include_deps: If True, create .semgrepignore that allows scanning
                         vendor/node_modules. If False, explicitly excludes them.

        Returns:
            True if creation succeeded, False otherwise

        Raises:
            OSError: If file operations fail
        """
        had_existing_file = self.file_path.exists()
        if had_existing_file and not self._backup_existing():
            return False

        content = (
            SemgrepIgnoreConfig.CONTENT_INCLUDE_DEPS
            if include_deps
            else SemgrepIgnoreConfig.CONTENT_EXCLUDE_DEPS
        )

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            print(
                f"ERROR: Failed to write {self.file_path}: {e}",
                file=sys.stderr,
            )
            if had_existing_file and self.backup_path.exists():
                self._restore_from_backup()
            return False

        if not self._validate(include_deps):
            if had_existing_file and self.backup_path.exists():
                self._restore_from_backup()
            else:
                try:
                    self.file_path.unlink()
                except OSError:
                    pass
            return False

        return True

    def _backup_existing(self) -> bool:
        """
        Backup existing .semgrepignore file.

        Returns:
            True if backup succeeded, False otherwise
        """
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as src:
                with open(self.backup_path, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            return True
        except OSError as e:
            print(
                f"ERROR: Failed to backup existing {self.file_path}: {e}",
                file=sys.stderr,
            )
            return False

    def _validate(self, include_deps: bool = False) -> bool:
        """
        Validate .semgrepignore file content.

        Args:
            include_deps: Whether the file should include dependencies

        Returns:
            True if validation passes, False otherwise
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            print(
                f"ERROR: Failed to read {self.file_path} for validation: {e}",
                file=sys.stderr,
            )
            return False

        lines = content.strip().split("\n")
        expected_count = (
            SemgrepIgnoreConfig.EXPECTED_LINE_COUNT_INCLUDE_DEPS
            if include_deps
            else SemgrepIgnoreConfig.EXPECTED_LINE_COUNT_EXCLUDE_DEPS
        )

        if len(lines) != expected_count:
            print(
                f"ERROR: {self.file_path} has {len(lines)} lines, "
                f"expected {expected_count}",
                file=sys.stderr,
            )
            return False

        if include_deps:
            for forbidden in SemgrepIgnoreConfig.FORBIDDEN_PATTERNS:
                if forbidden in content:
                    print(
                        f"ERROR: {self.file_path} contains forbidden entry: {forbidden}",
                        file=sys.stderr,
                    )
                    return False
        else:
            missing_patterns = [
                pattern
                for pattern in SemgrepIgnoreConfig.DEPENDENCY_PATTERNS
                if pattern not in content
            ]
            if missing_patterns:
                print(
                    f"ERROR: {self.file_path} must exclude dependency directories when include_deps=False. "
                    f"Missing: {', '.join(missing_patterns)}",
                    file=sys.stderr,
                )
                return False

        return True

    def remove(self) -> None:
        """Remove .semgrepignore file, restoring backup if present."""
        if self.backup_path.exists():
            self._restore_from_backup()
        elif self.file_path.exists():
            try:
                self.file_path.unlink()
            except OSError as e:
                print(
                    f"WARNING: Failed to remove {self.file_path}: {e}",
                    file=sys.stderr,
                )

    def _restore_from_backup(self) -> None:
        """Restore .semgrepignore from backup file."""
        if not self.backup_path.exists():
            return

        try:
            with open(self.backup_path, "r", encoding="utf-8", errors="ignore") as src:
                content = src.read()
                with open(self.file_path, "w", encoding="utf-8") as dst:
                    dst.write(content)
            try:
                self.backup_path.unlink()
            except OSError as e:
                print(
                    f"WARNING: Failed to remove backup file {self.backup_path}: {e}",
                    file=sys.stderr,
                )
        except OSError as e:
            print(
                f"WARNING: Failed to restore {self.file_path} from backup: {e}",
                file=sys.stderr,
            )
            if self.file_path.exists():
                try:
                    self.file_path.unlink()
                except OSError:
                    pass


class SemgrepRunner:
    """Runs semgrep scans with proper configuration."""

    SEMGREP_COMMAND = "semgrep"
    SUCCESS_EXIT_CODES = (0, 1)

    def __init__(
        self,
        config_url: str,
        output_file: str,
        scan_directory: str = SemgrepIgnoreConfig.SCAN_DIRECTORY,
    ):
        self.config_url = config_url
        self.output_file = Path(output_file)
        self.scan_directory = Path(scan_directory)

    def _validate_paths(self) -> bool:
        """
        Validate that paths exist and are accessible.

        Returns:
            True if paths are valid, False otherwise
        """
        if not self.scan_directory.exists():
            print(
                f"ERROR: Scan directory does not exist: {self.scan_directory}",
                file=sys.stderr,
            )
            return False

        if not self.scan_directory.is_dir():
            print(
                f"ERROR: Scan path is not a directory: {self.scan_directory}",
                file=sys.stderr,
            )
            return False

        output_parent = self.output_file.parent
        if output_parent and not output_parent.exists():
            try:
                output_parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                print(
                    f"ERROR: Cannot create output directory {output_parent}: {e}",
                    file=sys.stderr,
                )
                return False

        if self.output_file.exists() and self.output_file.is_dir():
            print(
                f"ERROR: Output path is a directory: {self.output_file}",
                file=sys.stderr,
            )
            return False

        return True

    def run(self) -> int:
        """
        Run semgrep scan.

        Returns:
            Exit code (0 = success, >0 = error)
        """
        if not self._validate_paths():
            return ExitCode.ERROR

        cmd = self._build_command()

        print(f"Running semgrep: {' '.join(cmd)}", file=sys.stderr)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            print(
                f"ERROR: {self.SEMGREP_COMMAND} not found. Please install semgrep.",
                file=sys.stderr,
            )
            return ExitCode.SEMGREP_ERROR
        except OSError as e:
            print(
                f"ERROR: Failed to execute semgrep: {e}",
                file=sys.stderr,
            )
            return ExitCode.ERROR

        if result.returncode not in self.SUCCESS_EXIT_CODES:
            print(
                f"ERROR: Semgrep failed with exit code {result.returncode}",
                file=sys.stderr,
            )
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return ExitCode.SEMGREP_ERROR

        print(
            f"✓ Semgrep scan completed. Results saved to {self.output_file}",
            file=sys.stderr,
        )
        return ExitCode.SUCCESS

    def _build_command(self) -> List[str]:
        """Build semgrep command arguments."""
        return [
            self.SEMGREP_COMMAND,
            "--config",
            self.config_url,
            "--no-git-ignore",
            "--json",
            "--output",
            str(self.output_file),
            str(self.scan_directory),
        ]


def run_semgrep_scan(
    config_url: str, output_file: str, include_deps: bool = False
) -> int:
    """
    Run semgrep scan with proper .semgrepignore handling.

    This function always creates a .semgrepignore file to ensure deterministic
    behavior regardless of whether the repo has its own .semgrepignore or relies
    on .gitignore. Since we use --no-git-ignore, .gitignore is bypassed, so we
    must explicitly control what gets scanned via .semgrepignore.

    Args:
        config_url: Semgrep config URL
        output_file: Output file path for JSON results
        include_deps: If True, create .semgrepignore that allows scanning
                     vendor/node_modules. If False, explicitly excludes them.

    Returns:
        Exit code (0 = success, >0 = error)
    """
    ignore_manager = SemgrepIgnoreManager()
    semgrepignore_created = False

    try:
        print(
            f"Creating .semgrepignore ({'including' if include_deps else 'excluding'} dependencies)...",
            file=sys.stderr,
        )
        if not ignore_manager.create(include_deps=include_deps):
            print(
                "ERROR: Failed to create .semgrepignore correctly",
                file=sys.stderr,
            )
            return ExitCode.ERROR
        semgrepignore_created = True
        print("✓ .semgrepignore created successfully", file=sys.stderr)

        runner = SemgrepRunner(config_url, output_file)
        exit_code = runner.run()

        return exit_code

    finally:
        if semgrepignore_created:
            ignore_manager.remove()
            print("✓ .semgrepignore cleaned up", file=sys.stderr)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Execute semgrep scan with proper .semgrepignore handling"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Semgrep config URL (e.g., https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output file path for JSON results",
    )
    parser.add_argument(
        "--include-deps",
        action="store_true",
        help="Create .semgrepignore to ensure vendor/dependency directories are scanned",
    )

    args = parser.parse_args()

    try:
        exit_code = run_semgrep_scan(
            config_url=args.config,
            output_file=args.output,
            include_deps=args.include_deps,
        )
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except (OSError, subprocess.SubprocessError, argparse.ArgumentError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(ExitCode.ERROR)


if __name__ == "__main__":
    main()
