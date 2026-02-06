# FBC Art Images Plugin

A Claude Code plugin for testing operators built in FBC (File-Based Catalog) by Konflux. This plugin automates the generation of Kubernetes manifests and cluster configuration needed to test operators using images from the art-image-share registry.

## Overview

When testing OpenShift operators built with Konflux's FBC tooling, you need to:

1. Create a **CatalogSource** pointing to the FBC index image
2. Configure **IDMS** (ImageDigestMirrorSet) to mirror images from art-image-share
3. Update the cluster **pull-secret** with credentials to access art-image-share registry

This plugin automates all three steps, providing both a complete setup command and individual commands for granular control.

## Prerequisites

- OpenShift cluster access (4.14+)
- `oc` CLI installed and authenticated
- **`oras` CLI** installed for image discovery ([installation guide](https://oras.land/docs/installation))
- `jq` command-line JSON processor
- **Pull-secret configured**: The cluster pull-secret must include credentials for `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share`. See `how-to-update-pull-secret.md` in this plugin directory for detailed instructions on obtaining and configuring the pull-secret.
- Cluster-admin or similar permissions (for pull-secret and IDMS updates)

## Commands

### `/fbc-art-images:setup`

Complete setup that generates all three manifests and optionally applies them.

**Usage:**
```bash
/fbc-art-images:setup <ocp-version> <operator-name>
```

**Example:**
```bash
/fbc-art-images:setup 4.20 amq-broker-rhel9
```

**What it does:**
1. Generates CatalogSource manifest for the operator
2. Generates IDMS manifest for registry mirroring
3. Optionally applies all manifests to the cluster

**Output files:**
- `.work/fbc-art-images/<ocp-version>_<operator-name>/catalogsource.yaml`
- `.work/fbc-art-images/<ocp-version>_<operator-name>/idms.yaml`

---

### `/fbc-art-images:catalog-source`

Generate only the CatalogSource manifest.

**Usage:**
```bash
/fbc-art-images:catalog-source <ocp-version> <operator-name>
```

**Example:**
```bash
/fbc-art-images:catalog-source 4.20 amq-broker-rhel9
```

**What it does:**
- Creates a CatalogSource pointing to the FBC index image
- Uses the Konflux FBC image pattern: `quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<version>__<operator>`

---

### `/fbc-art-images:idms`

Generate only the IDMS manifest for registry mirroring.

**Usage:**
```bash
/fbc-art-images:idms <ocp-version> <operator-name>
```

**Example:**
```bash
/fbc-art-images:idms 4.20 amq-broker-rhel9
```

**What it does:**
- Discovers all related operator images from the FBC image using `oras` CLI
- Creates ImageDigestMirrorSet to mirror each discovered image to art-images-share repository
- Generates operator-specific IDMS named `art-image-share-<ocp-version>-<operator-name>`

**Important:**
- Requires `oras` CLI to be installed
- Applying an IDMS triggers MachineConfig updates which will cause cluster nodes to restart sequentially (20-30 minutes)

---

## Typical Workflow

### Quick Setup (Recommended)

**Before you begin**, ensure the pull-secret is configured (see `how-to-update-pull-secret.md` for instructions).

For most use cases, use the setup command:

```bash
# Run the setup command
/fbc-art-images:setup 4.20 amq-broker-rhel9

# Review generated manifests
# Choose to apply or manually review
```

### Manual Step-by-Step Setup

For more control, use individual commands:

```bash
# 1. Configure pull-secret first (one time per cluster)
#    See how-to-update-pull-secret.md for detailed instructions

# 2. Generate and apply IDMS (triggers node restarts)
/fbc-art-images:idms 4.20 amq-broker-rhel9

# 3. Wait for nodes to finish updating (20-30 minutes)
oc get mcp
oc get nodes

# 4. Generate and apply CatalogSource
/fbc-art-images:catalog-source 4.20 amq-broker-rhel9

# 5. Verify CatalogSource is ready
oc get catalogsource test-4.20-amq-broker-rhel9-catalog -n openshift-marketplace
```

## After Setup

Once the setup is complete, you can:

1. **View available operators:**
   ```bash
   oc get packagemanifests -n openshift-marketplace | grep <operator-name>
   ```

2. **Create a Subscription to install the operator:**
   ```yaml
   apiVersion: operators.coreos.com/v1alpha1
   kind: Subscription
   metadata:
     name: <operator-name>
     namespace: openshift-operators
   spec:
     channel: stable
     name: <operator-package-name>
     source: <operator-name>-catalog
     sourceNamespace: openshift-marketplace
   ```

3. **Monitor the installation:**
   ```bash
   oc get csv -n openshift-operators
   oc get installplan -n openshift-operators
   ```

## Troubleshooting

### CatalogSource not ready

```bash
# Check CatalogSource status
oc get catalogsource <operator-name>-catalog -n openshift-marketplace -o yaml

# Check catalog pod logs
oc logs -n openshift-marketplace -l olm.catalogSource=<operator-name>-catalog

# Common issues:
# - Image pull errors (check pull-secret)
# - IDMS not applied or nodes not updated
# - Network connectivity to quay.io
```

### Image pull errors

```bash
# Verify pull-secret has art-image-share credentials
# (Should contain quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share)
oc get secret pull-secret -n openshift-config -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq .

# Verify IDMS is applied
oc get imagedigestmirrorset art-image-share-<ocp-version>-<operator-name> -o yaml

# Check node status (nodes must complete MachineConfig updates)
oc get nodes
oc get mcp
```

### MachineConfig updates stuck

```bash
# Check MachineConfigPool status
oc get mcp -o wide

# Check machine-config-operator logs
oc logs -n openshift-machine-config-operator -l k8s-app=machine-config-controller

# If nodes are stuck, check specific node:
oc describe node <node-name>
```

## Security Notes

- **Credentials**: The pull-secret contains sensitive credentials. Handle with care. See `how-to-update-pull-secret.md` for details.
- **File permissions**: Generated files should have restricted permissions (600)
- **Clean up**: Consider deleting intermediate files after applying manifests

## FBC Image Naming Convention

The plugin uses the Konflux FBC image naming convention for per-operator catalogs:

```text
quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__<version>__<operator-name>
```

Examples:
- OCP 4.20, AMQ Broker: `quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.20__amq-broker-rhel9`
- OCP 4.19, Advanced Cluster Management: `quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.19__advanced-cluster-management`
- OCP 4.18, Kubernetes NMState: `quay.io/redhat-user-workloads/ocp-art-tenant/art-fbc:ocp__4.18__kubernetes-nmstate-rhel9-operator`

## Files Created

Generated files are organized under `.work/fbc-art-images/`:

```text
.work/fbc-art-images/
├── <ocp-version>_<operator-name>/
│   ├── catalogsource.yaml           # CatalogSource manifest
│   ├── idms.yaml                    # ImageDigestMirrorSet manifest
│   ├── related-images-list.txt      # List of discovered operator images
│   └── related-images.json          # Raw related images data from oras

```

Example for OCP 4.20 with amq-broker-rhel9:
```text
.work/fbc-art-images/
├── 4.20_amq-broker-rhel9/
│   ├── catalogsource.yaml
│   ├── idms.yaml
│   ├── related-images-list.txt
│   └── related-images.json
```

## Related Documentation

- [Replacing pre-releases with FBCs](https://docs.google.com/document/d/1YpMZrKUHQG1QAVstVY4Z7RvM3jyZec6sMSCYoNOAaA8/edit?tab=t.0)
- [ORAS CLI](https://oras.land/) - OCI Registry As Storage CLI for image artifact discovery
- [Konflux Documentation](https://konflux-ci.dev/)
- [OpenShift Operator Lifecycle Manager](https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html)
- [ImageDigestMirrorSet](https://docs.openshift.com/container-platform/latest/openshift_images/image-configuration.html#images-configuration-registry-mirror_image-configuration)
- [CatalogSource](https://olm.operatorframework.io/docs/concepts/crds/catalogsource/)

## Contributing

This plugin is part of the [ai-helpers](https://github.com/openshift-eng/ai-helpers) repository. Contributions are welcome!

## Support

For issues or questions:
- GitHub Issues: [openshift-eng/ai-helpers](https://github.com/openshift-eng/ai-helpers/issues)
- Plugin Repository: [openshift-eng/ai-helpers](https://github.com/openshift-eng/ai-helpers)
