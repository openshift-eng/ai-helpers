---
description: Generate OpenShift Console operator dashboard from operator name and CRD discovery
argument-hint: "<operator-name> [--namespace <ns>] [--output-dir <dir>]"
---

## Name
operator-dashboard:generate-dashboard

## Synopsis
```
/operator-dashboard:generate-dashboard <operator-name> [--namespace <ns>] [--output-dir <dir>]
```

## Description

This command adds a new operator to an OpenShift Console dynamic plugin. It discovers the operator's CRDs via cluster API (e.g. `oc api-resources`), then generates the dashboard page, one table component per resource kind using the shared ResourceTable pattern, operator CSS, and extends ResourceInspect for the detail view. Optional parameters allow scoping to a namespace and writing output to a custom directory. The template components in `skills/dashboard-templates/` define the CRD models (`.ts`) and list/detail UI components (ResourceTable, ResourceInspect) that are adapted to the target operator's API group, version, kind, and printer columns.

## Implementation

> Before starting, read the skill at
> `skills/dashboard-templates/SKILL.md`. It documents every template component,
> explains when to use each one, and describes the patterns to follow when
> adapting them to a new operator's CRDs.

1. **Step 0 — Verify API groups on the cluster (REQUIRED before any coding)**
   - Run on the cluster and record the output:
     ```bash
     oc api-resources | grep -i <operator-keyword>
     ```
   - From the output use:
     - **APIVERSION column** → correct `group` and `version` for every K8s model and GVK. Format `<group>/<version>` (e.g. `nfd.openshift.io/v1` → group `nfd.openshift.io`, version `v1`). Entry with no slash (e.g. `v1`) means core group (`""`).
     - **NAMESPACED column** → `true` means resource needs `selectedProject` and Namespace column; `false` means cluster-scoped (no namespace in inspect URL, no `selectedProject`).
     - **KIND column** → exact kind name to use.
   - Do not proceed until verified API group/version/scope for every resource kind to expose.

2. **Step 1 — Directories**
   - Create: `mkdir -p src/hooks src/components/crds`

3. **Step 2 — `src/hooks/useOperatorDetection.ts`**
   - Use `useK8sModel` with `{ group, version, kind }` for the primary resource.
   - Export `OperatorStatus`, `OperatorInfo`, `<OPERATOR>_OPERATOR_INFO`, and `useOperatorDetection()`.
   - If the file exists, add the new operator's info and extend the hook.
   - **Critical:** `useK8sModel` returns `[model, inFlight]` where `inFlight` is `true` **while loading**. Check `if (inFlight) return 'loading'` — NOT `if (!inFlight)`.

4. **Step 3 — `src/components/crds/index.ts`**
   - For each resource kind, export a **K8sModel** (K8sGroupVersionKind) and a TypeScript interface extending `K8sResourceCommon` with optional `spec`/`status`.
   - Append if the file exists.

5. **Step 4 — `src/components/crds/Events.ts`**
   - Add `plural: 'Kind'` to **RESOURCE_TYPE_TO_KIND** for each new resource (so events can resolve involvedObject kind from resource type).

6. **Step 5 — `src/components/OperatorNotInstalled.tsx`**
   - Create only if missing.
   - Generic empty state with `EmptyState` (titleText, icon={SearchIcon}, headingLevel), `EmptyStateBody`, and operator display name message.

7. **Step 6 — Table components (`src/components/<KindPlural>Table.tsx`)**
   - Use **ResourceTable** only. One file per resource kind.
   - Import: `import { Link } from 'react-router-dom';`
   - Build **columns**: array of `{ title, width? }` — Name, Namespace (if namespaced), then columns from algorithm (additionalPrinterColumns priority 0; priority 1 if total ≤ 8; fallback: Status from `status.conditions[type=Ready]`, Age from `metadata.creationTimestamp`), then Actions.
   - Build **rows** from `useK8sWatchResource` list; each row **cells**:
     - Name: `<Link key="name" to={inspectHref}>{name}</Link>` (no `<a href>`).
     - Namespace (if namespaced), Status (Label with **status** prop), Created (Timestamp).
     - Actions: `<ResourceTableRowActions resource={obj} inspectHref={inspectHref} />` (do not call `useDeleteModal` inside `.map()`).
   - Pass **loading** (`!loaded && !loadError`), **error** (`loadError?.message`), **emptyStateTitle**, **emptyStateBody**, **selectedProject** (namespaced only), **data-test**.
   - Namespaced: `selectedProject`, inspect href `/<page>/inspect/<plural>/${namespace}/${name}`.
   - Cluster-scoped: no `selectedProject`, inspect href `/<page>/inspect/<plural>/${name}`.
   - Do not use VirtualizedTable, `<a href>`, or custom button logic; use ResourceTableRowActions for Actions cell.

8. **Step 6b — Expandable Row Components (if relationships defined)**
   - When one-to-many relationships are specified (e.g. parent → child with matchField/matchType):
     - Create or extend `src/components/ExpandableResourceTable.tsx` with props: columns, rows (each row: key, cells, isExpanded, onToggle, expandedContent), loading, error, emptyStateTitle, emptyStateBody, selectedProject, data-test. First column is expand toggle (AngleRightIcon/AngleDownIcon); expanded row `<tr><td colSpan={columns.length + 1}>...</td></tr>`.
     - For each relationship, create a child table component that fetches children with `useK8sWatchResource`, filters by matchField/matchType (field | ownerRef | label), and renders ResourceTable or "No related <ChildKind>s" when empty. Children must be fetched **lazily** only when the parent row is expanded.
     - Parent table uses ExpandableResourceTable; state `expandedRows: Set<string>`; each row's expandedContent is the child table component with parentName/parentNamespace.

9. **Step 7 — CSS (`src/components/<operator-short-name>.css`)**
   - Add only missing classes. Use **PatternFly variables only** (no hex). Required classes:
   - **Page Layout:** `.console-plugin-template__inspect-page` (padding), `.console-plugin-template__dashboard-cards` (display flex, flex-direction column, gap), `.console-plugin-template__resource-card` (margin-bottom 0).
   - **Table Structure:** `.console-plugin-template__resource-table`, `.console-plugin-template__table-responsive`, `.console-plugin-template__table` (border-collapse, width 100%, background-color var), `.console-plugin-template__table-th` (padding, text-align, vertical-align, background-color, border-bottom, font-weight), `.console-plugin-template__table-tr` (border-bottom), `.console-plugin-template__table-tr:hover` (background-color hover), `.console-plugin-template__table-td` (padding, text-align, vertical-align, word-wrap, overflow), `.console-plugin-template__table-message` (padding).
   - **Loading:** `.console-plugin-template__loader` (flex, gap, align-items, justify-content, padding), `.console-plugin-template__loader-dot` (width 10px, height 10px, border-radius 50%, background-color var, animation), nth-child(1)(2)(3) animation-delay 0s, 0.2s, 0.4s; keyframes `console-plugin-template-loader-bounce`: 0%/80%/100% scale(0.6) opacity 0.5, 40% scale(1) opacity 1.
   - **Action Buttons:** `.console-plugin-template__action-buttons` (display flex, gap, flex-wrap nowrap), `.console-plugin-template__action-inspect`, `.console-plugin-template__action-delete` (flex-shrink 0). Do NOT add background-color/border-color for buttons; colors from variant prop.
   - **Expandable Rows (if relationships):** `.console-plugin-template__expand-toggle`, `.console-plugin-template__expanded-row`, `.console-plugin-template__expanded-content`, `.console-plugin-template__child-table`, `.console-plugin-template__no-children`.
   - Never use `co-m-*`, `table-hover`, or inline `style`; keyframes names must be **kebab-case**.

10. **Step 7b — Optional: Overview dashboard**
    - Optional: summary count cards above tables (useK8sWatchResource per kind, Grid + Card, plugin-prefixed classes). Not required.

11. **Step 8 — Operator page (`src/<OperatorShortName>Page.tsx`)**
    - Imports: Title, Card, CardTitle, CardBody, Spinner from `@patternfly/react-core`; Helmet; useTranslation, useActiveNamespace, useOperatorDetection.
    - `selectedProject = activeNamespace === '#ALL_NS#' ? '#ALL_NS#' : activeNamespace` (do not use `'all'`).
    - If `operatorStatus === 'loading'`: wrap in `console-plugin-template__inspect-page`, render `<Spinner size="lg">`.
    - If `operatorStatus === 'not-installed'`: same wrapper, Title, OperatorNotInstalled with operator display name.
    - Else: Helmet, wrapper, Title with marginBottom, optional fixed-namespace Alert, `console-plugin-template__dashboard-cards` containing one Card per resource kind with CardTitle and CardBody wrapping the corresponding Table. Pass selectedProject only to namespaced tables; for fixed-namespace operator pass the fixed namespace value.
    - Export both named (`export const`) and default (`export default`).

12. **Step 9 — `src/ResourceInspect.tsx` (extend only)**
    - Do not rewrite. Add: DISPLAY_NAMES entries (plural → display name), getResourceModel(resourceType) cases returning the new kind's K8sModel, getPagePath(resourceType) returning the operator page path (e.g. `'/cert-manager'`). Cluster-scoped: component already handles 2-segment path (plural/name). Keep URL parsing and Card + Grid layout as-is.

13. **Step 10 — `console-extensions.json`**
    - Append page route: exact true, path `/<operator-short-name>`, component `$codeRef`: `"<OperatorShortName>Page.<OperatorShortName>Page"` (e.g. `CertManagerPage.CertManagerPage`).
    - Append inspect route: exact false, path `["/<operator-short-name>/inspect"]`, component `$codeRef`: `"ResourceInspect.ResourceInspect"`.
    - If missing, add `console.navigation/section` with id `"plugins"`, insertAfter `"observe"`. Add `console.navigation/href` with id `<operator-short-name>`, href `/<operator-short-name>`, **section: "plugins"** (do not use section "home").

14. **Step 11 — `package.json`**
    - Add to `consolePlugin.exposedModules`: `"<OperatorShortName>Page": "./<OperatorShortName>Page"`. Add `"ResourceInspect": "./ResourceInspect"` only if not already present.

15. **Step 12 — Locales**
    - Add all new strings to `locales/en/plugin__console-plugin-template.json` (page title, resource display names, empty states, Inspect, Delete, error messages, "Plugins" if section added). Do not remove existing keys.

16. **Step 13 — RBAC**
    - In `charts/openshift-console-plugin/templates/rbac-clusterroles.yaml`, add or append ClusterRoles and bindings: Reader (get, list, watch) and Admin (get, list, watch, delete) for the new API groups/resources. Template names: `{{ template "openshift-console-plugin.name" . }}-<operator-short-name>-reader` and `-admin`.

17. **Validation**
    - Confirm `oc api-resources` output was used for all API groups/versions/scope.
    - Run `yarn build-dev`; it must succeed. If "Invalid module export 'default' in extension [N] property 'component'" appears, fix `console-extensions.json` to use `moduleName.exportName` for every route component.
    - Run `yarn lint`; fix any issues in src/ or CSS.
    - Runtime: navigate to `/<operator-short-name>`; if "Operator not installed" when operator is installed, re-run `oc api-resources` and correct CRD models and useOperatorDetection.

## Return Value

- **Generated/updated files**: `src/hooks/useOperatorDetection.ts`, `src/components/crds/index.ts`, `src/components/crds/Events.ts`, `src/components/OperatorNotInstalled.tsx` (if created), `src/components/<KindPlural>Table.tsx` per kind, `src/components/ExpandableResourceTable.tsx` (if relationships), `src/components/<operator-short-name>.css`, `src/<OperatorShortName>Page.tsx`, `src/ResourceInspect.tsx` (extended), `console-extensions.json`, `package.json`, `locales/en/plugin__console-plugin-template.json`, `charts/openshift-console-plugin/templates/rbac-clusterroles.yaml`.

## Examples

1. **Basic usage**:
   ```
   /operator-dashboard:generate-dashboard cert-manager
   ```

2. **Scoped to a namespace**:
   ```
   /operator-dashboard:generate-dashboard external-secrets --namespace external-secrets
   ```

3. **Custom output directory**:
   ```
   /operator-dashboard:generate-dashboard my-operator --output-dir ./src/dashboard
   ```

## Arguments

- `$1`: The operator name used to discover its CRDs (and for naming the dashboard route and page).
- `--namespace`: Kubernetes namespace to scope CR listing. Default: all namespaces.
- `--output-dir`: Directory to write generated files into. Default: project root (e.g. `./` or `./src` as appropriate).
