---
description: Update OpenShift node firmware via HostFirmwareComponents CRD [host-name] [component] [firmware-url]
argument-hint: "[host-name] [component] [firmware-url]"
---

## Name
openshift:firmware-update

## Synopsis
```
/openshift:firmware-update [host-name] [component] [firmware-url]
```

## Description

The `firmware-update` command performs firmware updates on OpenShift baremetal nodes using the HostFirmwareComponents (HFC) Custom Resource Definition. It automates the process of updating BIOS, BMC, NIC, and other firmware components on baremetal hosts managed by Metal3.

This command is useful for:
- Updating BMC/iDRAC/iLO firmware on baremetal nodes
- Applying BIOS updates to worker or master nodes
- Updating NIC firmware for network interface cards
- Managing firmware lifecycle in baremetal OpenShift clusters
- Day-2 operations on baremetal infrastructure

The command can run in:
- **Interactive mode**: Prompts for host, component, and firmware details
- **Non-interactive mode**: Accepts all parameters as command arguments

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift baremetal cluster**: Running cluster with baremetal platform
   - Verify with: `oc get infrastructure cluster -o jsonpath='{.status.platform}'`
   - Should return: `BareMetal`

2. **Cluster admin privileges**: Required to manage baremetal hosts
   - Verify with: `oc auth can-i '*' baremetalhosts -n openshift-machine-api`

3. **Access to firmware files**: Direct URLs to firmware binaries
   - Dell: Firmware from https://www.dell.com/support
   - HPE: Firmware from https://support.hpe.com
   - Or custom firmware hosting

4. **OpenShift CLI**: `oc` command line tool
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/

## Arguments

- **host-name** (optional): Name of the BareMetalHost to update
  - Example: `worker-01`, `master-00`, `openshift-worker-0`
  - If not provided, command will list available hosts and prompt for selection

- **component** (optional): Firmware component to update
  - Valid values: `bmc`, `bios`, `nic`, `raid`, `disk`
  - Most common: `bmc` (iDRAC/iLO) or `bios`
  - If not provided, command will prompt for selection

- **firmware-url** (optional): Direct URL to firmware file
  - Example (Dell): `https://dl.dell.com/FOLDER12249926M/1/iDRAC-Firmware.EXE`
  - Example (HPE): `https://downloads.hpe.com/pub/softlib2/software1/fwpkg-ilo/p991377599/v243854/ilo5_302.fwpkg`
  - If not provided, command will prompt for URL

## Implementation

The command performs the following steps:

### 1. Parse Command Arguments

```bash
HOST_NAME="$1"
COMPONENT="$2"
FIRMWARE_URL="$3"
```

If any arguments are missing, enter interactive mode to gather them.

### 2. Select Target Host and Get Current Firmware Info

List available baremetal hosts:

```bash
oc get bmh -n openshift-machine-api
```

If `HOST_NAME` is not provided, prompt user to select from list.

Get vendor and current firmware information:

```bash
# Get vendor
VENDOR=$(oc get bmh -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.hardware.firmware.bios.vendor}')
echo "Vendor: $VENDOR"

# Get current firmware version from HostFirmwareComponents
INITIAL_VERSION=$(oc get hostfirmwarecomponents -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.components[?(@.component=="'$COMPONENT'")].currentVersion}')
echo "Current $COMPONENT version: $INITIAL_VERSION"

# List all available firmware components
oc get hostfirmwarecomponents -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.components[*].component}' | tr ' ' '\n'
```

### 3. Create HostUpdatePolicy

Create a HostUpdatePolicy to enable firmware updates on reboot:

```bash
cat <<EOF | oc apply -f -
apiVersion: metal3.io/v1alpha1
kind: HostUpdatePolicy
metadata:
  name: ${HOST_NAME}
  namespace: openshift-machine-api
spec:
  firmwareSettings: onReboot
  firmwareUpdates: onReboot
EOF
```

### 4. Set Up In-Cluster Web Server for Firmware Files

Create a test namespace and configure security:

```bash
TEST_NAMESPACE="firmware-update-test"
oc new-project $TEST_NAMESPACE || oc project $TEST_NAMESPACE

# Set namespace security labels to allow privileged workloads
oc label namespace $TEST_NAMESPACE \
  pod-security.kubernetes.io/enforce=privileged \
  pod-security.kubernetes.io/audit=privileged \
  pod-security.kubernetes.io/warn=privileged \
  --overwrite
```

Label a worker node to host the web server (should not be the node being updated):

```bash
WORKER_NODE=$(oc get nodes -l node-role.kubernetes.io/worker -o jsonpath='{.items[0].metadata.name}')
oc label node $WORKER_NODE nginx-node=true --overwrite
```

Create ConfigMap with firmware URL and component:

```bash
cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: firmware-download
  namespace: $TEST_NAMESPACE
data:
  firmware_url: "$FIRMWARE_URL"
  component: "$COMPONENT"
EOF
```

Create nginx configuration ConfigMap:

```bash
cat <<'EOF' | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-no-ssl
  namespace: firmware-update-test
data:
  default.conf: |
    server {
        listen 8080;
        server_name _;

        location / {
            root /usr/share/nginx/html;
            autoindex on;
        }
    }
EOF
```

Deploy nginx pod with init container to download and extract firmware:

```bash
cat <<'EOF' | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
  namespace: firmware-update-test
  labels:
    app: nginx
spec:
  nodeSelector:
    nginx-node: "true"
  volumes:
    - name: firmware-dir
      emptyDir: {}
    - name: firmware-file
      emptyDir: {}
    - name: firmware-config
      configMap:
        name: firmware-download
    - name: nginx-conf
      configMap:
        name: nginx-no-ssl
    - name: nginx-cache
      emptyDir: {}
    - name: nginx-run
      emptyDir: {}
  initContainers:
    - name: init-download-firmware
      image: ghcr.io/crazy-max/7zip
      imagePullPolicy: IfNotPresent
      env:
        - name: FIRMWARE_URL
          valueFrom:
            configMapKeyRef:
              name: firmware-download
              key: firmware_url
      command:
      - /bin/sh
      - -c
      - |
        set -xe
        rm -f /fw/*
        rm -f /fw-extracted/*
        wget --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36" \
          --directory-prefix=/fw \
          "${FIRMWARE_URL}"

        7za e /fw/* -o/fw-extracted
      volumeMounts:
        - name: firmware-config
          mountPath: /config
        - name: firmware-dir
          mountPath: /fw-extracted
        - name: firmware-file
          mountPath: /fw
  containers:
    - name: nginx
      image: quay.io/openshifttest/nginx-alpine:armbm
      ports:
      - containerPort: 8080
      volumeMounts:
        - name: firmware-dir
          mountPath: /usr/share/nginx/html
        - name: nginx-conf
          mountPath: /etc/nginx/conf.d/
        - name: nginx-cache
          mountPath: /var/cache/nginx
        - name: nginx-run
          mountPath: /var/run
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
  namespace: firmware-update-test
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8080
EOF
```

Create Ingress to expose firmware files:

```bash
# Get cluster domain
CLUSTER_DOMAIN=$(oc get ingress.config/cluster -o jsonpath='{.spec.domain}')
FW_HOST="fw.${CLUSTER_DOMAIN}"

# Create Ingress
cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
  namespace: $TEST_NAMESPACE
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: $FW_HOST
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx-service
            port:
              number: 80
EOF
```

Wait for pod and extract firmware filename:

```bash
oc wait --for=condition=Ready pod/nginx-pod -n $TEST_NAMESPACE --timeout=600s

# Check extraction results
oc logs nginx-pod -n $TEST_NAMESPACE -c init-download-firmware

# Get extracted firmware filename
# For Dell: firmimgFIT.d9
# For HPE: .bin file
FIRMWARE_FILE=$(oc exec nginx-pod -n $TEST_NAMESPACE -- ls /usr/share/nginx/html/ | grep -E '(firmimgFIT\.d9|\.bin)$' | head -1)
echo "Firmware file: $FIRMWARE_FILE"

# Construct firmware URL (IMPORTANT: Use HTTP not HTTPS)
FIRMWARE_URL="http://${FW_HOST}/${FIRMWARE_FILE}"
echo "Firmware URL: $FIRMWARE_URL"

# Test accessibility
oc debug node/$(oc get nodes -l node-role.kubernetes.io/worker -o jsonpath='{.items[0].metadata.name}') -- chroot /host curl -I "$FIRMWARE_URL"
```

### 5. Update HostFirmwareComponents CRD

Patch the HFC to specify the firmware update:

```bash
cat <<EOF | oc patch hostfirmwarecomponents -n openshift-machine-api $HOST_NAME --type=json --patch-file=/dev/stdin
[
  {
    "op": "replace",
    "path": "/spec/updates",
    "value": [
      {
        "component": "$COMPONENT",
        "url": "$FIRMWARE_URL"
      }
    ]
  }
]
EOF

# Verify the update is set
oc get hostfirmwarecomponents -n openshift-machine-api $HOST_NAME -o jsonpath='{.spec.updates}'
```

### 6. Reboot the Host

Trigger a reboot by annotating the BareMetalHost:

```bash
oc annotate baremetalhosts $HOST_NAME reboot.metal3.io= -n openshift-machine-api

# Verify annotation
oc get bmh -n openshift-machine-api $HOST_NAME -o jsonpath='{.metadata.annotations}'
```

### 7. Monitor the Update Process

Get node name and watch status:

```bash
NODE_NAME=$(oc get bmh -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.provisioning.nodeName}')

# Watch node status (may take 10-30 minutes)
echo "Waiting for node to reboot and come back..."
sleep 60
oc wait --for=condition=Ready node/$NODE_NAME --timeout=30m

# Monitor HostFirmwareComponents status
watch -n 10 "oc get hostfirmwarecomponents -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.updates}' | jq"
```

### 8. Verify Firmware Update

Check the updated firmware version:

```bash
UPDATED_VERSION=$(oc get hostfirmwarecomponents -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.components[?(@.component=="'$COMPONENT'")].currentVersion}')

echo "Initial version: $INITIAL_VERSION"
echo "Updated version: $UPDATED_VERSION"

if [ "$INITIAL_VERSION" != "$UPDATED_VERSION" ]; then
  echo "✓ Firmware update successful!"
else
  echo "✗ Firmware version did not change"
fi
```

### 9. Cleanup

Remove the firmware update configuration:

```bash
# Clear the updates
oc patch hostfirmwarecomponents -n openshift-machine-api $HOST_NAME --type=json -p '[{"op": "replace", "path": "/spec/updates", "value": []}]'

# Delete HostUpdatePolicy
oc delete hostupdatepolicy -n openshift-machine-api $HOST_NAME

# Delete nginx web server
oc delete project $TEST_NAMESPACE
oc label node $WORKER_NODE nginx-node-

# Verify cluster health
oc get nodes
oc get co
```

## Return Value

**Success**: Displays firmware update progress and verification results:
```
Vendor: Dell Inc.
Current bmc version: 7.10.70.00
Creating HostUpdatePolicy...
Firmware file: firmimgFIT.d9
Firmware URL: http://fw.apps.cluster.example.com/firmimgFIT.d9
Triggering reboot...
Waiting for node to reboot and come back...
Initial version: 7.10.70.00
Updated version: 7.20.70.50
✓ Firmware update successful!
```

**Failure scenarios**:
- `Error: No baremetal hosts found` - Cluster is not baremetal platform
- `Error: HostUpdatePolicy spec is empty` - Policy not properly configured
- `Error: Firmware file not accessible from BMC` - Network connectivity issue
- `Error: BMH in error state` - Incompatible firmware or download failure

## Examples

### 1. Interactive Mode

```bash
/openshift:firmware-update
```

The command will:
- List available baremetal hosts and prompt for selection
- Display current firmware components and versions
- Ask for component to update (bmc, bios, etc.)
- Request firmware file URL
- Proceed with update process

### 2. Update Dell iDRAC BMC Firmware

```bash
/openshift:firmware-update worker-01 bmc https://dl.dell.com/FOLDER12249926M/1/iDRAC-Firmware.EXE
```

Updates the BMC (iDRAC) firmware on `worker-01` using Dell firmware package.

### 3. Update HPE iLO BMC Firmware

```bash
/openshift:firmware-update worker-02 bmc https://downloads.hpe.com/pub/softlib2/software1/fwpkg-ilo/p991377599/v243854/ilo5_302.fwpkg
```

Updates the BMC (iLO) firmware on `worker-02` using HPE firmware package.

### 4. Update BIOS Firmware

```bash
/openshift:firmware-update master-00 bios https://dl.dell.com/FOLDER11965413M/1/BIOS_C4FT0_WN64_2.24.2.EXE
```

Updates the BIOS firmware on `master-00`.

## Troubleshooting

### BMH in Error State

If the BareMetalHost transitions to `error` state:

```bash
# Check error message
oc get bmh -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.errorMessage}'

# Check operational status
oc get bmh -n openshift-machine-api $HOST_NAME -o jsonpath='{.status.operationalStatus}'

# Check firmware-specific errors
oc describe bmh -n openshift-machine-api $HOST_NAME | grep -A 10 "firmware"
```

**Common causes**:
1. Firmware file not accessible from BMC
2. Wrong firmware format (Dell needs `firmimgFIT.d9`, HPE needs `.bin`)
3. Incompatible firmware version or downgrade attempt
4. BMC network connectivity issues

**Recovery**:
```bash
# Clear firmware update
oc patch hostfirmwarecomponents -n openshift-machine-api $HOST_NAME --type=json -p '[{"op": "replace", "path": "/spec/updates", "value": []}]'

# Power cycle BMH
oc annotate bmh $HOST_NAME -n openshift-machine-api reboot.metal3.io/poweroff=
sleep 30
oc annotate bmh $HOST_NAME -n openshift-machine-api reboot.metal3.io=
```

### Firmware Version Not Changing

If firmware version doesn't change after reboot:

```bash
# Verify HostUpdatePolicy has correct spec
oc get hostupdatepolicy -n openshift-machine-api $HOST_NAME -o yaml

# If spec is empty, recreate it
cat <<EOF | oc apply -f -
apiVersion: metal3.io/v1alpha1
kind: HostUpdatePolicy
metadata:
  name: $HOST_NAME
  namespace: openshift-machine-api
spec:
  firmwareSettings: onReboot
  firmwareUpdates: onReboot
EOF

# Trigger another reboot
oc annotate baremetalhosts $HOST_NAME reboot.metal3.io= -n openshift-machine-api --overwrite
```

### Check Ironic Logs

```bash
IRONIC_POD=$(oc get pods -n openshift-machine-api -l baremetal.openshift.io/cluster-baremetal-operator=metal3-state -o jsonpath='{.items[0].metadata.name}')
oc logs -n openshift-machine-api $IRONIC_POD -c ironic-conductor | grep -i firmware
oc logs -n openshift-machine-api $IRONIC_POD -c ironic-conductor | grep -i error | tail -20
```

### Verify Firmware File Accessibility

```bash
# Test from within cluster
oc run curl-test --image=curlimages/curl:latest --rm -it --restart=Never -- curl -I "$FIRMWARE_URL"

# Check extraction
oc exec nginx-pod -n $TEST_NAMESPACE -- ls -lh /usr/share/nginx/html/
oc logs nginx-pod -n $TEST_NAMESPACE -c init-download-firmware | tail -20
```

## Important Notes

1. **Disruptive Operation**: Node will reboot during firmware update
2. **Workload Impact**: Ensure workloads can tolerate node unavailability
3. **Firmware File Format**:
   - **Dell BMC**: Use `firmimgFIT.d9` extracted from .EXE archives
   - **Dell BIOS**: Typically `.bin` files
   - **HPE BMC**: Use `.bin` extracted from .fwpkg archives
   - **HPE BIOS**: Typically `.bin` files
   - Init container automatically extracts using 7zip
4. **URL Requirements**:
   - **MUST use HTTP, not HTTPS** - BMCs cannot validate SSL certificates
   - Firmware URL must be accessible from BMC network
   - Use in-cluster web server for reliable access
5. **Timeout**: Updates can take 10-30 minutes
6. **Cluster Health**: Monitor cluster operators and nodes after update
7. **Vendor Firmware Sources**:
   - Dell: https://www.dell.com/support (requires proper user agent)
   - HPE: https://support.hpe.com
8. **Web Server Configuration**:
   - Use `quay.io/openshifttest/nginx-alpine:armbm` for nginx
   - Set namespace to `privileged` security level
   - Timeout 600s for large firmware downloads

## Common Firmware Components

- `bios` - System BIOS
- `bmc` - Baseboard Management Controller (iDRAC, iLO)
- `raid` - RAID controller
- `nic` - Network interface cards
- `disk` - Disk firmware
