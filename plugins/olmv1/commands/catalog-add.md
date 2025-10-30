# Add Catalog Command

You are helping the user add a new catalog source to their OLM v1 enabled cluster.

## Task

Add a ClusterCatalog resource to make extensions available for installation.

## Steps

1. **Gather catalog information**:
   - Catalog name (provided by user)
   - Image reference (provided by user)
   - Optional: Poll interval (default: 15m)

2. **Create ClusterCatalog resource**:
   ```yaml
   apiVersion: olm.operatorframework.io/v1alpha1
   kind: ClusterCatalog
   metadata:
     name: <catalog-name>
   spec:
     source:
       type: Image
       image:
         ref: <image-ref>
         pollInterval: <poll-interval>
   ```

3. **Apply the resource**:
   ```bash
   kubectl apply -f <catalog-file>
   ```

4. **Verify catalog availability**:
   ```bash
   kubectl get clustercatalog <catalog-name>
   kubectl wait --for=condition=Unpacked clustercatalog/<catalog-name> --timeout=5m
   ```

5. **Report status**:
   - Confirm catalog was added successfully
   - Show catalog status and last update time
   - Provide next steps (e.g., search for extensions)

## Error Handling

- If catalog image is unreachable, suggest checking image reference and network connectivity
- If catalog fails to unpack, check the ClusterCatalog status conditions for details
- If RBAC errors occur, suggest checking cluster permissions

## Example Output

```
✓ Created ClusterCatalog: my-catalog
✓ Waiting for catalog to unpack...
✓ Catalog ready: my-catalog (Last updated: 2025-10-28T10:30:00Z)

Next steps:
- Search for extensions: /olmv1:search <keyword> --catalog my-catalog
- List all catalogs: /olmv1:catalog-list
```
