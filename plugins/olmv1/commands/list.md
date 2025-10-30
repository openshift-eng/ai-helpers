# List Extensions Command

You are helping the user list all installed extensions in their cluster.

## Task

Display all ClusterExtension resources with their status and health.

## Steps

1. **List all ClusterExtensions**:
   ```bash
   kubectl get clusterextensions
   ```

2. **Get detailed information**:
   For each extension, gather:
   - Name
   - Package name
   - Installed version
   - Channel (if applicable)
   - Status (Installed, Progressing, Failed)
   - Namespace

3. **Check health indicators**:
   - Installation status condition
   - Associated pod health
   - Recent events or errors

4. **Format output**:
   Display in tabular format with key information.

5. **Highlight issues**:
   - Mark failed or degraded extensions
   - Show extensions with pending updates (if tracking channel)

## Example Output

```
Installed Extensions:

NAME                          PACKAGE                     VERSION   CHANNEL    STATUS      NAMESPACE
cert-manager-operator         cert-manager                1.14.5    stable     ✓ Healthy   cert-manager
argocd-operator              argocd-operator             0.11.0    alpha      ✓ Healthy   argocd
prometheus-operator          prometheus                   0.68.0    beta       ⚠ Degraded  monitoring
strimzi-kafka-operator       strimzi-kafka-operator      0.40.0    stable     ✓ Healthy   kafka

Total: 4 extensions (3 healthy, 1 degraded)

Issues detected:
- prometheus-operator: CRD validation warnings (use /olmv1:status for details)
```
