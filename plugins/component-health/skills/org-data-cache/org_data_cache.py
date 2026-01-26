#!/usr/bin/env python3
"""
Script to safely manage a local cache of OpenShift org data from GCS.

The cache is stored in ~/.cache/ai-helpers/org_data.json, which is:
- Outside any git repository (safe from accidental commits)
- A standard cache location per XDG Base Directory specification
- Automatically managed with a 7-day freshness policy

The script only outputs cache metadata (path, age, status, size) to stdout.
The actual org data is cached locally and can be read from the cache file.

Usage:
    python3 org_data_cache.py [--force-refresh] [--info]

Examples:
    # Ensure cache is fresh (downloads if stale/missing)
    python3 org_data_cache.py

    # Force refresh regardless of cache age
    python3 org_data_cache.py --force-refresh

    # Show cache info (same as default, but skips download checks)
    python3 org_data_cache.py --info
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "ai-helpers"
CACHE_FILE = CACHE_DIR / "org_data.json"
GCS_BUCKET_PATH = "gs://resolved-org/orgdata/comprehensive_index_dump.json"
CACHE_MAX_AGE_DAYS = 7


def check_git_context():
    """
    Check if we're running inside a git repository.

    This is a safety check to ensure we never accidentally cache
    sensitive org data inside a git repository.

    Raises:
        RuntimeError: If a git repository is detected in current directory
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        if result.returncode == 0:
            print(
                "WARNING: Git repository detected in current directory.",
                file=sys.stderr
            )
            print(
                f"Cache will be safely stored in: {CACHE_FILE}",
                file=sys.stderr
            )
            print(
                "This location is outside any git repository.",
                file=sys.stderr
            )
    except FileNotFoundError:
        # git not installed, that's fine
        pass


def check_gsutil_available():
    """
    Check if gsutil is available in PATH.

    Returns:
        bool: True if gsutil is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["which", "gsutil"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def check_gcloud_authenticated():
    """
    Check if user is authenticated with gcloud.

    Returns:
        bool: True if authenticated, False otherwise
    """
    try:
        result = subprocess.run(
            ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def get_cache_age_days():
    """
    Get the age of the cache file in days.

    Returns:
        float: Age in days, or None if cache doesn't exist
    """
    if not CACHE_FILE.exists():
        return None

    mtime = CACHE_FILE.stat().st_mtime
    age_seconds = datetime.now().timestamp() - mtime
    age_days = age_seconds / (24 * 60 * 60)
    return age_days


def get_cache_size_mb():
    """
    Get the size of the cache file in megabytes.

    Returns:
        float: Size in MB, or None if cache doesn't exist
    """
    if not CACHE_FILE.exists():
        return None

    size_bytes = CACHE_FILE.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return size_mb


def get_cache_mtime():
    """
    Get the last modified time of the cache file.

    Returns:
        str: ISO format timestamp, or None if cache doesn't exist
    """
    if not CACHE_FILE.exists():
        return None

    mtime = CACHE_FILE.stat().st_mtime
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return dt.isoformat()


def download_org_data():
    """
    Download org data from GCS using gsutil.

    Returns:
        dict: The org data as a dictionary

    Raises:
        RuntimeError: If download fails
    """
    print(f"Downloading org data from: {GCS_BUCKET_PATH}", file=sys.stderr)

    # Create cache directory if it doesn't exist
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Download using gsutil
    try:
        result = subprocess.run(
            ["gsutil", "cp", GCS_BUCKET_PATH, str(CACHE_FILE)],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Successfully downloaded to: {CACHE_FILE}", file=sys.stderr)

        # Set secure file permissions (user read/write only, no group/other access)
        # 0o600 = rw------- (owner can read/write, no access for group/others)
        os.chmod(CACHE_FILE, 0o600)
        print(f"Set secure permissions on cache file (600)", file=sys.stderr)

        # Load and return the data
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)

        # Provide helpful error messages
        if "AccessDeniedException" in error_msg or "403" in error_msg:
            raise RuntimeError(
                f"Access denied to {GCS_BUCKET_PATH}\n"
                "Please ensure you have access to the gs://resolved-org bucket.\n"
                "Contact your team lead if you need access."
            )
        elif "NotFoundException" in error_msg or "404" in error_msg:
            raise RuntimeError(
                f"Org data not found at {GCS_BUCKET_PATH}\n"
                "The file may have been moved or renamed."
            )
        else:
            raise RuntimeError(f"Failed to download org data: {error_msg}")
    except Exception as e:
        raise RuntimeError(f"Failed to download org data: {e}")


def load_cache():
    """
    Load org data from cache.

    Returns:
        dict: The cached org data

    Raises:
        FileNotFoundError: If cache doesn't exist
        json.JSONDecodeError: If cache is corrupted
    """
    # Check and fix permissions if needed
    if CACHE_FILE.exists():
        current_perms = CACHE_FILE.stat().st_mode & 0o777
        if current_perms != 0o600:
            print(f"Updating cache file permissions from {oct(current_perms)} to 0600", file=sys.stderr)
            os.chmod(CACHE_FILE, 0o600)

    with open(CACHE_FILE, 'r') as f:
        return json.load(f)


def get_org_data(force_refresh=False):
    """
    Get org data, using cache if fresh or downloading if stale/missing.

    Args:
        force_refresh: If True, always download fresh data

    Returns:
        tuple: (data, status) where status is "fresh", "stale", "missing", or "updated"
    """
    cache_age = get_cache_age_days()

    # Determine if we need to refresh
    needs_refresh = force_refresh or cache_age is None or cache_age > CACHE_MAX_AGE_DAYS

    if needs_refresh:
        if cache_age is None:
            status = "missing"
            print("Cache not found, downloading...", file=sys.stderr)
        elif force_refresh:
            status = "updated"
            print("Force refresh requested, downloading...", file=sys.stderr)
        else:
            status = "stale"
            print(f"Cache is {cache_age:.1f} days old (max {CACHE_MAX_AGE_DAYS}), downloading...", file=sys.stderr)

        data = download_org_data()
        return data, "updated"
    else:
        print(f"Using cached data ({cache_age:.1f} days old)", file=sys.stderr)
        data = load_cache()
        return data, "fresh"


def get_cache_info():
    """
    Get information about the cache without loading data.

    Returns:
        dict: Cache metadata
    """
    cache_age = get_cache_age_days()

    if cache_age is None:
        status = "missing"
    elif cache_age > CACHE_MAX_AGE_DAYS:
        status = "stale"
    else:
        status = "fresh"

    return {
        "cache_path": str(CACHE_FILE),
        "cache_age_days": cache_age,
        "cache_status": status,
        "cache_size_mb": get_cache_size_mb(),
        "last_updated": get_cache_mtime()
    }


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Safely manage a local cache of OpenShift org data from GCS'
    )

    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh the cache regardless of age'
    )

    parser.add_argument(
        '--info',
        action='store_true',
        help='Show cache information without loading data'
    )

    args = parser.parse_args()

    try:
        # Safety check: warn if in git context
        check_git_context()

        # Check prerequisites
        if not args.info:
            if not check_gsutil_available():
                print(
                    "Error: gsutil not found. Please install Google Cloud SDK.",
                    file=sys.stderr
                )
                print(
                    "Installation: https://cloud.google.com/sdk/docs/install",
                    file=sys.stderr
                )
                sys.exit(1)

            if not check_gcloud_authenticated():
                print(
                    "Error: Not authenticated with gcloud.",
                    file=sys.stderr
                )
                print(
                    "Please run: gcloud auth login",
                    file=sys.stderr
                )
                sys.exit(1)

        # Get cache info or org data
        if args.info:
            info = get_cache_info()
            output = info
        else:
            # Ensure cache is fresh (download if needed)
            data, status = get_org_data(force_refresh=args.force_refresh)
            # Only return metadata, not the actual data
            info = get_cache_info()
            output = info

        # Output as JSON
        print(json.dumps(output, indent=2))

    except FileNotFoundError as e:
        print(f"Error: Cache file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Cache file is corrupted: {e}", file=sys.stderr)
        print(f"Try running with --force-refresh to re-download", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
