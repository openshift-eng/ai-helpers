---
description: Upgrade an operator (v0) or extension (v1) to a new version
argument-hint: <name> [namespace] [--channel <channel>] [--approve] [--version v0|v1]
---

## Name
olm:upgrade

## Synopsis
```
/olm:upgrade <name> [namespace] [--channel <channel>] [--approve] [--version v0|v1]
```

## Description
Upgrade an operator (OLM v0) or extension (OLM v1) to a new version or switch channels.

**You must explicitly specify which OLM version to use** via `--version` flag or context.

## Implementation

### 1. Determine OLM Version
**See [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md)**

---

## OLM v0 Implementation

### Steps

1. **Parse Arguments**:
   - `<operator-name>` (required)
   - `[namespace]` (optional, auto-discovered)
   - `--channel <channel>`: Switch to different channel
   - `--approve`: Approve pending InstallPlan

2. **Get Subscription**:
   ```bash
   if [ -z "{namespace}" ]; then
     SUB=$(oc get subscription --all-namespaces -o json | \
       jq --arg op "{operator-name}" '.items[] | select(.metadata.name | contains($op))' | head -1)
     NAMESPACE=$(echo "$SUB" | jq -r '.metadata.namespace')
   else
     NAMESPACE="{namespace}"
     SUB=$(oc get subscription {operator-name} -n $NAMESPACE -o json)
   fi
   
   CURRENT_CHANNEL=$(echo "$SUB" | jq -r '.spec.channel')
   CURRENT_CSV=$(echo "$SUB" | jq -r '.status.currentCSV')
   INSTALLED_CSV=$(echo "$SUB" | jq -r '.status.installedCSV')
   ```

3. **Check for Channel Switch**:
   ```bash
   if [ -n "{channel}" ] && [ "{channel}" != "$CURRENT_CHANNEL" ]; then
     echo "Switching channel: $CURRENT_CHANNEL → {channel}"
     oc patch subscription {operator-name} -n $NAMESPACE --type=merge \
       -p "{\"spec\":{\"channel\":\"{channel}\"}}"
     echo "✓ Channel updated"
   fi
   ```

4. **Check for Pending Updates**:
   ```bash
   if [ "$CURRENT_CSV" != "$INSTALLED_CSV" ]; then
     echo "Update available:"
     echo "  Current: $CURRENT_CSV"
     echo "  Installed: $INSTALLED_CSV"
   fi
   ```

5. **Approve InstallPlan** (if --approve or Manual mode):
   ```bash
   if [ "{approve}" == "true" ]; then
     PENDING_PLAN=$(oc get installplan -n $NAMESPACE -o json | \
       jq -r '.items[] | select(.spec.approved==false) | .metadata.name' | head -1)
     
     if [ -n "$PENDING_PLAN" ]; then
       oc patch installplan $PENDING_PLAN -n $NAMESPACE --type=merge \
         -p '{"spec":{"approved":true}}'
       echo "✓ Approved InstallPlan: $PENDING_PLAN"
     fi
   fi
   ```

6. **Monitor Upgrade**:
   ```bash
   echo "Monitoring upgrade..."
   for i in {1..30}; do
     NEW_CSV=$(oc get subscription {operator-name} -n $NAMESPACE -o jsonpath='{.status.installedCSV}')
     CSV_PHASE=$(oc get csv $NEW_CSV -n $NAMESPACE -o jsonpath='{.status.phase}' 2>/dev/null)
     
     if [ "$CSV_PHASE" == "Succeeded" ]; then
       echo "✓ Upgrade completed: $NEW_CSV"
       break
     fi
     sleep 10
   done
   ```

---

## OLM v1 Implementation

### Steps

1. **Parse Arguments**:
   - `<extension-name>` (required)
   - `--channel <channel>`: Switch channel
   - `--version <version>`: Pin to specific version

2. **Get ClusterExtension**:
   ```bash
   EXT=$(kubectl get clusterextension {extension-name} -o json)
   CURRENT_VERSION=$(echo "$EXT" | jq -r '.status.resolution.bundle.version')
   CURRENT_CHANNEL=$(echo "$EXT" | jq -r '.status.resolution.bundle.channel // .spec.source.catalog.channel')
   ```

3. **Update ClusterExtension**:
   ```bash
   if [ -n "{channel}" ]; then
     echo "Updating to channel: {channel}"
     kubectl patch clusterextension {extension-name} --type=merge \
       -p '{"spec":{"source":{"catalog":{"channel":"{channel}"}}}}'
   elif [ -n "{version}" ]; then
     echo "Pinning to version: {version}"
     kubectl patch clusterextension {extension-name} --type=merge \
       -p '{"spec":{"source":{"catalog":{"version":"{version}"}}}}'
   fi
   ```

4. **Monitor Upgrade**:
   ```bash
   echo "Monitoring upgrade..."
   for i in {1..60}; do
     NEW_VERSION=$(kubectl get clusterextension {extension-name} \
       -o jsonpath='{.status.resolution.bundle.version}')
     INSTALLED=$(kubectl get clusterextension {extension-name} \
       -o jsonpath='{.status.conditions[?(@.type=="Installed")].status}')
     
     if [ "$INSTALLED" == "True" ] && [ "$NEW_VERSION" != "$CURRENT_VERSION" ]; then
       echo "✓ Upgraded: $CURRENT_VERSION → $NEW_VERSION"
       break
     fi
     sleep 5
   done
   ```

---

## Return Value
- Upgrade status and new version
- Any errors or required actions

## Examples

```bash
# Upgrade to latest in channel
/olm:upgrade cert-manager --version v1

# Switch channel
/olm:upgrade postgres-operator --channel stable --version v0

# Approve pending upgrade
/olm:upgrade prometheus --approve --version v0
```

## Arguments
- **$1** (name): Operator/extension name (required)
- **$2** (namespace): Namespace (v0 only, optional)
- **--channel <channel>**: Switch to channel
- **--version <version>**: Pin to version (v1 only)
- **--approve**: Approve InstallPlan (v0 only)
- **--version v0|v1**: OLM version

## Notes
- **v0**: Updates Subscription channel or approves InstallPlan
- **v1**: Updates ClusterExtension version/channel constraint
- Channel switching may trigger immediate upgrade
- Monitor upgrade with `/olm:status`
