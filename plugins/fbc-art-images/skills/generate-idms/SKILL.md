---
name: Generate IDMS Manifest
description: Generate an ImageDigestMirrorSet manifest for art-image-share registry mirroring
---

# Generate IDMS Manifest

This skill provides detailed implementation guidance for generating an ImageDigestMirrorSet (IDMS) manifest that configures registry mirroring to the art-image-share registry for operator images.

## When to Use This Skill

Use this skill when you need to:
- Generate an IDMS manifest for operator image mirroring
- Configure the cluster to pull operator images from art-image-share registry
- Discover related images from FBC artifacts built in Konflux
- Implement the IDMS generation step in commands like `/fbc-art-images:idms` or `/fbc-art-images:setup`

## Prerequisites

- **OCP version**: Must be in `X.Y` format (e.g., "4.20", "4.19")
- **Operator name**: Valid operator name (e.g., "amq-broker-rhel9", "advanced-cluster-management")
- **oras CLI**: Required for discovering related images from FBC artifacts
  - Installation: [https://oras.land/docs/installation](https://oras.land/docs/installation)
  - Check: `which oras`
- **jq CLI**: Required for parsing JSON output from oras
  - Check: `which jq`

## Implementation Steps

### Step 1: Validate Prerequisites

**Check for oras CLI:**
```bash
which oras
```

If not installed, show installation instructions:
```text
Error: oras CLI is not installed

Install oras from: https://oras.land/docs/installation

Quick install options:
- macOS: brew install oras
- Linux: Download from https://github.com/oras-project/oras/releases
```

**Check for jq CLI:**
```bash
which jq
```

If not installed:
```text
Error: jq CLI is not installed

Install jq:
- macOS: brew install jq
- Linux: sudo apt-get install jq (Debian/Ubuntu) or sudo yum install jq (RHEL/CentOS)
```

**Detect oras version:**
```bash
oras version
```

Parse the output to determine if version is >= 1.3.0 or < 1.3.0. This determines which JSON field to use (`.referrers` vs `.manifests`).

### Step 2: Create Working Directory

Create a directory for storing discovered images and manifests:

```bash
mkdir -p .work/fbc-art-images/<ocp-version>_<operator-name>/
cd .work/fbc-art-images/<ocp-version>_<operator-name>/
```

**Notes:**
- Use underscore `_` to separate OCP version and operator name
- If the directory already exists, that's fine (reuse it)
- Change into this directory to run oras commands

### Step 3: Construct FBC Image URL

The FBC image URL follows the same pattern as CatalogSource:

```text
quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<ocp-version>__<operator-name>
```

**Example:**
- OCP version: `4.20`
- Operator: `amq-broker-rhel9`
- URL: `quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.20__amq-broker-rhel9`

### Step 4: Discover Related Images

Use oras to discover and extract related images from the FBC artifact. The command differs based on oras version.

**For oras version < 1.3.0:**
```bash
cd .work/fbc-art-images/<ocp-version>_<operator-name>/
oras discover --format json quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<ocp-version>__<operator-name> | \
  jq -r '.manifests[] | select(.artifactType == "application/vnd.konflux-ci.attached-artifact") | .digest' | \
  xargs -I {} oras pull quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc@{} && \
  cat related-images.json | jq -r '.[]' | sed 's/@sha256:.*//' > related-images-list.txt
```

**For oras version >= 1.3.0:**
```bash
cd .work/fbc-art-images/<ocp-version>_<operator-name>/
oras discover --format json quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<ocp-version>__<operator-name> | \
  jq -r '.referrers[] | select(.artifactType == "application/vnd.konflux-ci.attached-artifact") | .digest' | \
  xargs -I {} oras pull quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc@{} && \
  cat related-images.json | jq -r '.[]' | sed 's/@sha256:.*//' > related-images-list.txt
```

**Command breakdown:**
1. `oras discover`: Finds artifacts attached to the FBC image
2. `jq -r '.manifests[]'` or `jq -r '.referrers[]'`: Extracts manifests/referrers from JSON (version-dependent)
3. `select(.artifactType == "application/vnd.konflux-ci.attached-artifact")`: Filters for Konflux artifacts
4. `.digest`: Extracts the digest of the artifact
5. `xargs -I {} oras pull`: Pulls the artifact by digest (creates `related-images.json`)
6. `cat related-images.json | jq -r '.[]'`: Extracts image references from the artifact
7. `sed 's/@sha256:.*//'`: Removes digest suffixes, leaving only image repositories

**Output files:**
- `related-images.json`: Raw JSON artifact containing all related image references
- `related-images-list.txt`: Clean list of image repositories (one per line, no digests)

**Example `related-images-list.txt` content:**
```text
registry.redhat.io/amq-broker-7/amq-broker-rhel8-operator
registry.redhat.io/amq-broker-7/amq-broker-init-rhel8
registry.redhat.io/amq-broker-7/amq-broker-rhel8
```

### Step 5: Display Discovered Images

Read the `related-images-list.txt` file and show the user what was discovered:

```bash
wc -l related-images-list.txt  # Count images
cat related-images-list.txt     # Display list
```

Example output:
```text
Discovered 3 related images for amq-broker-rhel9 (OCP 4.20):
  - registry.redhat.io/amq-broker-7/amq-broker-rhel8-operator
  - registry.redhat.io/amq-broker-7/amq-broker-init-rhel8
  - registry.redhat.io/amq-broker-7/amq-broker-rhel8
```

### Step 6: Generate IDMS YAML

Create the manifest file at:
```text
.work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml
```

**Template structure:**
```yaml
apiVersion: config.openshift.io/v1
kind: ImageDigestMirrorSet
metadata:
  name: art-image-share-<ocp-version>-<operator-name>
spec:
  imageDigestMirrors:
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: <image-1-from-related-images-list>
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: <image-2-from-related-images-list>
  # ... repeat for each image in related-images-list.txt
```

**Generation logic:**
1. Read `related-images-list.txt` line by line
2. For each line (image source), create an `imageDigestMirrors` entry
3. Each entry has:
   - `mirrors`: Always `["quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share"]`
   - `source`: The image repository from related-images-list.txt

**Example manifest** (for amq-broker-rhel9 on OCP 4.20):
```yaml
apiVersion: config.openshift.io/v1
kind: ImageDigestMirrorSet
metadata:
  name: art-image-share-4.20-amq-broker-rhel9
spec:
  imageDigestMirrors:
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: registry.redhat.io/amq-broker-7/amq-broker-rhel8-operator
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: registry.redhat.io/amq-broker-7/amq-broker-init-rhel8
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: registry.redhat.io/amq-broker-7/amq-broker-rhel8
```

### Step 7: Return Manifest Location

Return the paths to the generated files:
- IDMS manifest: `.work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml`
- Related images list: `.work/fbc-art-images/<ocp-version>_<operator-name>/related-images-list.txt`
- Raw JSON artifact: `.work/fbc-art-images/<ocp-version>_<operator-name>/related-images.json`

## Error Handling

### oras CLI Not Installed
```text
Error: oras CLI is not installed

Install oras from: https://oras.land/docs/installation

Quick install options:
- macOS: brew install oras
- Linux: Download from https://github.com/oras-project/oras/releases
```

### jq CLI Not Installed
```text
Error: jq CLI is not installed

Install jq:
- macOS: brew install jq
- Linux: sudo apt-get install jq (Debian/Ubuntu) or sudo yum install jq (RHEL/CentOS)
```

### oras discover Fails
If `oras discover` returns an error:
```text
Error: Failed to discover related images for FBC image:
quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<ocp-version>__<operator-name>

Possible causes:
1. Network connectivity issues
2. Invalid FBC image tag (check OCP version and operator name)
3. Image doesn't exist in the registry
4. Authentication required (check quay.io credentials)

Try verifying the image exists:
oras manifest fetch quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<ocp-version>__<operator-name>
```

### No Related Images Found
If `related-images-list.txt` is empty or doesn't exist:
```text
Error: No related images found for this operator

Possible causes:
1. The FBC image doesn't have attached Konflux artifacts
2. The artifact format has changed
3. Wrong oras version (try >= 1.3.0 and use .referrers instead of .manifests)

The FBC image may not be built with Konflux CI, or the related-images artifact is missing.
```

### related-images.json Not Found
If `oras pull` doesn't create `related-images.json`:
```text
Error: related-images.json not found after pulling artifact

Possible causes:
1. The artifact doesn't contain a related-images.json file
2. The artifact format has changed
3. Konflux CI build didn't attach the related images

Check what files were pulled:
ls -la .work/fbc-art-images/<ocp-version>_<operator-name>/
```

### Invalid Image Format in related-images.json
If jq parsing fails or produces unexpected output:
```text
Error: Failed to parse related-images.json

The artifact format may have changed. Expected JSON array of image strings.

Check the file content:
cat .work/fbc-art-images/<ocp-version>_<operator-name>/related-images.json
```

### Working Directory Creation Failure
```text
Error: Failed to create working directory: .work/fbc-art-images/<ocp-version>_<operator-name>/
Check filesystem permissions and available disk space.
```

### File Write Failure
```text
Error: Failed to write IDMS manifest to: .work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml
Check filesystem permissions and available disk space.
```

## Examples

### Example 1: AMQ Broker on OCP 4.20

**Input:**
- OCP version: `4.20`
- Operator name: `amq-broker-rhel9`

**Commands executed:**
```bash
mkdir -p .work/fbc-art-images/4.20_amq-broker-rhel9/
cd .work/fbc-art-images/4.20_amq-broker-rhel9/

# Assuming oras >= 1.3.0
oras discover --format json quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.20__amq-broker-rhel9 | \
  jq -r '.referrers[] | select(.artifactType == "application/vnd.konflux-ci.attached-artifact") | .digest' | \
  xargs -I {} oras pull quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc@{} && \
  cat related-images.json | jq -r '.[]' | sed 's/@sha256:.*//' > related-images-list.txt
```

**Generated `related-images-list.txt`:**
```text
registry.redhat.io/amq-broker-7/amq-broker-rhel8-operator
registry.redhat.io/amq-broker-7/amq-broker-init-rhel8
registry.redhat.io/amq-broker-7/amq-broker-rhel8
```

**Generated `idms.yaml`:**
```yaml
apiVersion: config.openshift.io/v1
kind: ImageDigestMirrorSet
metadata:
  name: art-image-share-4.20-amq-broker-rhel9
spec:
  imageDigestMirrors:
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: registry.redhat.io/amq-broker-7/amq-broker-rhel8-operator
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: registry.redhat.io/amq-broker-7/amq-broker-init-rhel8
  - mirrors:
    - quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share
    source: registry.redhat.io/amq-broker-7/amq-broker-rhel8
```

### Example 2: Advanced Cluster Management on OCP 4.19

**Input:**
- OCP version: `4.19`
- Operator name: `advanced-cluster-management`

**Generated files:**
- `.work/fbc-art-images/4.19_advanced-cluster-management/idms.yaml`
- `.work/fbc-art-images/4.19_advanced-cluster-management/related-images-list.txt`
- `.work/fbc-art-images/4.19_advanced-cluster-management/related-images.json`

**Generated `idms.yaml`:**
```yaml
apiVersion: config.openshift.io/v1
kind: ImageDigestMirrorSet
metadata:
  name: art-image-share-4.19-advanced-cluster-management
spec:
  imageDigestMirrors:
  # ... entries for each discovered ACM image
```

### Example 3: Handling oras Version Differences

**oras version 1.2.0 (older):**
```bash
oras discover --format json <image> | jq -r '.manifests[]...'
```

**oras version 1.3.0+ (newer):**
```bash
oras discover --format json <image> | jq -r '.referrers[]...'
```

**Version detection logic:**
```bash
oras_version=$(oras version | grep -oP 'Version:\s+\K[0-9.]+')
if [[ $(echo "$oras_version 1.3.0" | tr " " "\n" | sort -V | head -n1) == "1.3.0" ]]; then
  # Use .referrers
  json_field=".referrers"
else
  # Use .manifests
  json_field=".manifests"
fi
```

## Output Format

The skill should return:
- **IDMS manifest path**: Path to the generated IDMS YAML file
- **Related images count**: Number of images discovered
- **Related images list**: Display of discovered images for user review
- **Success message**: Confirmation that manifests were created

## Important Notes

### IDMS Impact on Cluster
- Applying an IDMS triggers MachineConfig updates
- Cluster nodes will restart sequentially (rolling restart)
- The restart process typically takes 20-30 minutes for a standard cluster
- Nodes are updated one at a time to minimize disruption

### Image Format Details
- Related images in `related-images.json` include digest suffixes (`@sha256:...`)
- The IDMS `source` field requires only the repository (no digest)
- Use `sed 's/@sha256:.*//'` to strip digests from image references
- Example transformation:
  - Input: `registry.redhat.io/amq-broker-7/amq-broker-rhel8@sha256:abc123...`
  - Output: `registry.redhat.io/amq-broker-7/amq-broker-rhel8`

### IDMS Naming Convention
- Format: `art-image-share-<ocp-version>-<operator-name>`
- Use hyphens between all components
- Each operator/version combination gets its own IDMS to avoid conflicts
- Example: `art-image-share-4.20-amq-broker-rhel9`

### Mirror Configuration
- All operator images mirror to: `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share`
- This is a single shared mirror repository for all art-images-share content
- The cluster will attempt to pull from the mirror first before falling back to the source

### oras CLI Version Considerations
- The JSON structure changed in oras 1.3.0
- Older versions use `.manifests[]` to access discovered artifacts
- Newer versions use `.referrers[]` to access discovered artifacts
- Always detect the version and use the appropriate field

## See Also

- Related skill: `generate-catalog-source` - Generate CatalogSource manifests
- Command: `/fbc-art-images:idms` - User-facing command that uses this skill
- Command: `/fbc-art-images:setup` - Orchestrates both CatalogSource and IDMS generation
- oras documentation: [https://oras.land/docs/](https://oras.land/docs/)
- Konflux CI: [https://konflux-ci.dev/](https://konflux-ci.dev/)
