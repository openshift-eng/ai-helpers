---
description: Search for available operators in catalog sources
argument-hint: [query] [--catalog <catalog-name>]
---

## Name
olm:search

## Synopsis
```
/olm:search [query] [--catalog <catalog-name>]
```

## Description
The `olm:search` command searches for available operators in the cluster's catalog sources (OperatorHub). It helps you discover operators that can be installed, showing their names, descriptions, versions, channels, and catalog sources.

This command helps you:
- Find operators by name, description, or keywords
- Discover what operators are available for installation
- View operator details before installing
- Check available versions and channels
- Identify which catalog source contains a specific operator

The command searches across all available catalog sources (redhat-operators, certified-operators, community-operators, redhat-marketplace, and custom catalogs) and presents results in an easy-to-read format.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Query string (optional) - Search term for filtering operators
     - If not provided, lists all available operators
     - Can be partial name, keyword, or description
   - `$2+`: Flags (optional):
     - `--catalog <catalog-name>`: Limit search to specific catalog source
     - `--exact`: Only show exact name matches
     - `--installed`: Show only installed operators (combination with /olm:list)

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - If not installed or not authenticated, provide clear instructions

3. **Fetch Catalog Data**:
   - Get all PackageManifests from openshift-marketplace:
     ```bash
     oc get packagemanifests -n openshift-marketplace -o json
     ```
   - If `--catalog` flag is specified, filter by catalog source:
     ```bash
     oc get packagemanifests -n openshift-marketplace -o json | jq '.items[] | select(.status.catalogSource=="{catalog-name}")'
     ```

4. **Parse PackageManifest Data**:
   - For each PackageManifest, extract:
     - Name: `.metadata.name`
     - Display Name: `.status.channels[0].currentCSVDesc.displayName`
     - Description: `.status.channels[0].currentCSVDesc.description`
     - Provider: `.status.provider.name`
     - Catalog Source: `.status.catalogSource`
     - Catalog Namespace: `.status.catalogSourceNamespace`
     - Default Channel: `.status.defaultChannel`
     - All Channels: `.status.channels[].name`
     - Latest Version: `.status.channels[] | select(.name==.status.defaultChannel) | .currentCSVDesc.version`
     - Categories: `.status.channels[0].currentCSVDesc.annotations["categories"]`
     - Capabilities: `.status.channels[0].currentCSVDesc.annotations["capabilities"]`

5. **Apply Search Filter** (if query provided):
   - Case-insensitive search across:
     - Operator name (`.metadata.name`)
     - Display name (`.status.channels[0].currentCSVDesc.displayName`)
     - Description (`.status.channels[0].currentCSVDesc.description`)
     - Provider name (`.status.provider.name`)
     - Categories
   - If `--exact` flag, only match exact operator names

6. **Sort Results**:
   - Primary sort: By catalog source (redhat-operators first, then certified, community, etc.)
   - Secondary sort: By operator name alphabetically

7. **Format Search Results**:
   
   **A. Summary Header**
   ```
   Found X operators matching "{query}"
   ```
   
   **B. Results List**
   For each operator:
   ```
   ┌─────────────────────────────────────────────────────────────
   │ cert-manager-operator for Red Hat OpenShift
   ├─────────────────────────────────────────────────────────────
   │ Name:        openshift-cert-manager-operator
   │ Provider:    Red Hat
   │ Catalog:     redhat-operators
   │ Default:     stable-v1
   │ Channels:    stable-v1, tech-preview-v1.13
   │ Version:     v1.13.1
   │ Categories:  Security
   │ 
   │ Description: Manages the lifecycle of TLS certificates...
   │ 
   │ Install:     /olm:install openshift-cert-manager-operator
   └─────────────────────────────────────────────────────────────
   ```

8. **Group by Catalog** (optional, for better readability):
   ```
   ═════════════════════════════════════════════════════════════
   RED HAT OPERATORS (3)
   ═════════════════════════════════════════════════════════════
   
   [List of operators from redhat-operators]
   
   ═════════════════════════════════════════════════════════════
   CERTIFIED OPERATORS (1)
   ═════════════════════════════════════════════════════════════
   
   [List of operators from certified-operators]
   
   ═════════════════════════════════════════════════════════════
   COMMUNITY OPERATORS (2)
   ═════════════════════════════════════════════════════════════
   
   [List of operators from community-operators]
   ```

9. **Provide Installation Guidance**:
   - For each operator, show ready-to-use install command:
     ```
     To install: /olm:install {operator-name}
     ```
   - For operators with specific channel recommendations, note them

10. **Handle No Results**:
    - If no operators match the query:
      ```
      No operators found matching "{query}"
      
      Suggestions:
      - Try a broader search term
      - List all available operators: /olm:search
      - Check specific catalog: /olm:search {query} --catalog redhat-operators
      ```

11. **Show Popular/Recommended Operators** (if no query provided):
    - Highlight commonly used operators:
      - cert-manager
      - external-secrets-operator
      - OpenShift Pipelines
      - OpenShift GitOps
      - Service Mesh
      - etc.

## Return Value
- **Success**: List of matching operators with detailed information
- **No Results**: Message indicating no matches with suggestions
- **Error**: Connection or permission error with troubleshooting guidance
- **Format**:
  - Summary of search results
  - Detailed operator information cards
  - Installation commands for each operator
  - Grouped by catalog source

## Examples

1. **Search for cert-manager operator**:
   ```
   /olm:search cert-manager
   ```

2. **Search for secrets-related operators**:
   ```
   /olm:search secrets
   ```
   Output listing multiple operators related to secrets management.

3. **List all operators** (no query):
   ```
   /olm:search
   ```

4. **Search in specific catalog**:
   ```
   /olm:search prometheus --catalog community-operators
   ```
   Output showing only Prometheus-related operators from community-operators catalog.

5. **Exact name match**:
   ```
   /olm:search external-secrets-operator --exact
   ```
   Output showing only the exact match for external-secrets-operator.

6. **Search for operators by category** (e.g., security):
   ```
   /olm:search security
   ```
   Output listing all security-related operators.

## Arguments
- **$1** (query): Search term to filter operators (optional)
  - If not provided, lists all available operators (may be very long)
  - Searches across name, display name, description, provider
  - Case-insensitive partial matching
  - Example: "cert", "secrets", "security", "monitoring"
- **$2+** (flags): Optional flags
  - `--catalog <catalog-name>`: Limit search to specific catalog
    - Values: "redhat-operators", "certified-operators", "community-operators", "redhat-marketplace", or custom catalog name
  - `--exact`: Only show exact name matches (no partial matching)
  - `--installed`: Show only operators that are currently installed


## Troubleshooting

- **No operators found**: 
  - Verify catalog sources are available:
    ```bash
    oc get catalogsources -n openshift-marketplace
    ```
  - Check if catalog sources are healthy:
    ```bash
    oc get pods -n openshift-marketplace
    ```
- **Slow search**:
  - Use more specific search terms
  - Search in specific catalog: `--catalog redhat-operators`
- **Incomplete information**:
  - Some operators may have limited metadata in their PackageManifest
- **Permission denied**:
  - Ensure you can read PackageManifests:
    ```bash
    oc auth can-i list packagemanifests -n openshift-marketplace
    ```

## Related Commands

- `/olm:install <operator-name>` - Install an operator found in search results
- `/olm:list` - List installed operators
- `/olm:status <operator-name>` - Check status of an installed operator

## Additional Resources

- [OperatorHub.io](https://operatorhub.io/) - Browse operators online
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)

