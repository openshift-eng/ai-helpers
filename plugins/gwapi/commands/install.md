---
description: Install Gateway API resources to a Kubernetes/OpenShift cluster
argument-hint: [namespace]
---

## Name
gwapi:install

## Synopsis
```
/gwapi:install [namespace]
```

## Description
The `gwapi:install` command applies Gateway API YAML resources to a Kubernetes or OpenShift cluster. It installs:
1. `gatewayclass.yaml` - Defines the GatewayClass resource
2. `gateway.yaml` - Defines the Gateway resource with cluster-specific domain configuration

The command automatically retrieves the cluster's ingress domain and substitutes it into the gateway.yaml before applying. It uses `oc` (preferred) or `kubectl` to install the resources.

## Arguments
- `$1` (optional): Target namespace for installing Gateway API resources. If not specified, uses the namespace defined in the YAML files or the current namespace context.

## Implementation

1. **Tool Detection**
   - Check if `oc` is available: `which oc`
   - If not available, check for `kubectl`: `which kubectl`
   - If neither is available, inform the user to install one of these tools:
     - OpenShift CLI: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html
     - Kubernetes CLI: https://kubernetes.io/docs/tasks/tools/

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
   - If namespace argument was provided, add `-n <namespace>` flag
   - Capture and display any errors or warnings

6. **Install Gateway with Domain Substitution**
   - Locate `plugins/gwapi/resources/gateway.yaml`
   - Display: "Installing Gateway with domain: $DOMAIN"
   - Substitute the domain in the YAML file:
     - Use environment variable substitution: `envsubst < plugins/gwapi/resources/gateway.yaml | oc apply -f -`
     - Alternative approach: `sed "s/\${DOMAIN}/$DOMAIN/g" plugins/gwapi/resources/gateway.yaml | oc apply -f -`
   - If namespace argument was provided, add `-n <namespace>` flag
   - Capture and display any errors or warnings

7. **Installation Verification**
   - Check GatewayClass: `oc get gatewayclass` or `kubectl get gatewayclass`
   - Check Gateway: `oc get gateway` or `kubectl get gateway`
   - Display installation status summary with resource names and statuses

8. **Error Handling**
   - If domain retrieval fails:
     - Display the error and ask user to verify they're connected to an OpenShift cluster
     - Suggest manual domain input
   - If any YAML application fails:
     - Display the error message
     - Continue with remaining resources (don't fail fast)
     - Provide summary of successful and failed resources at the end
   - If verification fails:
     - Display current state of resources
     - Suggest troubleshooting steps

## Return Value
- **Success**: Confirmation message with list of installed resources and their status
- **Partial Success**: List of successful and failed resources with error details
- **Failure**: Error message with troubleshooting steps

## Examples

1. **Install to default namespace**:
   ```
   /gwapi:install
   ```
   Installs `gatewayclass.yaml` and `gateway.yaml` with the cluster's ingress domain automatically configured.

2. **Install to specific namespace**:
   ```
   /gwapi:install gateway-system
   ```
   Installs both resources to the `gateway-system` namespace with domain substitution.

## Notes
- YAML files should be placed in `plugins/gwapi/resources/` directory:
  - `gatewayclass.yaml` - GatewayClass definition
  - `gateway.yaml` - Gateway definition with `${DOMAIN}` placeholder
- The `gateway.yaml` file should use `${DOMAIN}` as a placeholder for the cluster's ingress domain
- Domain is automatically retrieved from OpenShift cluster: `oc get ingresses.config/cluster -o jsonpath={.spec.domain}`
- Resources are applied with `oc apply` which is idempotent - safe to run multiple times
- The command does not modify existing resources unless YAML content has changed
- The original YAML files are not modified; domain substitution happens in-memory during application
