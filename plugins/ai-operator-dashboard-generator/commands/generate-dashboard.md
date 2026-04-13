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

### CRITICAL: What NOT to Do

Before implementing, review these common mistakes that break dashboard quality:

**Button & Actions:**
- ❌ **DO NOT** create inline `ResourceTableRowActions` components in table files
- ❌ **DO NOT** use plain `<button>` tags — use PatternFly `<Button>` component
- ❌ **DO NOT** put `className` on `<Link>` wrapper — put it on `<Button>`
- ❌ **DO NOT** add custom background-color/border-color CSS for buttons
- ❌ **DO NOT** call `useDeleteModal` inside `.map()` loops
- ❌ **DO NOT** forget the Delete button — users need to delete resources!
- ✅ **DO** use `<Button variant="primary">` for Inspect (blue)
- ✅ **DO** use `<Button variant="danger">` for Delete (red)
- ✅ **DO** import and use shared `ResourceTableRowActions` from `./ResourceTable`

**PatternFly 6 APIs:**
- ❌ **DO NOT** use old CSS variable format `--pf-v6-global--*`
- ❌ **DO NOT** use old EmptyState API with child `<Title>` component
- ❌ **DO NOT** use `date={new Date(...)}` with Timestamp
- ❌ **DO NOT** use `variant` prop for Label status colors
- ✅ **DO** use token variables `--pf-t--global--*` (PatternFly 6 semantic tokens)
- ✅ **DO** use EmptyState props: `titleText`, `icon={SearchIcon}`, `headingLevel`
- ✅ **DO** use `timestamp={resource.metadata?.creationTimestamp}` with Timestamp
- ✅ **DO** use Label `status` prop: `status="success|danger|warning"`

**Page Layout:**
- ❌ **DO NOT** use `size="lg"` for main page titles
- ❌ **DO NOT** use OpenShift console classes (`co-m-*`, `table-hover`)
- ❌ **DO NOT** use hex colors in CSS
- ✅ **DO** use `size="xl"` for page titles (`<Title headingLevel="h1" size="xl">`)
- ✅ **DO** use plugin-prefixed classes (`console-plugin-template__*`)
- ✅ **DO** use PatternFly token variables only

---

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
   - Use PatternFly 6 EmptyState props API: `<EmptyState titleText={...} icon={SearchIcon} headingLevel="h4"><EmptyStateBody>...</EmptyStateBody></EmptyState>`.
   - **DO NOT** use old API with separate `<Title>` component child.

6a. **Step 5b — `src/components/ResourceTable.tsx` (shared component)**
   - Create or verify this file exists with **ResourceTable** component AND **ResourceTableRowActions** export.
   - **ResourceTable** component:
     - Props: `columns`, `rows`, `loading`, `error`, `emptyStateTitle`, `emptyStateBody`, `selectedProject`, `data-test`.
     - Renders three-dot loader (`.console-plugin-template__loader` with three `.console-plugin-template__loader-dot`), error Alert, EmptyState with **props API** (`titleText`, `icon={SearchIcon}`, `headingLevel="h4"`), or table with plugin-prefixed classes.
     - Uses `console-plugin-template__table`, `__table-th`, `__table-td`, `__table-tr` classes (NO `co-m-*` or `table-hover`).
   - **ResourceTableRowActions** component (CRITICAL - exports both Inspect AND Delete):
     ```tsx
     import { Link } from 'react-router-dom';
     import { Button } from '@patternfly/react-core';
     import { useDeleteModal } from '@openshift-console/dynamic-plugin-sdk';
     
     interface ResourceTableRowActionsProps {
       resource: any;
       inspectHref: string;
     }
     
     export const ResourceTableRowActions: React.FC<ResourceTableRowActionsProps> = ({
       resource,
       inspectHref,
     }) => {
       const { t } = useTranslation('plugin__console-plugin-template');
       const launchDeleteModal = useDeleteModal(resource);
     
       return (
         <div className="console-plugin-template__action-buttons">
           <Link to={inspectHref}>
             <Button className="console-plugin-template__action-inspect" variant="primary" size="sm">
               {t('Inspect')}
             </Button>
           </Link>
           <Button
             className="console-plugin-template__action-delete"
             variant="danger"
             size="sm"
             onClick={launchDeleteModal}
           >
             {t('Delete')}
           </Button>
         </div>
       );
     };
     ```
   - **CRITICAL PATTERNS:**
     - Use PatternFly `<Button>` component (NOT plain `<button>` tag)
     - `className` goes on `<Button>` (NOT on wrapping `<Link>`)
     - Colors from `variant` prop: `variant="primary"` (blue Inspect), `variant="danger"` (red Delete)
     - Never add custom background-color/border-color CSS for buttons
     - `useDeleteModal` called once per row (in this component), NOT in table's `.map()` loop

7. **Step 6 — Table components (`src/components/<KindPlural>Table.tsx`)**
   - Use **ResourceTable** with **ResourceTableRowActions** (both imported from `./ResourceTable`). One file per resource kind.
   - Imports: `import { Link } from 'react-router-dom';`, `import { Label } from '@patternfly/react-core';`, `import { useK8sWatchResource, Timestamp } from '@openshift-console/dynamic-plugin-sdk';`, `import { ResourceTable, ResourceTableRowActions } from './ResourceTable';`
   - Build **columns**: array of `{ title, width? }` — Name, Namespace (if namespaced), then columns from algorithm (additionalPrinterColumns priority 0; priority 1 if total ≤ 8; fallback: Status from `status.conditions[type=Ready]`, Age from `metadata.creationTimestamp`), then Actions.
   - Build **rows** from `useK8sWatchResource` list; each row **cells**:
     - Name: `<Link key="name" to={inspectHref}>{name}</Link>` (no `<a href>`).
     - Namespace (if namespaced), Status (`<Label key="status" status={statusColor}>{t(statusText)}</Label>` with **status** prop: `"success"` for ready, `"danger"` for not ready, `"warning"` for unknown), Age (`<Timestamp key="age" timestamp={resource.metadata?.creationTimestamp} />`).
     - Actions: `<ResourceTableRowActions key="actions" resource={obj} inspectHref={inspectHref} />` (ResourceTableRowActions internally calls `useDeleteModal`, do NOT call it in `.map()`).
   - Pass **loading** (`!loaded && !loadError`), **error** (`loadError?.message`), **emptyStateTitle**, **emptyStateBody**, **selectedProject** (namespaced only), **data-test**.
   - Namespaced: `selectedProject`, inspect href `/<page>/inspect/<plural>/${namespace}/${name}`.
   - Cluster-scoped: no `selectedProject`, inspect href `/<page>/inspect/<plural>/${name}`.
   - **CRITICAL:** Use `ResourceTableRowActions` from `./ResourceTable` (includes both Inspect AND Delete buttons). Do NOT create inline action components. Do NOT use VirtualizedTable, `<a href>`, or custom button logic.

8. **Step 6b — Expandable Row Components (if relationships defined)**
   - When one-to-many relationships are specified (e.g. parent → child with matchField/matchType):
     - Create or extend `src/components/ExpandableResourceTable.tsx` with props: columns, rows (each row: key, cells, isExpanded, onToggle, expandedContent), loading, error, emptyStateTitle, emptyStateBody, selectedProject, data-test. First column is expand toggle (AngleRightIcon/AngleDownIcon); expanded row `<tr><td colSpan={columns.length + 1}>...</td></tr>`.
     - For each relationship, create a child table component that fetches children with `useK8sWatchResource`, filters by matchField/matchType (field | ownerRef | label), and renders ResourceTable or "No related <ChildKind>s" when empty. Children must be fetched **lazily** only when the parent row is expanded.
     - Parent table uses ExpandableResourceTable; state `expandedRows: Set<string>`; each row's expandedContent is the child table component with parentName/parentNamespace.

9. **Step 7 — CSS (`src/components/<operator-short-name>.css`)**
   - Add only missing classes. Use **PatternFly 6 token variables only** (format: `var(--pf-t--global--*)`). **NEVER use hex colors or old `--pf-v6-global--*` format.**
   - **Page Layout:**
     ```css
     .console-plugin-template__inspect-page {
       padding: var(--pf-t--global--spacer--lg) var(--pf-t--global--spacer--xl);
     }
     .console-plugin-template__dashboard-cards {
       display: flex;
       flex-direction: column;
       gap: var(--pf-t--global--spacer--xl);
     }
     .console-plugin-template__resource-card {
       margin-bottom: 0;
     }
     ```
   - **Table Structure:**
     ```css
     .console-plugin-template__resource-table {
       overflow: hidden;
     }
     .console-plugin-template__table-responsive {
       overflow-x: auto;
     }
     .console-plugin-template__table {
       border-collapse: collapse;
       width: 100%;
       background-color: var(--pf-t--global--background--color--primary--default);
     }
     .console-plugin-template__table-th {
       padding: var(--pf-t--global--spacer--sm) var(--pf-t--global--spacer--md);
       text-align: left;
       vertical-align: middle;
       background-color: var(--pf-t--global--background--color--secondary--default);
       border-bottom: 1px solid var(--pf-t--global--border--color--default);
       font-weight: var(--pf-t--global--font--weight--body--bold);
     }
     .console-plugin-template__table-tr {
       border-bottom: 1px solid var(--pf-t--global--border--color--default);
     }
     .console-plugin-template__table-tr:hover {
       background-color: var(--pf-t--global--background--color--secondary--hover);
     }
     .console-plugin-template__table-td {
       padding: var(--pf-t--global--spacer--sm) var(--pf-t--global--spacer--md);
       text-align: left;
       vertical-align: middle;
       word-wrap: break-word;
       overflow: hidden;
     }
     .console-plugin-template__table-message {
       padding: var(--pf-t--global--spacer--lg);
     }
     ```
   - **Loading (three-dot animated loader):**
     ```css
     .console-plugin-template__loader {
       display: flex;
       gap: var(--pf-t--global--spacer--sm);
       align-items: center;
       justify-content: center;
       padding: var(--pf-t--global--spacer--lg);
     }
     .console-plugin-template__loader-dot {
       width: 10px;
       height: 10px;
       border-radius: 50%;
       background-color: var(--pf-t--global--color--brand--default);
       animation: console-plugin-template-loader-bounce 1.2s infinite ease-in-out;
     }
     .console-plugin-template__loader-dot:nth-child(1) {
       animation-delay: 0s;
     }
     .console-plugin-template__loader-dot:nth-child(2) {
       animation-delay: 0.2s;
     }
     .console-plugin-template__loader-dot:nth-child(3) {
       animation-delay: 0.4s;
     }
     @keyframes console-plugin-template-loader-bounce {
       0%, 80%, 100% {
         transform: scale(0.6);
         opacity: 0.5;
       }
       40% {
         transform: scale(1);
         opacity: 1;
       }
     }
     ```
   - **Action Buttons:**
     ```css
     .console-plugin-template__action-buttons {
       display: flex;
       gap: var(--pf-t--global--spacer--xs);
       flex-wrap: nowrap;
     }
     .console-plugin-template__action-inspect {
       flex-shrink: 0;
     }
     .console-plugin-template__action-delete {
       flex-shrink: 0;
     }
     ```
     **CRITICAL:** Do NOT add background-color/border-color CSS for buttons. Button colors come from PatternFly's `variant` prop (`variant="primary"` for blue Inspect, `variant="danger"` for red Delete).
   - **Expandable Rows (if relationships):** `.console-plugin-template__expand-toggle`, `.console-plugin-template__expanded-row`, `.console-plugin-template__expanded-content`, `.console-plugin-template__child-table`, `.console-plugin-template__no-children` (use token variables for colors/spacing).
   - **Never use:** `co-m-*`, `table-hover`, inline `style` attributes, hex colors, or old `--pf-v6-global--*` variable format. Keyframes names must be **kebab-case**.

10. **Step 7b — Optional: Overview dashboard**
    - Optional: summary count cards above tables (useK8sWatchResource per kind, Grid + Card, plugin-prefixed classes). Not required.

11. **Step 8 — Operator page (`src/<OperatorShortName>Page.tsx`)**
    - **Imports:** `import { Title, Card, CardTitle, CardBody, Spinner } from '@patternfly/react-core';`, `import Helmet from 'react-helmet';`, `import { useTranslation } from 'react-i18next';`, `import { useActiveNamespace } from '@openshift-console/dynamic-plugin-sdk';`, `import { useOperatorDetection, <OPERATOR>_OPERATOR_INFO } from './hooks/useOperatorDetection';`, `import { OperatorNotInstalled } from './components/OperatorNotInstalled';`, table imports, CSS import.
    - **Structure:**
      ```tsx
      const selectedProject = activeNamespace === '#ALL_NS#' ? '#ALL_NS#' : activeNamespace;
      const pageTitle = t('<operator-display-name>');
      
      if (operatorStatus === 'loading') {
        return (
          <>
            <Helmet><title>{pageTitle}</title></Helmet>
            <div className="console-plugin-template__inspect-page">
              <Spinner size="lg" aria-label={t('Loading...')} />
            </div>
          </>
        );
      }
      
      if (operatorStatus === 'not-installed') {
        return (
          <>
            <Helmet><title>{pageTitle}</title></Helmet>
            <div className="console-plugin-template__inspect-page">
              <Title headingLevel="h1" size="xl">
                {pageTitle}
              </Title>
              <OperatorNotInstalled operatorDisplayName={<OPERATOR>_OPERATOR_INFO.displayName} />
            </div>
          </>
        );
      }
      
      return (
        <>
          <Helmet><title>{pageTitle}</title></Helmet>
          <div className="console-plugin-template__inspect-page">
            <Title
              headingLevel="h1"
              size="xl"
              style={{ marginBottom: 'var(--pf-t--global--spacer--lg)' }}
            >
              {pageTitle}
            </Title>
            
            <div className="console-plugin-template__dashboard-cards">
              <Card className="console-plugin-template__resource-card">
                <CardTitle>{t('<ResourceKind Plural>')}</CardTitle>
                <CardBody>
                  <<KindPlural>Table selectedProject={selectedProject} />
                </CardBody>
              </Card>
              {/* Repeat Card for each resource kind */}
            </div>
          </div>
        </>
      );
      ```
    - **CRITICAL:** Use `size="xl"` for page title (NOT `size="lg"`). Pass `selectedProject` only to namespaced tables. For cluster-scoped tables, do not pass `selectedProject`. For fixed-namespace operators, pass the fixed namespace string instead of `selectedProject`.
    - Export both named (`export const <OperatorShortName>Page`) and default (`export default <OperatorShortName>Page`).

12. **Step 9 — `src/ResourceInspect.tsx` (extend only)**
    - Do not rewrite. Add: DISPLAY_NAMES entries (plural → display name), getResourceModel(resourceType) cases returning the new kind's K8sModel, getPagePath(resourceType) returning the operator page path (e.g. `'/cert-manager'`). Cluster-scoped: component already handles 2-segment path (plural/name). Keep URL parsing and Card + Grid layout as-is.

13. **Step 10 — `console-extensions.json`**
    - Append page route: exact true, path `/<operator-short-name>`, component `$codeRef`: `"<OperatorShortName>Page.<OperatorShortName>Page"` (e.g. `CertManagerPage.CertManagerPage`).
    - Append inspect route: exact false, path `["/<operator-short-name>/inspect"]`, component `$codeRef`: `"ResourceInspect.ResourceInspect"`.
    - If missing, add `console.navigation/section` with id `"plugins"`, insertAfter `"observe"`. Add `console.navigation/href` with id `<operator-short-name>`, href `/<operator-short-name>`, **section: "plugins"** (do not use section "home").

14. **Step 11 — `package.json`**
    - Add to `consolePlugin.exposedModules`: `"<OperatorShortName>Page": "./<OperatorShortName>Page"`. Add `"ResourceInspect": "./ResourceInspect"` only if not already present.

15. **Step 12 — Locales**
    - Add all new strings to `locales/en/plugin__console-plugin-template.json`. **CRITICAL:** Include `"Inspect": "Inspect"` and `"Delete": "Delete"` for action buttons. Also add page title, resource display names, empty states, error messages, "Plugins" if section added, "Loading..." for spinner aria-label. Do not remove existing keys.

16. **Step 13 — RBAC**
    - In `charts/openshift-console-plugin/templates/rbac-clusterroles.yaml`, add or append ClusterRoles and bindings: Reader (get, list, watch) and Admin (get, list, watch, delete) for the new API groups/resources. Template names: `{{ template "openshift-console-plugin.name" . }}-<operator-short-name>-reader` and `-admin`.

17. **Validation**
    - Confirm `oc api-resources` output was used for all API groups/versions/scope.
    - Run `yarn build-dev`; it must succeed. If "Invalid module export 'default' in extension [N] property 'component'" appears, fix `console-extensions.json` to use `moduleName.exportName` for every route component.
    - Run `yarn lint`; fix any issues in src/ or CSS.
    - Runtime: navigate to `/<operator-short-name>`; if "Operator not installed" when operator is installed, re-run `oc api-resources` and correct CRD models and useOperatorDetection.

## Return Value

- **Generated/updated files**: 
  - `src/hooks/useOperatorDetection.ts`
  - `src/components/ResourceTable.tsx` (CRITICAL: must export ResourceTableRowActions with Delete button)
  - `src/components/crds/index.ts`
  - `src/components/crds/Events.ts`
  - `src/components/OperatorNotInstalled.tsx` (if created)
  - `src/components/<KindPlural>Table.tsx` per kind (imports ResourceTableRowActions)
  - `src/components/ExpandableResourceTable.tsx` (if relationships)
  - `src/components/<operator-short-name>.css` (PatternFly 6 token variables)
  - `src/<OperatorShortName>Page.tsx`
  - `src/ResourceInspect.tsx` (extended)
  - `console-extensions.json`
  - `package.json`
  - `locales/en/plugin__console-plugin-template.json` (includes "Inspect" and "Delete")
  - `charts/openshift-console-plugin/templates/rbac-clusterroles.yaml`

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
