---
description: Check status of Ironic baremetal nodes in OpenShift cluster
---

## Name
openshift:ironic-status

## Synopsis
```
/openshift:ironic-status
```

## Description

The `openshift:ironic-status` command checks the status of Ironic baremetal nodes in an OpenShift cluster.

This command is useful for:
- Monitoring baremetal node health and provisioning status
- Troubleshooting node provisioning issues
- Verifying node enrollment and availability
- Checking node maintenance states
- Diagnosing baremetal infrastructure problems

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (`oc`)**: Must be installed and configured
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Verify with: `oc version`

2. **Active cluster connection**: Must be connected to an OpenShift cluster with baremetal nodes
   - Verify with: `oc whoami`
   - Ensure KUBECONFIG is set if needed

3. **Sufficient permissions**: Must have access to the openshift-machine-api namespace
   - Ability to exec into pods in openshift-machine-api namespace
   - Read access to services and deployments

4. **baremetal cluster**: The cluster must be running on baremetal infrastructure with Metal3/Ironic enabled
   - Verify Metal3 components: `oc get pods -n openshift-machine-api | grep metal3-ironic`

## Implementation

The command performs the following steps to retrieve Ironic node status:

### 1. Detect Ironic Service Endpoint

Locate the Ironic service in the openshift-machine-api namespace:

```bash
# Find the Ironic service (typically named metal3-state)
oc get service -n openshift-machine-api metal3-state

# Get the ClusterIP of the Ironic service
IRONIC_SERVICE=$(oc get service -n openshift-machine-api metal3-state)
IRONIC_IP=$(oc get service -n openshift-machine-api $IRONIC_SERVICE -o jsonpath='{.spec.clusterIP}')

# Ironic API typically runs on port 6385
IRONIC_ENDPOINT="https://localhost:6385"
```

### 2. Retrieve Ironic Credentials

Extract authentication credentials from the baremetal operator container:

```bash
# Find the metal3-baremetal-operator pod
BAREMETAL_OPERATOR_POD=$(oc get pods -n openshift-machine-api -l baremetal.openshift.io/cluster-baremetal-operator=metal3-baremetal-operator -o jsonpath='{.items[0].metadata.name}')

# Extract username from the mounted auth volume
IRONIC_USERNAME=$(oc exec -n openshift-machine-api $BAREMETAL_OPERATOR_POD -c metal3-baremetal-operator -- cat /auth/ironic/username)

# Extract password from the mounted auth volume
IRONIC_PASSWORD=$(oc exec -n openshift-machine-api $BAREMETAL_OPERATOR_POD -c metal3-baremetal-operator -- cat /auth/ironic/password)
```

### 3. Query Ironic Node List

Execute the baremetal client command to retrieve node status:

```bash
# Find the metal3-ironic pod
# Example: oc get pods -n openshift-machine-api
# Output may show: metal3-65bd97647f-hbd48

# Execute baremetal node list command
oc exec -n openshift-machine-api $METAL3_POD -c metal3-ironic -- \
  baremetal \
    --os-cacert /certs/ironic/tls.crt
    --os-auth-type http_basic \
    --os-username "$IRONIC_USERNAME" \
    --os-password "$IRONIC_PASSWORD" \
    --os-endpoint "$IRONIC_ENDPOINT" \
    node list
```

### 4. Parse and Present Node Information

The output typically includes:

- **UUID**: Unique identifier for each node
- **Name**: Node name (usually matches BareMetalHost name)
- **Instance UUID**: Associated instance if provisioned
- **Power State**: Current power status (power on, power off)
- **Provisioning State**: Current provisioning status (available, active, deploying, etc.)
- **Maintenance**: Whether the node is in maintenance mode

### 5. Error Handling

Handle common error scenarios:

```bash
# Check if Metal3 components are running
if ! oc get pods -n openshift-machine-api | grep -q metal3; then
    echo "Error: Metal3 components not found. This may not be a baremetal cluster."
    exit 1
fi

# Check if credentials were retrieved successfully
if [ -z "$IRONIC_USERNAME" ] || [ -z "$IRONIC_PASSWORD" ]; then
    echo "Error: Failed to retrieve Ironic credentials"
    exit 1
fi

# Handle connection failures
if ! oc exec ... 2>&1 | grep -q "UUID"; then
    echo "Error: Failed to connect to Ironic API"
    echo "Check that the Ironic service is accessible"
    exit 1
fi
```

## Return Value

The command outputs a table with the following columns:

- **Format**: ASCII table with columns for UUID, Name, Instance UUID, Power State, Provisioning State, and Maintenance

**Example output:**
```
+--------------------------------------+------------------------+--------------------------------------+-------------+--------------------+-------------+
| UUID                                 | Name                   | Instance UUID                        | Power State | Provisioning State | Maintenance |
+--------------------------------------+------------------------+--------------------------------------+-------------+--------------------+-------------+
| 12345678-1234-1234-1234-123456789012 | openshift-worker-0     | abcdef12-3456-7890-abcd-ef1234567890 | power on    | active             | False       |
| 23456789-2345-2345-2345-234567890123 | openshift-worker-1     | bcdef123-4567-8901-bcde-f12345678901 | power on    | active             | False       |
| 34567890-3456-3456-3456-345678901234 | openshift-worker-2     | None                                 | power off   | available          | False       |
+--------------------------------------+------------------------+--------------------------------------+-------------+--------------------+-------------+
```

**Exit codes:**
- **0**: Successfully retrieved and displayed node status
- **1**: Error occurred (Metal3 not found, credential retrieval failed, connection error)

## Examples

### Example 1: Basic usage

```
/openshift:ironic-status
```

Output:
```
Detecting Ironic endpoint...
Found Ironic service: metal3-state at 172.30.123.45:6385

Retrieving Ironic credentials...
Successfully retrieved credentials from baremetal operator

Querying Ironic node list...

+--------------------------------------+------------------------+--------------------------------------+-------------+--------------------+-------------+
| UUID                                 | Name                   | Instance UUID                        | Power State | Provisioning State | Maintenance |
+--------------------------------------+------------------------+--------------------------------------+-------------+--------------------+-------------+
| 12345678-1234-1234-1234-123456789012 | openshift-worker-0     | abcdef12-3456-7890-abcd-ef1234567890 | power on    | active             | False       |
| 23456789-2345-2345-2345-234567890123 | openshift-worker-1     | bcdef123-4567-8901-bcde-f12345678901 | power on    | active             | False       |
| 34567890-3456-3456-3456-345678901234 | openshift-worker-2     | None                                 | power off   | available          | False       |
+--------------------------------------+------------------------+--------------------------------------+-------------+--------------------+-------------+

Summary: 3 nodes total (2 active, 1 available)
```

## Common Provisioning States

Understanding the provisioning states:

- **available**: Node is ready to be provisioned
- **active**: Node is provisioned and in use
- **deploying**: Node is currently being provisioned
- **deploy failed**: Provisioning attempt failed
- **cleaning**: Node is being cleaned for reuse
- **manageable**: Node is manageable but not available for deployment
- **inspect failed**: Introspection failed
- **error**: Node is in an error state

## Troubleshooting

### Metal3 Components Not Found

If Metal3 components are not running:

```bash
oc get pods -n openshift-machine-api
# Look for pods starting with 'metal3-'

# Check BareMetalHost resources
oc get baremetalhosts -n openshift-machine-api
```

### Credential Retrieval Failure

If unable to retrieve credentials:

```bash
# Check if the secret exists
oc get secrets -n openshift-machine-api | grep metal3

# Verify the baremetal operator pod is running
oc get pods -n openshift-machine-api -l k8s-app=metal3-baremetal-operator
```

### Connection Timeout

If unable to connect to Ironic API:

```bash
# Check if the Ironic pod is running
oc get pods -n openshift-machine-api -l app=metal3

# Check Ironic logs
oc logs -n openshift-machine-api <metal3-pod-name> -c metal3-ironic
```

## Security Considerations

- **Credentials**: The command retrieves sensitive Ironic credentials; ensure output is not shared publicly
- **Cluster access**: Requires exec permissions into cluster pods
- **Read-only operation**: This command only reads node status and does not modify any resources

## See Also

- Metal3 Documentation: https://metal3.io/
- OpenShift baremetal Documentation: https://docs.openshift.com/container-platform/latest/installing/installing_bare_metal/
- Ironic API Reference: https://docs.openstack.org/ironic/latest/
- Related commands: `/openshift:cluster-health-check`

## Notes

- This command is specific to OpenShift clusters deployed on baremetal infrastructure
- The Ironic service endpoint and pod names may vary depending on the OpenShift version
- Ensure you have network connectivity to the cluster

