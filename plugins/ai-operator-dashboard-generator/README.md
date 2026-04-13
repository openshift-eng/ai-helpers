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

## Version 1.0.0 Updates

**Major improvements to match PatternFly 6 best practices:**

- ✅ **Delete Button**: ResourceTableRowActions now includes both Inspect AND Delete buttons
- ✅ **PatternFly 6 Tokens**: Updated CSS to use `--pf-t--global--*` semantic token variables
- ✅ **Modern EmptyState API**: Uses props-based API (`titleText`, `icon`, `headingLevel`)
- ✅ **Proper Button Components**: Uses `<Button variant="primary|danger">` instead of plain `<button>` tags
- ✅ **Better Page Titles**: Uses `size="xl"` for main page titles
- ✅ **Plugin-Prefixed Classes**: Uses `console-plugin-template__*` instead of console classes
- ✅ **Correct Timestamp API**: Uses `timestamp` prop instead of `date`
- ✅ **Shared ResourceTableRowActions**: Exported from ResourceTable.tsx for reusability

These updates ensure generated dashboards have professional appearance, proper delete functionality, and follow current OpenShift Console plugin standards.
