#!/usr/bin/env python3
"""Extract and recursively decompress must-gather archives."""

import os
import sys
import tarfile
import gzip
import shutil
from pathlib import Path


def human_readable_size(size_bytes):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def extract_tar_archive(tar_path, extract_to):
    """Extract a tar archive (including .tar.gz and .tgz)."""
    try:
        print(f"  Extracting: {tar_path}")
        with tarfile.open(tar_path, 'r:*') as tar:
            tar.extractall(path=extract_to)
        return True
    except Exception as e:
        print(f"  ERROR: Failed to extract {tar_path}: {e}", file=sys.stderr)
        return False


def gunzip_file(gz_path):
    """Gunzip a .gz file (not a tar.gz)."""
    try:
        # Output file is the same name without .gz extension
        output_path = gz_path[:-3] if gz_path.endswith('.gz') else gz_path + '.decompressed'

        print(f"  Decompressing: {gz_path}")
        with gzip.open(gz_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True, output_path
    except Exception as e:
        print(f"  ERROR: Failed to decompress {gz_path}: {e}", file=sys.stderr)
        return False, None


def find_and_rename_ci_directory(base_path):
    """Find directory containing '-ci-' and rename it to 'content'."""
    try:
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path) and '-ci-' in item:
                content_path = os.path.join(base_path, 'content')
                print(f"\nRenaming directory:")
                print(f"  From: {item}")
                print(f"  To: content/")
                os.rename(item_path, content_path)
                return True
        print("\nWARNING: No directory containing '-ci-' found to rename", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: Failed to rename directory: {e}", file=sys.stderr)
        return False


def process_nested_archives(base_path):
    """Recursively find and extract nested archives."""
    archives_processed = 0
    errors = []

    print("\nProcessing nested archives...")

    # Keep processing until no more archives are found
    # (since extracting one archive might create new archives)
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        found_archives = False

        # Walk directory tree
        for root, dirs, files in os.walk(base_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                processed = False

                # Handle .tar.gz and .tgz files
                if filename.endswith('.tar.gz') or filename.endswith('.tgz'):
                    parent_dir = os.path.dirname(file_path)
                    if extract_tar_archive(file_path, parent_dir):
                        os.remove(file_path)
                        archives_processed += 1
                        processed = True
                        found_archives = True
                    else:
                        errors.append(f"Failed to extract: {file_path}")

                # Handle plain .gz files (not .tar.gz)
                elif filename.endswith('.gz') and not filename.endswith('.tar.gz'):
                    success, output_path = gunzip_file(file_path)
                    if success:
                        os.remove(file_path)
                        archives_processed += 1
                        processed = True
                        found_archives = True
                    else:
                        errors.append(f"Failed to decompress: {file_path}")

        # If no archives were found in this iteration, we're done
        if not found_archives:
            break

    if iteration >= max_iterations:
        print(f"\nWARNING: Stopped after {max_iterations} iterations. Some nested archives may remain.", file=sys.stderr)

    return archives_processed, errors


def count_files_and_size(base_path):
    """Count total files and calculate total size."""
    total_files = 0
    total_size = 0

    for root, dirs, files in os.walk(base_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                total_files += 1
                total_size += os.path.getsize(file_path)
            except:
                pass

    return total_files, total_size


def main():
    if len(sys.argv) != 3:
        print("Usage: extract_archives.py <must-gather.tar> <output-directory>")
        print("  <must-gather.tar>: Path to the must-gather.tar file")
        print("  <output-directory>: Directory to extract to")
        sys.exit(1)

    tar_file = sys.argv[1]
    output_dir = sys.argv[2]

    # Validate inputs
    if not os.path.exists(tar_file):
        print(f"ERROR: Input file not found: {tar_file}", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 80)
    print("Must-Gather Archive Extraction")
    print("=" * 80)

    # Step 1: Extract main tar file
    print(f"\nStep 1: Extracting must-gather.tar")
    print(f"  From: {tar_file}")
    print(f"  To: {output_dir}")

    if not extract_tar_archive(tar_file, output_dir):
        print("ERROR: Failed to extract must-gather.tar", file=sys.stderr)
        sys.exit(1)

    # Step 2: Rename directory containing '-ci-' to 'content'
    print(f"\nStep 2: Renaming long directory to 'content/'")
    find_and_rename_ci_directory(output_dir)

    # Step 3: Process nested archives
    print(f"\nStep 3: Processing nested archives")
    archives_processed, errors = process_nested_archives(output_dir)

    # Final statistics
    print("\n" + "=" * 80)
    print("Extraction Complete")
    print("=" * 80)

    total_files, total_size = count_files_and_size(output_dir)

    print(f"\nStatistics:")
    print(f"  Total files: {total_files:,}")
    print(f"  Total size: {human_readable_size(total_size)}")
    print(f"  Archives processed: {archives_processed}")

    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    print(f"\nExtracted to: {output_dir}")
    print("")


if __name__ == '__main__':
    main()
