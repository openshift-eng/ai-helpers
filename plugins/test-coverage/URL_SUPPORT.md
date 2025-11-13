# URL Support for Test Coverage Commands

Test coverage commands support both **local file paths** and **remote URLs** for input files and directories.

## Supported Commands

Both test-coverage commands support URL inputs:

1. **`/test-coverage:analyze`** - Analyze test structure from local or remote sources
2. **`/test-coverage:gaps`** - Identify coverage gaps using local or remote coverage files

## Supported URL Types

### GitHub URLs

**Blob URLs** (automatically converted to raw URLs):
```
https://github.com/owner/repo/blob/main/test/file_test.go
```

**Raw URLs** (used directly):
```
https://raw.githubusercontent.com/owner/repo/main/test/file_test.go
```

**Archive URLs**:
```
https://github.com/owner/repo/archive/refs/heads/main.zip
```

### GitLab URLs

**Blob URLs** (automatically converted to raw URLs):
```
https://gitlab.com/owner/repo/-/blob/main/test/file_test.py
```

**Raw URLs** (used directly):
```
https://gitlab.com/owner/repo/-/raw/main/test/file_test.py
```

### Generic HTTP(S) URLs

Any direct file URL to test files:
```
https://ci.example.com/artifacts/test_file.go
https://example.com/reports/integration_test.go
```

## How It Works

### Automatic URL Detection

The path handler automatically detects if an input is a URL or local path:

```python
from utils.path_handler import PathHandler

handler = PathHandler()

# Detects and downloads URL
handler.resolve("https://github.com/owner/repo/blob/main/test.go")

# Validates and resolves local path
handler.resolve("./test/file_test.go")
```

### Caching

Downloaded files are cached to avoid repeated downloads:

- **Cache directory**: `.work/test-coverage/cache/`
- **Cache key**: MD5 hash of URL + original filename
- **Reuse**: Cached files are reused on subsequent runs

### Clear Cache

To force re-download of cached files:

```bash
rm -rf .work/test-coverage/cache/
```

Or use the utility directly:

```bash
python3 utils/path_handler.py --clear-cache
```

## Usage Examples

### Example 1: Analyze Remote Test File

```bash
/test-coverage:analyze https://github.com/openshift/origin/blob/master/test/extended/networking/infw.go --test-structure-only
```

**What happens**:
1. URL is detected
2. GitHub blob URL is converted to raw URL
3. File is downloaded to `.work/test-coverage/cache/infw_abc123.go`
4. Cached file is analyzed

### Example 2: Gaps Analysis with Remote Test File

```bash
/test-coverage:gaps https://github.com/openshift/origin/blob/master/test/extended/storage/volume.go
```

**What happens**:
1. Test file URL is detected and downloaded
2. File is cached locally
3. Gap analysis is performed on the test file


## Implementation Details

### PathHandler Class

Located in `utils/path_handler.py`, the `PathHandler` class provides:

- **URL detection**: Identifies HTTP(S), FTP, and file:// URLs
- **GitHub/GitLab conversion**: Converts blob URLs to raw URLs automatically
- **Download management**: Downloads files with proper headers and error handling
- **Caching**: Stores downloaded files for reuse
- **Path resolution**: Converts relative paths to absolute paths

### Key Methods

```python
class PathHandler:
    def __init__(self, cache_dir=None):
        """Initialize with optional custom cache directory"""

    def is_url(self, path):
        """Check if input is a URL"""

    def resolve(self, path_or_url, force_download=False):
        """Main entry point: resolve URL or path to local file"""

    def clear_cache(self):
        """Clear download cache"""
```

### Convenience Functions

```python
from utils.path_handler import resolve_path, resolve_paths

# Resolve single path/URL
local_path = resolve_path("https://example.com/file.go")

# Resolve multiple paths/URLs
local_paths = resolve_paths([
    "./local/file1.go",
    "https://example.com/file2.go",
    "https://github.com/owner/repo/blob/main/file3.go"
])
```

## Command Integration

All commands have been updated to use `PathHandler`:

### Before (local paths only)

```markdown
## Arguments
- `<source-directory>`: Path to source code directory to analyze
```

### After (local paths OR URLs)

```markdown
## Arguments
- `<source-directory>`: Path or URL to source code directory/file to analyze
  - **Local path**: `./pkg/`, `/home/user/project/test/file.go`
  - **GitHub URL**: `https://github.com/owner/repo/blob/main/test/file_test.go`
  - **HTTP(S) URL**: Any direct file URL
  - URLs are automatically downloaded and cached
```

## Benefits

1. **Remote Analysis**: Analyze test files directly from GitHub without cloning
2. **CI Integration**: Fetch coverage reports from CI artifacts URLs
3. **Caching**: Avoid repeated downloads with automatic caching
4. **Flexibility**: Mix local and remote sources in the same command

## Error Handling

The path handler provides clear error messages:

- **Invalid URL**: Reports HTTP error codes and reasons
- **Network errors**: Reports connection issues with helpful messages
- **Missing files**: Reports when local paths don't exist
- **Download failures**: Provides detailed error information

## Testing

Test the path handler directly:

```bash
# Test local path resolution
python3 utils/path_handler.py ./test/file.go

# Test URL resolution (doesn't actually download, just shows what would happen)
python3 utils/path_handler.py https://github.com/owner/repo/blob/main/file.go

# Clear cache
python3 utils/path_handler.py --clear-cache

# Force re-download
python3 utils/path_handler.py --force https://example.com/file.go
```

## Future Enhancements

Potential future improvements:

1. **Progress indicators**: Show download progress for large files
2. **Archive extraction**: Automatic extraction of .zip and .tar.gz archives
3. **Authentication**: Support for private repositories with tokens
4. **Parallel downloads**: Download multiple files concurrently
5. **Smart caching**: TTL-based cache expiration
6. **Proxy support**: HTTP/HTTPS proxy configuration

## See Also

- [`/test-coverage:analyze` command](commands/analyze.md)
- [`/test-coverage:gaps` command](commands/gaps.md)
- [Path Handler Utility](utils/path_handler.py)
