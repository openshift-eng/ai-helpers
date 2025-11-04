---
description: Manage catalog sources for discovering and installing operators
argument-hint: <list|add|remove|refresh|status> [arguments]
---

## Name
olm:catalog

## Synopsis
```
/olm:catalog list
/olm:catalog add <name> <image> [--namespace=openshift-marketplace]
/olm:catalog remove <name> [--namespace=openshift-marketplace]
/olm:catalog refresh <name> [--namespace=openshift-marketplace]
/olm:catalog status <name> [--namespace=openshift-marketplace]
```

## Description
The `olm:catalog` command manages catalog sources for operator discovery and installation. Catalog sources provide the list of operators available for installation in the cluster.

This command helps you:
- List all available catalog sources and their health status
- Add custom or private catalog sources
- Remove catalog sources
- Refresh catalog sources to get latest operator updates

## Implementation

### Subcommand: list

1. **Get All CatalogSources**:
   ```bash
   oc get catalogsource -n openshift-marketplace -o json
   ```

2. **Parse CatalogSource Data**:
   For each catalog, extract:
   - Name: `.metadata.name`
   - Display Name: `.spec.displayName`
   - Publisher: `.spec.publisher`
   - Source Type: `.spec.sourceType` (grpc, configmap, etc.)
   - Image: `.spec.image` (for grpc type)
   - Connection State: `.status.connectionState.lastObservedState`
   - Last Updated: `.status.connectionState.lastUpdatedTime`
   - Number of Operators: Count from PackageManifests with this catalog

3. **Get Catalog Pod Status**:
   ```bash
   oc get pods -n openshift-marketplace -l olm.catalogSource={catalog-name}
   ```

4. **Format Output**:
   ```
   ═══════════════════════════════════════════════════════════
   CATALOG SOURCES
   ═══════════════════════════════════════════════════════════
   
   NAME                     STATUS    OPERATORS  LAST UPDATED  SOURCE TYPE
   redhat-operators         READY     150        2h ago        grpc
   certified-operators      READY     45         3h ago        grpc
   community-operators      READY     200        1h ago        grpc
   redhat-marketplace       READY     30         4h ago        grpc
   custom-catalog           FAILED    0          -             grpc
   
   ═══════════════════════════════════════════════════════════
   DETAILS
   ═══════════════════════════════════════════════════════════
   
   redhat-operators:
     Display Name: Red Hat Operators
     Publisher: Red Hat
     Image: registry.redhat.io/redhat/redhat-operator-index:v4.20
     Pod: redhat-operators-abc123 (Running)
   
   custom-catalog (FAILED):
     Display Name: Custom Catalog
     Publisher: My Company
     Image: registry.example.com/custom-catalog:latest
     Pod: custom-catalog-xyz789 (CrashLoopBackOff)
     Error: ImagePullBackOff
     
     To troubleshoot:
     /olm:catalog status custom-catalog
   ```

### Subcommand: add

1. **Parse Arguments**:
   - `name`: Catalog source name (required)
   - `image`: Catalog image (required)
   - `--namespace`: Target namespace (default: openshift-marketplace)
   - `--display-name`: Display name (optional)
   - `--publisher`: Publisher name (optional)

2. **Validate Image**:
   - Check if image format is valid
   - Optionally test image accessibility (if possible)

3. **Create CatalogSource Manifest**:
   ```yaml
   apiVersion: operators.coreos.com/v1alpha1
   kind: CatalogSource
   metadata:
     name: {name}
     namespace: {namespace}
   spec:
     sourceType: grpc
     image: {image}
     displayName: {display-name}
     publisher: {publisher}
     updateStrategy:
       registryPoll:
         interval: 30m
   ```

4. **Apply CatalogSource**:
   ```bash
   oc apply -f /tmp/catalogsource-{name}.yaml
   ```

5. **Wait for CatalogSource to be Ready**:
   ```bash
   oc wait --for=condition=READY catalogsource/{name} -n {namespace} --timeout=300s
   ```

6. **Verify Pod is Running**:
   ```bash
   oc get pods -n {namespace} -l olm.catalogSource={name}
   ```

7. **Display Result**:
   ```
   ✓ Catalog source added: {name}
   
   Name: {name}
   Namespace: {namespace}
   Image: {image}
   Status: READY
   Pod: {pod-name} (Running)
   
   To search operators: /olm:search --catalog {name}
   ```

### Subcommand: remove

1. **Parse Arguments**:
   - `name`: Catalog source name (required)
   - `--namespace`: Namespace (default: openshift-marketplace)

2. **Check if CatalogSource Exists**:
   ```bash
   oc get catalogsource {name} -n {namespace} --ignore-not-found
   ```

3. **Check for Operators Using This Catalog**:
   ```bash
   oc get subscription --all-namespaces -o json | \
     jq -r '.items[] | select(.spec.source=="{name}") | "\(.metadata.namespace)/\(.metadata.name)"'
   ```

4. **Display Warning** (if operators found):
   ```
   WARNING: The following operators are using this catalog:
   - namespace-1/operator-1
   - namespace-2/operator-2
   
   Removing this catalog will prevent these operators from receiving updates.
   
   Do you want to continue? (yes/no)
   ```

5. **Delete CatalogSource**:
   ```bash
   oc delete catalogsource {name} -n {namespace}
   ```

6. **Wait for Pod to be Deleted**:
   ```bash
   oc wait --for=delete pod -l olm.catalogSource={name} -n {namespace} --timeout=60s
   ```

7. **Display Result**:
   ```
   ✓ Catalog source removed: {name}
   ```

### Subcommand: refresh

1. **Parse Arguments**:
   - `name`: Catalog source name (required)
   - `--namespace`: Namespace (default: openshift-marketplace)

2. **Get Current CatalogSource**:
   ```bash
   oc get catalogsource {name} -n {namespace} -o json
   ```

3. **Trigger Refresh by Deleting Pod**:
   ```bash
   oc delete pod -n {namespace} -l olm.catalogSource={name}
   ```
   - This forces OLM to recreate the pod and re-fetch catalog data

4. **Wait for New Pod to be Ready**:
   ```bash
   oc wait --for=condition=Ready pod -l olm.catalogSource={name} -n {namespace} --timeout=300s
   ```

5. **Verify Catalog is Updated**:
   ```bash
   oc get catalogsource {name} -n {namespace} -o json | \
     jq -r '.status.connectionState.lastUpdatedTime'
   ```

6. **Display Result**:
   ```
   ✓ Catalog source refreshed: {name}
   
   Last Updated: {timestamp}
   Status: READY
   Pod: {pod-name} (Running)
   
   New operators may now be available: /olm:search --catalog {name}
   ```

### Subcommand: status

1. **Parse Arguments**:
   - `name`: Catalog source name (required)
   - `--namespace`: Namespace (default: openshift-marketplace)

2. **Get CatalogSource Details**:
   ```bash
   oc get catalogsource {name} -n {namespace} -o json
   ```

3. **Get Pod Details**:
   ```bash
   oc get pods -n {namespace} -l olm.catalogSource={name} -o json
   ```

4. **Get Recent Events**:
   ```bash
   oc get events -n {namespace} --field-selector involvedObject.name={name} --sort-by='.lastTimestamp'
   ```

5. **Count Available Operators**:
   ```bash
   oc get packagemanifests -n openshift-marketplace -o json | \
     jq -r '.items[] | select(.status.catalogSource=="{name}") | .metadata.name' | wc -l
   ```

6. **Verify Catalog Connectivity**:
   - Check if catalog is serving content by verifying PackageManifest count > 0
   - If count is 0 but pod is Running, indicates connectivity or catalog index issues
   - Review catalog pod logs for gRPC errors, image pull issues, or index corruption:
     ```bash
     oc logs -n {namespace} {catalog-pod-name}
     ```

7. **Format Comprehensive Status Report**:
   ```
   ═══════════════════════════════════════════════════════════
   CATALOG SOURCE STATUS: {name}
   ═══════════════════════════════════════════════════════════
   
   General Information:
     Name: {name}
     Namespace: {namespace}
     Display Name: {display-name}
     Publisher: {publisher}
     Source Type: {source-type}
     Image: {image}
   
   Connection Status:
     State: {state} (READY | CONNECTING | CONNECTION_FAILED)
     Last Updated: {timestamp}
     Last Successful: {timestamp}
   
   Pod Status:
     Name: {pod-name}
     Status: {status} (Running | CrashLoopBackOff | ImagePullBackOff)
     Ready: {ready-containers}/{total-containers}
     Restarts: {restart-count}
     Age: {age}
   
   Catalog Content:
     Operators Available: {count}
   
   [If issues detected:]
   ⚠️  Issues Detected:
     - Pod in CrashLoopBackOff
     - Last update: 24h ago (stale)
     - Connection state: CONNECTION_FAILED
   
   Recent Events:
     {timestamp} Warning: Failed to pull image
     {timestamp} Warning: Back-off restarting failed container
   
   Troubleshooting Steps:
     1. Check pod logs: oc logs -n {namespace} {pod-name}
     2. Check image accessibility
     3. Refresh catalog: /olm:catalog refresh {name}
     4. Verify network connectivity (for disconnected environments)
   
   Related Commands:
     - Refresh: /olm:catalog refresh {name}
     - List operators: /olm:search --catalog {name}
   ```

## Return Value
- **list**: Table of all catalog sources with status
- **add**: Confirmation of added catalog with details
- **remove**: Confirmation of removed catalog
- **refresh**: Confirmation of refresh with updated timestamp
- **status**: Comprehensive status report for specific catalog

## Examples

1. **List all catalog sources**:
   ```
   /olm:catalog list
   ```

2. **Add custom catalog**:
   ```
   /olm:catalog add my-catalog registry.example.com/my-catalog:v1.0
   ```

3. **Add catalog with metadata**:
   ```
   /olm:catalog add my-catalog registry.example.com/catalog:latest \
     --display-name="My Custom Catalog" \
     --publisher="My Company"
   ```

4. **Remove catalog**:
   ```
   /olm:catalog remove my-catalog
   ```

5. **Refresh catalog to get latest operators**:
   ```
   /olm:catalog refresh redhat-operators
   ```

6. **Check catalog health**:
   ```
   /olm:catalog status custom-catalog
   ```

7. **Add catalog for disconnected environment**:
   ```
   /olm:catalog add disconnected-operators \
     mirror-registry.local:5000/olm/redhat-operators:v4.20 \
     --namespace=openshift-marketplace
   ```

## Arguments

### list
No arguments required.

### add
- **name** (required): Name for the catalog source
- **image** (required): Container image containing the catalog
- **--namespace**: Target namespace (default: openshift-marketplace)
- **--display-name**: Human-readable display name
- **--publisher**: Publisher/organization name

### remove
- **name** (required): Name of the catalog source to remove
- **--namespace**: Namespace (default: openshift-marketplace)

### refresh
- **name** (required): Name of the catalog source to refresh
- **--namespace**: Namespace (default: openshift-marketplace)

### status
- **name** (required): Name of the catalog source to check
- **--namespace**: Namespace (default: openshift-marketplace)

## Troubleshooting

- **Catalog pod failing**:
  ```bash
  # Check pod logs
  oc logs -n openshift-marketplace {catalog-pod-name}
  
  # Check image pull issues
  oc describe pod -n openshift-marketplace {catalog-pod-name}
  ```

- **No operators showing up**:
  ```bash
  # Verify catalog is ready
  /olm:catalog status {catalog-name}
  
  # Check PackageManifests
  oc get packagemanifests -n openshift-marketplace
  ```

- **Image pull errors (disconnected environment)**:
  - Verify image registry is accessible
  - Check pull secrets are configured
  - Ensure image has been mirrored correctly

- **Stale catalog data**:
  ```bash
  # Force refresh
  /olm:catalog refresh {catalog-name}
  ```

- **Connection failures**:
  ```bash
  # Check catalog source definition
  oc get catalogsource {catalog-name} -n openshift-marketplace -o yaml
  
  # Run cluster diagnostics
  /olm:diagnose --cluster
  ```

## Related Commands

- `/olm:search` - Search for operators in catalogs
- `/olm:install` - Install operators from catalogs
- `/olm:diagnose` - Diagnose catalog health issues

## Additional Resources
- [Building Catalog Images with opm](https://olm.operatorframework.io/docs/tasks/creating-catalog-from-index/)
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)


