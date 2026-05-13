---
description: Generate OpenShift API stubs with automatic error detection and fixing, optionally updating client-go
argument-hint: "[api-repo-path] [--client-go [client-go-path]]"
---

## Name
openshift:generate-api

## Synopsis
```
/openshift:generate-api [api-repo-path] [--client-go [client-go-path]]
```

## Description

The `openshift:generate-api` command automates running code generation in the openshift/api repository and optionally regenerates openshift/client-go. It handles the common pain points of API stub generation: working directory validation, GOPATH structure requirements, missing tools, and iterative error fixing.

The command uses an iterative fix-and-retry loop (up to 5 attempts) to automatically resolve common generation errors before escalating to the user.

### What It Generates

In openshift/api:
- **Deepcopy methods** (`zz_generated.deepcopy.go`)
- **Swagger documentation** (`zz_generated.swagger_doc_generated.go`)
- **OpenAPI definitions** (`zz_generated.openapi.go`)
- **CRD manifests**
- **Protobuf bindings** (if `protoc` is available)

In openshift/client-go (with `--client-go`):
- **Typed clients** for all API resources
- **Informers** and **listers**
- **Apply configurations**

## Implementation

1. **Working Directory Validation**
   - Verify the openshift/api repository is located at `$GOPATH/src/github.com/openshift/api`
   - If not, offer to create a symlink or adjust GOPATH
   - Run `${CLAUDE_PLUGIN_ROOT}/scripts/check_working_directory.sh` for validation

2. **Run Code Generation**
   - Execute `make update-codegen-crds` (the primary generation target in openshift/api)
   - Capture output and check exit code
   - Set `GOPATH` and optionally `PROTO_OPTIONAL=1` if protoc is unavailable

3. **Error Detection and Auto-Fix**
   - Run `${CLAUDE_PLUGIN_ROOT}/scripts/detect_generation_errors.py` on failures
   - Automatically fix recognized patterns (missing markers, vendor sync, missing tools)
   - Retry generation after each fix (max 5 iterations)

4. **Validation**
   - Run `${CLAUDE_PLUGIN_ROOT}/scripts/validate_generated_code.sh`
   - Verify generated files exist, are non-empty, and compile

5. **Client-Go Workflow** (when `--client-go` is specified)
   - Validate client-go working directory (same GOPATH structure requirement)
   - Add `go mod edit -replace github.com/openshift/api=<local-api-path>` to client-go's go.mod
   - Run `go mod vendor` to sync vendor directory
   - Execute `make generate` in client-go
   - Apply the same iterative error detection and fixing
   - Validate generated client code
   - Warn user to remove the replace directive before pushing

6. **Report Results**
   - Show files modified in each repository
   - Summarize errors encountered and fixes applied
   - Provide `git diff --stat` for review
   - Suggest next steps

## Examples

### Example 1: Generate from current directory
```
/openshift:generate-api
```
Runs generation in the current directory (must be openshift/api).

### Example 2: Generate from a specific path
```
/openshift:generate-api ~/code/api
```
Runs generation using the openshift/api repository at the given path.

### Example 3: Generate API and update client-go
```
/openshift:generate-api ~/code/api --client-go ~/code/client-go
```
Generates API stubs, then updates client-go vendoring to use the local API and regenerates client code.

### Example 4: Generate API and auto-detect client-go
```
/openshift:generate-api --client-go
```
Generates API stubs in the current directory, then searches common locations for client-go.

## Arguments

- **api-repo-path** (optional): Path to the openshift/api repository. Defaults to the current working directory.
- **--client-go** (optional): Also update and regenerate openshift/client-go. Optionally accepts a path to the client-go repository; if omitted, searches common locations (`~/code/client-go`, `$GOPATH/src/github.com/openshift/client-go`).

## Common Issues

### GOPATH Structure
Code generators require repositories at `$GOPATH/src/github.com/openshift/<repo>`. The command detects this automatically and offers to create symlinks.

### Missing protoc
Protobuf generation requires `protoc 23.x`. If unavailable, the command sets `PROTO_OPTIONAL=1` to skip protobuf generation. Other generated code proceeds normally.

### Branch Compatibility
When using `--client-go`, both repositories must be on compatible branches. If client-go references API packages that don't exist in your local API branch, you'll see import errors during vendoring.

## See Also

- [openshift/api repository](https://github.com/openshift/api/)
- [openshift/client-go repository](https://github.com/openshift/client-go/)
- [Kubernetes Code Generator](https://github.com/kubernetes/code-generator)
