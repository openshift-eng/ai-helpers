---
description: Generate CatalogSource manifest for testing operators built in Konflux
argument-hint: <ocp-version> <operator-name>
---

## Name
fbc-art-images:catalog-source

## Synopsis
```bash
/fbc-art-images:catalog-source <ocp-version> <operator-name>
```

## Description
The `fbc-art-images:catalog-source` command generates a CatalogSource manifest for testing operators built in FBC (File-Based Catalog) by Konflux. This command creates only the CatalogSource manifest, allowing users to have fine-grained control over the setup process.

The CatalogSource points to the FBC image in the OpenShift release registry, making the operator available in the cluster's OperatorHub.

## Implementation

### Step 1: Validate Inputs
- Verify `$1` (ocp-version) is provided and follows the format `X.Y` (e.g., "4.18")
- Verify `$2` (operator-name) is provided and is a valid operator name (e.g, "kubernetes-nmstate-rhel9-operator")

### Step 2: Generate CatalogSource Manifest
- Invoke the **generate-catalog-source** skill with the provided OCP version and operator name
- See detailed implementation: `plugins/fbc-art-images/skills/generate-catalog-source/SKILL.md`
- The skill will:
  - Construct the FBC image URL
  - Create the working directory (`.work/fbc-art-images/<ocp-version>_<operator-name>/`)
  - Generate the CatalogSource manifest at `catalogsource.yaml`

### Step 3: Display Manifest to User
- Show the generated manifest content
- Display the file path: `.work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml`
- Ask if the user wants to apply the manifest:
  ```text
  CatalogSource manifest generated at:
  .work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml

  Apply this manifest now? [y/n]
  ```

### Step 4: Apply Manifest (if requested)
- If user confirms, apply the manifest:
  ```bash
  oc apply -f .work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml
  ```
- Wait for the CatalogSource to become ready:
  ```bash
  oc wait --for=condition=Ready catalogsource/test-<ocp-version>-<operator-name>-catalog -n openshift-marketplace --timeout=5m
  ```
- Display success message:
  ```text
  CatalogSource applied successfully!

  Check the status:
  oc get catalogsource test-<ocp-version>-<operator-name>-catalog -n openshift-marketplace

  View available operators:
  oc get packagemanifests -n openshift-marketplace | grep test-<ocp-version>-<operator-name>-catalog
  ```

### Error Handling
- **Invalid OCP version**: Show error and supported format (X.Y)
- **Missing operator name**: Prompt user to provide operator name
- **No cluster access**: Guide user to run `oc login`
- **CatalogSource not ready**: Show pod logs and troubleshooting steps
- **Image pull errors**: Suggest checking pull-secret and IDMS configuration

## Return Value
- **Success**: Displays manifest location and optionally applies it
- **File created**: `.work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml`

## Examples

1. **Generate CatalogSource for AMQ broker on OCP 4.20**:
   ```bash
   /fbc-art-images:catalog-source 4.20 amq-broker-rhel9
   ```
   Output:
   ```text
   CatalogSource manifest generated for amq-broker-rhel9 (OCP 4.20)
   File: .work/fbc-art-images/4.20_amq-broker-rhel9/catalogsource.yaml

   Apply this manifest now? [y/n]
   ```

2. **Generate CatalogSource for Compliance Operator on OCP 4.17**:
   ```bash
   /fbc-art-images:catalog-source 4.17 compliance-operator
   ```

3. **Generate CatalogSource for ServiceMesh on OCP 4.19**:
   ```bash
   /fbc-art-images:catalog-source 4.19 servicemeshoperator
   ```

## Arguments
- $1: OCP version in X.Y format (e.g., "4.20", "4.19")
- $2: Operator name (e.g., "vertical-pod-autoscaler", "compliance-operator")

## See Also
- `/fbc-art-images:setup` - Complete setup (CatalogSource + IDMS)
- `/fbc-art-images:idms` - Generate IDMS manifest
- `how-to-update-pull-secret.md` - FOR HUMAN USE ONLY: Instructions for configuring the pull-secret prerequisite
