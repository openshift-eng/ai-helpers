---
description: Generate IDMS manifest so that art-image-share mirrors would be used on the cluster for all operator related images
argument-hint: <ocp-version> <operator-name>
---

## Name
fbc-art-images:idms

## Synopsis
```
/fbc-art-images:idms <ocp-version> <operator-name>
```

## Description
The `fbc-art-images:idms` command generates an ImageDigestMirrorSet (IDMS) manifest for configuring registry mirroring to the art-image-share registry. This allows the cluster to pull operator images from the internal Red Hat art-image-share registry.

The IDMS configures mirroring for any related images referenced in the operator bundle to use mirror quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share.

**Note**: Applying an IDMS may trigger MachineConfig updates which will cause cluster nodes to restart sequentially.

## Implementation

### Step 1: Validate Inputs
- Verify `$1` (ocp-version) is provided and follows the format `X.Y` (e.g., "4.20")
- Verify `$2` (operator-name) is provided and is a valid operator name

### Step 2: Generate IDMS Manifest
- Invoke the **generate-idms** skill with the provided OCP version and operator name
- See detailed implementation: `plugins/fbc-art-images/skills/generate-idms/SKILL.md`
- The skill will:
  - Validate that `oras` and `jq` CLIs are installed
  - Detect oras version to use correct JSON field (`.manifests` vs `.referrers`)
  - Create the working directory (`.work/fbc-art-images/<ocp-version>_<operator-name>/`)
  - Discover related images from the FBC artifact using oras
  - Generate the IDMS manifest at `idms.yaml`
  - Generate `related-images-list.txt` with discovered images

### Step 3: Check for Existing IDMS
- Check if an IDMS with the same name already exists:
  ```bash
  oc get imagedigestmirrorset art-image-share-<ocp-version>-<operator-name> -o name 2>/dev/null
  ```
- If it exists, warn the user:
  ```
  Warning: An IDMS named 'art-image-share-<ocp-version>-<operator-name>' already exists on the cluster.

  You can:
  1. Skip applying (use existing IDMS)
  2. Replace existing IDMS
  3. View existing IDMS configuration
  ```

### Step 4: Display Manifest to User
- Show the generated manifest content
- Display the file path: `.work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml`
- Show discovered images from `related-images-list.txt`
- Warn about node restarts:
  ```
  IDMS manifest generated at:
  .work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml

  Discovered <N> related images for <operator-name>

  WARNING: Applying this IDMS will trigger MachineConfig updates.
  Cluster nodes will restart sequentially, which may take 20-30 minutes.

  Apply this manifest now? [y/n]
  ```

### Step 5: Apply Manifest (if requested)
- If user confirms, apply the manifest:
  ```bash
  oc apply -f .work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml
  ```
- Monitor MachineConfigPool status:
  ```bash
  oc get mcp
  ```
- Display guidance:
  ```text
  IDMS applied successfully!

  Monitor MachineConfigPool updates:
  oc get mcp

  Watch for nodes updating:
  oc get nodes

  The cluster will automatically update nodes in a rolling fashion.
  This typically takes 20-30 minutes for a standard cluster.
  ```

### Error Handling
- **Invalid OCP version**: Show error and supported format (X.Y)
- **Missing operator name**: Prompt user to provide operator name
- **oras not installed**: Guide user to install from https://oras.land/docs/installation
- **jq not installed**: Guide user to install jq
- **oras discover fails**: Check network connectivity, image URL, and quay.io access
- **No related images found**: The FBC image may not have attached artifacts or may be for a different OCP version
- **No cluster access**: Guide user to run `oc login`
- **IDMS already exists**: Provide options to view, replace, or skip
- **Apply failure**: Show error details and suggest manual review
- **MCP errors**: Guide user to check MachineConfigPool and node status

## Return Value
- **Success**: Displays manifest location and optionally applies it
- **Files created**:
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml` - IDMS manifest
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/related-images-list.txt` - List of discovered images
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/related-images.json` - Raw related images data (from oras)

## Examples

1. **Generate IDMS for AMQ Broker operator on OCP 4.20**:
   ```bash
   /fbc-art-images:idms 4.20 amq-broker-rhel9
   ```
   Output:
   ```text
   IDMS manifest generated at:
   .work/fbc-art-images/4.20_amq-broker-rhel9/idms.yaml

   WARNING: Applying this IDMS will trigger MachineConfig updates.
   Apply this manifest now? [y/n]
   ```

2. **Generate IDMS for Advanced Cluster Management on OCP 4.19**:
   ```bash
   /fbc-art-images:idms 4.19 advanced-cluster-management
   ```

3. **Generate IDMS for Kubernetes NMState operator on OCP 4.18**:
   ```bash
   /fbc-art-images:idms 4.18 kubernetes-nmstate-rhel9-operator
   ```

## Arguments
- $1: OCP version in X.Y format (e.g., "4.20", "4.19")
- $2: Operator name (e.g., "amq-broker-rhel9", "advanced-cluster-management", "kubernetes-nmstate-rhel9-operator")

## Notes
- **Prerequisites**: This command requires the `oras` CLI to be installed. Install from https://oras.land/docs/installation
- The IDMS is operator and version-specific, named: `art-image-share-<ocp-version>-<operator-name>`
- Each operator/version combination gets its own IDMS to avoid conflicts
- The IDMS only mirrors images discovered from the specific FBC image
- MachineConfigPool updates happen automatically after applying IDMS
- Nodes restart one at a time to minimize cluster disruption
- The related images are pulled from Konflux-attached artifacts on the FBC image

## See Also
- `/fbc-art-images:setup` - Complete setup (CatalogSource + IDMS)
- `/fbc-art-images:catalog-source` - Generate CatalogSource manifest
- `how-to-update-pull-secret.md` - FOR HUMAN USE ONLY: Instructions for configuring the pull-secret prerequisite
