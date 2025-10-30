# Upgrade Extension Command

You are helping the user upgrade an installed extension using OLM v1.

## Task

Upgrade an extension to a new version or channel using various upgrade strategies.

## Steps

1. **Verify extension is installed**:
   ```bash
   kubectl get clusterextension <extension-name>
   ```

2. **Get current version/channel**:
   ```bash
   kubectl get clusterextension <extension-name> -o jsonpath='{.status.resolution}'
   ```

3. **Determine upgrade strategy**:
   - **Channel-based**: Switch or update to latest in channel
   - **Version-specific**: Upgrade to exact version
   - **Version range**: Update version constraint range
   - **Z-stream**: Stay within minor version (e.g., ~1.14.0)

4. **Validate upgrade path**:
   - Check if target version/channel exists
   - Verify upgrade is supported (no major version skips if restricted)
   - Check for breaking changes

5. **Update ClusterExtension**:
   ```bash
   kubectl patch clusterextension <extension-name> --type=merge -p '
   spec:
     source:
       catalog:
         version: "<new-version-constraint>"
         channel: "<new-channel>"
   '
   ```

6. **Monitor upgrade process**:
   ```bash
   kubectl get clusterextension <extension-name> -w
   ```

7. **Verify upgrade completion**:
   - Check new version is installed
   - Verify all pods are ready
   - Check for any errors or warnings

8. **Report results**:
   - Old version → New version
   - Upgrade status
   - Any required manual steps
   - Rollback instructions if needed

## Upgrade Strategies

### Channel-Based Upgrade
```yaml
spec:
  source:
    catalog:
      channel: "stable-v2"  # Switch to new channel
```

### Version Pinning
```yaml
spec:
  source:
    catalog:
      version: "2.0.0"  # Exact version
```

### Version Range
```yaml
spec:
  source:
    catalog:
      version: ">=2.0.0 <3.0.0"  # Allow minor updates
```

### Z-Stream Upgrade
```yaml
spec:
  source:
    catalog:
      version: "~1.14.0"  # Stay in 1.14.x
```

## Error Handling

- Extension not found: Confirm extension name
- Version doesn't exist: Show available versions
- Upgrade forbidden: Check upgrade constraints
- Upgrade failed: Parse error and suggest rollback
- Breaking changes: Warn user and require confirmation

## Example Output

```
Upgrading cert-manager-operator...

Current State:
  Version: 1.14.5
  Channel: stable

Target State:
  Version: 1.15.0
  Channel: stable

✓ Validated upgrade path
✓ Updated ClusterExtension resource
✓ Waiting for upgrade to complete...
✓ Upgrade completed successfully

Upgraded: cert-manager-operator
Previous Version: 1.14.5
New Version: 1.15.0
Upgraded At: 2025-10-28T10:45:00Z

Changes:
- Updated CRD: certificates.cert-manager.io (v1beta1 → v1)
- New feature: Enhanced ACME support
- All pods restarted and healthy

Next steps:
- Verify functionality: /olmv1:status cert-manager-operator
- Rollback if needed: /olmv1:upgrade cert-manager-operator --version 1.14.5
```
