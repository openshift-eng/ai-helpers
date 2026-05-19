---
name: Generate API Stubs
description: Run `make generate` in openshift/api repository to generate client code, deepcopy methods, informers, and listers. Automatically troubleshoot and fix common errors including working directory issues, missing markers, and import path problems. Also handles multi-repo workflow with openshift/client-go, updating vendoring and regenerating clients. Use when the user needs to generate OpenShift API stubs, run make generate, update client-go vendoring, troubleshoot code generation errors in openshift/api or openshift/client-go, or mentions working with openshift/api types and client-go together.
tools: [Bash, Read, Write, Edit]
---

# Generate API Stubs

Automate running `make generate` in the openshift/api repository with intelligent error detection and automatic fixing.

## When to Use This Skill

Use this skill when:
- User asks to "run make generate" in openshift/api
- User mentions generating stubs, client code, deepcopy methods, informers, or listers
- User reports errors with code generation in openshift/api
- User is making changes to API types and needs to regenerate derived code
- User mentions issues with "goroot src directory" or GOPATH-related errors
- User asks to "update client-go vendoring" or "regenerate client-go"
- User mentions working with both openshift/api and openshift/client-go together

## Prerequisites

- Must be in openshift/api repository (or user provides path to it)
- Go toolchain installed (`go version` works)
- Internet access to download code-generator tools if needed
- Write permissions in the repository directory

## Implementation Workflow

This skill uses an iterative loop with a maximum of 5 attempts to successfully generate API stubs.

### Phase 1: Working Directory Validation

Before attempting generation, validate the working directory location:

1. **Check current location**:
   - Run `${CLAUDE_PLUGIN_ROOT}/scripts/check_working_directory.sh` from the openshift/api repository
   - This script validates that the repository is in the correct Go workspace structure

2. **Common issue - GOPATH structure requirement**:
   - Kubernetes code-generators require the repository to be at `$GOPATH/src/github.com/openshift/api`
   - Default Go workspace: `~/go/src/github.com/openshift/api`
   - **Why**: Code generators use import path detection that requires this specific directory structure

3. **If validation fails**, guide the user with options:
   - **Option A**: Clone to the correct location:
     ```bash
     mkdir -p ~/go/src/github.com/openshift
     git clone https://github.com/openshift/api ~/go/src/github.com/openshift/api
     cd ~/go/src/github.com/openshift/api
     ```
   - **Option B**: Create a symlink (if current directory has work):
     ```bash
     mkdir -p ~/go/src/github.com/openshift
     ln -s $PWD ~/go/src/github.com/openshift/api
     cd ~/go/src/github.com/openshift/api
     ```
   - **Option C**: Set up temporary GOPATH:
     ```bash
     # If repo is at /home/user/repos/api
     export GOPATH=/home/user/repos
     # Now the import path github.com/openshift/api resolves correctly
     ```

4. **Document the context**: Explain to the user why this directory structure matters and which option was chosen.

### Phase 2: Run make generate

Execute the code generation:

1. **Capture output**:
   ```bash
   make generate > /tmp/make-generate-output.log 2>&1
   echo "Exit code: $?" >> /tmp/make-generate-output.log
   ```

2. **Check exit code**:
   - If exit code = 0: Proceed to Phase 4 (Validation)
   - If exit code ≠ 0: Proceed to Phase 3 (Error Diagnosis)

3. **Save iteration state**: Track how many attempts have been made to prevent infinite loops.

### Phase 3: Error Diagnosis and Auto-Fix

When `make generate` fails, diagnose and fix the issue:

1. **Run error detection**:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/detect_generation_errors.py /tmp/make-generate-output.log
   ```
   This returns JSON with `error_type`, `suggested_fix`, and `files_to_check`.

2. **Match against known patterns** (see `${CLAUDE_PLUGIN_ROOT}/references/common_errors.md` for full catalog):

   **Pattern 1: Missing deepcopy-gen markers**
   - Signature: `Types need DeepCopy methods` or `missing deepcopy-gen markers`
   - Fix: Add `// +k8s:deepcopy-gen=true` comment above the type definition
   - Example:
     ```go
     // +k8s:deepcopy-gen=true
     type MyAPIType struct {
         // ...
     }
     ```

   **Pattern 2: Missing genclient markers**
   - Signature: `type X does not have genclient marker` or needs client generation
   - Fix: Add `// +genclient` above resource types (not list types or subresources)
   - Example:
     ```go
     // +genclient
     // +k8s:deepcopy-gen=true
     type MyResource struct {
         // ...
     }
     ```

   **Pattern 3: Import path resolution errors**
   - Signature: `cannot resolve import path` or `package not found`
   - Fixes to try in order:
     1. Run `go mod tidy` to sync dependencies
     2. Verify GOPATH is set: `go env GOPATH`
     3. Return to Phase 1 (working directory validation)

   **Pattern 4: Missing code-generator tools**
   - Signature: `deepcopy-gen: command not found`, `client-gen: not found`, etc.
   - Fix: Check Makefile for tool installation targets:
     ```bash
     # Most openshift/api repos have update-codegen-crds or similar
     make update-codegen-crds
     ```
   - Alternative: Manual tool installation:
     ```bash
     go install k8s.io/code-generator/cmd/deepcopy-gen@latest
     go install k8s.io/code-generator/cmd/client-gen@latest
     ```

   **Pattern 5: GOPATH/GOROOT not set correctly**
   - Signature: `cannot find package in any of GOPATH/GOROOT`
   - Fix: Return to Phase 1, the working directory is wrong

   **Pattern 6: Permission errors**
   - Signature: `permission denied` writing generated files
   - Fix: Check write permissions, may need to adjust file ownership

   **Pattern 7: Stale generated code**
   - Signature: Conflicts between existing generated code and new generation
   - Fix: Remove old generated files and retry:
     ```bash
     find . -name 'zz_generated.*.go' -delete
     rm -rf ./generated/
     ```

3. **Apply the fix**:
   - If pattern is recognized: Apply fix automatically and explain what was done
   - If pattern is NOT recognized: Show the user the error output, explain what you see, and ask for guidance

4. **After applying fix**: Return to Phase 2 to retry `make generate`

5. **Track attempted fixes**: Maintain a list of fixes already tried to avoid repeating the same fix in a loop.

### Phase 4: Validation

After successful generation (exit code 0), validate the results:

1. **Run validation script**:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/validate_generated_code.sh
   ```

2. **Validation checks**:
   - Expected generated files exist:
     - `zz_generated.deepcopy.go` files in API type directories
     - `generated/clientset/` directory
     - `generated/informers/` directory
     - `generated/listers/` directory
   - Generated code compiles: `go build ./...`
   - No obvious errors in generated files (import cycles, syntax errors)

3. **Validation outcomes**:
   - If validation passes: Proceed to Phase 5 (Report Results)
   - If validation fails: Treat as an error and return to Phase 3 with the validation failure as the error

### Phase 5: Report Results

Provide a comprehensive summary of what was done:

1. **List modified files**:
   ```bash
   git status --short
   ```

2. **Show diff summary**:
   ```bash
   git diff --stat
   ```

3. **Report structure**:
   ```markdown
   ## Generation Results

   **Working Directory**: <path used>
   **Attempts**: <number of iterations>
   **Status**: ✓ Success

   ### Files Modified:
   - <list of changed files>

   ### Errors Encountered and Fixed:
   1. <error 1>: <fix applied>
   2. <error 2>: <fix applied>

   ### Validation:
   - ✓ deepcopy methods generated
   - ✓ Client code generated
   - ✓ Informers generated
   - ✓ Listers generated
   - ✓ Code compiles successfully

   ### Next Steps:
   1. Review the generated code changes
   2. Run tests: `make test` or `make verify`
   3. If updating client-go is needed, proceed to Phase 6 (Multi-Repository Workflow)
   4. Commit the changes: `git add . && git commit -m "Generate API stubs"`
   ```

4. **If warnings exist**, include them in a "Warnings" section.

## Error Handling

### Maximum Iteration Limit

- **Maximum 5 iterations** of the fix-and-retry loop
- If limit is reached without success:
  1. Report all attempted fixes
  2. Show current error state
  3. Display the last error output
  4. Recommend manual intervention with specific guidance

### Infinite Loop Prevention

- Track which fixes have been attempted
- Never apply the exact same fix twice
- If the same error pattern appears after a fix, escalate to user for guidance

### Unrecognized Errors

When encountering an error pattern not in the catalog:

1. Show the full error output to the user
2. Explain what you understand about the error
3. Provide diagnostic information:
   - Current working directory
   - GOPATH value
   - Go version
   - Available code-generator tools
4. Ask the user for guidance on how to proceed
5. If the user provides a fix, apply it and add it to your notes for future reference

## Phase 6: Multi-Repository Workflow (Optional)

After successfully generating API stubs in openshift/api, you may need to update openshift/client-go to use the local API changes. This is common during development when client-go needs to regenerate clients based on unreleased API changes.

### When to Use Multi-Repo Workflow

Use this phase when:
- User mentions "client-go" after API generation
- User says to "update vendoring" or "regenerate client-go"
- User asks to test API changes in client-go
- This is part of a multi-repo change workflow

### Step 1: Locate openshift/client-go Repository

1. **Check if client-go exists locally**:
   ```bash
   # Common locations
   ls -d ~/go/src/github.com/openshift/client-go 2>/dev/null || \
   ls -d ~/code/client-go 2>/dev/null
   ```

2. **If not found**, ask user for the location or offer to clone:
   ```bash
   mkdir -p ~/go/src/github.com/openshift
   git clone https://github.com/openshift/client-go ~/go/src/github.com/openshift/client-go
   ```

3. **Validate working directory** (same GOPATH structure requirement):
   - Must be at `$GOPATH/src/github.com/openshift/client-go`
   - Use the same working directory validation approach as Phase 1
   - Create symlink if needed

### Step 2: Update Vendoring to Point to Local API

Use `go mod replace` to point client-go at the local API directory:

1. **Determine the local API path**:
   ```bash
   API_PATH=$(cd /path/to/openshift/api && pwd)
   # Example: /home/user/go/src/github.com/openshift/api
   ```

2. **Add replace directive to go.mod**:
   ```bash
   cd ~/go/src/github.com/openshift/client-go
   go mod edit -replace github.com/openshift/api=$API_PATH
   ```

3. **Verify the replace directive**:
   ```bash
   grep "github.com/openshift/api" go.mod
   # Should show: replace github.com/openshift/api => /path/to/local/api
   ```

4. **Update dependencies**:
   ```bash
   go mod tidy
   go mod vendor  # If client-go uses vendoring
   ```

### Step 3: Run Client-Go Generation

Apply the same iterative generation workflow to client-go:

1. **Check Makefile for generation target**:
   ```bash
   grep -E "^(generate|update):" Makefile
   ```
   Common targets: `make generate`, `make update-codegen`, `make update`

2. **Run generation** using Phases 2-4:
   - Execute make target (Phase 2)
   - Detect and fix errors (Phase 3)
   - Validate generated code (Phase 4)

3. **Common client-go specific issues**:
   - **Import path errors**: If generation can't find openshift/api types, verify the `replace` directive is correct
   - **Stale generated code**: May need to clean old generated files first
   - **Version mismatches**: Ensure code-generator tool versions match between api and client-go

### Step 4: Validate Client-Go Changes

After successful generation:

1. **Check what was generated**:
   ```bash
   git status --short
   git diff --stat
   ```

2. **Verify compilation**:
   ```bash
   go build ./...
   ```

3. **Run tests** (if applicable):
   ```bash
   make test-unit
   go test ./...
   ```

### Step 5: Report Multi-Repo Results

Provide a comprehensive summary of both repositories:

```markdown
## Multi-Repository Generation Results

### openshift/api
**Status**: ✓ Successfully generated
**Files modified**: <count> files
**Key changes**: <summary>

### openshift/client-go
**Status**: ✓ Successfully generated
**Vendoring**: Updated to use local API at <path>
**Files modified**: <count> files
**Key changes**: <summary>

### Next Steps:
1. Review changes in both repositories
2. Run integration tests if available
3. Commit changes in both repos:
   - api: `git commit -m "Generate API stubs"`
   - client-go: `git commit -m "Regenerate clients for API changes"`
4. When ready to push: Remove go.mod replace directive in client-go before pushing
```

### Important Notes

**Before pushing client-go**:
- **Remove the replace directive** from go.mod:
  ```bash
  go mod edit -dropreplace github.com/openshift/api
  ```
- This is critical - you can't push with a replace pointing to a local path
- Only use replace directives during local development

**Workflow variations**:
- Some repos use `go mod vendor`, others use modules directly
- Check for a `vendor/` directory to determine vendoring strategy
- If vendoring is used, run `go mod vendor` after `go mod tidy`

## Output Format

### Primary Output
- Generated Go source files (*.go) in the repository
- Modified files: types, client code, informers, listers, deepcopy methods
- (Multi-repo): Updated go.mod with replace directive and regenerated client-go files

### Secondary Output
- Summary report (markdown format) showing:
  - Working directory used
  - Number of retry attempts
  - Errors encountered and fixes applied
  - Validation results
  - Git diff summary
  - Suggested next steps
  - (Multi-repo): Status of both api and client-go repositories

## Integration with Parent

This skill can be invoked:

1. **Directly by user**: "run make generate in openshift/api"
2. **From other commands**: Commands that modify API types can invoke this skill to regenerate code
3. **As part of workflows**: Future PR preparation workflows can include this skill

When invoked from another command or skill, the invoking context should provide:
- Path to openshift/api repository (if not current directory)
- Whether to auto-commit results or leave them staged

## Examples

### Example 1: Successful generation from correct directory

```bash
User: "run make generate in openshift/api"