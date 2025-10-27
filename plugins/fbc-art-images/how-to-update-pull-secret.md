# How to update the pull-secret with the token for art-images-share


## Description
This file provides instructions on how to update the OpenShift cluster's pull-secret to include credentials for pulling images from mirror `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share`. 

Overall, the user fetches the current pull-secret, adds or updates the art-image-share credentials, and applies the updated secret to the cluster.

This is a cluster-scoped configuration that only needs to be done once per cluster, regardless of which operators you're testing.

**Note**: Updating the pull-secret may trigger a cluster-wide update as nodes refresh their credentials.

## Prerequisites

### Obtaining art-image-share Pull Secret

Before running this command, you must obtain the art-image-share pull secret from BitWarden:

1. **Request access to BitWarden collection**:
   - Your rover ID must be added to the rover group: [art-images-share group](https://rover.redhat.com/groups/group/art-images-share)
   - Request access from the ART team on #forum-ocp-art
   - Provide your rover ID when requesting access

2. **Download the pull secret from BitWarden**:
   - Access the BitWarden collection "Art Images Share"
   - Download the pull secret file
   - Save it (for instance) to: `.work/fbc-art-images/art-images-share-pull-secret`
   - Verify it's a valid JSON file with Docker registry credentials

3. **Validate Environment**
- Verify cluster access: `oc whoami`
- Check if user has permissions to access secrets in openshift-config namespace


## Step 1: Fetch Current Pull-Secret
- Retrieve the current pull-secret from the cluster:
  ```bash
  oc get secret/pull-secret -n openshift-config -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d > .work/fbc-art-images/pull-secret.json
  ```
- If the command fails, check if the secret exists, and if you have permissions to update cluster scope secrets

## Step 2: Check for Existing Credentials
- Parse the pull-secret JSON to check if art-image-share credentials already exist
- Look for the key: `auths["quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share"]`
- If credentials exist, you might want to verify they are still valid and skip updating the secret.


## Step 3: Generate Updated Pull-Secret

- Update the pull-secret JSON structure by adding the entry for `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share` from `.work/fbc-art-images/art-images-share-pull-secret`:
  ```json
  {
    "auths": {
      "quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share": {
        "auth": "<base64(token)>"
      },
      ... existing auths ...
    }
  }
  ```
- Save the updated pull-secret to:
  - `.work/fbc-art-images/pull-secret-updated.json` (JSON format)

## Step 4: Create Kubernetes Secret Manifest
- Base64-encode the entire updated pull-secret JSON
  ```bash
  cat .work/fbc-art-images/pull-secret-updated.json | base64
  ```
- Use the following template to generate a `.work/fbc-art-images/pull-secret.yaml` file:
  ```yaml
  apiVersion: v1
  kind: Secret
  metadata:
    name: pull-secret
    namespace: openshift-config
  type: kubernetes.io/dockerconfigjson
  data:
    .dockerconfigjson: <base64-encoded-pull-secret-json>
  ```

## Step 5: Verify access to art-images-share
- Test image pull (any image, below an example):
  ```bash
  podman pull --authfile .work/fbc-art-images/pull-secret-updated.json quay.io/redhat-user-workloads/ocp-art-tenant/art-images-share@sha256:cb6baf5ddd055d99e406d6cee9921833cca16c0fa6ff0d5880df1c30e44e2f7e
  ```

## Step 6: Apply Updated Pull-Secret 
- Apply the manifest to update the `pull-secret` on the cluster:
  ```bash
  oc apply -f .work/fbc-art-images/pull-secret.yaml
  ```
