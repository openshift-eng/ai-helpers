---
description: Analyze an OpenShift CI payload image to extract component images, metadata and PRs included in the CI payload
argument-hint: <payload-image>
---

## Name
ci:analyze-payload

## Synopsis
```
/ci:analyze-payload <payload-image>
```

## Description

The `analyze-payload` command analyzes an OpenShift release payload image to extract detailed information about the release, including:
- Release version and metadata
- Component versions (operators, controllers, etc.)
- All images included in the payload
- Image digests and pull specs
- Architecture information
- Pull requests (PRs) included in the payload (via Sippy)
- Release notes and upgrade information

This command is useful for:
- Understanding what components are included in a release
- Verifying component versions before deployment
- Investigating payload composition
- Comparing payloads between releases
- Debugging release-related issues

## Arguments
- `$1` (payload-image): The full image reference to the OpenShift release payload (required)
  - Example: `quay.io/openshift-release-dev/ocp-release:4.21.0-ec.3-x86_64`
  - Can be specified with tag or digest
  - Supports both single-arch and multi-arch payloads

## Implementation

The command performs the following steps:

1. **Validate Arguments**:
   - Extract payload image from `$1`
   - Validate image format (should be a valid container image reference)
   - Check if image appears to be an OpenShift release payload (contains `ocp-release` or similar patterns)

2. **Check Prerequisites**:
   - Verify `oc` (OpenShift CLI) is installed: `which oc`
   - If not installed, provide installation instructions:
     - For macOS: `brew install openshift-cli`
     - For Linux: Download from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
     - For Windows: Download installer from the same location
   - Verify `oc` version is 4.x or later (required for `oc adm release info`)
   - **For CI payloads** (registry.ci.openshift.org):
     - Check if user is logged in: `oc whoami`
     - If not logged in, prompt user to authenticate:
       ```bash
       # Visit https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/
       # Log in with SSO, then run:
       oc login --server=https://api.ci.l2s4.p1.openshiftapps.com:6443
       ```
     - Check registry authentication: `oc registry login`
     - If registry login fails, prompt user to run:
       ```bash
       oc registry login
       ```
   - **For public payloads** (quay.io/openshift-release-dev): No authentication required

3. **Extract Payload Information**:
   - Use `oc adm release info` to extract payload metadata:
     ```bash
     oc adm release info <payload-image> --output=json
     ```
   - This provides:
     - Release version and metadata
     - Component versions
     - Image references
     - Architecture information
     - Release notes

4. **Extract Component Versions**:
   - Parse the JSON output to extract component information:
     ```bash
     oc adm release info <payload-image> --output=json | jq -r '.metadata.version'
     oc adm release info <payload-image> --output=json | jq -r '.metadata.name'
     ```
   - Extract all component versions from the payload

5. **List All Images**:
   - Extract all images included in the payload:
     ```bash
     oc adm release info <payload-image> --output=json | jq -r '.references.spec.tags[] | "\(.name): \(.from.name)"'
     ```
   - Or use the simpler format:
     ```bash
     oc adm release info <payload-image> --output=json | jq -r '.references.spec.tags[] | "\(.name) = \(.from.name)"'
     ```

6. **Extract Image Digests**:
   - Get digest information for each image:
     ```bash
     oc adm release info <payload-image> --output=json | jq -r '.references.spec.tags[] | "\(.name) = \(.from.name) (digest: \(.from.digest // "N/A"))"'
     ```

7. **Get Architecture Information**:
   - Determine supported architectures:
     ```bash
     oc adm release info <payload-image> --output=json | jq -r '.metadata | "Architecture: \(.architecture // "multi-arch")"'
     ```

8. **Extract Release Notes** (if available):
   - Check for release notes or upgrade information:
     ```bash
     oc adm release info <payload-image> --changelog=/dev/stdout 2>/dev/null || echo "No changelog available"
     ```

9. **Create Work Directory**:
   - Extract the release tag from payload metadata:
     ```bash
     RELEASE_TAG=$(oc adm release info <payload-image> --output=json | jq -r '.metadata.version')
     ```
   - Create work directory for storing analysis results:
     ```bash
     WORK_DIR=".work/analyze-payload/${RELEASE_TAG}"
     mkdir -p "${WORK_DIR}"
     ```
   - Store payload metadata JSON in the work directory:
     ```bash
     oc adm release info <payload-image> --output=json > "${WORK_DIR}/payload-info.json"
     ```

10. **Query Sippy API for PRs Included in Payload**:
    - **Extract Release Tag**: Use the full release tag from payload metadata (e.g., `4.21.0-ec.3`)
    - **Build Filter JSON**: Create filter for Sippy API:
      ```bash
      FILTER_JSON=$(jq -nc --arg release_tag "${RELEASE_TAG}" '{
        "items": [
          {
            "columnField": "release_tag",
            "operatorValue": "equals",
            "value": $release_tag
          }
        ]
      }')
      ```
    - **URL Encode Filter**: Encode the filter JSON for the URL:
      ```bash
      FILTER_ENCODED=$(echo "${FILTER_JSON}" | jq -c . | jq -sRr @uri)
      ```
    - **Query Sippy API**: Make GET request to Sippy API:
      ```bash
      curl -s "https://sippy.dptools.openshift.org/api/releases/pull_requests?filter=${FILTER_ENCODED}&sortField=pull_request_id&sort=asc" > "${WORK_DIR}/prs.json"
      ```
    - **Parse PR Response**: Extract PR information from JSON response:
      ```bash
      jq -r '.[] | "\(.url)|\(.name)|\(.description // "N/A")|\(.bug_url // "N/A")"' "${WORK_DIR}/prs.json" > "${WORK_DIR}/prs.txt"
      ```
    - **Error Handling**: 
      - If Sippy query fails (empty response or HTTP error), continue with payload metadata only
      - Display a message: "Unable to retrieve PR information from Sippy. Payload metadata is still available."
      - Check if PRs file is empty or contains valid JSON before processing

11. **Generate Markdown Report**:
    - Create a comprehensive markdown report in the work directory:
      ```bash
      PAYLOAD_IMAGE="$1"  # From command argument
      DIGEST=$(jq -r '.digest' "${WORK_DIR}/payload-info.json")
      ARCH=$(jq -r '.config.architecture // "multi-arch"' "${WORK_DIR}/payload-info.json")
      CREATED=$(jq -r '.config.created // "N/A"' "${WORK_DIR}/payload-info.json")
      TOTAL_IMAGES=$(jq -r '.references.spec.tags | length' "${WORK_DIR}/payload-info.json")
      PR_COUNT=$(jq -r 'length' "${WORK_DIR}/prs.json" 2>/dev/null || echo "0")
      
      # Generate components table
      COMPONENTS_TABLE=$(jq -r '.references.spec.tags[] | "| \(.name) | \(.from.name) | \(.from.digest // "N/A") |"' "${WORK_DIR}/payload-info.json")
      
      # Generate PRs section
      if [ "${PR_COUNT}" != "0" ] && [ "${PR_COUNT}" != "null" ]; then
        PRS_SECTION=$(jq -r '.[] | "- [\(.name)](\\(.url))\n  - **Description:** \(.description // "N/A")\n  - **Bug:** \(.bug_url // "N/A")\n  - **PR ID:** \(.pull_request_id)\n"' "${WORK_DIR}/prs.json")
      else
        PRS_SECTION="No pull requests found in Sippy for this release tag."
      fi
      
      cat > "${WORK_DIR}/report.md" <<EOF
      # OpenShift Release Payload Analysis
      
      **Payload Image:** \`${PAYLOAD_IMAGE}\`  
      **Release Tag:** \`${RELEASE_TAG}\`  
      **Analysis Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
      
      ## Release Information
      
      | Field | Value |
      |-------|-------|
      | Version | ${RELEASE_TAG} |
      | Digest | \`${DIGEST}\` |
      | Architecture | ${ARCH} |
      | Created | ${CREATED} |
      | Total Images | ${TOTAL_IMAGES} |
      
      ## Pull Requests
      
      **Total PRs:** ${PR_COUNT}
      
      ${PRS_SECTION}
      
      ## Components
      
      | Component | Image | Digest |
      |-----------|-------|--------|
      ${COMPONENTS_TABLE}
      
      ---
      
      *Results stored in: \`${WORK_DIR}\`*
      EOF
      ```

12. **Format and Display Results**:
   - Display summary information to the user:
     - Release version and metadata (version, digest, architecture, created date, total images)
     - **Pull Requests section** - Show all PRs with their details (this is the primary focus)
     - Indicate that components table is available in the markdown report
   - Show location of markdown report: `${WORK_DIR}/report.md`
   - **Do NOT display the full components table in the chat** - only show PRs
   - Mention that the complete components table is in the markdown report file

## Return Value

**Format**: Structured text output with:

**Release Information:**
- Release version (e.g., `4.21.0-ec.3`)
- Release name
- Architecture(s) supported
- Release date/timestamp (if available)

**Component Versions:**
- List of all components with their versions
- Grouped by category (operators, controllers, etc.) when possible

**Components Table:**
- Markdown table with all components, their images, and digests
- Organized by component name
- Includes full image pull specs
- **Note:** Components table is placed at the bottom of the report (after PRs) as it's less frequently needed

**Pull Requests:**
- List of all GitHub PRs included in the payload
- PR URLs, titles, and repository information
- Organized by repository or component (if available)

**Additional Information:**
- Release notes or changelog (if available)
- Upgrade information (if available)

**Important for Claude**:
1. **Prerequisites**: For CI payloads (registry.ci.openshift.org), verify `oc login` and `oc registry login` are completed before attempting to extract payload metadata
2. **Work Directory**: All analysis results are stored in `.work/analyze-payload/{release-tag}/` directory
3. **Sippy API**: Query the Sippy API directly at `https://sippy.dptools.openshift.org/api/releases/pull_requests` - no authentication required
4. **Release Tag**: Use the full release tag from payload metadata (e.g., `4.21.0-ec.3`) for the Sippy filter, not just the version number
5. **URL Encoding**: Properly URL-encode the filter JSON parameter when querying Sippy API
6. **Error Handling**: 
   - If authentication fails for CI payloads, prompt user to run `oc login` and `oc registry login`
   - If Sippy query fails, continue with payload metadata and inform the user that PR information is unavailable
7. **File Storage**: Store all results in the work directory:
   - `payload-info.json` - Full payload metadata (JSON)
   - `prs.json` - PR information from Sippy (JSON)
   - `prs.txt` - Human-readable PR list (text)
   - `report.md` - **Main markdown report (PRs first, components table at bottom)**
8. **Markdown Report Structure**: Generate a comprehensive markdown report (`report.md`) with sections in this order:
   - Release information table
   - **Pull requests list** (primary focus)
   - Components table (component name, image, digest) - **placed at the bottom**
9. **Display Results in Chat**: 
   - **ONLY show PRs in the chat summary** - do NOT display the components table
   - Show release information (version, digest, architecture, created date, total images)
   - Show all PRs with their details (name, URL, description, bug, PR ID)
   - Indicate that the complete components table is available in the markdown report file
   - Show location of markdown report: `${WORK_DIR}/report.md`
   - Mention that the components table contains all ${TOTAL_IMAGES} components

## Examples

1. **Analyze a standard release payload**:
   ```
   /ci:analyze-payload quay.io/openshift-release-dev/ocp-release:4.21.0-ec.3-x86_64
   ```
   Analyzes the 4.21.0-ec.3 release payload for x86_64 architecture.

2. **Analyze a multi-arch payload**:
   ```
   /ci:analyze-payload quay.io/openshift-release-dev/ocp-release:4.20.0-multi
   ```
   Analyzes the multi-architecture 4.20.0 release payload.

3. **Analyze by digest**:
   ```
   /ci:analyze-payload quay.io/openshift-release-dev/ocp-release@sha256:abc123...
   ```
   Analyzes a specific payload version by digest.

4. **Analyze an early candidate release**:
   ```
   /ci:analyze-payload quay.io/openshift-release-dev/ocp-release:4.21.0-ec.3-x86_64
   ```
   Analyzes an early candidate (ec) release payload.

## Notes

- **OC CLI Required**: This command requires the OpenShift CLI (`oc`) to be installed and available in PATH
- **Network Access**: The command needs network access to pull payload metadata from the registry and query Sippy
- **Authentication**: 
  - **For CI payloads** (registry.ci.openshift.org): 
    - **REQUIRED**: `oc login` to the app.ci cluster
    - **REQUIRED**: `oc registry login` to authenticate with the registry
    - Visit https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/ and follow authentication steps
  - **For public payloads** (quay.io/openshift-release-dev): No authentication required
  - Sippy API queries do NOT require authentication
- **Payload Format**: The command works with standard OpenShift release payload images
- **Architecture Support**: Can analyze both single-architecture and multi-architecture payloads
- **Performance**: 
  - Payload metadata extraction takes a few seconds depending on network speed
  - Sippy PR queries are fast (typically < 5 seconds)
- **Image Pull**: The command does NOT pull the full payload image, only metadata is fetched
- **Sippy PR Query**: PR information is retrieved from Sippy API directly using the release tag
- **Results Storage**: All analysis results are stored in `.work/analyze-payload/{release-tag}/` directory for later reference
- **Markdown Report**: The main report is generated as `report.md` with a comprehensive components table and all payload information

## Error Handling

- **OC not installed**: Provide installation instructions for the user's platform
- **Image not found**: Verify the image reference is correct and accessible
- **Authentication required**: 
  - **For CI payloads**: Check `oc whoami` and `oc registry info` to verify authentication
  - If not authenticated, provide clear instructions:
    1. Run `oc login --server=https://api.ci.l2s4.p1.openshiftapps.com:6443` (get command from console)
    2. Run `oc registry login`
  - **For public payloads**: No authentication needed
  - Sippy API does not require authentication
- **Invalid payload format**: Verify the image is a valid OpenShift release payload
- **Network errors**: Check connectivity to the registry and Sippy, retry if appropriate
- **Sippy query timeout**: If Sippy query takes too long or fails, inform user and continue with payload metadata only
- **No PRs found**: If Sippy doesn't return PR information, display a message indicating PRs could not be retrieved

## Output Example

```
================================================================================
OPENSHIFT RELEASE PAYLOAD ANALYSIS
================================================================================
Payload Image: quay.io/openshift-release-dev/ocp-release:4.21.0-ec.3-x86_64

RELEASE INFORMATION:
  Version:        4.21.0-ec.3
  Digest:         sha256:e3a750749770f4435360852de7c566e370bef20ad90cdc1446e8ac84e4728e49
  Architecture:   amd64
  Created:        2025-11-19T02:38:41Z
  Total Images:   190

PULL REQUESTS INCLUDED IN PAYLOAD:
  Found 45 PR(s):
  
  1. [baremetal-installer, installer, installer-artifacts](https://github.com/openshift/installer/pull/10178)
     Description: rename "var-ostree-container.mount" to something more computer-friendly
     Bug: https://issues.redhat.com/browse/OCPBUGS-69876
     PR ID: 10178
     
  2. [cluster-config-api](https://github.com/openshift/api/pull/2479)
     Description: Add CompatibilityRequirement
     Bug: https://issues.redhat.com/browse/OCPCLOUD-3164
     PR ID: 2479
     
  3. [hypershift](https://github.com/openshift/hypershift/pull/6874)
     Description: feat(hostedcluster): implement service account signing key rotation
     Bug: https://issues.redhat.com/browse/CNTRLPLANE-2119
     PR ID: 6874
     
  [... additional PRs ...]

RESULTS STORED IN:
  .work/analyze-payload/4.21.0-ec.3/
    - report.md (main markdown report - includes components table at bottom)
    - payload-info.json (full payload metadata)
    - prs.json (PR information from Sippy)
    - prs.txt (human-readable PR list)

View the full report: .work/analyze-payload/4.21.0-ec.3/report.md
  (The report includes a complete components table with all 190 components)

================================================================================
```

## See Also

- `/container-image:inspect` - Inspect container image metadata
- `/container-image:compare` - Compare two container images
- `/ci:ask-sippy` - Query Sippy for payload status and rejection reasons
- [Sippy API Documentation](https://sippy.dptools.openshift.org/api/releases/pull_requests) - Direct API endpoint for PR queries
- OpenShift Release Documentation: https://docs.openshift.com/

