# DRA Features by Kubernetes Version

Reference for DRA feature maturity levels across Kubernetes/OpenShift versions.

---

## Feature Maturity Matrix

| Feature | K8s 1.33 | K8s 1.34 | K8s 1.35 | K8s 1.36 | KEP | Plugin Flag |
|---------|----------|----------|----------|----------|-----|-------------|
| **Partitionable Devices** | Beta | Beta | Beta | Beta | [KEP-4815](https://github.com/kubernetes/enhancements/issues/4815) | `partitionable` |
| **Admin Access** | Beta | Beta | Beta | Beta | - | `admin-access` |
| **Prioritized List** | Beta | Beta | Beta | Beta | [KEP-4816](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/4816-dra-prioritized-list/README.md) | `prioritized-list` |
| **PodResources API** | Beta | Beta | Beta | Beta | - | `podresources-api` |
| **Extended Resources** | - | - | Alpha | Beta | [KEP-5004](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/5004-dra-extended-resource/README.md) | `extended-resources` |
| **Device Taints** | Alpha | Alpha | Alpha | Beta | [KEP-5055](https://github.com/kubernetes/enhancements/issues/5055) | `device-taints` |

---

## OpenShift to Kubernetes Version Mapping

| OCP Version | K8s Version | Default Tested Features |
|-------------|-------------|-------------------------|
| OCP 4.20 | 1.33.x | partitionable, admin-access, prioritized-list, podresources-api |
| OCP 4.21 | 1.34.x | partitionable, admin-access, prioritized-list, podresources-api |
| OCP 4.22 | 1.35.x | partitionable, admin-access, prioritized-list, podresources-api, extended-resources |
| OCP 4.23 | 1.36.x | All Beta features |

---

## Feature Descriptions

### 1. Partitionable Devices (KEP-4815)

**Status**: Beta in K8s 1.34+  
**Feature Gate**: `DRAPartitionableDevices` (enabled by default)  
**Driver Requirement**: DYNAMIC_MIG=true (NVIDIA)

**What it does:**
- Allows devices to be partitioned into smaller units
- Tracks resource consumption via SharedCounters
- Enables MIG (Multi-Instance GPU) support on NVIDIA

**Example:**
```yaml
spec:
  devices:
    requests:
    - name: gpu
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.35gb'"
        count: 1
```

**Validation:**
- MIG devices exposed in ResourceSlice
- SharedCounters track memory slice consumption
- Pods scheduled with partitioned devices

---

### 2. Admin Access

**Status**: Beta in K8s 1.34+  
**Feature Gate**: N/A (core Beta feature)

**What it does:**
- Namespace-level device access control
- Requires label `resource.kubernetes.io/admin-access=true`
- Prevents unauthorized admin access to devices

**Example:**
```yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
spec:
  devices:
    requests:
    - name: gpu
      exactly:
        deviceClassName: mig.nvidia.com
        adminAccess: true
        count: 1
```

**Validation:**
- Unauthorized namespace: ResourceClaim rejected
- Authorized namespace (with label): ResourceClaim accepted

---

### 3. Prioritized List (KEP-4816)

**Status**: Beta in K8s 1.34+  
**Feature Gate**: `DRAPrioritizedList` (enabled by default)

**What it does:**
- Request multiple device alternatives with preference order
- Scheduler selects first available option
- Fallback to secondary options if preferred unavailable

**Example:**
```yaml
spec:
  devices:
    requests:
    - name: preferred-large
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.70gb'"
        count: 1
    - name: fallback-small
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.35gb'"
        count: 2
```

**Validation:**
- Scheduler selects preferred when available
- Scheduler falls back when preferred exhausted
- Allocation shows which request was satisfied

---

### 4. PodResources API

**Status**: Beta in K8s 1.34+  
**Feature Gate**: `DRAPodResourcesAPI` (enabled by default)

**What it does:**
- Kubelet API for querying DRA resource allocations
- Socket at `/var/lib/kubelet/pod-resources/kubelet.sock`
- Provides gRPC API for device monitoring tools

**Example Query:**
```bash
# Requires gRPC client
grpcurl -unix /var/lib/kubelet/pod-resources/kubelet.sock \
  v1.PodResources/List
```

**Validation:**
- Pod.status.resourceClaimStatuses populated
- Socket accessible on nodes
- Device allocations queryable

---

### 5. Extended Resources (KEP-5004)

**Status**: Alpha in K8s 1.35, Beta in K8s 1.36  
**Feature Gate**: `DRAExtendedResources` (Alpha: disabled by default, Beta: enabled)  
**Availability**: K8s 1.35+ only

**What it does:**
- Map DRA devices to traditional resource names
- Backwards compatibility with existing tooling
- Expose DRA devices via `resources.limits`

**Example:**
```yaml
apiVersion: resource.k8s.io/v1
kind: DeviceClass
metadata:
  name: mig.nvidia.com
spec:
  extendedResourceName: nvidia.com/mig-1g.35gb
```

**Validation:**
- DeviceClass with extendedResourceName accepted
- Pods can request via traditional resource name
- Allocations tracked correctly

---

### 6. Device Taints (KEP-5055)

**Status**: Alpha in K8s 1.33-1.35, Beta in K8s 1.36  
**Feature Gate**: `DRADeviceTaints` (Alpha: disabled by default, Beta: enabled)

**What it does:**
- Device-level taints prevent pod scheduling
- Similar to node taints
- Pods need tolerations to use tainted devices

**Example:**
```yaml
# ResourceSlice with device taint
spec:
  devices:
  - name: gpu-0
    taints:
    - key: "special-workload"
      effect: "NoSchedule"
      value: "true"
---
# Pod with toleration
spec:
  tolerations:
  - key: "special-workload"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

**Validation:**
- Devices can have taints in ResourceSlice
- Pods without tolerations rejected
- Pods with tolerations scheduled

---

## Feature Dependencies

### NVIDIA Driver Requirements

| Feature | NVIDIA Driver Requirement |
|---------|---------------------------|
| Partitionable Devices | DYNAMIC_MIG=true in driver env |
| Admin Access | No special requirement |
| Prioritized List | No special requirement |
| PodResources API | No special requirement |
| Extended Resources | K8s 1.35+ API support |
| Device Taints | Driver must apply taints to ResourceSlice |

### Known Limitations

**CDMM + MIG Incompatibility (NVIDIA Grace-Blackwell):**
- CDMM enabled → MIG unavailable (driver limitation)
- Affects: Partitionable Devices feature
- Detection: NUMA node count check
- Workaround: Plugin auto-skips MIG tests when CDMM detected

---

## Testing Strategy

### Beta Features (Default Testing)
Plugin tests all Beta features by default:
```bash
/dra-ocp-validator:validate ~/kubeconfig
# Tests: partitionable, admin-access, prioritized-list, podresources-api
```

### Alpha Features (Opt-in Testing)
Must explicitly request Alpha features:
```bash
/dra-ocp-validator:validate ~/kubeconfig --features device-taints
# Checks if DRADeviceTaints feature gate enabled first
```

### Version-Gated Features
Automatically skipped on unsupported K8s versions:
```bash
# On K8s 1.34:
/dra-ocp-validator:validate ~/kubeconfig --features extended-resources
# → SKIP: requires Kubernetes 1.35+
```

---

## References

- [Kubernetes DRA Documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/)
- [KEP-4815: Partitionable Devices](https://github.com/kubernetes/enhancements/issues/4815)
- [KEP-4816: Prioritized List](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/4816-dra-prioritized-list/README.md)
- [KEP-5004: Extended Resources](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/5004-dra-extended-resource/README.md)
- [KEP-5055: Device Taints](https://github.com/kubernetes/enhancements/issues/5055)
- [Kubernetes v1.36 Release Notes](https://kubernetes.io/blog/2026/03/30/kubernetes-v1-36-sneak-peek/)
