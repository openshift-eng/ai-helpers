# operator-dashboard

Generate OpenShift Console operator dashboards from an operator name and cluster CRD discovery. The plugin uses template components (CRD models and list/detail UI) in `skills/dashboard-templates/` as the basis for generated files, adapting API group, version, kind, and column definitions to the target operator.

## Commands

### `/operator-dashboard:generate-dashboard`

Adds a new operator to an OpenShift Console dynamic plugin: discovers CRDs via the cluster, then generates the dashboard page, table components per resource kind, CSS, and extends ResourceInspect for the detail view.

**Usage:**
```
/operator-dashboard:generate-dashboard <operator-name> [--namespace <ns>] [--output-dir <dir>]
```

**Example:**
```
/operator-dashboard:generate-dashboard cert-manager
```

## Installation

```bash
/plugin install operator-dashboard@ai-helpers
```

## How It Works

Discovers the operator's CRDs via `kubectl` (e.g. `oc api-resources | grep -i <keyword>`), then uses the template components in `skills/dashboard-templates/` as the basis for generated files — the `.ts` files model each CRD kind (K8sGroupVersionKind and optional interfaces) and the `.tsx` files provide the list (ResourceTable) and detail (ResourceInspect) UI components — adapting field names and structure to match the target operator.
