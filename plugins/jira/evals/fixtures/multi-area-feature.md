Summary: Add configurable node drain timeout to NodePool API

## Context
When nodes are drained during upgrades, the default 5-minute timeout is too short
for some workloads. Customers need a way to configure the drain timeout per NodePool.

## Acceptance Criteria
- New `drainTimeout` field added to NodePool spec in api/hypershift/v1beta1/nodepool_types.go
- CRDs regenerated via controller-gen
- Vendor dependencies updated for new API validation library
- NodePool controller in controllers/nodepool/ updated to read and apply the timeout
- HostedCluster controller global default honours the nodepool input
- CLI flag added in cmd/nodepool/create.go to set drain timeout at creation time
- Unit tests added for the controller change
- Documentation updated in docs/content/how-to/nodepool-management.md

## Technical Details
The drain timeout should default to 300s if not set. Use metav1.Duration type.
The controller reads the field during the drain phase in controllers/nodepool/nodepool_controller.go.
Run `make api` to regenerate CRDs and clients after the API change.
