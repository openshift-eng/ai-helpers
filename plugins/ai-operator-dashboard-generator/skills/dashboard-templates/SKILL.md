---
name: Dashboard Template Components
description: Reference components for generating Kubernetes operator CRD dashboards
---

# Dashboard Template Components

Read this before generating any dashboard component. It explains which template file to use for each component type and how to adapt it to a new operator's CRDs.

## When to Use This Skill

Use this skill when:
- Generating a list view for a CRD kind (use ResourceTable.tsx)
- Generating a detail/inspect view for a single CR (use ResourceInspect.tsx)
- Defining the TypeScript model for a specific CRD kind (use the matching .ts file)
- Adapting any reference component to a new operator's CRD schema

## CRD Model Files (`.ts` files)

These files define the TypeScript types and K8sGroupVersionKind models for each CRD kind. Use them as the starting point when modelling a new CRD's API group, version, kind, and optional spec/status interfaces.

### `Certificate.ts`

**Purpose**: Exports the K8sGroupVersionKind model for cert-manager's Certificate CRD. Used for operator detection and for useK8sWatchResource / useK8sModel.

**Key interfaces**: None (model only).

**Model**:
```ts
export const CertificateModel: K8sGroupVersionKind = {
  group: 'cert-manager.io',
  version: 'v1',
  kind: 'Certificate',
};
```

**Fields to adapt**: Replace `group`, `version`, and `kind` with the target operator's values from `oc api-resources` (APIVERSION and KIND columns).

### `Events.ts`

**Purpose**: Core v1 Event model and a map from resource type (plural) to Kind for event involvedObject lookups; provides `getInvolvedObjectKind(resourceType)` for filtering events by resource.

**Key interfaces**:
```ts
export interface K8sEvent {
  apiVersion?: string;
  kind?: string;
  metadata?: {
    name?: string;
    namespace?: string;
    creationTimestamp?: string;
    [key: string]: unknown;
  };
  type?: string;
  reason?: string;
  message?: string;
  count?: number;
  firstTimestamp?: string;
  lastTimestamp?: string;
  involvedObject?: {
    kind?: string;
    name?: string;
    namespace?: string;
    [key: string]: unknown;
  };
}
```

**Fields to adapt**: Extend `RESOURCE_TYPE_TO_KIND` with `plural: 'Kind'` for each new resource type so events display correctly on the inspect page.

### `ExternalSecret.ts`

**Purpose**: K8sGroupVersionKind models for ExternalSecret and ClusterExternalSecret (external-secrets operator).

**Key interfaces**: None (models only).

**Models**: ExternalSecretModel, ClusterExternalSecretModel — group `external-secrets.io`, version `v1beta1`.

**Fields to adapt**: Replace group/version/kind with target operator's CRD. Use two models when the operator has both namespaced and cluster-scoped variants of the same kind.

### `Issuer.ts`

**Purpose**: K8sGroupVersionKind models for Issuer and ClusterIssuer (cert-manager).

**Key interfaces**: None (models only).

**Models**: IssuerModel, ClusterIssuerModel — group `cert-manager.io`, version `v1`.

**Fields to adapt**: Same as Certificate.ts; use for any operator that exposes namespaced and cluster-scoped kinds.

### `PushSecret.ts`

**Purpose**: K8sGroupVersionKind models for PushSecret and ClusterPushSecret (external-secrets operator).

**Key interfaces**: None (models only).

**Fields to adapt**: Replace group/version/kind with the target operator's API from cluster verification.

### `SecretProviderClass.ts`

**Purpose**: Models for SecretProviderClass and SecretProviderClassPodStatus (CSI secrets store); includes an interface for the pod status subresource used on the inspect page.

**Key interfaces**:
```ts
export interface SecretProviderClassPodStatus {
  apiVersion?: string;
  kind?: string;
  metadata?: {
    name?: string;
    namespace?: string;
    creationTimestamp?: string;
    [key: string]: unknown;
  };
  status?: {
    secretProviderClassName?: string;
    podName?: string;
    mounted?: boolean;
    [key: string]: unknown;
  };
}
```

**Fields to adapt**: Group/version/kind for both models. If the target operator has a similar “status” or pod-binding resource, add a parallel interface and model.

### `SecretStore.ts`

**Purpose**: K8sGroupVersionKind models for SecretStore and ClusterSecretStore (external-secrets operator).

**Key interfaces**: None (models only).

**Fields to adapt**: Replace group/version/kind with values from `oc api-resources`.

## UI Component Files (`.tsx` files)

### `ResourceTable.tsx`

**Purpose**: Shared table for listing CRs of a given kind. Renders loading (three-dot loader), error Alert, empty EmptyState, or a plain table with thead/tbody. Accepts columns and rows (cells as React nodes).

**Use when**: Displaying a list of CRs of a given kind in a table on the operator dashboard.

**Key patterns**:
- Columns: array of `{ title, width? }`; last column is typically Actions.
- Rows: array of `{ cells: React.ReactNode[] }`; build from `useK8sWatchResource` list; Name cell uses `<Link to={inspectHref}>`, Actions cell uses ResourceTableRowActions (so useDeleteModal is per row).
- Loading: show three-dot loader when `loading` is true; error: show Alert; empty: show EmptyState with titleText and EmptyStateBody; selectedProject used for project-aware empty message.

**Props interface**:
```ts
interface Column {
  title: string;
  width?: number;
}
interface Row {
  cells: React.ReactNode[];
}
interface ResourceTableProps {
  columns: Column[];
  rows: Row[];
  loading?: boolean;
  error?: string;
  emptyStateTitle?: string;
  emptyStateBody?: string;
  selectedProject?: string;
  'data-test'?: string;
}
```

**How to adapt**:
1. Replace CRD kind and API group/version in the table’s useK8sWatchResource (use the corresponding .ts model).
2. Build columns from the target CRD: Name, Namespace (if namespaced), then additionalPrinterColumns or fallback (Status, Age), then Actions.
3. Build rows from the list: name link (Link to inspect href), namespace, status Label, timestamp, ResourceTableRowActions. Use plugin-prefixed CSS classes (e.g. `console-plugin-template__table`) and PatternFly variables; do not use co-m-* or inline styles in the consuming plugin.

### `ResourceInspect.tsx`

**Purpose**: Shared resource detail (inspect) page: Card + Grid layout with back button, Metadata, Labels, Annotations, Specification, Status, Events (and optional Pod Statuses for SecretProviderClass). Parses URL for resourceType, namespace, name; uses getResourceModel(resourceType) and getPagePath(resourceType); supports optional “Show/Hide sensitive data” for spec/status.

**Use when**: Displaying the full detail view for a single CR instance at `/<operator-short-name>/inspect/<plural>/[namespace/]<name>`.

**Key patterns**:
- Parse path: find segment after `inspect` for resourceType; then either `namespace` + `name` (namespaced) or `name` only (cluster-scoped).
- getResourceModel(resourceType): switch returning the K8sGroupVersionKind for the resource (from crds/*.ts).
- useK8sWatchResource for the single resource; for Events, use EventModel and fieldSelector by involvedObject name/kind/namespace; getInvolvedObjectKind(resourceType) from Events.ts.
- Render: Metadata (DescriptionList), Labels/Annotations (Cards), Spec/Status (YAML dump with optional sensitive-data toggle), Events table, and optional kind-specific block (e.g. SecretProviderClassPodStatus).

**Props interface**: None (component uses URL and hooks only).

**How to adapt**:
1. Add DISPLAY_NAMES entries for each new plural (plural → display name).
2. Add cases in getResourceModel(resourceType) returning the new kind’s K8sModel.
3. Add case in getPagePath(resourceType) returning the operator page path (e.g. `'/cert-manager'`).
4. Add plural → Kind in Events.ts RESOURCE_TYPE_TO_KIND so events load correctly.
5. Do not change the overall Card + Grid layout or back button; extend only the maps and model lookups.

## Shared Patterns

### Data fetching

- **List view**: `useK8sWatchResource({ groupVersionKind, namespace?, isList: true })`; use `loaded` and `loadError` for loading/error; build rows from the list.
- **Detail view**: `useK8sWatchResource({ groupVersionKind, name, namespace?, isList: false })`; same loading/error handling.
- **Operator detection**: `useK8sModel({ group, version, kind })`; returns `[model, inFlight]`; check `if (inFlight) return 'loading'`.

### Status display

- Use PatternFly `<Label>` with **status** prop for status/conditions: `status="success"` (green), `status="danger"` (red), `status="warning"` (orange). Do not use `variant` for status colors.
- Status value often comes from `status.conditions` (e.g. type=Ready); map to success/danger/warning as appropriate.

### TypeScript model → UI column mapping

- Each CRD kind has a .ts file exporting a K8sGroupVersionKind (and optionally an interface). Table components import that model and pass it to useK8sWatchResource. Columns are derived from CRD additionalPrinterColumns (jsonPath, type) or fallback (Name, Namespace, Status, Age, Actions). Map jsonPath to row cells (e.g. Timestamp for dates, Label for status).

## Which File to Use

| What you need | Use this file |
|---------------|---------------|
| Type model for a known CRD kind | The matching `.ts` file (e.g. `Certificate.ts`) |
| Type model for a new/unknown CRD kind | Use the most structurally similar `.ts` file as a base (same group/version pattern or namespaced+cluster pair) |
| List view of CRs | `ResourceTable.tsx` |
| Detail view of a single CR | `ResourceInspect.tsx` |
