---
name: Generate CatalogSource Manifest
description: Generate a CatalogSource manifest for FBC operator testing
---

# Generate CatalogSource Manifest

This skill provides detailed implementation guidance for generating a CatalogSource manifest that points to FBC (File-Based Catalog) images built in Konflux.

## When to Use This Skill

Use this skill when you need to:
- Generate a CatalogSource manifest for an operator built in Konflux
- Create a manifest that makes operators available in the cluster's OperatorHub
- Implement the CatalogSource generation step in commands like `/fbc-art-images:catalog-source` or `/fbc-art-images:setup`

## Prerequisites

- **OCP version**: Must be in `X.Y` format (e.g., "4.20", "4.19")
- **Operator name**: Valid operator name (e.g., "amq-broker-rhel9", "advanced-cluster-management")

## Implementation Steps

### Step 1: Construct FBC Image URL

The FBC image URL follows a specific pattern in the art-fbc repository:

```
quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<ocp-version>__<operator-name>
```

**Pattern breakdown:**
- **Registry**: `quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc`
- **Tag format**: `ocp__<ocp-version>__<operator-name>` (note the double underscores)

**Example:**
- OCP version: `4.20`
- Operator: `advanced-cluster-management`
- Resulting URL: `quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.20__advanced-cluster-management`

### Step 2: Create Working Directory

Create a directory for storing generated manifests:

```bash
mkdir -p .work/fbc-art-images/<ocp-version>_<operator-name>/
```

**Notes:**
- Use underscore `_` to separate OCP version and operator name in directory name
- If the directory already exists, don't error (it's safe to reuse)
- This directory will contain all generated manifests for this operator/version combination

### Step 3: Generate CatalogSource YAML

Create the manifest file at:
```
.work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml
```

**Template:**
```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: test-<ocp-version>-<operator-name>-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: <fbc-image-url>
  displayName: <operator-name> Catalog (FBC)
  publisher: Red Hat
  updateStrategy:
    registryPoll:
      interval: 10m
```

**Field descriptions:**
- **name**: Format is `test-<ocp-version>-<operator-name>-catalog` (use hyphens between components)
- **namespace**: Always `openshift-marketplace` (where CatalogSources are deployed)
- **sourceType**: Always `grpc` for FBC images
- **image**: The FBC image URL constructed in Step 1
- **displayName**: Human-readable name shown in OperatorHub UI
- **publisher**: Always "Red Hat" for these operators
- **updateStrategy.registryPoll.interval**: Check for updates every 10 minutes

**Example manifest** (for amq-broker-rhel9 on OCP 4.20):
```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: test-4.20-amq-broker-rhel9-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.20__amq-broker-rhel9
  displayName: amq-broker-rhel9 Catalog (FBC)
  publisher: Red Hat
  updateStrategy:
    registryPoll:
      interval: 10m
```

### Step 4: Return Manifest Location

Return the path to the generated manifest:
```
.work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml
```

## Error Handling

### Invalid OCP Version Format
If the OCP version doesn't match `X.Y` format:
```
Error: Invalid OCP version format: '<provided-version>'
Expected format: X.Y (e.g., "4.20", "4.19", "4.18")
```

### Missing Operator Name
If operator name is empty or not provided:
```
Error: Operator name is required
Example operator names: "amq-broker-rhel9", "advanced-cluster-management", "kubernetes-nmstate-rhel9-operator"
```

### Working Directory Creation Failure
If unable to create the working directory:
```
Error: Failed to create working directory: .work/fbc-art-images/<ocp-version>_<operator-name>/
Check filesystem permissions and available disk space.
```

### File Write Failure
If unable to write the manifest file:
```
Error: Failed to write CatalogSource manifest to: .work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml
Check filesystem permissions and available disk space.
```

## Examples

### Example 1: AMQ Broker on OCP 4.20
**Input:**
- OCP version: `4.20`
- Operator name: `amq-broker-rhel9`

**Generated file:** `.work/fbc-art-images/4.20_amq-broker-rhel9/catalogsource.yaml`

**Content:**
```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: test-4.20-amq-broker-rhel9-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.20__amq-broker-rhel9
  displayName: amq-broker-rhel9 Catalog (FBC)
  publisher: Red Hat
  updateStrategy:
    registryPoll:
      interval: 10m
```

### Example 2: Advanced Cluster Management on OCP 4.19
**Input:**
- OCP version: `4.19`
- Operator name: `advanced-cluster-management`

**Generated file:** `.work/fbc-art-images/4.19_advanced-cluster-management/catalogsource.yaml`

**Content:**
```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: test-4.19-advanced-cluster-management-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.19__advanced-cluster-management
  displayName: advanced-cluster-management Catalog (FBC)
  publisher: Red Hat
  updateStrategy:
    registryPoll:
      interval: 10m
```

### Example 3: Kubernetes NMState on OCP 4.18
**Input:**
- OCP version: `4.18`
- Operator name: `kubernetes-nmstate-rhel9-operator`

**Generated file:** `.work/fbc-art-images/4.18_kubernetes-nmstate-rhel9-operator/catalogsource.yaml`

**Content:**
```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: test-4.18-kubernetes-nmstate-rhel9-operator-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.18__kubernetes-nmstate-rhel9-operator
  displayName: kubernetes-nmstate-rhel9-operator Catalog (FBC)
  publisher: Red Hat
  updateStrategy:
    registryPoll:
      interval: 10m
```

## Output Format

The skill should return:
- **File path**: Absolute or relative path to the generated manifest
- **Success message**: Confirmation that the manifest was created
- **Manifest content**: Display the generated YAML for user review

## Notes

- The CatalogSource name uses hyphens to separate components: `test-<ocp-version>-<operator-name>-catalog`
- The working directory uses underscore: `<ocp-version>_<operator-name>`
- The FBC image tag uses double underscores: `ocp__<ocp-version>__<operator-name>`
- All CatalogSources are deployed to the `openshift-marketplace` namespace
- The `grpc` sourceType is required for FBC-based catalogs
- The 10-minute poll interval ensures the catalog stays up-to-date with registry changes

## See Also

- Related skill: `generate-idms` - Generate IDMS manifests for registry mirroring
- Command: `/fbc-art-images:catalog-source` - User-facing command that uses this skill
- Command: `/fbc-art-images:setup` - Orchestrates both CatalogSource and IDMS generation
