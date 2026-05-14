## Context

The HTTP client in `pkg/api/client.go` creates connections without any timeout configuration. When upstream services become unresponsive, goroutines pile up waiting indefinitely on HTTP responses, causing memory leaks and eventual OOM kills in production.

This was observed in the `api-server` pod during the 2024-12-15 incident where the identity-provider service went down for 20 minutes, causing 3000+ goroutine leaks.

## Acceptance Criteria

- All HTTP client calls in `pkg/api/client.go` use a `context.WithTimeout` with a 30-second default timeout
- The timeout value is configurable via environment variable `HTTP_CLIENT_TIMEOUT`
- Existing unit tests are updated to verify timeout behavior
- A new integration test validates that requests are cancelled after the timeout period
- No goroutine leaks under sustained load (verify with `runtime.NumGoroutine()` in test)

## Technical Details

The `http.Client` struct at line 42 of `pkg/api/client.go` is created with zero-value fields, meaning no timeout. The fix should:

1. Wrap all outgoing calls with `context.WithTimeout(ctx, timeout)`
2. Use the existing `pkg/config` package to read the timeout from env
3. Follow the pattern established in `pkg/webhook/client.go` which already has proper timeouts
4. Update `TestClientGet` and `TestClientPost` in `pkg/api/client_test.go`
