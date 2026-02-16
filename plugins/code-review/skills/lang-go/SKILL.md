---
name: "Go Language Review"
description: "Language-specific review guidance for Go code including idiomatic patterns, test conventions, and build commands"
---

# Go Language Review

This skill provides Go-specific guidance for code quality reviews. It is loaded automatically by the `pre-commit-review` command when `--language go` is specified or when `.go` files are detected among the changed files.

## When to Use This Skill

Use this skill when reviewing Go source code. Its sections are referenced during the unit test coverage, idiomatic code, and build verification review steps.

## Test Conventions

- **Table-driven tests**: Prefer table-driven tests for functions with multiple input/output combinations
- **Subtests**: Use `t.Run()` for subtests to provide clear test case identification
- **Parallel tests**: Use `t.Parallel()` at the top of test functions and subtests where tests are independent
- **Race detection**: Tests must be compatible with the `-race` flag — avoid shared mutable state between parallel tests
- **File co-location**: Test files must be co-located with source files using the `_test.go` suffix
- **Test helpers**: Use `t.Helper()` in test helper functions so failure messages report the caller's line number
- **Behavior-focused**: Test names should describe behavior, not implementation. Test both success and error paths

## Idiomatic Go

Follow the conventions in [Effective Go](https://go.dev/doc/effective_go) and the [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments) wiki. Key reminders:

- **Formatting**: All code must be formatted with `gofmt`. Unformatted code is a blocking issue
- **Naming**: Use `MixedCaps` / `mixedCaps`. Avoid stuttering (`http.Server` not `http.HTTPServer`). Acronyms are all caps (`URL`, `HTTP`, `ID`)
- **Error handling**: Check every error. Wrap with `fmt.Errorf("context: %w", err)` to preserve the chain for `errors.Is()` / `errors.As()`
- **Interfaces**: Keep interfaces small. Accept interfaces, return concrete types
- **Early returns**: Handle error cases first; keep the happy path at the lowest indentation level
- **Context**: Pass `context.Context` as the first parameter to functions that perform I/O or may be long-running

## Build Commands

Use the following commands in priority order during build verification:

1. **Tests**: `make test` if a Makefile with a `test` target exists; otherwise `go test -race ./...`
2. **Verification**: `make verify` if available; otherwise `go vet ./...`
3. **Build**: `make build` if available; otherwise `go build ./...`
