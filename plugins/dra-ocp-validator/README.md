# DRA OCP Validator Plugin

Comprehensive Dynamic Resource Allocation (DRA) feature validation for OpenShift clusters.

## Overview

The `dra-ocp-validator` plugin automates end-to-end validation of DRA features on OpenShift clusters with GPU hardware (NVIDIA, AMD, Intel) or using the dra-example-driver for testing without physical GPUs.

**Key Features:**
- ✅ Automated cluster access verification and hardware discovery
- ✅ Prerequisites installation (NFD, GPU operators, DRA drivers)
- ✅ Feature gate management with cluster patching
- ✅ Comprehensive DRA feature testing (Alpha/Beta/GA based on K8s version)
- ✅ Artifact collection and validation reporting
- ✅ CDMM detection and automatic MIG test skipping (Grace-Blackwell)

## Installation

```bash
/plugin install dra-ocp-validator@ai-helpers
```

## Commands

### `/dra-ocp-validator:validate`

Complete end-to-end DRA validation: setup, test, and report.

```bash
/dra-ocp-validator:validate <kubeconfig-path> [options]
```

**Options:**
- `--driver <nvidia|amd|example>` - Driver to use (default: auto-detect)
- `--features <list>` - Comma-separated features to test (default: all Beta)
- `--skip-install` - Skip driver/operator installation
- `--enable-dynamic-mig` - Enable DynamicMIG feature gate (required for Partitionable Devices)
- `--driver-version <version>` - Specific driver version (default: latest)
- `--output-dir <path>` - Output directory (default: ./dra-validation-<timestamp>)

**Examples:**
```bash
# Full validation on NVIDIA cluster with MIG support
/dra-ocp-validator:validate ~/kubeconfig --driver nvidia --enable-dynamic-mig

# Test specific features on existing setup
/dra-ocp-validator:validate ~/kubeconfig --skip-install --features partitionable,admin-access

# Test without physical GPUs using dra-example-driver
/dra-ocp-validator:validate ~/kubeconfig --driver example
```

### `/dra-ocp-validator:setup`

Install prerequisites only (no testing).

```bash
/dra-ocp-validator:setup <kubeconfig-path> [options]
```

**Use Case:** Prepare cluster for manual testing or deferred test execution.

### `/dra-ocp-validator:test`

Run tests only (assumes setup already done).

```bash
/dra-ocp-validator:test <kubeconfig-path> [options]
```

**Use Case:** Re-run tests on already configured cluster, or test subset of features.

### `/dra-ocp-validator:cleanup`

Clean up test resources and optionally uninstall drivers.

```bash
/dra-ocp-validator:cleanup <kubeconfig-path> [options]
```

**Options:**
- `--remove-driver` - Uninstall DRA driver
- `--remove-operator` - Uninstall GPU operator
- `--keep-namespaces` - Don't delete test namespaces

## Supported Features

| Feature | K8s 1.34 | K8s 1.35 | K8s 1.36 | KEP |
|---------|----------|----------|----------|-----|
| Partitionable Devices | Beta | Beta | Beta | [KEP-4815](https://github.com/kubernetes/enhancements/issues/4815) |
| Admin Access | Beta | Beta | Beta | - |
| Prioritized List | Beta | Beta | Beta | [KEP-4816](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/4816-dra-prioritized-list/README.md) |
| PodResources API | Beta | Beta | Beta | - |
| Extended Resources | - | Alpha | Beta | [KEP-5004](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/5004-dra-extended-resource/README.md) |
| Device Taints | Alpha | Alpha | Beta | [KEP-5055](https://github.com/kubernetes/enhancements/issues/5055) |

## GPU Vendor Support

### NVIDIA (Production Ready)
- ✅ Blackwell (GB300, GB200)
- ✅ Hopper (H100, H200)
- ✅ MIG support with DYNAMIC_MIG feature gate
- ✅ CDMM detection and MIG test auto-skipping

**Installation:** NVIDIA GPU Operator + NVIDIA DRA Driver via Helm

### dra-example-driver (Testing Only)
- ✅ No physical GPU required
- ✅ Software-emulated DRA resources
- ✅ Full DRA feature testing

### AMD / Intel (Future)
- ⏳ Planned support

## Known Limitations

### CDMM + MIG Incompatibility (NVIDIA Grace-Blackwell)

On GB200/GB300 systems with CDMM (Coherent Driver Memory Management) enabled:
- **CDMM enabled** (default on Grace) → MIG tests will be **auto-skipped** (NVIDIA driver limitation)
- **CDMM disabled** → MIG tests run normally

The plugin automatically detects CDMM status via NUMA node count and skips MIG-dependent tests when needed.

**Reference:** [NVIDIA GPU Operator Known Issues](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/release-notes.html)

## Output

The validator generates:
- **Validation Report** (`DRA-VALIDATION-REPORT-<cluster>-<date>.md`) - Comprehensive results
- **Tarball** (`dra-validation-<cluster>-<date>.tar.gz`) - All test logs and artifacts
- **Individual Test Logs** - Timestamped directories per feature

## Prerequisites

**Cluster Requirements:**
- OpenShift 4.21+ (Kubernetes 1.34+)
- Cluster admin access
- Internet connectivity for pulling images

**Local Tools:**
- `oc` CLI (OpenShift client)
- `helm` CLI (for driver installation)
- `jq` (JSON processing)
- `kubectl` (Kubernetes CLI)

## References

- [Kubernetes DRA Documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/)
- [NVIDIA DRA Driver](https://github.com/NVIDIA/k8s-dra-driver)
- [dra-example-driver](https://github.com/kubernetes-sigs/dra-example-driver)
- [Installation Guide (NVIDIA)](https://gist.github.com/sairameshv/34a154649ec1339ca06664cb887187d6)

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for plugin development guidelines.

## Maintainers

See [OWNERS](./OWNERS) file.
