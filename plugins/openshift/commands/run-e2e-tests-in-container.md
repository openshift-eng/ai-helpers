---
description: Find and run e2e tests in a container
---

## Name
openshift:run-e2e-tests-in-container

## Synopsis
```
/openshift:run-e2e-tests-in-container
```

## Description

The `/openshift:run-e2e-tests-in-container` command finds e2e tests in the current repository and prepare them to run in a container using podman or docker.

## Workflow

This command will:
1. Auto-detect whether podman or docker is available (prefers podman if both exist)
2. Search for e2e test directories in common OpenShift repository locations (test/e2e, tests/e2e, e2e, pkg/e2e)
3. Look for an existing Dockerfile.e2e or create a generic one if needed
4. Build a container image with the e2e tests
5. Show the user the command to run the tests and ask if they would like Claude to run them or if they will run them themselves

The container will:
- Use the appropriate Go builder image
- Copy the source code and dependencies
- Mount kubeconfig from $KUBECONFIG to /kubeconfig in the container
- Run go test on the e2e test directory
- Support common OpenShift e2e test environment variables

### Pre-requisites:
1. Set `$KUBECONFIG` environment variable to point to your cluster's kubeconfig file
2. The `TEST_OPERATOR_NAMESPACE` can be set at runtime using `-e` flag

Common patterns for OpenShift e2e tests:
- Test location: test/e2e/, tests/e2e/, e2e/, pkg/e2e/
- Kubeconfig: mounted at /kubeconfig/config
- Test command: `go test -timeout 0 ./test/e2e/... -kubeconfig=/kubeconfig/config -v`

Container runtime detection:
```bash
CONTAINER_RUNTIME=$(command -v podman || command -v docker)
```

Build command:
```bash
$CONTAINER_RUNTIME build -t <repo-name>-e2e:latest -f Dockerfile.e2e .
```

Run command (podman with SELinux):
```bash
podman run --rm -v $KUBECONFIG:/kubeconfig/config:Z <repo-name>-e2e:latest
```

Run command with custom namespace (podman):
```bash
podman run --rm -e TEST_OPERATOR_NAMESPACE=my-namespace -v $KUBECONFIG:/kubeconfig/config:Z <repo-name>-e2e:latest
```

Run command (docker):
```bash
docker run --rm -v $KUBECONFIG:/kubeconfig/config <repo-name>-e2e:latest
```

Run command with custom namespace (docker):
```bash
docker run --rm -e TEST_OPERATOR_NAMESPACE=my-namespace -v $KUBECONFIG:/kubeconfig/config <repo-name>-e2e:latest
```

If no Dockerfile.e2e exists, a generic one will be created based on:
- Detected Go module path from go.mod
- Detected e2e test location
- Standard OpenShift builder image

Environment variables that are commonly supported:
- TEST_OPERATOR_NAMESPACE
- TEST_WATCH_NAMESPACE
- KUBECONFIG path (typically /kubeconfig/config)

For custom test runs or specific test selection, the container can be run with custom commands:
```bash
$CONTAINER_RUNTIME run --rm -v $KUBECONFIG:/kubeconfig/config$([ "$CONTAINER_RUNTIME" = "podman" ] && echo ":Z" || echo "") <repo-name>-e2e:latest \
  go test -timeout 0 ./test/e2e/... -kubeconfig=/kubeconfig/config -v -run TestSpecificTest
```

To override environment variables at runtime:
```bash
$CONTAINER_RUNTIME run --rm -e TEST_OPERATOR_NAMESPACE=custom-namespace -e TEST_WATCH_NAMESPACE=custom-namespace \
  -v $KUBECONFIG:/kubeconfig/config$([ "$CONTAINER_RUNTIME" = "podman" ] && echo ":Z" || echo "") <repo-name>-e2e:latest
```

IMPORTANT: When executing, first detect the container runtime with:
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

WORKFLOW:
1. Detect the container runtime (podman or docker)
2. Search for e2e tests in the repository
3. Build the container image using the detected runtime
4. Display the command to run the tests to the user, including:
   - Basic run command using $KUBECONFIG
   - Example with custom TEST_OPERATOR_NAMESPACE using -e flag
5. Use AskUserQuestion to ask the user if they would like Claude to run the tests now or if they will run them manually
6. If the user chooses to have Claude run them, execute the run command
7. If the user chooses to run manually, show them the commands and remind them to:
   - Ensure $KUBECONFIG is set to their cluster's kubeconfig
   - Override TEST_OPERATOR_NAMESPACE with -e flag if needed
