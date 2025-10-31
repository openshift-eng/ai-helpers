---
description: Get detailed status of an operator (v0) or extension (v1)
argument-hint: <name> [namespace] [--version v0|v1]
---

## Name
olm:status

## Synopsis
```
/olm:status <name> [namespace] [--version v0|v1]
```

## Description
Get comprehensive health and status information for a specific operator (OLM v0) or extension (OLM v1).

**You must explicitly specify which OLM version to use** via `--version` flag or context.

## Implementation

### 1. Determine OLM Version
**See [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md)**

---

## OLM v0 Implementation

### Steps

1. **Parse Arguments**: `<operator-name>` [namespace] [--version v0]

2. **Get CSV**:
   ```bash
   if [ -z "{namespace}" ]; then
     # Auto-discover namespace
     CSV=$(oc get csv --all-namespaces -o json | \
       jq --arg op "{operator-name}" '.items[] | select(.metadata.name | contains($op)) | {name: .metadata.name, namespace: .metadata.namespace}' | head -1)
     NAMESPACE=$(echo "$CSV" | jq -r '.namespace')
   else
     NAMESPACE="{namespace}"
   fi
   
   CSV_NAME=$(oc get csv -n $NAMESPACE -o json | \
     jq -r --arg op "{operator-name}" '.items[] | select(.metadata.name | contains($op)) | .metadata.name' | head -1)
   ```

3. **Get Subscription**:
   ```bash
   SUB=$(oc get subscription -n $NAMESPACE -o json | \
     jq --arg csv "$CSV_NAME" '.items[] | select(.status.installedCSV==$csv)' | head -1)
   ```

4. **Display Status**:
   ```bash
   CSV_PHASE=$(oc get csv $CSV_NAME -n $NAMESPACE -o jsonpath='{.status.phase}')
   CSV_VERSION=$(oc get csv $CSV_NAME -n $NAMESPACE -o jsonpath='{.spec.version}')
   CSV_MESSAGE=$(oc get csv $CSV_NAME -n $NAMESPACE -o jsonpath='{.status.message}')
   
   SUB_CHANNEL=$(echo "$SUB" | jq -r '.spec.channel')
   SUB_SOURCE=$(echo "$SUB" | jq -r '.spec.source')
   SUB_APPROVAL=$(echo "$SUB" | jq -r '.spec.installPlanApproval')
   
   echo "Status: {operator-name}"
   echo ""
   echo "Overall Health: $([ "$CSV_PHASE" == "Succeeded" ] && echo "✓ Healthy" || echo "⚠️ Unhealthy")"
   echo "Installation Status: $CSV_PHASE"
   echo "CSV: $CSV_NAME"
   echo "Version: $CSV_VERSION"
   echo "Namespace: $NAMESPACE"
   echo "Channel: $SUB_CHANNEL"
   echo "Catalog: $SUB_SOURCE"
   echo "Approval Mode: $SUB_APPROVAL"
   
   if [ -n "$CSV_MESSAGE" ]; then
     echo ""
     echo "Message: $CSV_MESSAGE"
   fi
   ```

5. **Show Workloads**:
   ```bash
   echo ""
   echo "Workloads:"
   oc get deployments,statefulsets -n $NAMESPACE -o wide
   echo ""
   echo "Pods:"
   oc get pods -n $NAMESPACE
   ```

6. **Check for Updates**:
   ```bash
   CURRENT_CSV=$(echo "$SUB" | jq -r '.status.currentCSV')
   INSTALLED_CSV=$(echo "$SUB" | jq -r '.status.installedCSV')
   
   if [ "$CURRENT_CSV" != "$INSTALLED_CSV" ]; then
     echo ""
     echo "⚠️  Update Available:"
     echo "  Current: $CURRENT_CSV"
     echo "  Installed: $INSTALLED_CSV"
     echo "  Upgrade: /olm:upgrade {operator-name} $NAMESPACE --version v0"
   fi
   ```

---

## OLM v1 Implementation

### Steps

1. **Parse Arguments**: `<extension-name>` [--version v1]

2. **Get ClusterExtension**:
   ```bash
   EXT=$(kubectl get clusterextension {extension-name} -o json 2>/dev/null)
   if [ -z "$EXT" ]; then
     echo "❌ Extension not found: {extension-name}"
     exit 1
   fi
   ```

3. **Parse Status**:
   ```bash
   NAMESPACE=$(echo "$EXT" | jq -r '.spec.namespace')
   VERSION=$(echo "$EXT" | jq -r '.status.resolution.bundle.version // "unknown"')
   CHANNEL=$(echo "$EXT" | jq -r '.status.resolution.bundle.channel // "unknown"')
   SA_NAME=$(echo "$EXT" | jq -r '.spec.serviceAccount.name')
   
   INSTALLED=$(echo "$EXT" | jq -r '.status.conditions[] | select(.type=="Installed") | .status')
   PROGRESSING=$(echo "$EXT" | jq -r '.status.conditions[] | select(.type=="Progressing") | .status')
   PROG_MSG=$(echo "$EXT" | jq -r '.status.conditions[] | select(.type=="Progressing") | .message')
   ```

4. **Check for Issues**:
   ```bash
   # Check for RBAC errors
   if [[ "$PROG_MSG" == *"pre-authorization failed"* ]]; then
     HAS_RBAC_ISSUES=true
   fi
   
   # Check for webhook errors
   if [[ "$PROG_MSG" == *"webhookDefinitions are not supported"* ]]; then
     HAS_WEBHOOK_ISSUES=true
   fi
   ```

5. **Display Status**:
   ```bash
   echo "Status: {extension-name}"
   echo ""
   
   if [ "$INSTALLED" == "True" ]; then
     echo "Overall Health: ✓ Healthy"
   elif [ "$PROGRESSING" == "True" ]; then
     echo "Overall Health: ⏳ Installing"
   else
     echo "Overall Health: ✗ Failed"
   fi
   
   echo "Installation Status: $([ "$INSTALLED" == "True" ] && echo "Installed" || echo "Not Installed")"
   echo "Version: $VERSION"
   echo "Channel: $CHANNEL"
   echo "Namespace: $NAMESPACE"
   echo "ServiceAccount: $SA_NAME"
   
   if [ "$HAS_RBAC_ISSUES" == "true" ]; then
     echo ""
     echo "⚠️  RBAC Permission Issues Detected"
     echo ""
     echo "$PROG_MSG"
     echo ""
     echo "Fix with: /olm:fix-rbac {extension-name} --version v1"
   fi
   
   if [ "$HAS_WEBHOOK_ISSUES" == "true" ]; then
     echo ""
     echo "⚠️  Webhook Support Required"
     echo "Enable: kubectl patch deployment operator-controller-controller-manager -n olmv1-system --type=json \\"
     echo "  -p='[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/args/-\", \"value\": \"--feature-gates=WebhookProviderCertManager=true\"}]'"
   fi
   ```

6. **Show Resources**:
   ```bash
   echo ""
   echo "Custom Resource Definitions:"
   kubectl get crds -l operators.coreos.com/clusterextension={extension-name} --no-headers | awk '{print "  - " $1}'
   
   echo ""
   echo "Workloads in $NAMESPACE:"
   kubectl get deployments,statefulsets,daemonsets -n $NAMESPACE
   ```

---

## Return Value
- Comprehensive status including health, version, workloads, and issues
- Actionable recommendations for problems

## Examples

```bash
/olm:status cert-manager --version v1
/olm:status openshift-pipelines-operator openshift-operators --version v0
```

## Arguments
- **$1** (name): Operator/extension name (required)
- **$2** (namespace): Namespace (optional for v0, auto-discovered; N/A for v1)
- **--version v0|v1**: OLM version

## Notes
- **v0**: Shows CSV, Subscription, workloads, and pending updates
- **v1**: Shows ClusterExtension, RBAC issues, webhook issues, and workloads
- Use `/olm:fix-rbac` for v1 RBAC problems
