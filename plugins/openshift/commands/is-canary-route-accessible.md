---
description: Check whether the ingress canary route is accessible or not
argument-hint: "[--to-cluster [namespace]]"
---

## Name
openshift:is-canary-route-accessible

## Synopsis
```
/openshift:is-canary-route-accessible
/openshift:is-canary-route-accessible --to-cluster
/openshift:is-canary-route-accessible --to-cluster default
```

## Description

This command checks whether the OpenShift ingress canary route is accessible. When cluster operators are degraded due to ingress-related issues, this command helps diagnose the root cause by testing route accessibility and checking the health of related components (DNS operator, ingress operator, load balancer service, and cluster nodes).

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (`oc`)**: Must be installed and configured
   - Install from: [https://mirror.openshift.com/pub/openshift-v4/clients/ocp/](https://mirror.openshift.com/pub/openshift-v4/clients/ocp/)
   - Verify with: `oc version`

2. **Active cluster connection**: Must be connected to a running OpenShift cluster
   - Verify with: `oc whoami`
   - Ensure KUBECONFIG is set if needed

3. **Sufficient permissions**: Must have cluster-admin privileges
   - Read access to routes, services, cluster operators, nodes
   - Exec access to pods in the target namespace
   - Verify with: `oc auth can-i patch clusterversion`

## Arguments

The command accepts one of the following options:

- **--to-cluster**: check if the ingress canary route is accessible to a cluster pod
  - By default, checking the canary route's accessiblity from a pod the openshift-ingress-operator namespace
  - User can also specify the namespace(not the default openshift-ingress-operator), for exmple, /is-canary-route-accessible --to-cluster test, \
    a pod in the test namespace will curl the canary route
  - If without this option, will check the ingress canary route's accessiblility from outside the cluster

### Arguments Checking

```bash
# Invalid argument
if [ $# -gt 2 ]; then
    echo "Error: too many arguments provided."
    echo ""
    echo "Usage:"
    echo "  /openshift:is-canary-route-accessible"
    echo "  /openshift:is-canary-route-accessible --to-cluster"
    echo "  /openshift:is-canary-route-accessible --to-cluster [namespace]"
    exit 1
fi

# Check the first parameter if it is --to-cluster
if [ -n "$1" ] && [ "$1" != "--to-cluster" ]; then
    echo "Error: the first parameter should be --to-cluster"
    exit 1
fi

# Check the second parameter if it is one of the cluster's namespaces
namespaces=$(oc get ns)
if [ -n "$2" ] && [[ "$namespaces" != *"$2"*]]; then
    echo "Error: the specified namespace doesn't exist"
    exit 1
fi
```
## Implementation

The command performs the following operations:

### 1. Verify Prerequisites

Check that `oc` is available and connected to a cluster:

```bash
# Check if oc is installed
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found. Please install OpenShift CLI."
    exit 1
fi

# Check cluster connectivity
if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to a cluster. Please login with 'oc login'."
    exit 1
fi

# Check permissions
if ! oc auth can-i patch clusterversion &> /dev/null; then
    echo "Error: Insufficient permissions. cluster-admin role required."
    exit 1
fi
```

### 2. Access the ingress canary route

```bash
# Step 1: Define the vars for the checking
ready_pod=""
curl_cmd=""
lb=""
ns=openshift-ingress-operator
co_jsonpath='{.status.conditions[?(@.type=="Available")].status}{.status.conditions[?(@.type=="Progressing")].status}{.status.conditions[?(@.type=="Degraded")].status}'

# Step 2: Prepare the curl command to access the ingress canary route from outside the cluster or inside the cluster
# Get the canary route hostname
route_host=$(oc -n openshift-ingress-canary get route canary -o=jsonpath='{.status.ingress[0].host}')

if [ -z "$1" ]; then
    # No arguments: curl from outside the cluster
    curl_cmd=$(printf "curl https://%s -Iks --connect-timeout 10" "$route_host")
else
    # Has arguments: curl from inside a cluster pod
    # Check if a specific namespace was provided as second argument
    if [ -n "$2" ]; then
        ns="$2"
    fi

    # Find a ready pod in the namespace
    ready_pod=$(oc get pods -n "$ns" -o jsonpath='{range .items[*]}{@.metadata.name}{"\t"}{@.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' | grep 'True' | awk '{print $1}' | head -n 1)

    # Check if we found a ready pod
    if [ -z "$ready_pod" ]; then
        echo "Error: No ready pod found in namespace $ns"
        exit 1
    fi

    curl_cmd=$(printf "oc -n %s exec %s -- curl https://%s -Iks --connect-timeout 10" "$ns" "$ready_pod" "$route_host")
fi

# The curl_cmd variable is now properly set and can be used with eval
echo "Command: $curl_cmd"

# Step 3: Curl the route, if HTTP 200 message is received, that is to say ingerss component works well
eval $curl_cmd;       #used to "ping" the server
output=$(eval $curl_cmd)
if [[ "$output" =~ (HTTP.+200) ]]; then
    echo "HTTP 200 message received, ingress component works well"
    #exit 0
else
    echo "HTTP 200 message not received, will try to find out the reason later"
fi

# Step 4.1: Check the clusteroperator dns
status_dns=$(oc get co dns -o=jsonpath=$co_jsonpath)
if [[ ! "$status_dns" =~ "TrueFalseFalse" ]]; then
    dns_message=$(oc get co dns -o=jsonpath='{.status.conditions[0].message}')
    echo "❌ clusteroperator dns is abnormal: $dns_message"
else
    echo "✅ clusteroperator dns is normal"
fi

# Step 4.2: Check the clusteroperator ingress
status_ingress=$(oc get co ingress -o=jsonpath=$co_jsonpath)
if [[ ! "$status_ingress" =~ "TrueFalseFalse" ]]; then
    ingress_message=$(oc get co ingress -o=jsonpath='{.status.conditions[0].message}')
    echo "❌ clusteroperator ingress is abnormal: $ingress_message"
else
    echo "✅ clusteroperator ingress is normal"
fi

# Step 4.3: Check the load balance service for cloud platform
echo "=== Checking Load Balancer Service ==="
service_list=$(oc -n openshift-ingress get svc -o=jsonpath='{..metadata.name}')
echo "Services in openshift-ingress: $service_list"
echo ""

if [[ "$service_list" =~ "router-default" ]]; then
    lb=$(oc -n openshift-ingress get svc router-default -o=jsonpath='{.status.loadBalancer.ingress[0].ip}{.status.loadBalancer.ingress[0].hostname}')
    lb_status=$(oc -n openshift-ingress get svc router-default -o=jsonpath='{.status.loadBalancer}')

    echo "Load Balancer value: ${lb:-<empty>}"

    # Check if load balancer is properly configured
    if [ -n "$lb" ] && [ "$lb" != "pending" ]; then
        # Check for valid IP (IPv4 or IPv6) or hostname
        if [[ "$lb" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || \
           [[ "$lb" =~ ^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$ ]] || \
           [[ "$lb" =~ ^[a-zA-Z0-9][a-zA-Z0-9\-\.]{18,298}[a-zA-Z0-9]$ ]]; then
               echo "✅ router-default service works as expected"
               echo "Load Balancer: $lb"
               echo "Status: $lb_status"
        else
            echo "⚠️  Load balancer value format is unexpected: $lb"
            echo "Status: $lb_status"
        fi
    else
        echo "⚠️  Something is wrong with router-default service"
        echo "Status: $lb_status"
    fi
else
    echo "ℹ️  router-default service not found in openshift-ingress namespace"
fi
echo ""

# Step 4.4 Check the nodes
not_ready_nodes=$(oc get nodes -o=jsonpath='{range .items[*]}{@.metadata.name}{"\t"}{@.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' | grep -v "True" || true)
if [ -n "$not_ready_nodes" ]; then
  echo "⚠️  not ready nodes are: $not_ready_nodes"
fi
```

## Return Value

The command provides different outputs based on the operation:

**Exit codes:**
- **0**: Operation completed successfully
- **1**: Error occurred (pod not ready, insufficient permissions, invalid parameters)

## Examples

### Example 1: Check if ingress canary route is accessible to the client which is outside of the cluster

```bash
/openshift:is-canary-route-accessible
```
### Example 2: Check if ingress canary route is accessible to a ready pod in the openshift-ingress-operator namespace
```bash
/openshift:is-canary-route-accessible --to-cluster
```

### Example 3: Check if ingress canary route is accessible to a ready pod in a specified namespace(a ready pod in the default namespace)

```bash
/openshift:is-canary-route-accessible --to-cluster default
```

### Example output:
```text
  Ingress Canary Route Accessibility Check Results

  Command executed:
  oc -n openshift-ingress-operator exec ingress-operator-b7576cd6c-8mdl7 -- curl https://canary-openshift-ingress-canary.apps.shudi-g2219.qe.gcp.devcluster.openshift.com -Iks --connect-timeout 10

  ✅ HTTP 200 message received - Ingress component works well from inside the cluster

  Component Health Status:

  1. ✅ Cluster Operator DNS: Normal
    - Status: Available=True, Progressing=False, Degraded=False
  2. ✅ Cluster Operator Ingress: Normal
    - Status: Available=True, Progressing=False, Degraded=False
  3. ✅ Load Balancer Service (router-default): Works as expected
    - Load Balancer IP: 34.66.59.247
    - IP Mode: VIP
    - Status: Properly configured
  4. ✅ Cluster Nodes: All nodes are ready
    - No nodes with NotReady status detected

  Conclusion: The ingress canary route is fully accessible from within the cluster (openshift-ingress-operator namespace). All related components (DNS operator, ingress operator, load balancer service, and cluster nodes) are healthy and functioning normally.
```

## Troubleshooting

### Permission Denied

**Symptom**: Error when trying to get something from the privileged namespace

**Solution**:
```bash
# Check your permissions
oc auth can-i patch clusterversion

# You need cluster-admin role
oc adm policy add-cluster-role-to-user cluster-admin <your-username>
```
