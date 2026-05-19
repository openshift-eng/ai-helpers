# Common Code Generation Errors

This document catalogs common error patterns encountered when running `make generate` in openshift/api, along with their signatures, root causes, and fixes.

## Error Pattern: Missing Deepcopy Markers

**Signature:**
```
Types need DeepCopy methods
missing deepcopy-gen markers
DeepCopy method not found for type X
```

**Root Cause:**
Kubernetes code-generator requires explicit markers to indicate which types should have DeepCopy methods generated. Without the marker, the generator skips the type.

**Fix:**
Add the `// +k8s:deepcopy-gen=true` comment above the type definition.

**Example:**

Input (before):
```go
package v1

type MyAPIType struct {
    Name string `json:"name"`
    Value int   `json:"value"`
}
```

Output (after):
```go
package v1

// +k8s:deepcopy-gen=true
type MyAPIType struct {
    Name string `json:"name"`
    Value int   `json:"value"`
}
```

**Auto-fixable:** Yes

---

## Error Pattern: Missing GenClient Markers

**Signature:**
```
type X does not have genclient marker
genclient marker required for client generation
missing genclient annotation
```

**Root Cause:**
To generate client code for a Kubernetes resource, the type must be marked with `// +genclient`. This tells the generator that this type represents a top-level API resource (not a list type or subresource).

**Fix:**
Add `// +genclient` comment above resource type definitions. Note: Do NOT add this to list types (e.g., `MyResourceList`) or embedded types.

**Example:**

Input (before):
```go
package v1

// +k8s:deepcopy-gen=true
type MyResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    
    Spec   MyResourceSpec   `json:"spec"`
    Status MyResourceStatus `json:"status,omitempty"`
}
```

Output (after):
```go
package v1

// +genclient
// +k8s:deepcopy-gen=true
type MyResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    
    Spec   MyResourceSpec   `json:"spec"`
    Status MyResourceStatus `json:"status,omitempty"`
}
```

**Auto-fixable:** Yes (with caution - must verify it's a resource type, not a list)

---

## Error Pattern: Import Path Resolution

**Signature:**
```
cannot resolve import path "github.com/openshift/api/..."
package github.com/openshift/api/... not found
cannot find package "github.com/openshift/api/..."
```

**Root Cause:**
Go's import path resolution can't find the openshift/api package. This usually means:
1. The repository is not in the correct GOPATH location
2. go.mod is out of sync with dependencies
3. GOPATH is not set correctly

**Fix (try in order):**
1. Run `go mod tidy` to sync dependencies
2. Verify GOPATH: `echo $GOPATH` and `go env GOPATH`
3. Check repository location matches `$GOPATH/src/github.com/openshift/api`
4. If location is wrong, see working directory validation section

**Example:**

```bash
# Verify GOPATH
$ go env GOPATH
/home/user/go

# Check current location
$ pwd
/home/user/repos/api  # WRONG - should be /home/user/go/src/github.com/openshift/api

# Fix by moving or symlinking
$ mkdir -p ~/go/src/github.com/openshift
$ ln -s /home/user/repos/api ~/go/src/github.com/openshift/api
$ cd ~/go/src/github.com/openshift/api
```

**Auto-fixable:** Partially (can run `go mod tidy`, directory fix requires user action)

---

## Error Pattern: Code Generator Tool Not Found

**Signature:**
```
deepcopy-gen: command not found
client-gen: not found
informer-gen: command not found
lister-gen: No such file or directory
controller-gen: command not found
```

**Root Cause:**
The Kubernetes code-generator tools are not installed or not in PATH. These tools must be available for `make generate` to work.

**Fix:**
Check if the Makefile has a tool installation target, or install manually:

```bash
# Check for Make targets
make help | grep -i tool
make help | grep -i codegen

# If there's an install target, use it
make install-tools
# or
make update-codegen-crds

# Manual installation
go install k8s.io/code-generator/cmd/deepcopy-gen@latest
go install k8s.io/code-generator/cmd/client-gen@latest
go install k8s.io/code-generator/cmd/informer-gen@latest
go install k8s.io/code-generator/cmd/lister-gen@latest
go install sigs.k8s.io/controller-tools/cmd/controller-gen@latest
```

**Auto-fixable:** Yes

---

## Error Pattern: GOPATH Not Set

**Signature:**
```
GOPATH is not set
cannot find package in any of GOPATH/GOROOT
GOROOT not found
```

**Root Cause:**
The GOPATH environment variable is not set, or is set incorrectly. Code generators rely on GOPATH to resolve import paths.

**Fix:**
1. Check GOPATH: `go env GOPATH`
2. If empty, set it: `export GOPATH=$(go env GOPATH)` or `export GOPATH=$HOME/go`
3. Verify repository is in `$GOPATH/src/github.com/openshift/api`

**Example:**

```bash
# Check if GOPATH is set
$ go env GOPATH
/home/user/go

# If empty, set it
$ export GOPATH=$HOME/go

# Verify
$ echo $GOPATH
/home/user/go

# Ensure repo is in correct location
$ pwd
/home/user/go/src/github.com/openshift/api  # Correct location
```

**Auto-fixable:** No (requires environment setup or directory relocation)

---

## Error Pattern: Permission Denied

**Signature:**
```
permission denied
cannot create directory: Permission denied
cannot write file: Permission denied
```

**Root Cause:**
The user doesn't have write permissions in the repository directory or for specific generated files.

**Fix:**
1. Check file ownership: `ls -la`
2. Check directory permissions: `ls -ld .`
3. Fix ownership if needed: `sudo chown -R $USER:$USER .`
4. Fix permissions: `chmod -R u+w .`

**Auto-fixable:** No (requires manual permission fixes)

---

## Error Pattern: Stale Generated Code

**Signature:**
```
conflict with existing generated code
generated code is out of date
Please run update-codegen
stale generated files detected
```

**Root Cause:**
Old generated code conflicts with new generation. This can happen when:
- Generator version changed
- API types were modified
- Generated files were manually edited

**Fix:**
Remove old generated files and regenerate:

```bash
# Remove all generated deepcopy files
find . -name 'zz_generated.*.go' -delete

# Remove generated directories
rm -rf ./generated/

# Re-run generation
make generate
```

**Auto-fixable:** Yes

---

## Error Pattern: go.mod Issues

**Signature:**
```
go.mod is malformed
go.sum mismatch
missing go.sum entry for module
```

**Root Cause:**
The go.mod or go.sum files are out of sync with the actual dependencies.

**Fix:**
```bash
# Tidy up dependencies
go mod tidy

# Verify modules
go mod verify

# Download missing modules
go mod download
```

**Auto-fixable:** Yes

---

## Error Pattern: Compilation Errors in Source

**Signature:**
```
syntax error: unexpected X
undefined: TypeName
type X is not defined
```

**Root Cause:**
There are syntax errors or undefined types in the source code before generation runs. Code generation requires valid Go source files.

**Fix:**
1. Fix the syntax error or undefined type in the source file
2. Ensure all imports are correct
3. Run `go build ./...` to verify source compiles
4. Then retry `make generate`

**Auto-fixable:** No (requires manual code fixes)

---

## Error Pattern: Wrong Working Directory

**Signature:**
```
Makefile not found
no such file or directory: Makefile
make: *** No rule to make target 'generate'
```

**Root Cause:**
Not in the openshift/api repository root, or in wrong subdirectory.

**Fix:**
```bash
# Find the repository root
git rev-parse --show-toplevel

# Change to repository root
cd $(git rev-parse --show-toplevel)

# Verify Makefile exists
ls -l Makefile

# Run make generate
make generate
```

**Auto-fixable:** Yes

---

## Error Pattern: Missing Package-Level Markers

**Signature:**
```
package X is missing groupName marker
package needs +k8s:deepcopy-gen=package
```

**Root Cause:**
Package-level markers are required in `doc.go` files to configure code generation for the entire package.

**Fix:**
Create or update `doc.go` in the package directory:

```go
// Package v1 contains API Schema definitions for the myapi v1 API group
// +k8s:deepcopy-gen=package
// +k8s:openapi-gen=true
// +groupName=myapi.openshift.io
package v1
```

**Auto-fixable:** Yes

---

## Error Pattern: API Version Mismatch

**Signature:**
```
API version mismatch
apiVersion field does not match package
GroupVersion mismatch
```

**Root Cause:**
The `apiVersion` in the type's JSON tags doesn't match the package's declared group and version.

**Fix:**
Ensure the GroupVersion is correctly defined in `register.go`:

```go
var (
    GroupVersion = schema.GroupVersion{
        Group:   "myapi.openshift.io",
        Version: "v1",
    }
)
```

And types reference it correctly:

```go
type MyResource struct {
    metav1.TypeMeta `json:",inline"`  // Will be set to myapi.openshift.io/v1
    // ...
}
```

**Auto-fixable:** No (requires understanding of API group/version structure)

---

## Error Pattern: Namespace Scope Marker Mismatch

**Signature:**
```
resource must specify namespaced marker
cluster-scoped resource with namespace field
```

**Root Cause:**
The `// +genclient:nonNamespaced` marker doesn't match the resource's actual scope.

**Fix:**
For cluster-scoped resources, add:
```go
// +genclient
// +genclient:nonNamespaced
// +k8s:deepcopy-gen=true
type MyClusterResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    // ...
}
```

For namespaced resources, omit `nonNamespaced`:
```go
// +genclient
// +k8s:deepcopy-gen=true
type MyNamespacedResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    // ...
}
```

**Auto-fixable:** No (requires understanding of resource scope)

---

## Error Pattern: ReadOnly Subresource Issues

**Signature:**
```
status subresource must be read-only
spec/status separation required
```

**Root Cause:**
OpenShift APIs should separate spec (desired state) and status (observed state), with status being a read-only subresource.

**Fix:**
Ensure proper structure and add subresource marker:

```go
// +genclient
// +genclient:subresource:status
// +k8s:deepcopy-gen=true
type MyResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    
    Spec   MyResourceSpec   `json:"spec"`
    Status MyResourceStatus `json:"status,omitempty"`
}
```

**Auto-fixable:** Partially (can add marker, but structure must be manually verified)

---

## Usage Notes

When using this reference:

1. **Match error output against signatures** - Use regex or substring matching
2. **Try auto-fixable errors first** - These have high success rates
3. **For non-auto-fixable errors** - Provide the fix steps to the user with explanation
4. **Chain multiple fixes** - Some errors require multiple fixes in sequence
5. **Track attempted fixes** - Don't apply the same fix twice in a row
