## Context

The auth handler in `pkg/auth/handler.go` crashes with a nil pointer dereference when the incoming request has an expired or malformed JWT token. The `ParseToken` function returns nil on error but the caller does not check for nil before accessing token fields.

This affects all authenticated endpoints and has been reported by three customers in the last week.

## Technical Details

The crash happens at line 87 of `pkg/auth/handler.go` where `token.Claims` is accessed without a nil check. The fix should add a nil check after `ParseToken()` returns and return a 401 status code with an appropriate error message.
