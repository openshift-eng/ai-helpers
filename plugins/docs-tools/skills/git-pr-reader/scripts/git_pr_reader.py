#!/usr/bin/env python3
"""
Git PR Reader - Unified Python library and CLI for GitHub PRs and GitLab MRs.

This module provides a complete API for:
- Fetching PR/MR information (title, description, changed files, diffs)
- Fetching review comments and discussions
- Posting inline review comments to GitHub PRs and GitLab MRs
- Extracting line numbers from PR/MR diffs for accurate comment placement
- Validating comments against actual diff content
- YAML-based file filtering for excluding irrelevant files
- Auto-detecting the PR/MR for the current git branch

Usage as library:
    from git_pr_reader import GitReviewAPI

    api = GitReviewAPI.from_url("https://github.com/owner/repo/pull/123")

    # Get PR info
    info = api.get_pr_info()

    # Get changed files
    files = api.get_changed_files()

    # Get review comments
    comments = api.get_review_comments()

    # Get filtered PR data (title, description, diffs)
    data = api.get_pr_data()

    # Post comments
    api.post_comments([
        {"file": "path/to/file.adoc", "line": 42, "message": "Issue description"}
    ])

Usage as CLI:
    python git_pr_reader.py read --url "https://github.com/owner/repo/pull/123"
    python git_pr_reader.py info https://github.com/owner/repo/pull/123
    python git_pr_reader.py files https://github.com/owner/repo/pull/123
    python git_pr_reader.py detect

Authentication:
    Requires tokens in .env or ~/.env:
    - GitHub: GITHUB_TOKEN environment variable
    - GitLab: GITLAB_TOKEN environment variable
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

try:
    from github import Auth, Github
except ImportError:
    Github = None  # type: ignore[assignment,misc]
    Auth = None  # type: ignore[assignment,misc]

try:
    from gitlab import Gitlab
except ImportError:
    Gitlab = None  # type: ignore[assignment,misc]


# =============================================================================
# Utilities
# =============================================================================


def load_env_file() -> None:
    """Load environment variables from .env files.

    Loads ./.env first (local settings), then ~/.env (global defaults).
    Pre-existing environment variables are never overwritten.
    Surrounding quotes on values are stripped.
    """
    for env_path in [".env", os.path.expanduser("~/.env")]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        value = value.strip()
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]
                        os.environ.setdefault(key.strip(), value)


def color_print(prefix: str, message: str) -> None:
    """Print output to terminal (Claude Code compatible, no color codes)."""
    print(f"  {prefix}: {message}")


# -- Ignore patterns for large PR filtering ----------------------------------

DEFAULT_IGNORE_PATTERNS: List[re.Pattern] = [
    re.compile(p)
    for p in [
        # -- Vendored / dependency dirs (all ecosystems) --
        r"(^|/)vendor/",
        r"(^|/)node_modules/",
        r"(^|/)venv/",
        r"(^|/)\.venv/",
        r"(^|/)env/",
        r"(^|/)__pycache__/",
        r"(^|/)\.tox/",
        r"\.egg-info/",
        # -- Test dirs and files --
        r"(^|/)test/",
        r"(^|/)tests/",
        r"(^|/)__tests__/",
        r"(^|/)testdata/",
        r"(^|/)src/test/",  # Java/Maven
        r"(^|/)spec/",  # Ruby RSpec
        r"(^|/)cypress/",
        r"(^|/)coverage/",
        r"_test\.go$",
        r"_test\.py$",
        r"test_.*\.py$",
        r"\.test\.[jt]sx?$",
        r"\.spec\.[jt]sx?$",
        # -- Build / output dirs --
        r"(^|/)dist/",
        r"(^|/)build/",
        r"(^|/)bin/",
        r"(^|/)target/",  # Java/Maven, Rust
        r"(^|/)out/",
        r"(^|/)\.next/",  # Next.js
        r"(^|/)\.nuxt/",  # Nuxt.js
        # -- Generated / compiled files --
        r"\.pb\.go$",
        r"\.gen\.go$",
        r"zz_generated",
        r"\.class$",
        r"\.pyc$",
        r"\.jar$",
        r"\.war$",
        r"\.min\.[jc]ss?$",
        r"\.bundle\.js$",
        # -- Lock / dependency manifests --
        r"go\.mod$",
        r"go\.sum$",
        r"\.lock$",
        r"package-lock\.json$",
        r"yarn\.lock$",
        r"pnpm-lock\.yaml$",
        r"Pipfile\.lock$",
        r"Gemfile\.lock$",
        r"Cargo\.lock$",
        r"poetry\.lock$",
        r"requirements\.txt$",
        r"requirements.*\.txt$",
        # -- Build / tooling files --
        r"(^|/)hack/",
        r"Makefile$",
        r"Tiltfile$",
        r"Dockerfile",
        r"docker-compose",
        r"pyproject\.toml$",
        r"setup\.cfg$",
        r"setup\.py$",
        r"pom\.xml$",  # Maven
        r"build\.gradle",  # Gradle
        # -- CI/CD --
        r"(^|/)\.(github|gitlab)",
        r"\.travis\.yml$",
        r"\.gitlab-ci\.yml$",
        r"[Jj]enkinsfile$",
        r"\.circleci/",
        # -- Config / linting --
        r"\.gitignore$",
        r"\.gitattributes$",
        r"\.editorconfig$",
        r"\.eslintrc",
        r"\.prettierrc",
        r"\.golangci",
        r"\.rubocop",
        r"\.flake8$",
        r"\.pylintrc$",
        r"tox\.ini$",
        # -- Media / assets --
        r"\.png$",
        r"\.jpg$",
        r"\.jpeg$",
        r"\.svg$",
        r"\.gif$",
        r"\.ico$",
        r"\.woff2?$",
        r"\.ttf$",
        r"\.eot$",
        # -- Infrastructure --
        r"\.tfstate",
        # -- Docs / meta --
        r"CHANGELOG\.md$",
        r"LICENSE$",
        r"NOTICE$",
    ]
]


def filter_files(file_list: List[str], patterns: List[re.Pattern]) -> List[str]:
    """Filter file paths, dropping any that match an ignore pattern."""
    return [f for f in file_list if not any(p.search(f) for p in patterns)]


def _redact_token(arg: str) -> str:
    """Redact auth tokens from git command arguments for safe error messages."""
    return re.sub(r"(https?://)[^@]+@", r"\1***@", arg)


def load_ignore_config(path: str) -> List[re.Pattern]:
    """Load ignore patterns from a YAML file with a `git_ignore_list` key."""
    if yaml is None:
        raise ImportError("PyYAML required for --ignore-config. Run: pip install pyyaml")
    with open(path) as f:
        config = yaml.safe_load(f)
    raw = config.get("git_ignore_list", [])
    return [re.compile(p) for p in raw]


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class ReviewComment:
    """Represents a single review comment to post."""

    file: str
    line: int
    message: str
    severity: str = "suggestion"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ReviewComment":
        """Create from dictionary."""
        return cls(
            file=data.get("file", ""),
            line=int(data.get("line", 0)),
            message=data.get("message", ""),
            severity=data.get("severity", "suggestion"),
        )


@dataclass
class DiffLine:
    """Represents a line from a diff with its file line number."""

    file_line: int
    content: str
    is_added: bool = True


@dataclass
class PostResult:
    """Result of posting comments."""

    posted: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "posted": self.posted,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


# =============================================================================
# File filtering
# =============================================================================


def load_filters(config_path: Optional[str] = None) -> List[re.Pattern]:
    """
    Load file filtering patterns from YAML config.

    Args:
        config_path: Path to git_filters.yaml. If None, auto-detects
                     relative to the script location.

    Returns:
        List of compiled regex patterns for file exclusion.
    """
    if config_path is None:
        resolved_path = str(pathlib.Path(__file__).parent.parent / "config" / "git_filters.yaml")
    else:
        resolved_path = config_path

    if not os.path.exists(resolved_path):
        return []

    if yaml is None:
        print("Warning: PyYAML not installed; file filtering disabled.", file=sys.stderr)
        return []

    with open(resolved_path) as f:
        config = yaml.safe_load(f)

    patterns = config.get("exclude_patterns", [])
    return [re.compile(p) for p in patterns]


# =============================================================================
# Abstract base class
# =============================================================================


class GitReviewAPI(ABC):
    """
    Abstract base class for Git review APIs (GitHub/GitLab).

    Provides common functionality for reading PR/MR data, posting review
    comments, extracting line numbers from diffs, and validating comments.
    """

    def __init__(self, url: str, config_path: Optional[str] = None):
        """
        Initialize the API with a PR/MR URL.

        Args:
            url: The full URL to the PR or MR.
            config_path: Optional path to git_filters.yaml for file filtering.
        """
        self.url = url
        self._pr_info: Optional[Dict] = None
        self._diff_cache: Dict[str, str] = {}
        self._filters: Optional[List[re.Pattern]] = None
        self._config_path = config_path

    @classmethod
    def from_url(cls, url: str, config_path: Optional[str] = None) -> "GitReviewAPI":
        """
        Factory method to create the appropriate API instance from a URL.

        Args:
            url: GitHub PR or GitLab MR URL.
            config_path: Optional path to git_filters.yaml.

        Returns:
            GitHubReviewAPI or GitLabReviewAPI instance.

        Raises:
            ValueError: If URL format is not recognized.
        """
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if "github.com" in host:
            return GitHubReviewAPI(url, config_path=config_path)
        elif "gitlab" in host:
            return GitLabReviewAPI(url, config_path=config_path)
        else:
            raise ValueError(
                f"Unable to determine platform from URL: {url}\n"
                "Supported formats:\n"
                "  GitHub: https://github.com/owner/repo/pull/123\n"
                "  GitLab: https://gitlab.com/group/project/-/merge_requests/123"
            )

    # -------------------------------------------------------------------------
    # File filtering
    # -------------------------------------------------------------------------

    @property
    def filters(self) -> List[re.Pattern]:
        """Lazily load file filters."""
        if self._filters is None:
            self._filters = load_filters(self._config_path)
        return self._filters

    @filters.setter
    def filters(self, value: List[re.Pattern]) -> None:
        self._filters = value

    def _should_include_file(self, filename: str) -> bool:
        """
        Check if a file should be included based on filter patterns.

        Args:
            filename: File path to check.

        Returns:
            True if file should be included, False if filtered out.
        """
        if not self.filters:
            return True
        return not any(regex.search(filename) for regex in self.filters)

    # -------------------------------------------------------------------------
    # Abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_pr_info(self) -> Dict:
        """
        Fetch PR/MR information.

        Returns:
            Dictionary with keys: head_sha, head_ref, title,
            body/description, base_ref, and platform-specific fields.
        """
        ...

    @abstractmethod
    def get_diff(self, file_path: Optional[str] = None) -> str:
        """
        Fetch the unified diff for the PR/MR.

        Args:
            file_path: Optional file path to get diff for a specific file.

        Returns:
            Unified diff as string.
        """
        ...

    @abstractmethod
    def get_existing_comments(self) -> List[str]:
        """
        Get existing review comments as "file:line" strings.

        Returns:
            List of "file:line" strings for existing comments.
        """
        ...

    @abstractmethod
    def post_inline_comment(
        self, comment: ReviewComment, signoff: str = "Claude Code docs review"
    ) -> Tuple[bool, str]:
        """
        Post an inline comment on a specific line.

        Args:
            comment: ReviewComment to post.
            signoff: Sign-off text appended to the comment.

        Returns:
            Tuple of (success, error_message).
        """
        ...

    @abstractmethod
    def post_pr_comment(self, file: str, line: int, body: str) -> Tuple[bool, str]:
        """
        Post a general PR/MR comment (not inline).

        Args:
            file: File path for context.
            line: Line number for context.
            body: Comment body.

        Returns:
            Tuple of (success, error_message).
        """
        ...

    @abstractmethod
    def get_changed_files(self) -> List[Dict]:
        """
        Get list of changed files in the PR/MR.

        Returns:
            List of dicts with 'path', 'status', 'additions', 'deletions'.
        """
        ...

    @abstractmethod
    def get_review_comments(self, include_resolved: bool = False) -> List[Dict]:
        """
        Get review comments/discussions on the PR/MR.

        Args:
            include_resolved: If True, include resolved comments.

        Returns:
            List of comment dicts with 'id', 'path', 'line', 'body',
            'author', 'resolved'.
        """
        ...

    @abstractmethod
    def get_pr_data(self, apply_filters: bool = True) -> Dict:
        """
        Convenience method to fetch PR/MR data with diffs and file filtering.

        Args:
            apply_filters: Whether to apply YAML-based file filtering.

        Returns:
            Dictionary with: git_type, url, title, description, diffs, stats.
        """
        ...

    @abstractmethod
    def get_metadata(self) -> Dict:
        """
        Get combined PR/MR metadata in a normalized schema.

        Returns:
            Dictionary with: platform, pr_number, title, description, state,
            author, base_branch, head_branch, labels, commits, changed_files, url.
        """
        ...

    # -------------------------------------------------------------------------
    # Shared concrete methods
    # -------------------------------------------------------------------------

    def extract_line_numbers(self, file_path: str) -> List[DiffLine]:
        """
        Extract line numbers for added/modified lines from the diff.

        Args:
            file_path: Path to file in the PR/MR.

        Returns:
            List of DiffLine objects with file line numbers and content.
        """
        diff = self.get_diff()
        return self._parse_diff_for_file(diff, file_path)

    def _parse_diff_for_file(self, diff: str, target_file: str) -> List[DiffLine]:
        """
        Parse unified diff to extract added lines with their file line numbers.

        Args:
            diff: Unified diff content.
            target_file: File path to extract lines for.

        Returns:
            List of DiffLine objects.
        """
        lines = diff.split("\n")
        result: List[DiffLine] = []
        in_file = False
        file_line = 0

        for line in lines:
            if line.startswith("diff --git"):
                in_file = f"b/{target_file}" in line
                continue

            if (
                line.startswith("---")
                or line.startswith("+++")
                or line.startswith("index")
                or line.startswith("new file")
                or line.startswith("deleted file")
            ):
                continue

            if line.startswith("@@") and in_file:
                match = re.search(r"\+(\d+)", line)
                if match:
                    file_line = int(match.group(1)) - 1
                continue

            if in_file:
                if line.startswith("-"):
                    continue
                elif line.startswith("+"):
                    file_line += 1
                    content = line[1:]
                    result.append(
                        DiffLine(
                            file_line=file_line,
                            content=content,
                            is_added=True,
                        )
                    )
                elif line.startswith(" ") or line == "":
                    file_line += 1

        return result

    def find_line_for_pattern(self, file_path: str, pattern: str) -> Optional[int]:
        """
        Find the line number for a pattern in a file's diff.

        Args:
            file_path: Path to file in the PR/MR.
            pattern: Pattern to search for.

        Returns:
            Line number if found, None otherwise.
        """
        diff_lines = self.extract_line_numbers(file_path)
        for diff_line in diff_lines:
            if pattern in diff_line.content:
                return diff_line.file_line
        return None

    def validate_comments(self, comments: List[Dict]) -> List[Dict]:
        """
        Validate comments against the actual diff.

        Args:
            comments: List of comment dictionaries.

        Returns:
            List of validation results with 'valid' and 'content' fields.
        """
        results: List[Dict] = []
        diff = self.get_diff()

        # Find all files in diff
        all_files: set = set()
        for line in diff.split("\n"):
            if line.startswith("diff --git"):
                match = re.search(r"b/(.+)$", line)
                if match:
                    all_files.add(match.group(1))

        for comment in comments:
            file_path = comment.get("file", "")
            line_num = int(comment.get("line", 0))
            diff_lines = self.extract_line_numbers(file_path)
            line_lookup = {dl.file_line: dl.content for dl in diff_lines}

            if line_num in line_lookup:
                results.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "valid": True,
                        "content": line_lookup[line_num][:60],
                    }
                )
            else:
                results.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "valid": False,
                        "content": None,
                        "reason": "Line not in diff (may be context-only)",
                    }
                )

        return results

    def post_comments(
        self, comments: List[Dict], dry_run: bool = False, signoff: str = "Claude Code docs review"
    ) -> PostResult:
        """
        Post multiple review comments.

        Args:
            comments: List of comment dictionaries.
            dry_run: If True, do not actually post comments.
            signoff: Sign-off text appended to each comment.

        Returns:
            PostResult with counts and errors.
        """
        result = PostResult()

        try:
            self.get_pr_info()
            existing = self.get_existing_comments()
        except Exception as e:
            result.failed = len(comments)
            result.errors.append(f"Failed to get PR info: {str(e)}")
            return result

        print("\nPosting comments...")

        for comment_dict in comments:
            comment = ReviewComment.from_dict(comment_dict)
            key = f"{comment.file}:{comment.line}"

            if key in existing:
                color_print("Skip", f"{key} (comment exists)")
                result.skipped += 1
                continue

            if dry_run:
                color_print("Would post", key)
                result.posted += 1
                continue

            body = f"{comment.message}\n\n\U0001f916 {signoff}"

            success, error = self.post_inline_comment(comment, signoff=signoff)

            if success:
                color_print("Posted", key)
                result.posted += 1
            else:
                color_print("Warning", f"Could not post inline at {key}")
                print(f"    Reason: {error}")
                print("    Fallback: Posting as PR comment...")

                success, error = self.post_pr_comment(comment.file, comment.line, body)
                if success:
                    color_print("Posted", f"{key} (as PR comment)")
                    result.posted += 1
                else:
                    color_print("Failed", key)
                    result.failed += 1
                    result.errors.append(f"{key}: {error}")

            time.sleep(0.3)

        print(f"\nPosted: {result.posted}, Skipped: {result.skipped}, Failed: {result.failed}")
        return result


# =============================================================================
# GitHub implementation
# =============================================================================


class GitHubReviewAPI(GitReviewAPI):
    """GitHub-specific implementation using PyGithub."""

    def __init__(self, url: str, config_path: Optional[str] = None):
        """
        Initialize GitHub API with PR URL.

        Args:
            url: GitHub PR URL.
            config_path: Optional path to git_filters.yaml.

        Raises:
            ImportError: If PyGithub is not installed.
            RuntimeError: If GITHUB_TOKEN is not set.
        """
        super().__init__(url, config_path=config_path)
        if Github is None or Auth is None:
            raise ImportError("PyGithub not installed. Run: python3 -m pip install PyGithub")
        self._parse_url()
        self._init_client()

    def _parse_url(self) -> None:
        """Parse GitHub PR URL to extract owner, repo, and PR number."""
        parsed = urlparse(self.url)
        parts = parsed.path.strip("/").split("/")

        if len(parts) < 4 or parts[2] != "pull":
            raise ValueError(f"Invalid GitHub PR URL format: {self.url}")

        self.owner = parts[0]
        self.repo_name = parts[1]
        self.pr_number = int(parts[3])
        self.owner_repo = f"{self.owner}/{self.repo_name}"

    def _init_client(self) -> None:
        """Initialize PyGithub client and fetch repo/PR objects."""
        load_env_file()
        self.token = os.environ.get("GITHUB_TOKEN")

        if self.token:
            self._github = Github(auth=Auth.Token(self.token))  # type: ignore[union-attr]
        else:
            self._github = Github()  # type: ignore[misc]

        self._repo = self._github.get_repo(self.owner_repo)
        self._pr = self._repo.get_pull(self.pr_number)

    # -- Abstract method implementations -------------------------------------

    def get_pr_info(self) -> Dict:
        """Fetch PR information including base and head SHAs."""
        if self._pr_info:
            return self._pr_info

        self._pr_info = {
            "head_sha": self._pr.head.sha,
            "head_ref": self._pr.head.ref,
            "base_sha": self._pr.base.sha,
            "title": self._pr.title,
            "body": self._pr.body or "",
            "base_ref": self._pr.base.ref,
        }
        return self._pr_info

    def get_diff(
        self,
        file_path: Optional[str] = None,
        ignore_patterns: Optional[List[re.Pattern]] = None,
        max_files: int = 1000,
    ) -> str:
        """
        Fetch the unified diff for the PR.

        Tier 1: Uses the raw GitHub API bulk diff endpoint.
        Tier 2: On HTTP 406 (PR too large), falls back to blobless git clone
        with Python regex filtering and targeted diffs.
        """
        cache_key = file_path or "_all_"
        if cache_key in self._diff_cache:
            return self._diff_cache[cache_key]

        try:
            diff = self._fetch_bulk_diff(file_path)
        except urllib.error.HTTPError as e:
            if e.code != 406:
                raise
            if not self.token:
                raise RuntimeError(
                    f"PR diff too large for GitHub API ({self._pr.changed_files} files) "
                    "and no GITHUB_TOKEN set for git clone fallback."
                ) from e
            print(
                f"Diff too large for GitHub API ({self._pr.changed_files} files), "
                "falling back to local git clone...",
                file=sys.stderr,
            )
            pr_info = self.get_pr_info()
            diff = self._blobless_clone_diff(
                pr_info["base_sha"],
                pr_info["head_sha"],
                ignore_patterns or DEFAULT_IGNORE_PATTERNS,
                max_files,
            )

        self._diff_cache[cache_key] = diff
        return diff

    def _fetch_bulk_diff(self, _file_path: Optional[str] = None) -> str:
        """Tier 1: Fetch full diff via GitHub's bulk diff API endpoint."""
        url = f"https://api.github.com/repos/{self.owner_repo}/pulls/{self.pr_number}"
        headers = {
            "Accept": "application/vnd.github.diff",
            "User-Agent": "git-pr-reader",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, headers=headers)  # noqa: S310
        with urllib.request.urlopen(req) as response:  # noqa: S310
            return response.read().decode()

    def _blobless_clone_diff(
        self,
        base_sha: str,
        head_sha: str,
        ignore_patterns: List[re.Pattern],
        max_files: int,
    ) -> str:
        """Tier 2: Blobless git clone with filtered targeted diffs."""
        for sha in (base_sha, head_sha):
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError(f"Invalid SHA: {sha}")

        auth_url = f"https://x-access-token:{self.token}@github.com/{self.owner_repo}.git"
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

        with tempfile.TemporaryDirectory(prefix="git-pr-reader-") as tmpdir:
            self._git_run(
                ["git", "clone", "--bare", "--filter=blob:none", auth_url, tmpdir],
                env=env,
            )

            self._git_run(
                ["git", "-C", tmpdir, "fetch", "origin", head_sha],
                env=env,
            )

            result = self._git_run(
                ["git", "-C", tmpdir, "diff", "--name-only", base_sha, head_sha],
                text=True,
            )
            all_files = [f for f in result.stdout.strip().split("\n") if f]
            self._blobless_total_files = len(all_files)

            filtered = filter_files(all_files, ignore_patterns)[:max_files]
            self._blobless_filtered_files = len(filtered)

            if not filtered:
                return ""

            diff_parts: List[str] = []
            for i in range(0, len(filtered), 50):
                batch = filtered[i : i + 50]
                diff_cmd = [
                    "git",
                    "-C",
                    tmpdir,
                    "diff",
                    base_sha,
                    head_sha,
                    "--",
                ] + batch
                result = self._git_run(diff_cmd, text=True, env=env)
                diff_parts.append(result.stdout)

            return "".join(diff_parts)

    @staticmethod
    def _git_run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run a git command, capturing output and redacting tokens from errors."""
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("check", True)
        try:
            return subprocess.run(cmd, **kwargs)  # noqa: S603
        except subprocess.CalledProcessError as e:
            safe_cmd = [_redact_token(arg) for arg in cmd]
            raise subprocess.CalledProcessError(
                e.returncode, safe_cmd, e.stdout, e.stderr
            ) from None

    def get_changed_files(self) -> List[Dict]:
        """Get list of changed files in the PR using PyGithub."""
        files: List[Dict] = []
        for f in self._pr.get_files():
            files.append(
                {
                    "path": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "changes": f.changes,
                }
            )
        return files

    def _fetch_resolved_thread_comment_ids(self) -> set:
        """Fetch comment IDs that belong to resolved review threads via GraphQL."""
        if not self.token:
            return set()

        query = """
        query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $pr) {
              reviewThreads(first: 100, after: $cursor) {
                pageInfo { hasNextPage, endCursor }
                nodes {
                  isResolved
                  comments(first: 1) {
                    nodes { databaseId }
                  }
                }
              }
            }
          }
        }
        """
        resolved_ids: set = set()
        cursor = None

        for _ in range(10):  # max 10 pages (1000 threads)
            variables = {
                "owner": self.owner,
                "repo": self.repo_name,
                "pr": self.pr_number,
                "cursor": cursor,
            }
            payload = json.dumps({"query": query, "variables": variables}).encode()
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "User-Agent": "git-pr-reader",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:  # noqa: S310
                    data = json.loads(resp.read().decode())
            except Exception:
                break

            threads = (
                data.get("data", {})
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads", {})
            )
            for node in threads.get("nodes", []):
                if node.get("isResolved"):
                    for c in node.get("comments", {}).get("nodes", []):
                        if c.get("databaseId"):
                            resolved_ids.add(c["databaseId"])

            page_info = threads.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        return resolved_ids

    def get_review_comments(self, include_resolved: bool = False) -> List[Dict]:
        """
        Get review comments on the PR using PyGithub.

        Filters out bot authors and reply comments. Uses the GitHub GraphQL
        API to determine review thread resolution status.
        """
        bot_patterns = ["bot", "gemini", "mergify", "github-actions", "dependabot"]
        resolved_ids = self._fetch_resolved_thread_comment_ids()
        comments: List[Dict] = []

        for c in self._pr.get_review_comments():
            # Skip replies
            if c.in_reply_to_id:
                continue

            author = c.user.login if c.user else ""
            if any(pat in author.lower() for pat in bot_patterns):
                continue

            is_resolved = c.id in resolved_ids

            if is_resolved and not include_resolved:
                continue

            comments.append(
                {
                    "id": c.id,
                    "path": c.path or "",
                    "line": c.line or c.original_line,
                    "body": c.body or "",
                    "author": author,
                    "resolved": is_resolved,
                    "created_at": c.created_at.isoformat() if c.created_at else "",
                    "url": c.html_url or "",
                }
            )

        return comments

    def get_existing_comments(self) -> List[str]:
        """Get existing review comments as file:line strings using PyGithub."""
        existing: List[str] = []
        for c in self._pr.get_review_comments():
            path = c.path or ""
            line = c.line or c.original_line
            if path and line:
                existing.append(f"{path}:{line}")
        return existing

    def post_inline_comment(
        self, comment: ReviewComment, signoff: str = "Claude Code docs review"
    ) -> Tuple[bool, str]:
        """Post an inline comment on a specific line using PyGithub."""
        try:
            pr_info = self.get_pr_info()
            body = f"{comment.message}\n\n\U0001f916 {signoff}"
            commit = self._repo.get_commit(pr_info["head_sha"])
            self._pr.create_review_comment(
                body=body,
                commit=commit,
                path=comment.file,
                line=comment.line,
            )
            return True, ""
        except Exception as e:
            return False, str(e)

    def post_pr_comment(self, file: str, line: int, body: str) -> Tuple[bool, str]:
        """Post a general PR comment (not inline) using PyGithub."""
        try:
            note_body = f"**{file}:{line}**\n\n{body}"
            self._pr.as_issue().create_comment(note_body)
            return True, ""
        except Exception as e:
            return False, str(e)

    def get_pr_data(self, apply_filters: bool = True) -> Dict:
        """
        Fetch PR data with diffs and optional file filtering.

        Uses PyGithub's pr.get_files() for file listing and patches.

        Args:
            apply_filters: Whether to apply YAML-based file filtering.

        Returns:
            Dictionary with git_type, url, title, description, diffs, stats.
        """
        original_filters = self._filters
        if not apply_filters:
            self._filters = []

        try:
            title = self._pr.title
            description = self._pr.body or ""

            diffs: List[Dict] = []
            total_files = 0
            filtered_count = 0
            max_files = 3000

            for f in self._pr.get_files():
                total_files += 1
                if total_files > max_files:
                    print(
                        f"Warning: capped file iteration at {max_files} "
                        f"(PR has more files). Use 'diff --save-diff' for "
                        f"large PRs.",
                        file=sys.stderr,
                    )
                    break
                filename = f.filename

                if not self._should_include_file(filename):
                    filtered_count += 1
                    continue

                if f.patch:
                    diffs.append(
                        {
                            "filename": filename,
                            "diff": f.patch,
                        }
                    )

            return {
                "git_type": "github",
                "url": self.url,
                "title": title,
                "description": description,
                "diffs": diffs,
                "stats": {
                    "total_files": total_files,
                    "filtered_files": filtered_count,
                    "included_files": len(diffs),
                    "truncated": total_files > max_files,
                },
            }
        except Exception as e:
            return {"error": f"Failed to fetch PR from {self.url}: {str(e)}", "url": self.url}
        finally:
            self._filters = original_filters

    def get_metadata(self) -> Dict:
        """Get combined PR metadata in a normalized schema."""
        info = self.get_pr_info()
        files = self.get_changed_files()

        author = self._pr.user.login if self._pr.user else ""
        labels = [label.name for label in self._pr.labels]

        commits = []
        for c in self._pr.get_commits():
            commits.append(
                {
                    "sha": c.sha[:12],
                    "message": c.commit.message.split("\n")[0],
                    "author": c.author.login
                    if c.author
                    else (c.commit.author.name if c.commit.author else ""),
                }
            )

        if self._pr.merged:
            state = "merged"
        elif self._pr.draft:
            state = "draft"
        else:
            state = self._pr.state.lower()

        status_map = {
            "removed": "deleted",
            "copied": "added",
            "changed": "modified",
            "unchanged": "modified",
        }
        for f in files:
            f["status"] = status_map.get(f["status"], f["status"])

        return {
            "platform": "github",
            "pr_number": self.pr_number,
            "title": info["title"],
            "description": info.get("body", ""),
            "state": state,
            "author": author,
            "base_branch": info["base_ref"],
            "head_branch": info["head_ref"],
            "labels": labels,
            "commits": commits,
            "changed_files": files,
            "url": self.url,
        }


# =============================================================================
# GitLab implementation
# =============================================================================


class GitLabReviewAPI(GitReviewAPI):
    """GitLab-specific implementation using python-gitlab."""

    def __init__(self, url: str, config_path: Optional[str] = None):
        """
        Initialize GitLab API with MR URL.

        Args:
            url: GitLab MR URL.
            config_path: Optional path to git_filters.yaml.

        Raises:
            ImportError: If python-gitlab is not installed.
            RuntimeError: If GITLAB_TOKEN is not set.
        """
        super().__init__(url, config_path=config_path)
        if Gitlab is None:
            raise ImportError(
                "python-gitlab not installed. Run: python3 -m pip install python-gitlab"
            )
        self._parse_url()
        self._init_client()

    def _parse_url(self) -> None:
        """Parse GitLab MR URL to extract host, project, and MR ID."""
        parsed = urlparse(self.url)
        self.host = parsed.netloc
        self.base_url = f"{parsed.scheme}://{self.host}"
        path = parsed.path.strip("/")

        if "/-/merge_requests/" in path:
            parts = path.split("/-/merge_requests/")
            self.project_path = parts[0]
            self.mr_id = int(parts[1].split("/")[0].split("?")[0])
        else:
            raise ValueError(f"Invalid GitLab MR URL format: {self.url}")

    def _init_client(self) -> None:
        """Initialize python-gitlab client and fetch project/MR objects."""
        load_env_file()
        self.token = os.environ.get("GITLAB_TOKEN")

        if self.token:
            self._gl = Gitlab(url=self.base_url, private_token=self.token, ssl_verify=True)  # type: ignore[misc]
        else:
            self._gl = Gitlab(url=self.base_url, ssl_verify=True)  # type: ignore[misc]

        self._project = self._gl.projects.get(self.project_path)
        self._mr = self._project.mergerequests.get(self.mr_id)

    # -- Abstract method implementations -------------------------------------

    def get_pr_info(self) -> Dict:
        """Fetch MR information including version SHAs."""
        if self._pr_info:
            return self._pr_info

        # Get version info for SHAs via the MR versions API
        try:
            import urllib.request as _ur

            ver_url = (
                f"{self.base_url}/api/v4/projects/"
                f"{self.project_path.replace('/', '%2F')}"
                f"/merge_requests/{self.mr_id}/versions"
            )
            headers = {"User-Agent": "git-pr-reader"}
            if self.token:
                headers["PRIVATE-TOKEN"] = self.token
            req = _ur.Request(ver_url, headers=headers)  # noqa: S310
            with _ur.urlopen(req) as resp:  # noqa: S310
                ver_data = json.loads(resp.read().decode())
            if ver_data and isinstance(ver_data, list):
                self._pr_info = {
                    "head_sha": ver_data[0].get("head_commit_sha", ""),
                    "head_ref": self._mr.source_branch,
                    "base_sha": ver_data[0].get("base_commit_sha", ""),
                    "start_sha": ver_data[0].get("start_commit_sha", ""),
                    "title": self._mr.title,
                    "body": self._mr.description or "",
                    "base_ref": self._mr.target_branch,
                }
                return self._pr_info
        except Exception:  # noqa: S110
            pass

        # Fallback: use MR attributes directly
        self._pr_info = {
            "head_sha": getattr(self._mr, "sha", ""),
            "head_ref": self._mr.source_branch,
            "base_sha": "",
            "start_sha": "",
            "title": self._mr.title,
            "body": self._mr.description or "",
            "base_ref": self._mr.target_branch,
        }
        return self._pr_info

    def get_diff(self, file_path: Optional[str] = None) -> str:
        """Fetch the unified diff for the MR using python-gitlab."""
        cache_key = file_path or "_all_"
        if cache_key in self._diff_cache:
            return self._diff_cache[cache_key]

        changes_data = self._mr.changes()
        file_changes = changes_data["changes"]  # type: ignore[index]

        diff_parts: List[str] = []
        for change in file_changes:
            old_path = change.get("old_path", "")
            new_path = change.get("new_path", "")
            diff_content = change.get("diff", "")
            diff_parts.append(f"diff --git a/{old_path} b/{new_path}")
            diff_parts.append(diff_content)

        diff = "\n".join(diff_parts)
        self._diff_cache[cache_key] = diff
        return diff

    def get_changed_files(self) -> List[Dict]:
        """Get list of changed files in the MR using python-gitlab."""
        changes_resp = self._mr.changes()
        file_changes = changes_resp["changes"]  # type: ignore[index]
        files: List[Dict] = []

        for c in file_changes:
            diff_text = c.get("diff", "")
            additions = diff_text.count("\n+") - diff_text.count("\n+++")
            deletions = diff_text.count("\n-") - diff_text.count("\n---")

            if c.get("new_file"):
                status = "added"
            elif c.get("deleted_file"):
                status = "deleted"
            else:
                status = "modified"

            files.append(
                {
                    "path": c.get("new_path", c.get("old_path", "")),
                    "status": status,
                    "additions": max(0, additions),
                    "deletions": max(0, deletions),
                    "changes": max(0, additions) + max(0, deletions),
                }
            )

        return files

    def get_review_comments(self, include_resolved: bool = False) -> List[Dict]:
        """Get review comments/discussions on the MR using python-gitlab."""
        bot_patterns = ["bot", "gemini", "mergify", "gitlab-actions"]
        comments: List[Dict] = []

        for discussion in self._mr.discussions.list(get_all=True):
            notes = discussion.attributes.get("notes", [])
            if not notes:
                continue

            note = notes[0]

            if note.get("system"):
                continue

            resolvable = note.get("resolvable", False)
            resolved = note.get("resolved", False)

            if resolvable and resolved and not include_resolved:
                continue

            author = note.get("author", {}).get("username", "")
            if any(pat in author.lower() for pat in bot_patterns):
                continue

            position = note.get("position")
            path = ""
            line = None
            if position:
                path = position.get("new_path", "")
                line = position.get("new_line")

            comments.append(
                {
                    "id": note.get("id"),
                    "discussion_id": discussion.id,
                    "path": path,
                    "line": line,
                    "body": note.get("body", ""),
                    "author": author,
                    "resolved": resolved,
                    "resolvable": resolvable,
                    "created_at": note.get("created_at", ""),
                    "url": note.get("web_url", ""),
                }
            )

        return comments

    def get_existing_comments(self) -> List[str]:
        """Get existing discussion comments as file:line strings."""
        existing: List[str] = []
        for discussion in self._mr.discussions.list(get_all=True):
            notes = discussion.attributes.get("notes", [])
            if notes:
                note = notes[0]
                position = note.get("position")
                if position and position.get("new_line"):
                    path = position.get("new_path", "")
                    line = position.get("new_line")
                    if path and line:
                        existing.append(f"{path}:{line}")
        return existing

    def post_inline_comment(
        self, comment: ReviewComment, signoff: str = "Claude Code docs review"
    ) -> Tuple[bool, str]:
        """Post an inline comment on a specific line using python-gitlab."""
        try:
            pr_info = self.get_pr_info()
            body = f"{comment.message}\n\n\U0001f916 {signoff}"

            position = {
                "base_sha": pr_info.get("base_sha", ""),
                "head_sha": pr_info.get("head_sha", ""),
                "start_sha": pr_info.get("start_sha", ""),
                "old_path": comment.file,
                "new_path": comment.file,
                "new_line": comment.line,
                "position_type": "text",
            }

            self._mr.discussions.create({"body": body, "position": position})
            return True, ""
        except Exception as e:
            return False, str(e)

    def post_pr_comment(self, file: str, line: int, body: str) -> Tuple[bool, str]:
        """Post a general MR note (not inline) using python-gitlab."""
        try:
            note_body = f"**{file}:{line}**\n\n{body}"
            self._mr.notes.create({"body": note_body})
            return True, ""
        except Exception as e:
            return False, str(e)

    def get_pr_data(self, apply_filters: bool = True) -> Dict:
        """
        Fetch MR data with diffs and optional file filtering.

        Uses python-gitlab's mr.changes() for file listing and diffs.

        Args:
            apply_filters: Whether to apply YAML-based file filtering.

        Returns:
            Dictionary with git_type, url, title, description, diffs, stats.
        """
        original_filters = self._filters
        if not apply_filters:
            self._filters = []

        try:
            title = self._mr.title
            description = self._mr.description or ""

            changes = self._mr.changes()
            file_diffs = changes["changes"]  # type: ignore[index]

            diffs: List[Dict] = []
            total_files = len(file_diffs)
            filtered_count = 0

            for file_data in file_diffs:
                filename = file_data.get("new_path", "")

                if not self._should_include_file(filename):
                    filtered_count += 1
                    continue

                diffs.append(
                    {
                        "filename": filename,
                        "diff": file_data.get("diff", ""),
                    }
                )

            return {
                "git_type": "gitlab",
                "url": self.url,
                "title": title,
                "description": description,
                "diffs": diffs,
                "stats": {
                    "total_files": total_files,
                    "filtered_files": filtered_count,
                    "included_files": len(diffs),
                },
            }
        except Exception as e:
            return {"error": f"Failed to fetch MR from {self.url}: {str(e)}", "url": self.url}
        finally:
            self._filters = original_filters

    def get_metadata(self) -> Dict:
        """Get combined MR metadata in a normalized schema."""
        info = self.get_pr_info()
        files = self.get_changed_files()

        author_obj = getattr(self._mr, "author", {}) or {}
        author = author_obj.get("username", author_obj.get("name", ""))

        labels = list(getattr(self._mr, "labels", []) or [])

        commits = []
        try:
            for c in self._mr.commits():
                commits.append(
                    {
                        "sha": c.id[:12],
                        "message": c.message.split("\n")[0],
                        "author": c.author_name or "",
                    }
                )
        except Exception:  # noqa: BLE001, S110
            pass

        state = getattr(self._mr, "state", "").lower()
        if state == "opened":
            state = "open"

        return {
            "platform": "gitlab",
            "pr_number": self.mr_id,
            "title": info["title"],
            "description": info.get("body", ""),
            "state": state,
            "author": author,
            "base_branch": info["base_ref"],
            "head_branch": info["head_ref"],
            "labels": labels,
            "commits": commits,
            "changed_files": files,
            "url": self.url,
        }


# =============================================================================
# Helpers
# =============================================================================


def format_markdown(data: Dict) -> str:
    """
    Format PR/MR data as Markdown.

    Args:
        data: PR/MR data dictionary from get_pr_data().

    Returns:
        Markdown formatted string.
    """
    if "error" in data:
        return f"# Error\n\n{data['error']}"

    output: List[str] = []

    output.append(f"# {data['title']}\n")
    output.append(f"**Source:** {data['url']}")
    git_type_label = (
        "GitHub Pull Request" if data["git_type"] == "github" else "GitLab Merge Request"
    )
    output.append(f"**Type:** {git_type_label}\n")

    if data.get("description"):
        output.append("## Description\n")
        output.append(data["description"])
        output.append("")

    stats = data.get("stats", {})
    total = stats.get("total_files", 0)
    included = stats.get("included_files", 0)
    output.append(f"## Changed Files ({included} of {total} total)\n")

    for diff_data in data.get("diffs", []):
        output.append(f"### {diff_data['filename']}")
        output.append("```diff")
        output.append(diff_data["diff"])
        output.append("```\n")

    return "\n".join(output)


def load_comments_file(file_path: str) -> List[Dict]:
    """
    Load and validate a comments JSON file.

    Args:
        file_path: Path to JSON file containing comments.

    Returns:
        List of comment dictionaries.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If JSON is invalid or not a list.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Comments file not found: {file_path}")

    with open(file_path) as f:
        try:
            comments = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in comments file: {e}") from e

    if not isinstance(comments, list):
        raise ValueError("Comments file must contain a JSON array")

    return comments


# =============================================================================
# CLI subcommand handlers
# =============================================================================


def cmd_read(args) -> int:
    """Handle 'read' subcommand -- the original get_pr_data mode."""
    try:
        api = GitReviewAPI.from_url(args.url, config_path=args.config)
        result = api.get_pr_data(apply_filters=not args.no_filter)

        if args.format == "markdown":
            print(format_markdown(result))
        else:
            print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"Unexpected error: {str(e)}"}))
        return 1

    return 0


def cmd_info(args) -> int:
    """Handle 'info' subcommand -- get PR/MR info."""
    try:
        api = GitReviewAPI.from_url(args.pr_url)
    except (ValueError, RuntimeError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        info = api.get_pr_info()
        if args.field:
            value = info.get(args.field)
            if value is None:
                print(
                    f"Error: unknown field '{args.field}'. Available: {', '.join(info.keys())}",
                    file=sys.stderr,
                )
                return 1
            print(value)
        elif args.json:
            print(json.dumps(info, indent=2))
        else:
            print(f"Title: {info.get('title', 'N/A')}")
            print(f"Base: {info.get('base_ref', 'N/A')}")
            print(f"Head: {info.get('head_ref', 'N/A')}")
            print(f"Head SHA: {info.get('head_sha', 'N/A')}")
            body = info.get("body", "")
            if body:
                print(f"\nDescription:\n{body[:500]}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_files(args) -> int:
    """Handle 'files' subcommand -- list changed files."""
    try:
        api = GitReviewAPI.from_url(args.pr_url)
    except (ValueError, RuntimeError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    max_files = getattr(args, "max_files", None)

    try:
        files = api.get_changed_files()

        total_count = len(files)
        if max_files and len(files) > max_files:
            files = files[:max_files]

        if args.filter:
            import fnmatch

            files = [f for f in files if fnmatch.fnmatch(f["path"], args.filter)]

        if args.json:
            print(json.dumps(files, indent=2))
        else:
            if max_files and total_count > max_files:
                print(f"Changed files: {len(files)} (capped from {total_count})")
            else:
                print(f"Changed files: {len(files)}")
            print()
            for f in files:
                status_char = {"added": "A", "modified": "M", "deleted": "D"}.get(f["status"], "?")
                print(f"  {status_char} {f['path']} (+{f['additions']}/-{f['deletions']})")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_comments(args) -> int:
    """Handle 'comments' subcommand -- list review comments."""
    try:
        api = GitReviewAPI.from_url(args.pr_url)
    except (ValueError, RuntimeError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        comments = api.get_review_comments(include_resolved=args.include_resolved)

        if args.json:
            print(json.dumps(comments, indent=2))
        else:
            if not comments:
                print("No unresolved review comments found.")
                return 0

            print(f"Review comments: {len(comments)}")
            print()
            for c in comments:
                location = f"{c['path']}:{c['line']}" if c["path"] and c["line"] else "(general)"
                resolved_marker = " [RESOLVED]" if c.get("resolved") else ""
                print(f"  @{c['author']} on {location}{resolved_marker}")
                body = c["body"][:200] + "..." if len(c["body"]) > 200 else c["body"]
                for line in body.split("\n")[:3]:
                    print(f"    > {line}")
                print()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def _parse_diff_file_stats(diff_text: str) -> List[Dict]:
    """Parse unified diff text to extract per-file addition/deletion counts."""
    files: List[Dict] = []
    current_path: Optional[str] = None
    additions = 0
    deletions = 0

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            if current_path is not None:
                files.append({"path": current_path, "additions": additions, "deletions": deletions})
            match = re.search(r"b/(.+)$", line)
            current_path = match.group(1) if match else "unknown"
            additions = 0
            deletions = 0
        elif current_path is not None:
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1

    if current_path is not None:
        files.append({"path": current_path, "additions": additions, "deletions": deletions})

    return files


def cmd_diff(args) -> int:
    """Handle 'diff' subcommand -- get PR/MR diff."""
    try:
        api = GitReviewAPI.from_url(args.pr_url)
    except (ValueError, RuntimeError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    ignore_patterns = DEFAULT_IGNORE_PATTERNS
    if getattr(args, "ignore_config", None):
        try:
            ignore_patterns = load_ignore_config(args.ignore_config)
        except Exception as e:
            print(f"Error loading ignore config: {e}", file=sys.stderr)
            return 1

    max_files = getattr(args, "max_files", 1000) or 1000

    try:
        if isinstance(api, GitHubReviewAPI):
            diff = api.get_diff(ignore_patterns=ignore_patterns, max_files=max_files)
        else:
            diff = api.get_diff()

        used_blobless = isinstance(api, GitHubReviewAPI) and hasattr(api, "_blobless_total_files")

        if args.save_diff:
            save_path = args.save_diff
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

            manifest: Dict = {
                "diff_saved_to": save_path if diff else None,
                "total_lines": diff.count("\n") + (1 if diff and not diff.endswith("\n") else 0),
                "total_bytes": len(diff.encode("utf-8")),
                "files": _parse_diff_file_stats(diff),
            }

            if used_blobless and isinstance(api, GitHubReviewAPI):
                manifest["diff_mode"] = "blobless_clone"
                manifest["total_files_in_pr"] = api._blobless_total_files
                manifest["files_after_filter"] = api._blobless_filtered_files
                manifest["ignore_patterns_applied"] = True
                if not diff:
                    manifest["reason"] = (
                        "All changed files matched ignore patterns (vendor, test, CI, etc.)"
                    )

            if diff:
                with open(save_path, "w") as f:
                    f.write(diff)

            print(json.dumps(manifest, indent=2))
        else:
            print(diff)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_post(args) -> int:
    """Handle 'post' subcommand -- post review comments."""
    try:
        comments = load_comments_file(args.comments_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if len(comments) == 0:
        print("No comments to post")
        return 0

    print(f"Processing {len(comments)} review comments...")

    try:
        api = GitReviewAPI.from_url(args.pr_url)
    except (ValueError, RuntimeError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    signoff_map = {
        "technical": "Claude Code docs technical review",
        "style": "Claude Code docs style review",
    }
    review_type = getattr(args, "review_type", None) or ""
    signoff = signoff_map.get(review_type, "Claude Code docs review")

    try:
        result = api.post_comments(comments, dry_run=args.dry_run, signoff=signoff)
    except Exception as e:
        print(f"Error posting comments: {e}", file=sys.stderr)
        return 1

    print()
    if args.dry_run:
        print("Dry run completed")
    else:
        print("Review comments completed")

    if result.errors:
        print(f"\nErrors: {json.dumps(result.errors)}")

    return 1 if result.failed > 0 else 0


def cmd_extract(args) -> int:
    """Handle 'extract' subcommand -- extract line numbers from diff."""
    try:
        api = GitReviewAPI.from_url(args.pr_url)
    except (ValueError, RuntimeError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.dump:
        print(f"# Lines added/modified in: {args.file_path}")
        print("# Format: LINE_NUMBER<tab>CONTENT")
        print()

        diff_lines = api.extract_line_numbers(args.file_path)
        for dl in diff_lines:
            print(f"{dl.file_line}\t{dl.content}")
        return 0

    elif args.validate:
        try:
            comments = load_comments_file(args.file_path)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print("Validating comments against PR diff...")
        print()

        results = api.validate_comments(comments)
        errors = 0
        validated = 0

        for result in results:
            file_path = result["file"]
            line = result["line"]

            if result["valid"]:
                content = result.get("content", "")
                print(f"OK: {file_path}:{line} -> {content}")
                validated += 1
            else:
                reason = result.get("reason", "Unknown")
                print(f"WARN: {file_path}:{line} - {reason}")
                errors += 1

        print()
        print("\u2501" * 78)
        print(f"Validated: {validated}, Issues: {errors}")

        return 1 if errors > 0 else 0

    else:
        if not args.pattern:
            print("Error: pattern is required in find mode", file=sys.stderr)
            return 1

        line_num = api.find_line_for_pattern(args.file_path, args.pattern)

        if line_num is None:
            print(
                f"Error: Pattern not found in diff for {args.file_path}: {args.pattern}",
                file=sys.stderr,
            )
            return 1

        print(line_num)
        return 0


def cmd_detect(args) -> int:
    """
    Handle 'detect' subcommand -- auto-detect PR/MR for current git branch.

    GitHub detection uses the `gh` CLI.
    GitLab detection uses urllib.request to query the API directly, since we
    are not yet tied to a specific project/MR object.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        if not branch:
            print("Error: Not on a branch (detached HEAD state)")
            return 1

        result = subprocess.run(
            ["git", "remote", "-v"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        remotes: Dict[str, str] = {}
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2 and "(fetch)" in line:
                remotes[parts[0]] = parts[1]

        if not remotes:
            print("Error: No git remotes found")
            return 1

        load_env_file()

        # Try GitHub first via gh CLI
        for _remote_name, remote_url in remotes.items():
            if "github.com" in remote_url:
                try:
                    result = subprocess.run(
                        ["gh", "pr", "view", "--json", "url", "--jq", ".url"],  # noqa: S607
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    pr_url = result.stdout.strip()
                    if pr_url:
                        if args.json:
                            print(
                                json.dumps(
                                    {
                                        "url": pr_url,
                                        "platform": "github",
                                        "branch": branch,
                                    }
                                )
                            )
                        else:
                            print(pr_url)
                        return 0
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass

        # Try GitLab via urllib.request
        gitlab_token = os.environ.get("GITLAB_TOKEN")
        if not gitlab_token:
            print("Error: GITLAB_TOKEN not set in .env or ~/.env")
            return 1

        for remote_name, remote_url in remotes.items():
            if "gitlab" not in remote_url.lower():
                continue

            host, project_path = _parse_git_remote(remote_url)
            if not host or not project_path:
                continue

            project_encoded = project_path.replace("/", "%2F")
            url = (
                f"https://{host}/api/v4/projects/{project_encoded}"
                f"/merge_requests?source_branch={branch}&state=opened"
            )
            req = urllib.request.Request(  # noqa: S310
                url,
                headers={
                    "PRIVATE-TOKEN": gitlab_token,
                    "User-Agent": "git-pr-reader",
                },
            )

            try:
                with urllib.request.urlopen(req) as response:  # noqa: S310
                    mrs = json.loads(response.read().decode())
                    if mrs and isinstance(mrs, list) and len(mrs) > 0:
                        mr_url = mrs[0].get("web_url", "")
                        if mr_url:
                            if args.json:
                                print(
                                    json.dumps(
                                        {
                                            "url": mr_url,
                                            "platform": "gitlab",
                                            "branch": branch,
                                            "remote": remote_name,
                                        }
                                    )
                                )
                            else:
                                print(mr_url)
                            return 0
            except urllib.error.HTTPError:
                continue

        # Check upstream remote for fork-based MRs
        if "upstream" in remotes and "origin" in remotes:
            remote_url = remotes["upstream"]
            if "gitlab" in remote_url.lower():
                host, project_path = _parse_git_remote(remote_url)
                if host and project_path:
                    project_encoded = project_path.replace("/", "%2F")
                    lookup_url = f"https://{host}/api/v4/projects/{project_encoded}"
                    req = urllib.request.Request(  # noqa: S310
                        lookup_url,
                        headers={
                            "PRIVATE-TOKEN": gitlab_token,
                            "User-Agent": "git-pr-reader",
                        },
                    )

                    try:
                        with urllib.request.urlopen(req) as response:  # noqa: S310
                            project_data = json.loads(response.read().decode())
                            project_id = project_data.get("id")
                            if project_id:
                                mr_api_url = (
                                    f"https://{host}/api/v4/projects/{project_id}"
                                    f"/merge_requests?source_branch={branch}&state=opened"
                                )
                                req2 = urllib.request.Request(  # noqa: S310
                                    mr_api_url,
                                    headers={
                                        "PRIVATE-TOKEN": gitlab_token,
                                        "User-Agent": "git-pr-reader",
                                    },
                                )
                                with urllib.request.urlopen(req2) as resp2:  # noqa: S310
                                    mrs = json.loads(resp2.read().decode())
                                    if mrs and isinstance(mrs, list) and len(mrs) > 0:
                                        mr_url = mrs[0].get("web_url", "")
                                        if mr_url:
                                            if args.json:
                                                print(
                                                    json.dumps(
                                                        {
                                                            "url": mr_url,
                                                            "platform": "gitlab",
                                                            "branch": branch,
                                                            "remote": "upstream",
                                                        }
                                                    )
                                                )
                                            else:
                                                print(mr_url)
                                            return 0
                    except urllib.error.HTTPError:
                        pass

        print(f"Error: No open PR/MR found for branch '{branch}'")
        return 1

    except subprocess.CalledProcessError as e:
        print(f"Error: Git command failed: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


# =============================================================================
# Shared helpers for resolve and clone subcommands
# =============================================================================


def _run_git_cmd(args: List[str], cwd: Optional[str] = None, check: bool = True):
    """Run a git command and return the CompletedProcess."""
    result = subprocess.run(  # noqa: S603
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, ["git"] + args, result.stdout, result.stderr
        )
    return result


def _normalize_git_url(url: str) -> str:
    """Normalize a git URL for comparison (strip .git suffix and trailing slash)."""
    return url.rstrip("/").removesuffix(".git")


def _extract_pr_number(pr_url: Optional[str]) -> Optional[int]:
    """Extract the PR/MR number from a GitHub PR or GitLab MR URL."""
    if not pr_url:
        return None
    m = re.search(r"/pull/(\d+)", pr_url)
    if m:
        return int(m.group(1))
    m = re.search(r"/merge_requests/(\d+)", pr_url)
    if m:
        return int(m.group(1))
    return None


# =============================================================================
# resolve subcommand — PR/MR metadata via PyGithub / python-gitlab
# =============================================================================


def resolve_pr_info(pr_url: str) -> Dict:
    """Resolve PR/MR metadata from a URL using the native API clients.

    Uses PyGithub for GitHub PRs and python-gitlab for GitLab MRs —
    the same clients already used by the rest of git_pr_reader.

    Returns a dict with: repo_url, branch (null if merged), state,
    platform, pr_number, base_ref.
    """
    api = GitReviewAPI.from_url(pr_url)
    info = api.get_pr_info()

    if isinstance(api, GitHubReviewAPI):
        is_merged = api._pr.merged
        state = "MERGED" if is_merged else api._pr.state.upper()
        return {
            "repo_url": f"https://github.com/{api.owner_repo}.git",
            "branch": None if is_merged else info["head_ref"],
            "state": state,
            "platform": "github",
            "pr_number": api.pr_number,
            "base_ref": info["base_ref"],
        }
    elif isinstance(api, GitLabReviewAPI):
        state = api._mr.state
        is_merged = state == "merged"
        return {
            "repo_url": f"{api.base_url}/{api.project_path}.git",
            "branch": None if is_merged else info["head_ref"],
            "state": state,
            "platform": "gitlab",
            "pr_number": api.mr_id,
            "base_ref": info["base_ref"],
        }

    raise ValueError(f"Unsupported platform for URL: {pr_url}")


def cmd_resolve(args) -> int:
    """Handle 'resolve' subcommand — resolve PR/MR metadata via gh/glab CLI."""
    try:
        result = resolve_pr_info(args.pr_url)
    except (ValueError, subprocess.CalledProcessError) as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Repo: {result['repo_url']}")
        print(f"Branch: {result['branch'] or '(merged/deleted)'}")
        print(f"State: {result['state']}")
        print(f"Platform: {result['platform']}")
        if result.get("pr_number"):
            print(f"PR: #{result['pr_number']}")
        print(f"Base: {result['base_ref']}")

    return 0


def cmd_metadata(args) -> int:
    """Handle 'metadata' subcommand — combined PR/MR metadata."""
    try:
        api = GitReviewAPI.from_url(args.pr_url)
    except (ValueError, RuntimeError, ImportError) as e:
        print(json.dumps({"error": str(e)}))
        return 1

    try:
        result = api.get_metadata()

        if args.diff_output:
            diff = api.get_diff()
            os.makedirs(os.path.dirname(args.diff_output) or ".", exist_ok=True)
            with open(args.diff_output, "w") as f:
                f.write(diff)

        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"Failed to fetch metadata: {str(e)}"}))
        return 1

    return 0


# =============================================================================
# clone subcommand — fork-aware git clone with configurable depth
# =============================================================================


def clone_repo(
    repo_url: str,
    output_dir: str,
    depth: int = 1,
    ref: Optional[str] = None,
    pr_url: Optional[str] = None,
    dry_run: bool = False,
) -> Dict:
    """Clone a repository with fork-aware PR ref fallback.

    Args:
        repo_url: Remote git URL to clone.
        output_dir: Target directory for the clone.
        depth: Clone depth (0 = full history, default 1).
        ref: Branch/tag/commit to checkout.
        pr_url: PR/MR URL for fork ref fallback.
        dry_run: If True, return success without cloning.

    Returns:
        Dict with status, path, ref, method.
    """
    if dry_run:
        return {"status": "cloned", "path": output_dir, "ref": ref, "method": "dry_run"}

    depth_args = [] if depth == 0 else ["--depth", str(depth)]

    if ref:
        result = _run_git_cmd(
            ["clone"] + depth_args + ["--branch", ref, repo_url, output_dir],
            check=False,
        )
        if result.returncode == 0:
            return {"status": "cloned", "path": output_dir, "ref": ref, "method": "branch"}

        # Fallback: clone default branch, then try to checkout the ref
        result = _run_git_cmd(
            ["clone"] + depth_args + [repo_url, output_dir],
            check=False,
        )
        if result.returncode != 0:
            return {"status": "error", "message": f"Clone failed: {result.stderr.strip()}"}

        fetch = _run_git_cmd(["fetch", "origin", ref], cwd=output_dir, check=False)
        if fetch.returncode == 0:
            checkout = _run_git_cmd(["checkout", "FETCH_HEAD"], cwd=output_dir, check=False)
            if checkout.returncode == 0:
                return {"status": "cloned", "path": output_dir, "ref": ref, "method": "fetch"}

        # Branch not on origin — try PR ref for fork-based PRs
        pr_number = _extract_pr_number(pr_url)
        if pr_number:
            pr_ref = (
                f"refs/merge-requests/{pr_number}/head"
                if "gitlab" in repo_url
                else f"refs/pull/{pr_number}/head"
            )
            pr_fetch = _run_git_cmd(
                ["fetch", "origin", pr_ref],
                cwd=output_dir,
                check=False,
            )
            if pr_fetch.returncode == 0:
                checkout = _run_git_cmd(
                    ["checkout", "FETCH_HEAD"],
                    cwd=output_dir,
                    check=False,
                )
                if checkout.returncode == 0:
                    print(
                        f"Checked out PR #{pr_number} via {pr_ref}"
                        f" (fork branch '{ref}' not on origin).",
                        file=sys.stderr,
                    )
                    return {"status": "cloned", "path": output_dir, "ref": ref, "method": "pr_ref"}

        print(
            f"WARNING: Cloned {repo_url} but ref '{ref}' not found"
            f" (branch may be in a fork or deleted after merge)."
            f" Using default branch.",
            file=sys.stderr,
        )
        return {"status": "cloned", "path": output_dir, "ref": None, "method": "default"}

    # No ref specified — clone default branch
    result = _run_git_cmd(
        ["clone"] + depth_args + [repo_url, output_dir],
        check=False,
    )
    if result.returncode != 0:
        return {"status": "error", "message": f"Clone failed: {result.stderr.strip()}"}
    return {"status": "cloned", "path": output_dir, "ref": None, "method": "default"}


def verify_clone(
    path: str,
    ref: Optional[str] = None,
    expected_url: Optional[str] = None,
) -> Dict:
    """Verify an existing clone is valid, optionally checking out a ref.

    Returns:
        Dict with status ("valid"/"invalid"), path, current_ref, and optional reason.
    """
    result = _run_git_cmd(["rev-parse", "HEAD"], cwd=path, check=False)
    if result.returncode != 0:
        return {"status": "invalid", "path": path, "reason": "Not a git repository"}

    if expected_url:
        origin = _run_git_cmd(["remote", "get-url", "origin"], cwd=path, check=False)
        if origin.returncode != 0:
            return {"status": "invalid", "path": path, "reason": "No origin remote"}
        if _normalize_git_url(origin.stdout.strip()) != _normalize_git_url(expected_url):
            return {
                "status": "invalid",
                "path": path,
                "reason": f"Origin URL mismatch: expected {expected_url}, "
                f"got {origin.stdout.strip()}",
            }

    current = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path, check=False)
    current_ref = current.stdout.strip() if current.returncode == 0 else None

    if ref and current_ref != ref:
        fetch = _run_git_cmd(["fetch", "origin", ref], cwd=path, check=False)
        if fetch.returncode != 0:
            print(
                f"WARNING: Could not fetch ref '{ref}' in {path} "
                f"(branch may have been deleted after merge). Using clone at HEAD.",
                file=sys.stderr,
            )
        else:
            checkout = _run_git_cmd(["checkout", ref], cwd=path, check=False)
            if checkout.returncode != 0:
                fallback = _run_git_cmd(["checkout", "FETCH_HEAD"], cwd=path, check=False)
                if fallback.returncode != 0:
                    print(
                        f"WARNING: Fetched ref '{ref}' but checkout failed in {path}. "
                        f"Using clone at HEAD.",
                        file=sys.stderr,
                    )
                else:
                    current_ref = ref
            else:
                current_ref = ref

    return {"status": "valid", "path": path, "current_ref": current_ref}


def cmd_clone(args) -> int:
    """Handle 'clone' subcommand — fork-aware git clone or verify existing clone."""
    if args.verify:
        result = verify_clone(
            path=args.verify,
            ref=args.ref,
            expected_url=args.expected_url,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "valid" else 1

    if not args.repo_url:
        print("Error: repo_url is required for clone mode", file=sys.stderr)
        return 1

    if not args.output_dir:
        print("Error: --output-dir is required for clone mode", file=sys.stderr)
        return 1

    result = clone_repo(
        repo_url=args.repo_url,
        output_dir=args.output_dir,
        depth=args.depth,
        ref=args.ref,
        pr_url=args.pr_url,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] != "error" else 1


def _parse_git_remote(remote_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a git remote URL to extract host and project path.

    Supports SSH (git@host:group/project.git) and HTTPS formats.

    Args:
        remote_url: Git remote URL string.

    Returns:
        Tuple of (host, project_path), either may be None on failure.
    """
    host = None
    project_path = None

    if remote_url.startswith("git@"):
        match = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", remote_url)
        if match:
            host = match.group(1)
            project_path = match.group(2)
    elif remote_url.startswith("https://") or remote_url.startswith("http://"):
        parsed = urlparse(remote_url)
        host = parsed.netloc
        project_path = parsed.path.strip("/").removesuffix(".git")

    return host, project_path


# =============================================================================
# CLI entry point
# =============================================================================


def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="Git PR Reader - Unified interface for GitHub PRs and GitLab MRs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read PR/MR data with file filtering (original mode)
  %(prog)s read --url https://github.com/owner/repo/pull/123
  %(prog)s read --url https://github.com/owner/repo/pull/123 --format markdown
  %(prog)s read --url https://github.com/owner/repo/pull/123 --no-filter

  # Get PR/MR info
  %(prog)s info https://github.com/owner/repo/pull/123
  %(prog)s info https://github.com/owner/repo/pull/123 --json

  # List changed files
  %(prog)s files https://github.com/owner/repo/pull/123
  %(prog)s files https://github.com/owner/repo/pull/123 --filter "*.adoc"

  # List review comments
  %(prog)s comments https://github.com/owner/repo/pull/123
  %(prog)s comments https://github.com/owner/repo/pull/123 --include-resolved

  # Get diff
  %(prog)s diff https://github.com/owner/repo/pull/123

  # Post review comments
  %(prog)s post https://github.com/owner/repo/pull/123 comments.json
  %(prog)s post https://github.com/owner/repo/pull/123 comments.json --dry-run

  # Extract line numbers
  %(prog)s extract https://github.com/owner/repo/pull/123 path/to/file.adoc "pattern"
  %(prog)s extract --dump https://github.com/owner/repo/pull/123 path/to/file.adoc
  %(prog)s extract --validate https://github.com/owner/repo/pull/123 comments.json

  # Auto-detect PR/MR for current branch
  %(prog)s detect
  %(prog)s detect --json

  # Resolve PR/MR metadata (branch, state) via gh/glab CLI
  %(prog)s resolve https://github.com/owner/repo/pull/123 --json

  # Clone a repo (fork-aware, configurable depth)
  %(prog)s clone https://github.com/owner/repo.git --output-dir /tmp/repo
  %(prog)s clone https://github.com/owner/repo.git --output-dir /tmp/repo --depth 0
  %(prog)s clone --verify /tmp/repo --ref main
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -- read subcommand (original git_pr_reader mode) -----------------------
    read_parser = subparsers.add_parser(
        "read",
        help="Read PR/MR data with diffs and optional file filtering",
    )
    read_parser.add_argument(
        "--url",
        required=True,
        help="GitHub PR or GitLab MR URL",
    )
    read_parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Disable file filtering (include all files)",
    )
    read_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    read_parser.add_argument(
        "--config",
        help="Path to git_filters.yaml (default: auto-detect)",
    )

    # -- info subcommand -----------------------------------------------------
    info_parser = subparsers.add_parser(
        "info",
        help="Get PR/MR information (title, description, base branch)",
    )
    info_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    info_parser.add_argument("--json", action="store_true", help="Output as JSON")
    info_parser.add_argument(
        "--field",
        metavar="NAME",
        help="Output a single field value (e.g., head_ref, base_ref, title)",
    )

    # -- files subcommand ----------------------------------------------------
    files_parser = subparsers.add_parser(
        "files",
        help="List changed files in the PR/MR",
    )
    files_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    files_parser.add_argument(
        "--filter",
        metavar="PATTERN",
        help='Filter files by glob pattern (e.g., "*.adoc")',
    )
    files_parser.add_argument("--json", action="store_true", help="Output as JSON")
    files_parser.add_argument(
        "--max-files",
        type=int,
        help="Max files to fetch (caps API pagination for large PRs)",
    )

    # -- comments subcommand -------------------------------------------------
    comments_parser = subparsers.add_parser(
        "comments",
        help="List review comments on the PR/MR",
    )
    comments_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    comments_parser.add_argument(
        "--include-resolved",
        action="store_true",
        help="Include resolved comments",
    )
    comments_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # -- diff subcommand -----------------------------------------------------
    diff_parser = subparsers.add_parser(
        "diff",
        help="Get the unified diff for the PR/MR",
    )
    diff_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    diff_parser.add_argument(
        "--save-diff",
        metavar="PATH",
        help="Write full diff to file and return file manifest as JSON",
    )
    diff_parser.add_argument(
        "--ignore-config",
        metavar="PATH",
        help="YAML file with git_ignore_list patterns (overrides defaults)",
    )
    diff_parser.add_argument(
        "--max-files",
        type=int,
        default=1000,
        help="Max files to include in diff after filtering (default: 1000)",
    )

    # -- post subcommand -----------------------------------------------------
    post_parser = subparsers.add_parser(
        "post",
        help="Post review comments to a PR/MR",
    )
    post_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    post_parser.add_argument(
        "comments_file",
        help="Path to JSON file containing comments",
    )
    post_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be posted without actually posting",
    )
    post_parser.add_argument(
        "--review-type",
        choices=["technical", "style"],
        help="Review type for sign-off text (technical or style)",
    )

    # -- extract subcommand --------------------------------------------------
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract line numbers from PR/MR diff",
    )
    extract_parser.add_argument(
        "--dump",
        action="store_true",
        help="Dump all added/modified lines with their file line numbers",
    )
    extract_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate a comments JSON file against the actual diff",
    )
    extract_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    extract_parser.add_argument(
        "file_path",
        help="File path (for find/dump) or comments JSON file (for validate)",
    )
    extract_parser.add_argument(
        "pattern",
        nargs="?",
        help="Pattern to search for (required in find mode)",
    )

    # -- detect subcommand ---------------------------------------------------
    detect_parser = subparsers.add_parser(
        "detect",
        help="Auto-detect PR/MR URL for the current branch",
    )
    detect_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON with platform and branch info",
    )

    # -- resolve subcommand --------------------------------------------------
    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Resolve PR/MR metadata (branch, state, repo URL) via gh/glab CLI",
    )
    resolve_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    resolve_parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Output as JSON (default)",
    )

    # -- metadata subcommand -------------------------------------------------
    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Get combined PR/MR metadata (author, labels, commits, files, state)",
    )
    metadata_parser.add_argument("pr_url", help="GitHub PR or GitLab MR URL")
    metadata_parser.add_argument(
        "--diff-output",
        metavar="PATH",
        help="Also save the unified diff to this file path",
    )

    # -- clone subcommand ----------------------------------------------------
    clone_parser = subparsers.add_parser(
        "clone",
        help="Clone a repo (fork-aware) or verify an existing clone",
    )
    clone_parser.add_argument(
        "repo_url",
        nargs="?",
        help="Remote git URL to clone",
    )
    clone_parser.add_argument(
        "--output-dir",
        help="Target directory for the clone",
    )
    clone_parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Clone depth (0 = full history, default: 1)",
    )
    clone_parser.add_argument(
        "--ref",
        help="Branch, tag, or commit to checkout after cloning",
    )
    clone_parser.add_argument(
        "--pr-url",
        help="PR/MR URL for fork ref fallback (refs/pull/N/head)",
    )
    clone_parser.add_argument(
        "--verify",
        metavar="PATH",
        help="Verify an existing clone instead of cloning",
    )
    clone_parser.add_argument(
        "--expected-url",
        help="Expected origin URL (used with --verify)",
    )
    clone_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Return success without cloning",
    )

    # -- parse and dispatch --------------------------------------------------
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "read": cmd_read,
        "info": cmd_info,
        "files": cmd_files,
        "comments": cmd_comments,
        "diff": cmd_diff,
        "post": cmd_post,
        "extract": cmd_extract,
        "detect": cmd_detect,
        "resolve": cmd_resolve,
        "metadata": cmd_metadata,
        "clone": cmd_clone,
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
