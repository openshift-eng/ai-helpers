---
description: Search for available operators (v0) or extensions (v1) in catalogs
argument-hint: [query] [--catalog <name>] [--version v0|v1]
---

## Name
olm:search

## Synopsis
```
/olm:search [query] [--catalog <name>] [--version v0|v1]
```

## Description
The `olm:search` command searches for available operators (OLM v0) or extensions (OLM v1) in catalog sources, helping you discover what can be installed.

**You must explicitly specify which OLM version to use** via:
- `--version` flag on this command, OR
- Setting the context with `/olm:use-version v0|v1`

## Implementation

### 1. Determine OLM Version

**See [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md) for complete logic.**

### 2. Branch to Version-Specific Implementation

---

## OLM v0 Implementation

### Synopsis (v0)
```
/olm:search [query] [--catalog <name>] [--exact] [--version v0]
```

### Steps

1. **Parse Arguments**:
   - `$1`: Query string (optional) - search term
   - `--catalog <name>`: Filter by specific CatalogSource
   - `--exact`: Only exact name matches
   - `--version v0`: OLM version

2. **Fetch PackageManifests**:
   ```bash
   if [ -n "{catalog}" ]; then
     PACKAGES=$(oc get packagemanifests -n openshift-marketplace -o json | \
       jq --arg cat "{catalog}" '.items[] | select(.status.catalogSource==$cat)')
   else
     PACKAGES=$(oc get packagemanifests -n openshift-marketplace -o json | jq '.items[]')
   fi
   ```

3. **Filter by Query**:
   ```bash
   if [ -n "{query}" ]; then
     if [ "{exact}" == "true" ]; then
       PACKAGES=$(echo "$PACKAGES" | jq --arg q "{query}" 'select(.metadata.name==$q)')
     else
       PACKAGES=$(echo "$PACKAGES" | jq --arg q "{query}" \
         'select(.metadata.name | test($q; "i")) or 
          select(.status.channels[0].currentCSVDesc.displayName | test($q; "i")) or
          select(.status.channels[0].currentCSVDesc.description | test($q; "i"))')
     fi
   fi
   ```

4. **Display Results**:
   ```bash
   echo "$PACKAGES" | jq -r '
     .metadata.name + "|" + 
     .status.catalogSource + "|" + 
     .status.defaultChannel + "|" + 
     (.status.channels[0].currentCSVDesc.displayName // "N/A") + "|" + 
     ((.status.channels[0].currentCSVDesc.description // "N/A") | .[0:80])' | \
   while IFS='|' read -r name catalog channel display desc; do
     echo "Name: $name"
     echo "  Catalog: $catalog"
     echo "  Channel: $channel"
     echo "  Display: $display"
     echo "  Description: $desc"
     echo ""
     echo "  Install: /olm:install $name --version v0"
     echo ""
   done
   ```

---

## OLM v1 Implementation

### Synopsis (v1)
```
/olm:search [query] [--catalog <name>] [--version v1]
```

### Steps

1. **Parse Arguments**:
   - `$1`: Query string (optional)
   - `--catalog <name>`: Filter by specific ClusterCatalog
   - `--version v1`: OLM version

2. **Check Prerequisites**:
   ```bash
   if ! kubectl get namespace olmv1-system &> /dev/null; then
     echo "❌ OLM v1 not installed"
     exit 1
   fi
   
   if ! kubectl get service catalogd-service -n olmv1-system &> /dev/null; then
     echo "❌ catalogd-service not found"
     exit 1
   fi
   ```

3. **Get ClusterCatalogs**:
   ```bash
   if [ -n "{catalog}" ]; then
     CATALOGS="{catalog}"
   else
     CATALOGS=$(kubectl get clustercatalogs --no-headers 2>/dev/null | awk '{print $1}')
   fi
   
   if [ -z "$CATALOGS" ]; then
     echo "No catalogs found"
     echo "Add a catalog: /olm:catalog add <name> <image> --version v1"
     exit 0
   fi
   ```

4. **Set up port forwarding to catalogd**:
   ```bash
   kubectl -n olmv1-system port-forward svc/catalogd-service 8443:443 &
   PORT_FORWARD_PID=$!
   sleep 2
   
   # Ensure cleanup on exit
   trap "kill $PORT_FORWARD_PID 2>/dev/null" EXIT
   ```

5. **Query each catalog**:
   ```bash
   for CATALOG in $CATALOGS; do
     echo "Searching catalog: $CATALOG"
     echo ""
     
     # Fetch all packages
     PACKAGES=$(curl -sk "https://localhost:8443/catalogs/$CATALOG/api/v1/all" | \
       jq -s '.[] | select(.schema == "olm.package")')
     
     # Filter by query if provided
     if [ -n "{query}" ]; then
       PACKAGES=$(echo "$PACKAGES" | jq --arg q "{query}" 'select(.name | test($q; "i"))')
     fi
     
     # Display each package
     echo "$PACKAGES" | jq -r '.name' | while read -r PKG_NAME; do
       # Get package details
       PKG_INFO=$(echo "$PACKAGES" | jq --arg name "$PKG_NAME" 'select(.name==$name)')
       DEFAULT_CHANNEL=$(echo "$PKG_INFO" | jq -r '.defaultChannel')
       DESCRIPTION=$(echo "$PKG_INFO" | jq -r '.description // "N/A"')
       
       # Get channels
       CHANNELS=$(curl -sk "https://localhost:8443/catalogs/$CATALOG/api/v1/all" | \
         jq -s --arg pkg "$PKG_NAME" '.[] | select(.schema == "olm.channel" and .package==$pkg) | .name' | tr '\n' ',' | sed 's/,$//')
       
       # Get latest version
       LATEST_VERSION=$(curl -sk "https://localhost:8443/catalogs/$CATALOG/api/v1/all" | \
         jq -s --arg pkg "$PKG_NAME" --arg ch "$DEFAULT_CHANNEL" \
         '.[] | select(.schema == "olm.channel" and .package==$pkg and .name==$ch) | .entries[0].name' | \
         grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
       
       echo "Name: $PKG_NAME"
       echo "  Catalog: $CATALOG"
       echo "  Default Channel: $DEFAULT_CHANNEL"
       echo "  Available Channels: $CHANNELS"
       echo "  Latest Version: ${LATEST_VERSION:-unknown}"
       echo "  Description: ${DESCRIPTION:0:80}"
       echo ""
       echo "  Install: /olm:install $PKG_NAME --version v1 --channel $DEFAULT_CHANNEL --namespace <namespace>"
       echo ""
     done
   done
   
   # Cleanup
   kill $PORT_FORWARD_PID 2>/dev/null
   ```

---

## Return Value

### OLM v0
- List of matching PackageManifests with install commands

### OLM v1
- List of matching packages from ClusterCatalogs with install commands

## Examples

### Example 1: Search all operators (v0)

```bash
/olm:use-version v0
/olm:search cert-manager
```

### Example 2: Search specific catalog (v1)

```bash
/olm:search postgres --catalog operatorhubio --version v1
```

### Example 3: List all available (v0)

```bash
/olm:search --version v0
```

## Arguments

- **$1** (query): Search term (optional)
- **--catalog <name>**: Filter by catalog
- **--version v0|v1**: OLM version (optional if context set)
- **--exact**: Exact match only (v0 only)

## Notes

- **v0**: Searches PackageManifests in openshift-marketplace
- **v1**: Queries ClusterCatalogs via catalogd API, requires port-forwarding
- Empty query lists all available packages
- Use install command shown in output to install
