---
description: List installed operators (v0) or extensions (v1) in the cluster
argument-hint: [namespace] [--all-namespaces] [--version v0|v1]
---

## Name
olm:list

## Synopsis
```
/olm:list [namespace] [--all-namespaces] [--version v0|v1]
```

## Description
The `olm:list` command lists all installed operators (OLM v0) or extensions (OLM v1) in your cluster, showing their status, version, and location. This provides a quick overview of what's currently installed.

**You must explicitly specify which OLM version to use** via:
- `--version` flag on this command, OR
- Setting the context with `/olm:use-version v0|v1`

**OLM v0:** Lists ClusterServiceVersions (CSVs) and their associated Subscriptions

**OLM v1:** Lists ClusterExtensions and their status

## Implementation

### 1. Determine OLM Version

**See [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md) for complete logic.**

### 2. Branch to Version-Specific Implementation

---

## OLM v0 Implementation

### Synopsis (v0)
```
/olm:list [namespace] [--all-namespaces|-A] [--version v0]
```

### Steps

1. **Parse v0 Arguments**:
   - `$1`: Namespace (optional) - if provided, list only operators in this namespace
   - `--all-namespaces` or `-A`: List operators across all namespaces (default if no namespace)
   - `--version v0`: OLM version (optional if context is set)

2. **Prerequisites Check**:
   ```bash
   if ! command -v oc &> /dev/null; then
     echo "❌ 'oc' command not found"
     exit 1
   fi
   
   if ! oc whoami &> /dev/null; then
     echo "❌ Not logged in to cluster"
     exit 1
   fi
   ```

3. **Determine Scope**:
   ```bash
   if [ -n "{namespace}" ]; then
     SCOPE_FLAG="-n {namespace}"
     echo "Listing operators in namespace: {namespace}"
   else
     SCOPE_FLAG="--all-namespaces"
     echo "Listing operators across all namespaces"
   fi
   ```

4. **Fetch CSV Data**:
   ```bash
   # Get all CSVs in scope
   CSVS=$(oc get csv $SCOPE_FLAG -o json 2>/dev/null)
   
   # Check if any CSVs found
   CSV_COUNT=$(echo "$CSVS" | jq '.items | length')
   if [ "$CSV_COUNT" -eq 0 ]; then
     echo "No operators found"
     exit 0
   fi
   ```

5. **Fetch Subscription Data**:
   ```bash
   # Get all Subscriptions in scope
   SUBS=$(oc get subscription $SCOPE_FLAG -o json 2>/dev/null)
   ```

6. **Process and Display**:
   ```bash
   echo ""
   echo "Installed Operators:"
   echo ""
   printf "%-40s %-20s %-15s %-15s %-20s\n" "NAME" "NAMESPACE" "VERSION" "STATUS" "CHANNEL"
   echo "────────────────────────────────────────────────────────────────────────────────────────────────────────"
   
   # Process each CSV
   echo "$CSVS" | jq -r '.items[] | 
     [.metadata.name, 
      .metadata.namespace, 
      .spec.version, 
      .status.phase, 
      (.metadata.namespace + "/" + .spec.displayName)] | 
     @tsv' | while IFS=$'\t' read -r name namespace version phase display; do
     
     # Get subscription info for this CSV
     CHANNEL=$(echo "$SUBS" | jq -r --arg ns "$namespace" --arg csv "$name" \
       '.items[] | select(.metadata.namespace==$ns and .status.installedCSV==$csv) | .spec.channel' 2>/dev/null || echo "unknown")
     
     # Format status with emoji
     case "$phase" in
       Succeeded)
         STATUS="✓ $phase"
         ;;
       Installing|Pending)
         STATUS="⏳ $phase"
         ;;
       Failed|Replacing)
         STATUS="✗ $phase"
         ;;
       *)
         STATUS="$phase"
         ;;
     esac
     
     printf "%-40s %-20s %-15s %-15s %-20s\n" \
       "${name:0:38}" \
       "${namespace:0:18}" \
       "${version:0:13}" \
       "$STATUS" \
       "${CHANNEL:0:18}"
   done
   ```

7. **Display Summary**:
   ```bash
   echo ""
   echo "────────────────────────────────────────────────────────────────────────────────────────────────────────"
   
   # Count by status
   SUCCEEDED=$(echo "$CSVS" | jq '[.items[] | select(.status.phase=="Succeeded")] | length')
   INSTALLING=$(echo "$CSVS" | jq '[.items[] | select(.status.phase=="Installing" or .status.phase=="Pending")] | length')
   FAILED=$(echo "$CSVS" | jq '[.items[] | select(.status.phase=="Failed")] | length')
   
   echo "Total: $CSV_COUNT operators ($SUCCEEDED healthy, $INSTALLING installing, $FAILED failed)"
   
   # Show operators needing attention
   if [ "$FAILED" -gt 0 ] || [ "$INSTALLING" -gt 0 ]; then
     echo ""
     echo "Operators requiring attention:"
     
     if [ "$FAILED" -gt 0 ]; then
       echo ""
       echo "Failed operators:"
       echo "$CSVS" | jq -r '.items[] | select(.status.phase=="Failed") | 
         "  - " + .metadata.name + " in " + .metadata.namespace' 
       echo "  Check with: /olm:status <operator-name> <namespace> --version v0"
     fi
     
     if [ "$INSTALLING" -gt 0 ]; then
       echo ""
       echo "Installing operators:"
       echo "$CSVS" | jq -r '.items[] | select(.status.phase=="Installing" or .status.phase=="Pending") | 
         "  - " + .metadata.name + " in " + .metadata.namespace'
     fi
   fi
   ```

---

## OLM v1 Implementation

### Synopsis (v1)
```
/olm:list [--all-namespaces|-A] [--version v1]
```

### Steps

1. **Parse v1 Arguments**:
   - `--all-namespaces` or `-A`: Show namespace information for each extension (informational, ClusterExtensions are cluster-scoped)
   - `--version v1`: OLM version (optional if context is set)

2. **Prerequisites Check**:
   ```bash
   if ! command -v kubectl &> /dev/null; then
     echo "❌ 'kubectl' command not found"
     exit 1
   fi
   
   if ! kubectl auth can-i get clusterextensions &> /dev/null; then
     echo "❌ Cannot access cluster"
     exit 1
   fi
   
   if ! kubectl get namespace olmv1-system &> /dev/null; then
     echo "❌ OLM v1 not installed"
     exit 1
   fi
   ```

3. **Fetch ClusterExtension Data**:
   ```bash
   echo "Listing installed extensions"
   echo ""
   
   EXTENSIONS=$(kubectl get clusterextensions -o json 2>/dev/null)
   
   EXT_COUNT=$(echo "$EXTENSIONS" | jq '.items | length')
   if [ "$EXT_COUNT" -eq 0 ]; then
     echo "No extensions found"
     echo ""
     echo "Install an extension: /olm:install <name> --version v1 --channel <channel> --namespace <ns>"
     exit 0
   fi
   ```

4. **Display ClusterExtensions**:
   ```bash
   echo "Installed Extensions:"
   echo ""
   printf "%-30s %-20s %-15s %-15s %-25s\n" "NAME" "NAMESPACE" "VERSION" "STATUS" "CHANNEL"
   echo "─────────────────────────────────────────────────────────────────────────────────────────────────────"
   
   echo "$EXTENSIONS" | jq -r '.items[] | 
     {
       name: .metadata.name,
       namespace: .spec.namespace,
       version: .status.resolution.bundle.version // "unknown",
       channel: .status.resolution.bundle.channel // "unknown",
       installed: (.status.conditions[] | select(.type=="Installed") | .status),
       progressing: (.status.conditions[] | select(.type=="Progressing") | .status)
     } | 
     [.name, .namespace, .version, (.installed // "unknown"), .channel] | 
     @tsv' | while IFS=$'\t' read -r name namespace version installed channel; do
     
     # Determine status
     if [ "$installed" == "True" ]; then
       STATUS="✓ Installed"
     elif [ "$installed" == "False" ]; then
       # Check if progressing
       PROGRESSING=$(echo "$EXTENSIONS" | jq -r --arg name "$name" \
         '.items[] | select(.metadata.name==$name) | 
          (.status.conditions[] | select(.type=="Progressing") | .status)')
       
       if [ "$PROGRESSING" == "True" ]; then
         STATUS="⏳ Installing"
       else
         STATUS="✗ Failed"
       fi
     else
       STATUS="❓ Unknown"
     fi
     
     printf "%-30s %-20s %-15s %-15s %-25s\n" \
       "${name:0:28}" \
       "${namespace:0:18}" \
       "${version:0:13}" \
       "$STATUS" \
       "${channel:0:23}"
   done
   ```

5. **Display Summary and Issues**:
   ```bash
   echo ""
   echo "─────────────────────────────────────────────────────────────────────────────────────────────────────"
   
   # Count by status
   INSTALLED=$(echo "$EXTENSIONS" | jq '[.items[] | select((.status.conditions[] | select(.type=="Installed") | .status) == "True")] | length')
   PROGRESSING=$(echo "$EXTENSIONS" | jq '[.items[] | select((.status.conditions[] | select(.type=="Progressing") | .status) == "True")] | length')
   FAILED=$(echo "$EXTENSIONS" | jq '[.items[] | select(
     ((.status.conditions[] | select(.type=="Installed") | .status) == "False") and
     ((.status.conditions[] | select(.type=="Progressing") | .status) != "True")
   )] | length')
   
   echo "Total: $EXT_COUNT extensions ($INSTALLED installed, $PROGRESSING installing, $FAILED failed)"
   
   # Show extensions needing attention
   if [ "$FAILED" -gt 0 ] || [ "$PROGRESSING" -gt 0 ]; then
     echo ""
     echo "Extensions requiring attention:"
     
     if [ "$FAILED" -gt 0 ]; then
       echo ""
       echo "Failed extensions:"
       echo "$EXTENSIONS" | jq -r '.items[] | 
         select(((.status.conditions[] | select(.type=="Installed") | .status) == "False") and
                ((.status.conditions[] | select(.type=="Progressing") | .status) != "True")) | 
         "  - " + .metadata.name + 
         " (Reason: " + ((.status.conditions[] | select(.type=="Progressing") | .reason) // "unknown") + ")"'
       echo ""
       echo "  Check with: /olm:status <extension-name> --version v1"
       echo "  Fix RBAC: /olm:fix-rbac <extension-name> --version v1"
     fi
     
     if [ "$PROGRESSING" -gt 0 ]; then
       echo ""
       echo "Installing extensions:"
       echo "$EXTENSIONS" | jq -r '.items[] | 
         select((.status.conditions[] | select(.type=="Progressing") | .status) == "True") | 
         "  - " + .metadata.name'
     fi
   fi
   
   # Check for RBAC or webhook issues
   HAS_RBAC_ISSUES=$(echo "$EXTENSIONS" | jq '[.items[] | 
     select(.status.conditions[] | select(.message | contains("pre-authorization failed")))] | length')
   
   HAS_WEBHOOK_ISSUES=$(echo "$EXTENSIONS" | jq '[.items[] | 
     select(.status.conditions[] | select(.message | contains("webhookDefinitions are not supported")))] | length')
   
   if [ "$HAS_RBAC_ISSUES" -gt 0 ]; then
     echo ""
     echo "⚠️  $HAS_RBAC_ISSUES extension(s) have RBAC permission issues"
     echo "   Use /olm:fix-rbac to automatically resolve"
   fi
   
   if [ "$HAS_WEBHOOK_ISSUES" -gt 0 ]; then
     echo ""
     echo "⚠️  $HAS_WEBHOOK_ISSUES extension(s) require webhook support"
     echo "   Enable: kubectl patch deployment operator-controller-controller-manager -n olmv1-system --type=json \\"
     echo "     -p='[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/args/-\", \"value\": \"--feature-gates=WebhookProviderCertManager=true\"}]'"
   fi
   ```

---

## Return Value

### OLM v0
- **Format**: Table with columns: NAME, NAMESPACE, VERSION, STATUS, CHANNEL
- **Summary**: Count of operators by status (healthy, installing, failed)
- **Alerts**: List of operators requiring attention

### OLM v1
- **Format**: Table with columns: NAME, NAMESPACE, VERSION, STATUS, CHANNEL
- **Summary**: Count of extensions by status (installed, installing, failed)
- **Alerts**: RBAC issues, webhook issues, failed installations

## Examples

### Example 1: List all operators (v0 with context)

```bash
/olm:use-version v0
/olm:list
```

Output:
```
Listing operators across all namespaces

Installed Operators:

NAME                                     NAMESPACE            VERSION         STATUS          CHANNEL
cert-manager-operator.v1.14.0           cert-manager         1.14.0          ✓ Succeeded     stable-v1
external-secrets-operator.v0.10.0       eso-operator         0.10.0          ✓ Succeeded     stable-v0.10
prometheus.v2.45.0                      monitoring           2.45.0          ⏳ Installing    beta

────────────────────────────────────────────────────────────────────────────────────────────────────────
Total: 3 operators (2 healthy, 1 installing, 0 failed)

Installing operators:
  - prometheus.v2.45.0 in monitoring
```

### Example 2: List extensions (v1 with flag)

```bash
/olm:list --version v1
```

Output:
```
Listing installed extensions

Installed Extensions:

NAME                          NAMESPACE            VERSION         STATUS          CHANNEL
cert-manager                  cert-manager         1.14.5          ✓ Installed     stable
argocd                        argocd               2.10.0          ✓ Installed     stable
postgres-operator             postgres             1.2.0           ✗ Failed        stable

─────────────────────────────────────────────────────────────────────────────────────────────────────
Total: 3 extensions (2 installed, 0 installing, 1 failed)

Failed extensions:
  - postgres-operator (Reason: PreAuthorizationFailed)

  Check with: /olm:status postgres-operator --version v1
  Fix RBAC: /olm:fix-rbac postgres-operator --version v1

⚠️  1 extension(s) have RBAC permission issues
   Use /olm:fix-rbac to automatically resolve
```

### Example 3: List operators in specific namespace (v0)

```bash
/olm:list cert-manager-operator --version v0
```

Output:
```
Listing operators in namespace: cert-manager-operator

Installed Operators:

NAME                                     NAMESPACE            VERSION         STATUS          CHANNEL
cert-manager-operator.v1.14.0           cert-manager         1.14.0          ✓ Succeeded     stable-v1

────────────────────────────────────────────────────────────────────────────────────────────────────────
Total: 1 operators (1 healthy, 0 installing, 0 failed)
```

## Arguments

### Common
- **--version v0|v1**: OLM version to use (optional if context is set)

### OLM v0 Specific
- **$1** (namespace): Target namespace (optional, defaults to all namespaces)
- **--all-namespaces** or **-A**: Explicitly list across all namespaces

### OLM v1 Specific
- **--all-namespaces** or **-A**: Show namespace column (ClusterExtensions are cluster-scoped but have target namespaces)

## Notes

### OLM v0 Notes
- Lists ClusterServiceVersions (CSVs) in the cluster
- Shows associated Subscription channel
- CSV status phases: Succeeded, Installing, Pending, Failed, Replacing
- Default behavior lists all namespaces unless specific namespace provided

### OLM v1 Notes
- Lists ClusterExtensions (cluster-scoped resources)
- Shows target namespace for each extension
- Extension status based on Installed and Progressing conditions
- Highlights RBAC and webhook issues
- Use `/olm:fix-rbac` for permission issues
- Use `/olm:status` for detailed troubleshooting

### Common Notes
- No default version - must be explicitly specified
- Use `/olm:use-version` to set context
- Flag overrides context
- Empty results suggest either nothing installed or wrong version selected
