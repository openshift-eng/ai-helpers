---
description: Install Gateway API resources to a Kubernetes/OpenShift cluster
argument-hint: "[namespace]"
---

## Name
gwapi:install

## Synopsis
```bash
/gwapi:install [namespace]
```

## Description
The `gwapi:install` command applies Gateway API YAML resources to a Kubernetes or OpenShift cluster. It installs:
1. `gatewayclass.yaml` - Defines the GatewayClass resource
2. `gateway.yaml` - Defines the Gateway resource with cluster-specific domain configuration

The command automatically retrieves the cluster's ingress domain and substitutes it into the gateway.yaml before applying. It uses `oc` (preferred) or `kubectl` to install the resources.

**The command waits for all resources to reach a successful status before completing** (up to 5 minutes timeout). This ensures that the Gateway API resources are fully reconciled and ready for use.

## Arguments
- `$1` (optional): Target namespace for installing Gateway API resources. If not specified, uses the namespace defined in the YAML files or the current namespace context.

## Implementation

1. **Tool Detection**
   - Check if `oc` is available: `which oc`
   - If not available, check for `kubectl`: `which kubectl`
   - If neither is available, inform the user to install one of these tools:
     - OpenShift CLI: <https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html>
     - Kubernetes CLI: <https://kubernetes.io/docs/tasks/tools/>

2. **Cluster Connection Verification**
   - Verify cluster connectivity: `oc whoami` or `kubectl cluster-info`
   - If connection fails, inform the user to authenticate to their cluster:
     - For OpenShift: `oc login <cluster-url>`
     - For Kubernetes: Configure kubeconfig properly

3. **Retrieve Cluster Domain**
   - Get the cluster's ingress domain: `DOMAIN=$(oc get ingresses.config/cluster -o jsonpath={.spec.domain})`
   - If this fails (e.g., on non-OpenShift clusters), ask the user to provide the domain manually
   - Verify domain is not empty: `echo $DOMAIN`

4. **Namespace Handling**
   - If namespace argument is provided:
     - Check if namespace exists: `oc get namespace <namespace>` or `kubectl get namespace <namespace>`
     - If it doesn't exist, create it: `oc create namespace <namespace>` or `kubectl create namespace <namespace>`
     - Set context to use this namespace for subsequent commands

5. **Install GatewayClass**
   - Locate `plugins/gwapi/resources/gatewayclass.yaml`
   - Display: "Installing GatewayClass..."
   - Apply the resource: `oc apply -f plugins/gwapi/resources/gatewayclass.yaml` or `kubectl apply -f plugins/gwapi/resources/gatewayclass.yaml`
   - Note: GatewayClass is cluster-scoped, so it does not require a namespace flag
   - Capture and display any errors or warnings

6. **Install Gateway with Domain Substitution**
   - Locate `plugins/gwapi/resources/gateway.yaml`
   - Display: "Installing Gateway with domain: $DOMAIN"
   - Export the domain as an environment variable: `export DOMAIN="<cluster-domain>"`
   - Substitute the domain in the YAML file using envsubst: `envsubst < plugins/gwapi/resources/gateway.yaml | oc apply -f -`
   - If namespace argument was provided, add `-n <namespace>` flag
   - Capture and display any errors or warnings

7. **Wait for Resources to be Ready**
   - Set timeout to 300 seconds (5 minutes)
   - Poll every 5 seconds until resources are ready or timeout is reached

   **GatewayClass readiness check:**
   - Get GatewayClass name from applied resource (e.g., `openshift-default`)
   - Check ACCEPTED condition: `oc get gatewayclass <name> -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}'`
   - GatewayClass is ready when: ACCEPTED condition status is `True`
   - Display progress: "Waiting for GatewayClass to be accepted... (attempt X/60)"

   **Gateway readiness check:**
   - Determine namespace where Gateway was created (from YAML or argument)
   - Get Gateway name from applied resource (e.g., `gateway`)
   - Check PROGRAMMED condition: `oc get gateway <name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}'`
   - Check ACCEPTED condition: `oc get gateway <name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}'`
   - Gateway is ready when: PROGRAMMED condition is `True` AND ACCEPTED condition is `True`
   - Display progress: "Waiting for Gateway to be programmed... (attempt X/60)"

   **Polling implementation:**
   ```bash
   TIMEOUT=300
   INTERVAL=5
   ELAPSED=0

   # Wait for GatewayClass
   while [ $ELAPSED -lt $TIMEOUT ]; do
     ACCEPTED=$(oc get gatewayclass <name> -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null)
     if [ "$ACCEPTED" = "True" ]; then
       echo "✓ GatewayClass is accepted"
       break
     fi
     echo "Waiting for GatewayClass to be accepted... ($(($ELAPSED))s / ${TIMEOUT}s)"
     sleep $INTERVAL
     ELAPSED=$(($ELAPSED + $INTERVAL))
   done

   # Wait for Gateway
   ELAPSED=0
   while [ $ELAPSED -lt $TIMEOUT ]; do
     PROGRAMMED=$(oc get gateway <name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}' 2>/dev/null)
     ACCEPTED=$(oc get gateway <name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null)
     if [ "$PROGRAMMED" = "True" ] && [ "$ACCEPTED" = "True" ]; then
       echo "✓ Gateway is ready"
       break
     fi
     echo "Waiting for Gateway to be ready... ($(($ELAPSED))s / ${TIMEOUT}s)"
     sleep $INTERVAL
     ELAPSED=$(($ELAPSED + $INTERVAL))
   done
   ```

   **Timeout handling:**
   - If timeout is reached before resources are ready:
     - Display current status of resources with detailed condition information
     - Show any error messages from status conditions
     - Command should exit with an error status
     - Display: "Timeout waiting for resources to be ready. Current status:"
     - Display full resource status: `oc get gatewayclass <name> -o yaml` and `oc get gateway <name> -n <namespace> -o yaml`

8. **Final Verification and Summary**
   - Once all resources are ready (or timeout occurred), display final summary:
   - Check GatewayClass: `oc get gatewayclass` or `kubectl get gatewayclass`
   - Check Gateway: `oc get gateway -A` or `kubectl get gateway -A`
   - Display complete installation status with resource names, namespaces, and conditions
   - If all resources are ready, display success message
   - If timeout occurred, display error message with troubleshooting steps

9. **Error Handling**
   - If domain retrieval fails:
     - Display the error and ask user to verify they're connected to an OpenShift cluster
     - Suggest manual domain input
   - If any YAML application fails:
     - Display the error message
     - Continue with remaining resources (don't fail fast)
     - Provide summary of successful and failed resources at the end
   - If resources don't become ready within timeout:
     - Display current state of resources with full YAML output
     - Show condition details and error messages
     - Exit with error status
     - Suggest troubleshooting steps (check controller logs, verify prerequisites)

## Return Value
- **Success**: All resources are installed and ready
  - GatewayClass ACCEPTED condition is `True`
  - Gateway PROGRAMMED and ACCEPTED conditions are `True`
  - Confirmation message with resource names, namespaces, and ready status
- **Timeout**: Resources were created but didn't become ready within 5 minutes
  - Display current status of all resources
  - Show condition details and any error messages
  - Exit with error status
- **Failure**: Resources failed to apply
  - Error message with details about what failed
  - Troubleshooting steps

## Examples

1. **Install to default namespace**:
   ```bash
   /gwapi:install
   ```
   Installs `gatewayclass.yaml` and `gateway.yaml` with the cluster's ingress domain automatically configured, then waits for resources to be ready.

   Example output:
   ```
   Installing GatewayClass...
   gatewayclass.gateway.networking.k8s.io/openshift-default created
   Installing Gateway with domain: apps.example.com
   gateway.gateway.networking.k8s.io/gateway created
   Waiting for GatewayClass to be accepted... (0s / 300s)
   Waiting for GatewayClass to be accepted... (5s / 300s)
   ✓ GatewayClass is accepted
   Waiting for Gateway to be ready... (0s / 300s)
   Waiting for Gateway to be ready... (5s / 300s)
   ✓ Gateway is ready

   Installation complete! All resources are ready.
   ```

2. **Install to specific namespace**:
   ```bash
   /gwapi:install gateway-system
   ```
   Installs both resources to the `gateway-system` namespace with domain substitution, then waits for resources to be ready.

## Notes
- YAML files should be placed in `plugins/gwapi/resources/` directory:
  - `gatewayclass.yaml` - GatewayClass definition
  - `gateway.yaml` - Gateway definition with `${DOMAIN}` placeholder
- The `gateway.yaml` file should use `${DOMAIN}` as a placeholder for the cluster's ingress domain
- Domain is automatically retrieved from OpenShift cluster: `oc get ingresses.config/cluster -o jsonpath={.spec.domain}`
- Domain substitution is performed using `envsubst` which replaces `${DOMAIN}` with the actual cluster domain
- Resources are applied with `oc apply` which is idempotent - safe to run multiple times
- The command does not modify existing resources unless YAML content has changed
- The original YAML files are not modified; domain substitution happens in-memory during application
- **Waiting behavior:**
  - Default timeout: 300 seconds (5 minutes)
  - Poll interval: 5 seconds
  - GatewayClass is considered ready when ACCEPTED condition is `True`
  - Gateway is considered ready when both PROGRAMMED and ACCEPTED conditions are `True`
  - If timeout is reached, the command exits with an error and displays the current resource status
- The command blocks until all resources are ready or timeout occurs
- Progress updates are displayed every 5 seconds during the wait
