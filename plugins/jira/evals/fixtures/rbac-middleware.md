Summary: Add RBAC middleware with tests and docs

## Context
Need to add role-based access control middleware to the API server.

## Acceptance Criteria
- RBAC middleware added to pkg/middleware/rbac.go
- Unit tests in pkg/middleware/rbac_test.go
- API documentation updated in docs/api.md
- Integration test in test/e2e/rbac_test.go

## Technical Details
Follow existing middleware pattern in pkg/middleware/auth.go.
Use the Role enum from pkg/auth/types.go.
