---
description: Find and run e2e tests in a container
argument-hint: [--run]
---

## Name
openshift:run-e2e-tests-in-container

## Synopsis
```
/openshift:run-e2e-tests-in-container [--run]
```

## Description

The `/openshift:run-e2e-tests-in-container` command finds e2e tests in the current repository and prepares them to run in a container using podman or docker.

## Arguments

- `--run`: Optional. If provided, automatically run the tests after building the container instead of asking for user confirmation.

## Implementation

This command uses three skills that can be found in `plugins/openshift/skills/`:

1. **detect-container-runtime**: Detects whether podman or docker is available
2. **discover-e2e-tests**: Finds e2e test directories in the repository
3. **generate-e2e-dockerfile**: Locates or creates a Dockerfile for e2e tests

### Step 1: Detect Container Runtime

Use the `detect-container-runtime` skill to determine the available container runtime:

```bash
if command -v podman &> /dev/null; then
    CONTAINER_RUNTIME="podman"
    SELINUX_FLAG=":Z"
elif command -v docker &> /dev/null; then
    CONTAINER_RUNTIME="docker"
    SELINUX_FLAG=""
else
    echo "Error: Neither podman nor docker found in PATH"
    exit 1
fi
```

See: `plugins/openshift/skills/detect-container-runtime/SKILL.md`

### Step 2: Discover E2E Tests

Use the `discover-e2e-tests` skill to find the e2e test directory:

1. Extract the Go module path from `go.mod`
2. Search common e2e test locations: `test/e2e`, `tests/e2e`, `e2e`, `pkg/e2e`, `test/e2e-test`
3. Validate that test files exist in the found directory

See: `plugins/openshift/skills/discover-e2e-tests/SKILL.md`

### Step 3: Generate or Locate Dockerfile

Use the `generate-e2e-dockerfile` skill:

1. Check for existing Dockerfiles: `Dockerfile.ci`, `Dockerfile.e2e`, `Dockerfile.test`
2. If none found, generate a `Dockerfile.ci` with:
   - Openshift Go toolset base image
   - Multi-stage build for efficiency
   - Correct e2e test path
   - Kubeconfig mount support

See: `plugins/openshift/skills/generate-e2e-dockerfile/SKILL.md`

### Step 4: Build Container Image

Build the container image:

```bash
REPO_NAME=$(basename "$(head -1 go.mod | awk '{print $2}')")
IMAGE_NAME="${REPO_NAME}-e2e:latest"

$CONTAINER_RUNTIME build -t "$IMAGE_NAME" -f "$DOCKERFILE" .
```

### Step 5: Show Run Commands

Display the commands to run the tests:

**Basic run command:**
```bash
$CONTAINER_RUNTIME run --rm \
  -v $KUBECONFIG:/kubeconfig/config${SELINUX_FLAG} \
  ${IMAGE_NAME}
```

**With custom namespace:**
```bash
$CONTAINER_RUNTIME run --rm \
  -e TEST_OPERATOR_NAMESPACE=my-namespace \
  -v $KUBECONFIG:/kubeconfig/config${SELINUX_FLAG} \
  ${IMAGE_NAME}
```

**Running specific tests:**
```bash
$CONTAINER_RUNTIME run --rm \
  -v $KUBECONFIG:/kubeconfig/config${SELINUX_FLAG} \
  ${IMAGE_NAME} \
  go test -timeout 0 -v ./${E2E_PATH}/... -run TestSpecificTest
```

### Step 6: Ask User or Execute

If `--run` argument was provided, execute the run command automatically.

Otherwise, use AskUserQuestion to ask:
- "Would you like me to run the tests now, or will you run them manually?"

Options:
- **Run now**: Execute the container run command
- **Manual**: Show the commands and remind user about prerequisites

## Prerequisites

1. **$KUBECONFIG**: Environment variable must be set to point to your cluster's kubeconfig file
2. **Container runtime**: Either podman or docker must be installed
3. **Go module**: Repository must have a `go.mod` file
4. **E2E tests**: At least one `*_test.go` file in an e2e directory

## Environment Variables

Variables that can be passed to the container with `-e`:

| Variable | Description |
|----------|-------------|
| `TEST_OPERATOR_NAMESPACE` | Namespace for operator testing |
| `TEST_WATCH_NAMESPACE` | Namespace to watch |
| `KUBECONFIG` | Path to kubeconfig (default: `/kubeconfig/config`) |

## Return Value

- **Success**: Container image built and test run command displayed (or tests executed)
- **Failure**: Error message indicating what went wrong (no runtime, no tests found, build failed)

## Examples

1. **Basic usage** - discover, build, and show run commands:
   ```
   /openshift:run-e2e-tests-in-container
   ```

2. **Auto-run** - discover, build, and run tests automatically:
   ```
   /openshift:run-e2e-tests-in-container --run
   ```

## Related Skills

- `plugins/openshift/skills/detect-container-runtime/SKILL.md`
- `plugins/openshift/skills/discover-e2e-tests/SKILL.md`
- `plugins/openshift/skills/generate-e2e-dockerfile/SKILL.md`
