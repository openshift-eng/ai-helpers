---
description: Check Gateway API resources status in the cluster
argument-hint: "[namespace]"
---

## Name
gwapi:check

## Synopsis
```bash
/gwapi:check [namespace]
```

## Description
The `gwapi:check` command verifies the status of Gateway API resources in a Kubernetes or OpenShift cluster. It checks:
1. Presence and status of GatewayClass resources
2. Presence and status of Gateway resources
3. Gateway listener configuration and readiness
4. Gateway addresses and connectivity

This command helps troubleshoot Gateway API deployments and verify successful installation.

## Arguments
- `$1` (optional): Target namespace to check for Gateway resources. If not specified, checks all namespaces for GatewayClass (cluster-scoped) and Gateway resources.

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

3. **Check GatewayClass Resources**
   - List all GatewayClass resources: `oc get gatewayclass` or `kubectl get gatewayclass`
   - For each GatewayClass found:
     - Display name, controller, and ACCEPTED status
     - Get detailed status: `oc get gatewayclass <name> -o yaml`
     - Check the `status.conditions` for any errors or warnings
   - If no GatewayClass found:
     - Display: "No GatewayClass resources found. You may need to install Gateway API CRDs or run /gwapi:install"

4. **Check Gateway Resources**
   - If namespace argument provided:
     - Check Gateway resources in specified namespace: `oc get gateway -n <namespace>`
   - If no namespace argument:
     - Check all namespaces: `oc get gateway --all-namespaces`
   - For each Gateway found:
     - Display name, namespace, class, and PROGRAMMED status
     - Get detailed information: `oc get gateway <name> -n <namespace> -o yaml`
     - Extract and display:
       - Gateway addresses (LoadBalancer IPs/hostnames)
       - Listener configurations (hostnames, ports, protocols)
       - Listener status and attached routes count
     - Check the `status.conditions` for any errors or warnings
   - If no Gateway found:
     - Display: "No Gateway resources found in [namespace/cluster]"

5. **Status Summary**
   - Create a summary report with:
     - Total GatewayClass count and their statuses
     - Total Gateway count per namespace
     - Number of ready vs not-ready Gateways
     - Any errors or warnings found

6. **Connectivity Check (Optional)**
   - For each Gateway with an address:
     - Display the address (LoadBalancer hostname/IP)
     - Suggest testing connectivity: `curl -v http://<gateway-address>`
   - Note: Actual connectivity testing is optional and should be suggested rather than automatically performed

7. **Error Handling**
   - If API resources not found:
     - Display: "Gateway API CRDs not installed. Install them using /gwapi:install or manually install Gateway API CRDs"
   - If access denied:
     - Display: "Insufficient permissions. GatewayClass requires cluster-scoped read access, Gateway requires namespace read access"
   - If cluster unreachable:
     - Display connection error and suggest checking cluster status

## Return Value
- **Success**: Status report showing all Gateway API resources and their health
- **No Resources**: Information that no Gateway API resources were found with suggestion to run /gwapi:install
- **Error**: Error message with troubleshooting steps

## Examples

1. **Check all Gateway API resources**:
   ```bash
   /gwapi:check
   ```
   Displays status of all GatewayClass and Gateway resources across the cluster.

2. **Check Gateway resources in specific namespace**:
   ```bash
   /gwapi:check openshift-ingress
   ```
   Shows Gateway resources only in the `openshift-ingress` namespace, plus all cluster-scoped GatewayClass resources.

## Output Format

The command should produce output similar to:

```text
Gateway API Status Check
========================

GatewayClass Resources:
-----------------------
NAME                CONTROLLER                           ACCEPTED   AGE
openshift-default   openshift.io/gateway-controller/v1   True       2h

Gateway Resources:
------------------
NAMESPACE           NAME      CLASS               PROGRAMMED   AGE
openshift-ingress   gateway   openshift-default   True         1h

Gateway Details: gateway (openshift-ingress)
---------------------------------------------
Address: a0a658ac4b2d447fa83d2f247a0dc714-1135029665.us-west-1.elb.amazonaws.com
Listeners:
  - Name: demo
    Hostname: *.gwapi.apps.ci-ln-42q9hck-76ef8.aws-4.ci.openshift.org
    Port: 80
    Protocol: HTTP
    Status: Ready
    Attached Routes: 3

Summary:
--------
✓ 1 GatewayClass (1 accepted)
✓ 1 Gateway (1 programmed)
✓ All resources healthy
```

## Notes
- GatewayClass is cluster-scoped, so it's always checked regardless of namespace argument
- Gateway is namespace-scoped, filtered by namespace argument if provided
- The command is read-only and makes no modifications to the cluster
- Useful for verifying successful installation after running /gwapi:install
- Can be run repeatedly to monitor Gateway API resource health
