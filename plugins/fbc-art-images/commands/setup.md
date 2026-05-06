---
description: Generate CatalogSource, IDMS, and configure pull-secret for FBC testing
argument-hint: <ocp-version> <operator-name>
---

## Name
fbc-art-images:setup

## Synopsis
```bash
/fbc-art-images:setup <ocp-version> <operator-name>
```

## Description
The `fbc-art-images:setup` command automates the setup process for testing operators built in FBC (File-Based Catalog) by Konflux. It generates all necessary Kubernetes manifests and updates the cluster configuration to enable testing with art-image-share registry images.

This command orchestrates two key operations:
1. Creates a CatalogSource manifest pointing to the FBC image
2. Generates an IDMS (ImageDigestMirrorSet) manifest for registry mirroring

**Prerequisites**: The cluster pull-secret must be configured with art-image-share credentials before running this command. See `how-to-update-pull-secret.md` in the plugin directory for detailed instructions (FOR HUMAN USE ONLY).

The command is designed to streamline the workflow for OpenShift engineers testing operator releases.

## Implementation

### Step 1: Validate Inputs and Prerequisites
- Verify `$1` (ocp-version) is provided and follows the format `X.Y` (e.g., "4.18")
- Verify `$2` (operator-name) is provided and is a valid operator name
- Confirm the user has cluster access by checking `oc whoami`
- **Check pull-secret prerequisite**: Verify that the cluster's `pull-secret` contains a token that allows pulling images from `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share` 
  - If it doesn't exist, show error:
    ```text
    Error: Pull-secret doesn't have auth credentials for `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share`
    Before using this plugin, you must configure the art-image-share pull-secret.
    See how-to-update-pull-secret.md in the plugin directory for detailed instructions.
    ```
  - Exit immediatly if pull-secret verification doesn't contain that token
- Check if `oras` CLI is installed:
  ```bash
  which oras
  ```
- If `oras` not installed, guide the user to install it from [`https://oras.land/docs/installation`](https://oras.land/docs/installation)
- Check if `jq` is installed:
  ```bash
  which jq
  ```

### Step 2: Generate CatalogSource Manifest
- Invoke the **generate-catalog-source** skill with the provided OCP version and operator name
- See detailed implementation: `plugins/fbc-art-images/skills/generate-catalog-source/SKILL.md`
- The skill will:
  - Construct the FBC image URL
  - Create the working directory (`.work/fbc-art-images/<ocp-version>_<operator-name>/`)
  - Generate the CatalogSource manifest at `catalogsource.yaml`

### Step 3: Generate IDMS Manifest
- Invoke the **generate-idms** skill with the provided OCP version and operator name
- See detailed implementation: `plugins/fbc-art-images/skills/generate-idms/SKILL.md`
- The skill will:
  - Validate that `oras` and `jq` CLIs are installed
  - Detect oras version to use correct JSON field (`.manifests` vs `.referrers`)
  - Discover related images from the FBC artifact using oras
  - Generate the IDMS manifest at `idms.yaml`
  - Generate `related-images-list.txt` with discovered images
- Display discovered images to user

### Step 4: Verify Pull-Secret
- Fetch the current pull-secret from the cluster:
  ```bash
  oc get secret/pull-secret -n openshift-config -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d > .work/fbc-art-images/pull-secret.json
  ```
- Check if quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share credentials already exist in the pull-secret
- If credentials don't exist, prompt the user:
  ```text
  To access quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share repository, you need to add credentials to the pull-secret.
```
  Display instructions from `how-to-update-pull-secret.md`

### Step 5: Present Manifests to User
- Display the generated manifests to the user
- Show file locations:
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml`
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml`
  - `.work/fbc-art-images/pull-secret.yaml`
- Ask the user if they want to apply the manifests:
  ```text
  Generated manifests are ready. Would you like to:
  1. Apply all manifests now
  2. Review manifests before applying
  3. Only generate (don't apply)
  ```

### Step 6: Apply Manifests (if requested)
- If user chooses to apply, execute:
  ```bash
  oc apply -f .work/fbc-art-images/pull-secret.yaml
  oc apply -f .work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml
  oc apply -f .work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml
  ```
- Wait for CatalogSource to be ready:
  ```bash
  oc wait --for=condition=Ready catalogsource/test-<ocp-version>-<operator-name>-catalog -n openshift-marketplace --timeout=5m
  ```
- Display success message with next steps:
  ```text
  Setup complete! The CatalogSource is ready.

  Next steps:
  1. Check available operators: oc get packagemanifests -n openshift-marketplace
  2. Create a Subscription to install your operator
  3. Monitor MachineConfig updates (IDMS may trigger node restarts)
  ```

### Error Handling
- **No cluster access**: Prompt user to login with `oc login`
- **Invalid OCP version**: Show supported format (X.Y)
- **Missing pull-secret prerequisite**: Display configuration instructions from `how-to-update-pull-secret.md`
- **CatalogSource generation errors**: See detailed error handling in `plugins/fbc-art-images/skills/generate-catalog-source/SKILL.md`
- **IDMS generation errors**: See detailed error handling in `plugins/fbc-art-images/skills/generate-idms/SKILL.md`
  - Includes: oras/jq not installed, oras version differences, discovery failures, no related images found
- **Failed manifest apply**: Show error and suggest manual application
- **CatalogSource not ready**: Show troubleshooting tips (check image pull, check logs, verify pull-secret)

## Return Value
- **Success**: Displays manifest locations and application status
- **Files created**:
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml`
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml`
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/related-images-list.txt` (discovered images)
  - `.work/fbc-art-images/<ocp-version>_<operator-name>/related-images.json` (raw oras data)

## Examples

1. **Basic usage for OpenShift 4.20 with AMQ Broker operator**:
   ```bash
   /fbc-art-images:setup 4.20 amq-broker-rhel9
   ```
   Output:
   ```text
   Generated manifests for amq-broker-rhel9 on OCP 4.20:
   - CatalogSource: .work/fbc-art-images/4.20_amq-broker-rhel9/catalogsource.yaml
   - IDMS: .work/fbc-art-images/4.20_amq-broker-rhel9/idms.yaml

   Apply manifests? [y/n]
   ```

2. **Setup for OCP 4.19 with Advanced Cluster Management**:
   ```bash
   /fbc-art-images:setup 4.19 advanced-cluster-management
   ```

3. **Setup for OCP 4.18 with Kubernetes NMState operator**:
   ```bash
   /fbc-art-images:setup 4.18 kubernetes-nmstate-rhel9-operator
   ```

## Arguments
- $1: OCP version in X.Y format (e.g., "4.20", "4.19")
- $2: Operator name (e.g., "amq-broker-rhel9", "advanced-cluster-management", "kubernetes-nmstate-rhel9-operator")

## See Also
- `/fbc-art-images:catalog-source` - Generate CatalogSource manifest
- `/fbc-art-images:idms` - Generate IDMS manifest
- `how-to-update-pull-secret.md` - Instructions for configuring the pull-secret prerequisite
