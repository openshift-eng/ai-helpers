---
description: Manage catalog sources (v0) or ClusterCatalogs (v1)
argument-hint: <action> [args] [--version v0|v1]
---

## Name
olm:catalog

## Synopsis
```
/olm:catalog <action> [args] [--version v0|v1]
```

## Description
Manage catalog sources (OLM v0 CatalogSource) or ClusterCatalogs (OLM v1) for discovering available operators/extensions.

**You must explicitly specify which OLM version to use** via `--version` flag or context.

## Implementation

### 1. Determine OLM Version
**See [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md)**

### 2. Parse Action
- `list`: List all catalogs
- `add <name> <image> [--poll-interval <duration>]`: Add new catalog
- `remove <name>`: Remove catalog
- `refresh <name>`: Force catalog refresh
- `status <name>`: Check catalog health

---

## OLM v0 Implementation

### Actions

#### list
```bash
oc get catalogsources -n openshift-marketplace -o json | \
  jq -r '.items[] | [.metadata.name, .spec.sourceType, .status.connectionState.lastObservedState] | @tsv' | \
  while IFS=$'\t' read -r name type state; do
    echo "Name: $name"
    echo "  Type: $type"
    echo "  State: $state"
    echo ""
  done
```

#### add
```bash
cat <<EOF | oc apply -f -
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: {name}
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: {image}
  displayName: {name}
  publisher: Custom
  updateStrategy:
    registryPoll:
      interval: {poll-interval}
EOF
echo "✓ Created CatalogSource: {name}"
```

#### remove
```bash
oc delete catalogsource {name} -n openshift-marketplace
echo "✓ Deleted CatalogSource: {name}"
```

#### refresh
```bash
oc delete pod -n openshift-marketplace -l olm.catalogSource={name}
echo "✓ Refreshing catalog: {name}"
```

#### status
```bash
oc get catalogsource {name} -n openshift-marketplace -o yaml
oc get pods -n openshift-marketplace -l olm.catalogSource={name}
```

---

## OLM v1 Implementation

### Actions

#### list
```bash
kubectl get clustercatalogs -o json | \
  jq -r '.items[] | [.metadata.name, .spec.source.image.ref, .status.phase] | @tsv' | \
  while IFS=$'\t' read -r name image state; do
    echo "Name: $name"
    echo "  Image: $image"
    echo "  State: $state"
    echo ""
  done
```

#### add
```bash
cat <<EOF | kubectl apply -f -
apiVersion: olm.operatorframework.io/v1alpha1
kind: ClusterCatalog
metadata:
  name: {name}
spec:
  source:
    type: Image
    image:
      ref: {image}
      pollInterval: {poll-interval}
EOF
echo "✓ Created ClusterCatalog: {name}"

# Wait for unpacking
kubectl wait --for=condition=Unpacked clustercatalog/{name} --timeout=5m
```

#### remove
```bash
kubectl delete clustercatalog {name}
echo "✓ Deleted ClusterCatalog: {name}"
```

#### refresh
```bash
kubectl annotate clustercatalog {name} refresh="$(date +%s)" --overwrite
echo "✓ Refreshing catalog: {name}"
```

#### status
```bash
kubectl get clustercatalog {name} -o yaml
kubectl get pods -n olmv1-system | grep catalog
```

---

## Return Value
- List of catalogs with status, OR
- Confirmation of add/remove/refresh action

## Examples

```bash
# List all catalogs
/olm:catalog list --version v0
/olm:catalog list --version v1

# Add custom catalog
/olm:catalog add my-catalog quay.io/my-org/catalog:latest --version v0
/olm:catalog add my-catalog quay.io/my-org/catalog:latest --poll-interval 1h --version v1

# Remove catalog
/olm:catalog remove my-catalog --version v0

# Check status
/olm:catalog status operatorhubio --version v1
```

## Arguments
- **$1** (action): Action to perform (required): list, add, remove, refresh, status
- **$2** (name): Catalog name (required for add, remove, refresh, status)
- **$3** (image): Catalog image (required for add)
- **--poll-interval <duration>**: Poll interval for catalog updates (default: 15m)
- **--version v0|v1**: OLM version

## Notes
- **v0**: Manages CatalogSource in `openshift-marketplace` namespace
- **v1**: Manages cluster-scoped ClusterCatalog resources
- Catalog refresh may take a few minutes
- After adding catalog, use `/olm:search` to discover packages
