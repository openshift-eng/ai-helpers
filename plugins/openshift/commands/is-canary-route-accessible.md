---
description: Check wether the ingress canary route is accessable or not
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

Sometimes, some cluster operators are abnormal, which may due to something wrong with the ingress operator. 
is-canary-route-accessible could be used check if the ingress canary route is accessable. If yes, all cluster's services are available. 
If not, find out the reason, for example, cluster nodes are not ready, someting is wrong with cluster dns operator etc.

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (`oc`)**: Must be installed and configured
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Verify with: `oc version`

2. **Active cluster connection**: Must be connected to a running OpenShift cluster
   - Verify with: `oc whoami`
   - Ensure KUBECONFIG is set if needed

3. **Sufficient permissions**: Must have cluster-admin privileges
   - Ability to patch ClusterVersion resource
   - Ability to scale deployments in operator namespaces
   - Verify with: `oc auth can-i patch clusterversion`

## Arguments

The command accepts one of the following options:

- **--to-cluster**: check if the ingress canary route is accessable to a cluster pod in the openshift-ingress-operator namespace
  - if accessable, which means ingress component works well
  - if not, check dns, ingress operators' status and the load balancer's service
  - if not, check cluster' nodes

### Arguments Checking

```bash
# Invalid argument
if [ $# -gt 2 ]; then
    echo "Error: too more arguments provided."
    echo ""
    echo "Usage:"
    echo "  /is-canary-route-accessible"
    echo "  /openshift:set-operator-override --to-cluster"
    echo "  /openshift:set-operator-override --to-cluster [namespace]"
    exit 1
fi

# Check the first parameter if it is --to-cluster
if [ "$1" != "--to-cluster" ]; then
    echo "Error: the first parameter should be --to-cluster"
    exit 1
fi

# Check the second parameter if it is one of the cluster's namespaces
namespaces=$(oc get ns)
if [[ ! $namespaces =~ $2]]; then
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

### 2. Access the ingress carary route

```bash
# Setp 1: Define the vars for the checking
ns=openshift-ingress-operator
ready_pod=""
curl_cmd=""
co_jsonpath='{.status.conditions[?(@.type=="Available")].status}{.status.conditions[?(@.type=="Progressing")].status}{.status.conditions[?(@.type=="Degraded")].status}'
lb=""

# Step 2: Prepare the curl command to access the ingress canary route from outside the cluster or inside the cluster
# Get the canary route hostname
route_host=$(oc -n openshift-ingress-canary get route canary -o=jsonpath='{.status.ingress[0].host}')

# Default namespace for cluster pod testing
ns="openshift-ingress-operator"

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
eval $curl_cmd;       #used to "ping" the server
output=$(eval $curl_cmd)
if [[ "$output" =~ (HTTP.+200) ]]; then
    echo "HTTP 200 message received, ingerss component works well"
    #exit 0
else
    echo "HTTP 200 message not received, will try to find out the reason later"
fi

# Step 4.1: Check the clusteroperator dns
status_dns=$(oc get co dns -o=jsonpath=$co_jsonpath)
if [ ! $status_dns =~ "TrueFalseFalse" ]; then
    dns_message=$(oc get co dns -o=jsonpath='{.status.conditions[0].message}')
    echo "❌ clusteroperator dns is abnormal: $dns_message"
else
    echo "✅ clusteroperator dns is normal"
fi

# Step 4.2: Check the clusteroperator ingress
status_ingress=$(oc get co ingress -o=jsonpath=$co_jsonpath)
if [ ! $status_ingress =~ "TrueFalseFalse" ]; then
    ingress_message=$(oc get co ingress -o=jsonpath='{.status.conditions[0].message}')
    echo "❌ clusteroperator ingress is normal: $ingress_message"
else
    echo "✅ clusteroperator ingress is normal"
fi

# Step 4.3: Check the load balance service for cloud platform
service_list=$(oc -n openshift-ingress get svc -o=jsonpath='{..metadata.name}')
if [[ "$service_list" =~ "router-default" ]]; then
    lb=$(oc -n openshift-ingress get svc router-default -o=jsonpath='{.status.loadBalancer.ingress[0].ip}{.status.loadBalancer.ingress[0].hostname}')
    status=$(oc -n openshift-ingress get svc router-default -o=jsonpath='{.status.loadBalancer}')

    # Check if load balancer is properly configured
    # Valid states: IPv4, IPv6, or hostname (20+ alphanumeric chars)
    # Invalid states: empty, "pending", or any other unexpected value
    if [[ -n "$lb" && "$lb" != "pending" ]] && \
       [[ "$lb" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ || \
          "$lb" =~ ^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$ || \
          "$lb" =~ ^[a-zA-Z0-9][a-zA-Z0-9\-]{18,298}[a-zA-Z0-9]$ ]]; then
        echo "✅ router-default service works as expected"
        echo "Load Balancer: $lb"
        echo "$status"
    else
        echo "⚠️  Something is wrong with router-default service"
        echo "Load Balancer value: ${lb:-<empty>}"
        echo "Status: $status"
    fi
else
    echo "ℹ️  router-default service not found in openshift-ingress namespace"
fi

#Step 4.4 Check the nodes
not_Ready_Nodes=$(oc get nodes -n default  -o=jsonpath='{range .items[*]}{@.metadata.name}{"\t"}{@..status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' | grep -v "True")
if [ -n "$not_Ready_Nodes" ]; then
  echo "⚠️  not ready nodes are: $not_Ready_Nodes"
fi
```

## Return Value

The command provides different outputs based on the operation:

**Exit codes:**
- **0**: Operation completed successfully
- **1**: Error occurred (pod not ready, insufficient permissions, invalid parameters)

## Examples

### Example 1: Check if ingress canary route is accessable to the client which is outside of the cluster

```
/openshift:is-canary-route-accessible
```
### Example 2: Check if ingress canary route is accessable to a ready pod in the openshift-ingress-operator namespace
```
/openshift:is-canary-route-accessible --to-cluster
```

### Example 3: Check if ingress canary route is accessable to a ready pod in a specified namespace(a ready pod in the default namespace)

```
/openshift:is-canary-route-accessible --to-cluster default
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
