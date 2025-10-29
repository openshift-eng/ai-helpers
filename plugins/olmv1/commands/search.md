# Search Extensions Command

You are helping the user discover available extensions across catalogs.

## Task

Search for extensions matching the provided keyword across available catalogs using the catalogd service API.

## Prerequisites

- Verify `jq` is installed (required for JSON parsing)
- Port-forwarding access to the catalogd-service in olmv1-system namespace

## Steps

1. **Verify catalogs are available**:
   ```bash
   kubectl get clustercatalogs
   ```

2. **Determine which catalogs to search**:
   - If `--catalog` flag provided: Search only that catalog
   - Otherwise: Search all available catalogs

3. **Set up port forwarding to catalogd service**:
   ```bash
   kubectl -n olmv1-system port-forward svc/catalogd-service 8443:443 &
   PORT_FORWARD_PID=$!
   sleep 2  # Give port-forward time to establish
   ```

4. **Query catalog(s) for matching packages**:
   For each catalog to search:
   ```bash
   # Fetch all catalog data and filter for matching packages
   curl -sk https://localhost:8443/catalogs/<catalog-name>/api/v1/all | \
     jq -s --arg keyword "<keyword>" '.[] |
       select(.schema == "olm.package") |
       select(.name | test($keyword; "i"))'
   ```

5. **Get package details**:
   For each matching package, gather:
   - Package name
   - Description
   - Default channel
   - Available channels (query olm.channel schema)
   - Latest version from default channel

   ```bash
   # Get channels for a package
   curl -sk https://localhost:8443/catalogs/<catalog-name>/api/v1/all | \
     jq -s --arg pkg "<package-name>" '.[] |
       select(.schema == "olm.channel") |
       select(.package == $pkg) |
       {name: .name, entries: .entries}'

   # Get bundles for a package
   curl -sk https://localhost:8443/catalogs/<catalog-name>/api/v1/all | \
     jq -s --arg pkg "<package-name>" '.[] |
       select(.schema == "olm.bundle") |
       select(.package == $pkg)'
   ```

6. **Clean up port forwarding**:
   ```bash
   kill $PORT_FORWARD_PID
   ```

7. **Format results**:
   For each matching extension show:
   - Name
   - Description (from package metadata)
   - Default channel (from package metadata)
   - Available channels (from channel query)
   - Source catalog
   - Latest version (from default channel entries)

8. **Provide installation hints**:
   Show example install command for found extensions.

## Error Handling

- If no catalogs exist, suggest adding one first with `/olmv1:catalog-add`
- If keyword matches nothing, suggest broader search terms
- If catalog specified doesn't exist, list available catalogs
- If `jq` is not installed, provide installation instructions
- If port-forwarding fails, check olmv1-system namespace and catalogd-service existence
- If catalog is not ready/unpacked, show catalog status and suggest waiting

## Implementation Notes

- Use `-k` flag with curl to skip TLS verification (catalogd uses self-signed cert)
- The catalog API endpoint format is: `https://localhost:8443/catalogs/<catalog-name>/api/v1/all`
- Three main schemas to query:
  - `olm.package`: Package metadata and default channel
  - `olm.channel`: Channel information and version entries
  - `olm.bundle`: Bundle/version details
- Port forwarding runs in background; ensure cleanup even on errors

## Example Output

```
Found 3 extensions matching "cert-manager":

1. cert-manager-operator
   Description: Certificate management for Kubernetes
   Catalog: operatorhubio
   Default Channel: stable
   Available Channels: stable, candidate
   Latest Version: 1.14.5

2. openshift-cert-manager-operator
   Description: OpenShift certificate management
   Catalog: certified
   Default Channel: stable-v1
   Latest Version: 1.13.0

3. cert-manager-community
   Description: Community cert-manager operator
   Catalog: community-operators
   Default Channel: alpha
   Latest Version: 1.15.0-alpha.1

Install example:
/olmv1:install cert-manager-operator --channel stable
```
