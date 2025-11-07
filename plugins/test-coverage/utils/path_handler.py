#!/usr/bin/env python3
"""
Path Handler Utility for Test Coverage Commands

Handles both local file paths and remote URLs for test coverage analysis.
Supports fetching files from GitHub, GitLab, and other HTTP(S) sources.
"""

import os
import re
import sys
import tempfile
import urllib.request
import urllib.error
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote


class PathHandler:
    """
    Unified handler for local paths and remote URLs.

    Automatically detects input type and handles:
    - Local file paths (absolute or relative)
    - Local directory paths
    - HTTP/HTTPS URLs (direct file downloads)
    - GitHub raw URLs
    - GitHub repository URLs (converts to raw URLs)
    - GitLab raw URLs
    """

    def __init__(self, cache_dir=None):
        """
        Initialize PathHandler.

        Args:
            cache_dir: Directory to cache downloaded files (default: .work/test-coverage/cache/)
        """
        if cache_dir is None:
            cache_dir = os.path.join('.work', 'test-coverage', 'cache')

        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_url(self, path):
        """
        Check if the given path is a URL (HTTP/HTTPS only).

        Args:
            path: String to check

        Returns:
            True if path is an HTTP(S) URL, False otherwise
        """
        if not isinstance(path, str):
            return False

        # Only accept HTTP/HTTPS URLs for security
        url_patterns = [
            r'^https?://',  # HTTP/HTTPS
        ]

        for pattern in url_patterns:
            if re.match(pattern, path, re.IGNORECASE):
                return True

        return False

    def is_github_url(self, url):
        """Check if URL is from GitHub."""
        return 'github.com' in url.lower()

    def is_gitlab_url(self, url):
        """Check if URL is from GitLab."""
        return 'gitlab' in url.lower()

    def convert_to_raw_url(self, url):
        """
        Convert GitHub/GitLab URLs to raw file URLs.

        Args:
            url: GitHub or GitLab URL

        Returns:
            Raw file URL suitable for downloading
        """
        # GitHub blob URL to raw URL
        # https://github.com/owner/repo/blob/branch/path/file.go
        # -> https://raw.githubusercontent.com/owner/repo/branch/path/file.go
        # Don't convert archive URLs or release URLs
        if self.is_github_url(url):
            if '/blob/' in url:
                url = url.replace('github.com', 'raw.githubusercontent.com')
                url = url.replace('/blob/', '/')
            return url

        # GitLab blob URL to raw URL
        # https://gitlab.com/owner/repo/-/blob/branch/path/file.py
        # -> https://gitlab.com/owner/repo/-/raw/branch/path/file.py
        if self.is_gitlab_url(url):
            url = url.replace('/blob/', '/raw/')
            return url

        return url

    def get_cache_path(self, url):
        """
        Generate a cache file path for a URL.

        Args:
            url: URL to cache

        Returns:
            Absolute path to cache file
        """
        # Create a hash of the URL for the cache filename
        url_hash = hashlib.md5(url.encode()).hexdigest()

        # Try to extract a meaningful filename from URL
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')

        # Get the filename from URL path
        filename = path_parts[-1] if path_parts else 'downloaded_file'
        filename = unquote(filename)  # Decode URL-encoded characters

        # If no extension, try to infer from content type later
        if not filename or '.' not in filename:
            filename = f"file_{url_hash[:8]}"
        else:
            # Prepend hash to avoid collisions
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{url_hash[:8]}{ext}"

        return os.path.join(self.cache_dir, filename)

    def download_file(self, url, destination):
        """
        Download a file from URL to destination (HTTP/HTTPS only).

        Args:
            url: HTTP(S) URL to download from
            destination: Local path to save file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate URL scheme for security (only allow HTTP/HTTPS)
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                print(f"Error: Unsupported URL scheme '{parsed.scheme}'. Only HTTP(S) URLs are allowed.", file=sys.stderr)
                return False

            print(f"Downloading from URL: {url}")

            # Add user agent to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; TestCoverageBot/1.0)'
            }

            request = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(request, timeout=30) as response:
                # Check if request was successful
                if response.status != 200:
                    print(f"Error: HTTP {response.status} when downloading {url}", file=sys.stderr)
                    return False

                # Read content
                content = response.read()

                # Write to destination
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                with open(destination, 'wb') as f:
                    f.write(content)

                print(f"Downloaded to: {destination}")
                return True

        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason} when downloading {url}", file=sys.stderr)
            return False
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason} when downloading {url}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error downloading {url}: {e}", file=sys.stderr)
            return False

    def resolve(self, path_or_url, force_download=False):
        """
        Resolve a path or URL to a local file path.

        This is the main entry point for the PathHandler.

        Args:
            path_or_url: Local path or URL to resolve
            force_download: If True, re-download even if cached

        Returns:
            Absolute path to local file/directory, or None if resolution failed
        """
        # Handle None or empty input
        if not path_or_url:
            print("Error: Empty path or URL provided", file=sys.stderr)
            return None

        # If it's a URL, download it
        if self.is_url(path_or_url):
            # Convert to raw URL if needed
            raw_url = self.convert_to_raw_url(path_or_url)

            # Get cache path
            cache_path = self.get_cache_path(raw_url)

            # Download if not cached or force_download is True
            if force_download or not os.path.exists(cache_path):
                if not self.download_file(raw_url, cache_path):
                    return None
            else:
                print(f"Using cached file: {cache_path}")

            return cache_path

        # Otherwise, treat as local path
        else:
            # Expand user home directory (~)
            path_or_url = os.path.expanduser(path_or_url)

            # Convert to absolute path
            abs_path = os.path.abspath(path_or_url)

            # Check if path exists
            if not os.path.exists(abs_path):
                print(f"Error: Path does not exist: {abs_path}", file=sys.stderr)
                return None

            return abs_path

    def resolve_multiple(self, paths_or_urls, force_download=False):
        """
        Resolve multiple paths or URLs to local paths.

        Args:
            paths_or_urls: List of paths or URLs
            force_download: If True, re-download even if cached

        Returns:
            List of resolved local paths (None for failed resolutions)
        """
        return [self.resolve(p, force_download) for p in paths_or_urls]

    def clear_cache(self):
        """
        Clear the download cache directory.

        Returns:
            Number of files deleted
        """
        count = 0
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1

        print(f"Cleared {count} cached files")
        return count


def resolve_path(path_or_url, cache_dir=None, force_download=False):
    """
    Convenience function to resolve a single path or URL.

    Args:
        path_or_url: Local path or URL to resolve
        cache_dir: Directory to cache downloaded files (optional)
        force_download: If True, re-download even if cached

    Returns:
        Absolute path to local file/directory, or None if resolution failed
    """
    handler = PathHandler(cache_dir)
    return handler.resolve(path_or_url, force_download)


def resolve_paths(paths_or_urls, cache_dir=None, force_download=False):
    """
    Convenience function to resolve multiple paths or URLs.

    Args:
        paths_or_urls: List of paths or URLs
        cache_dir: Directory to cache downloaded files (optional)
        force_download: If True, re-download even if cached

    Returns:
        List of resolved local paths (None for failed resolutions)
    """
    handler = PathHandler(cache_dir)
    return handler.resolve_multiple(paths_or_urls, force_download)


if __name__ == '__main__':
    # Command-line interface for testing
    import argparse

    parser = argparse.ArgumentParser(description='Resolve local paths or download URLs')
    parser.add_argument('paths', nargs='+', help='Paths or URLs to resolve')
    parser.add_argument('--cache-dir', help='Cache directory for downloads')
    parser.add_argument('--force', action='store_true', help='Force re-download')
    parser.add_argument('--clear-cache', action='store_true', help='Clear cache and exit')

    args = parser.parse_args()

    handler = PathHandler(args.cache_dir)

    if args.clear_cache:
        handler.clear_cache()
        sys.exit(0)

    for path_or_url in args.paths:
        resolved = handler.resolve(path_or_url, args.force)
        if resolved:
            print(f"✓ Resolved: {path_or_url} -> {resolved}")
        else:
            print(f"✗ Failed: {path_or_url}")
            sys.exit(1)
