---
description: List and analyze available tags for a container image repository
argument-hint: <repository>
---

## Name
container-image:tags

## Synopsis
```
/container-image:tags <repository>
```

## Description

The `container-image:tags` command lists and analyzes all available tags for a container image repository. It provides detailed information about each tag including creation date, size, architecture support, and digest.

This command helps you:
- Discover available image versions
- Identify the latest stable releases
- Find images for specific architectures
- Track image update frequency
- Identify deprecated or outdated tags
- Plan image upgrades
- Understand tagging conventions

The command works with any OCI-compliant registry and can filter, sort, and analyze tags based on various criteria.

## Prerequisites

**Required Tools:**

1. **skopeo** - For listing and inspecting tags
   - Check if installed: `which skopeo`
   - Installation:
     - RHEL/Fedora: `sudo dnf install skopeo`
     - Ubuntu/Debian: `sudo apt-get install skopeo`
     - macOS: `brew install skopeo`
   - Documentation: https://github.com/containers/skopeo

**Registry Authentication:**

For private registries:
```bash
skopeo login registry.example.com
```

## Implementation

The command performs the following analysis:

1. **Check Tool Availability**:
   - Verify `skopeo` is installed
   - If missing, provide installation instructions

2. **List All Tags**:
   ```bash
   skopeo list-tags docker://<repository>
   ```

   This returns all available tags for the repository.

3. **Inspect Each Tag** (for detailed analysis):
   For each tag (or a sample of tags for large repositories):
   ```bash
   skopeo inspect docker://<repository>:<tag>
   ```

   Extract:
   - Image digest
   - Creation date
   - Size
   - Architecture(s)
   - Labels
   - Manifest type

4. **Categorize Tags**:
   - **Version tags**: Semantic versions (v1.0.0, 2.1.3)
   - **Latest tags**: Tags like `latest`, `stable`, `production`
   - **Date-based tags**: Tags with dates (20240115, 2024-01-15)
   - **Branch tags**: Development branches (main, develop)
   - **SHA tags**: Git commit SHAs
   - **Custom tags**: Other tagging schemes

5. **Sort and Filter**:
   - Sort by creation date (newest first)
   - Sort by semantic version
   - Filter by pattern (e.g., only `v4.*` tags)
   - Filter by architecture support
   - Show only recent tags (e.g., last 30 days)

6. **Identify Key Tags**:
   - Current `latest` tag
   - Most recent version tag
   - Long-term support (LTS) tags
   - Deprecated tags
   - Duplicate tags (same digest, different names)

7. **Present Organized Analysis**:
   - Summary of tag categories
   - Detailed tag list with metadata
   - Recommendations for tag selection
   - Notable patterns or issues

## Return Value

The command outputs a structured tag listing:

```
================================================================================
CONTAINER IMAGE TAGS
================================================================================
Repository: quay.io/openshift-release-dev/ocp-release

Total Tags: 487

TAG SUMMARY:
  Version Tags:     312  (e.g., 4.17.0, 4.16.1)
  Date Tags:        150  (e.g., 2024-01-15)
  Latest Tags:      3    (latest, stable, production)
  Other Tags:       22

RECENT TAGS (Last 30 days):
--------------------------------------------------------------------------------
TAG                          CREATED              SIZE      ARCH        DIGEST
4.17.0                       2024-01-15 10:30     1.2 GB    multi       sha256:abc123...
4.17.0-rc.1                  2024-01-10 08:15     1.2 GB    multi       sha256:def456...
4.16.2                       2024-01-08 14:22     1.1 GB    multi       sha256:ghi789...
latest                       2024-01-15 10:30     1.2 GB    multi       sha256:abc123...
stable                       2024-01-08 14:22     1.1 GB    multi       sha256:ghi789...

VERSION TAGS (Semantic):
--------------------------------------------------------------------------------
4.17.0         2024-01-15  1.2 GB  multi  sha256:abc123...  [LATEST]
4.17.0-rc.1    2024-01-10  1.2 GB  multi  sha256:def456...
4.16.2         2024-01-08  1.1 GB  multi  sha256:ghi789...
4.16.1         2023-12-20  1.1 GB  multi  sha256:jkl012...
4.16.0         2023-12-01  1.1 GB  multi  sha256:mno345...
4.15.18        2023-11-28  1.0 GB  multi  sha256:pqr678...
...

SPECIAL TAGS:
--------------------------------------------------------------------------------
latest    → 4.17.0 (sha256:abc123...)
stable    → 4.16.2 (sha256:ghi789...)
lts       → 4.15.18 (sha256:pqr678...)

ARCHITECTURE SUPPORT:
  Multi-arch tags: 465 (linux/amd64, linux/arm64, linux/ppc64le, linux/s390x)
  Single-arch:     22  (linux/amd64 only)

DUPLICATE TAGS (same image, multiple tags):
  4.17.0 = latest = 2024-01-15 (sha256:abc123...)
  4.16.2 = stable (sha256:ghi789...)

TAG PATTERNS:
  • Semantic versioning (4.x.y)
  • Release candidates (-rc.x)
  • Date-based snapshots (YYYY-MM-DD)
  • Architecture-specific suffixes (-amd64, -arm64)

RECOMMENDATIONS:
  • For production: Use stable (4.16.2) or specific version tag
  • For testing: Use latest (4.17.0)
  • For LTS: Use lts (4.15.18)
  • Avoid: Using generic tags like 'latest' in production
  • Pin by digest: Use @sha256:abc123... for reproducibility

NOTABLE:
  • 3 tags updated in the last 7 days
  • 15 release candidates available
  • Average tag age: 45 days
  • Update frequency: ~2 tags per week
================================================================================
```

**For Small Repositories:**
```
================================================================================
CONTAINER IMAGE TAGS
================================================================================
Repository: docker.io/library/alpine

Total Tags: 47

ALL TAGS:
--------------------------------------------------------------------------------
TAG              CREATED              SIZE      ARCH        DIGEST
latest           2024-01-20 12:00     7.3 MB    multi       sha256:abc123...
3.19             2024-01-20 12:00     7.3 MB    multi       sha256:abc123...
3.18             2023-11-15 09:30     7.0 MB    multi       sha256:def456...
3.17             2023-08-10 14:15     6.8 MB    multi       sha256:ghi789...
edge             2024-01-22 08:00     7.5 MB    multi       sha256:jkl012...
...

RECOMMENDATIONS:
  • For production: Use 3.19 (latest stable)
  • For edge features: Use edge
  • For compatibility: Use 3.18 or 3.17
================================================================================
```

## Examples

1. **List tags for OpenShift release images**:
   ```
   /container-image:tags quay.io/openshift-release-dev/ocp-release
   ```
   Shows all available OpenShift release versions.

2. **Check available UBI tags**:
   ```
   /container-image:tags registry.redhat.io/ubi9/ubi
   ```
   Lists all UBI 9 image tags.

3. **Explore nginx versions**:
   ```
   /container-image:tags docker.io/library/nginx
   ```
   Shows available nginx versions and variants.

4. **Check private repository tags**:
   ```
   /container-image:tags registry.example.com/myorg/myapp
   ```
   Lists tags from a private registry (requires authentication).

5. **Analyze Prometheus tags**:
   ```
   /container-image:tags quay.io/prometheus/prometheus
   ```
   Shows Prometheus versions and release patterns.

## Advanced Options

The command can support optional filters and sorting:

**Filter by Pattern:**
```
/container-image:tags quay.io/openshift-release-dev/ocp-release --filter "4.17.*"
```
Shows only 4.17.x tags.

**Limit Results:**
```
/container-image:tags docker.io/library/alpine --limit 10
```
Shows only the 10 most recent tags.

**Sort Options:**
```
/container-image:tags quay.io/myapp --sort version   # Semantic version sort
/container-image:tags quay.io/myapp --sort date      # Creation date sort
/container-image:tags quay.io/myapp --sort size      # Size sort
```

**Architecture Filter:**
```
/container-image:tags registry.example.com/myapp --arch arm64
```
Shows only tags that support arm64.

## Error Handling

- **Repository not found**: Verify repository name and registry
- **Authentication required**: Guide user to login with `skopeo login`
- **Network errors**: Check connectivity and registry availability
- **Tool not available**: Provide installation instructions for `skopeo`
- **Rate limiting**: Handle registry rate limits gracefully
- **Large repositories**: For repositories with 1000+ tags, sample or paginate results

## Notes

- **Tag Mutability**: Tags (except digests) can be reassigned to different images
- **Latest Tag**: "latest" doesn't always mean newest; it's just a convention
- **Digest Pinning**: For reproducible deployments, always use digest (@sha256:...)
- **Semantic Versioning**: Many projects follow semver (MAJOR.MINOR.PATCH)
- **Multi-arch Support**: Check which tags support your target architecture
- **Deprecation**: Older tags may be removed; check registry retention policies

## Performance Considerations

For repositories with many tags:
- The command samples tags rather than inspecting all
- Full inspection can be requested with `--full` flag
- Results can be cached for repeated queries
- Pagination is used for very large tag lists

## Use Cases

1. **Version Discovery**: Find the latest stable version before deployment
2. **Update Planning**: Identify available updates for current images
3. **Architecture Planning**: Verify multi-arch support before migration
4. **Cleanup Planning**: Identify old/unused tags for cleanup
5. **Compliance**: Document available versions for audit trails
6. **CI/CD Integration**: Automate image version selection
7. **Troubleshooting**: Compare production tag with available versions

## Arguments

- **$1** (repository): Required. The repository path (without tag).
  - Format: `[registry/]repository`
  - Examples:
    - `quay.io/openshift-release-dev/ocp-release`
    - `docker.io/library/nginx`
    - `registry.redhat.io/ubi9/ubi`
    - `registry.example.com/myorg/myapp`

**Note**: Do NOT include the tag (`:tagname`) in the repository argument.
