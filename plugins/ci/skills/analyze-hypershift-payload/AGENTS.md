# Contributor guidance

- Use pure-Go dependencies and the standard `flag` package for CLI options.
- Evolve stage contracts with their callers. Document field semantics on the [internal API types](cli/internal/api/types.go).
- Keep each findings validation rule in its own stateless function.
