Summary: Remove deprecated API endpoints
Description: |
  ## Context
  Several API endpoints marked deprecated in v2.0 need to be removed.
  ## Acceptance Criteria
  - All deprecated endpoints removed from pkg/api/routes.go
  - Migration guide updated in docs/migration-v3.md
  ## Technical Details
  Endpoints to remove: /v2/users/legacy, /v2/auth/token-v1