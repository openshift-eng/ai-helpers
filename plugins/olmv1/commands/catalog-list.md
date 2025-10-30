# List Catalogs Command

You are helping the user list all available catalogs in their OLM v1 enabled cluster.

## Task

Display all ClusterCatalog resources and their status.

## Steps

1. **List all ClusterCatalogs**:
   ```bash
   kubectl get clustercatalogs
   ```

2. **Get detailed status**:
   ```bash
   kubectl get clustercatalogs -o wide
   ```

3. **Format output**:
   Show for each catalog:
   - Name
   - Source image
   - Status (Ready, Unpacking, Failed)
   - Last updated timestamp
   - Number of available packages (if available)

4. **Check for issues**:
   - Identify catalogs that are not ready
   - Show any error conditions

## Example Output

```
Available Catalogs:

NAME              IMAGE                                    STATUS   LAST UPDATED
operatorhubio     quay.io/operatorhubio/catalog:latest    Ready    2025-10-28T09:15:00Z
certified         registry.redhat.io/certified:v4.15      Ready    2025-10-28T08:30:00Z
my-catalog        registry.example.com/catalog:v1         Ready    2025-10-28T10:00:00Z

Total: 3 catalogs (3 ready, 0 failed)
```
