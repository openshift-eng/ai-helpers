---
name: bump-scos-bootimage
description: Update the pinned SCOS (CentOS Stream CoreOS) bootimage in openshift/installer's scos.json. Use when the OKD team needs to bump bootimages to a newer build.
---

## Name
okd-scos:bump-scos-bootimage

## Synopsis
```text
/okd-scos:bump-scos-bootimage [--build-id <BUILD_ID>]
```

## Description
Updates `data/data/coreos/scos.json` in `openshift/installer` to point at a
newer CentOS Stream CoreOS 10 (SCOS) build. This file pins the bootimage that
OKD clusters use during installation.

The skill discovers the latest eligible build (one available for all four
architectures), runs `plume cosa2stream` inside the CoreOS Assembler
container to regenerate the JSON, verifies the result, and opens a PR.

## Implementation

### Step 1: Determine the target build

1. If `--build-id` was provided, use it directly. Skip to Step 2.

2. Otherwise, discover the latest build available for all 4 architectures.
   Fetch the builds index JSON (accessible from the workspace pod):

   ```bash
   curl -sS "https://releases-rhcos--prod-pipeline.apps.int.prod-stable-spoke1-dc-iad2.itup.redhat.com/storage/prod/streams/c10s/builds/builds.json" \
     | python3 -c "
   import sys, json
   data = json.load(sys.stdin)
   required = {'x86_64','aarch64','s390x','ppc64le'}
   for b in data['builds']:
       if required.issubset(set(b['arches'])):
           print(b['id']); break
   else:
       print('ERROR: no build found with all 4 arches')
       sys.exit(1)
   "
   ```

   > **Note**: The `?stream=...&arch=...` query params serve the HTML browser
   > UI. The JSON API endpoint is at `/storage/prod/streams/c10s/builds/builds.json`.

   **Fallback** (equivalent endpoint, requires Red Hat VPN from outside):
   ```bash
   curl -sS https://rhcos.mirror.openshift.com/art/storage/prod/streams/c10s/builds/builds.json \
     | python3 -c "
   import sys, json
   data = json.load(sys.stdin)
   required = {'x86_64','aarch64','s390x','ppc64le'}
   for b in data['builds']:
       if required.issubset(set(b['arches'])):
           print(b['id']); break
   "
   ```

3. Record the build ID (e.g. `10.0.20260819-0`). Print it.
   **Important**: Recent c10s builds are frequently missing `aarch64`.
   The selected build may be several weeks old — that is expected.

### Step 2: Clone and branch

```bash
gh repo clone openshift/installer -- --depth=1
cd installer
git checkout -b "okd-scos-bootimage-bump-${BUILD_ID}"
```

Record the current (old) build ID for the PR description:
```bash
OLD_BUILD_ID=$(python3 -c "import json; print(json.load(open('data/data/coreos/scos.json'))['architectures']['x86_64']['artifacts']['metal']['release'])")
echo "Old build: $OLD_BUILD_ID"
```

### Step 3: Generate the updated scos.json

Run `plume cosa2stream` inside the CoreOS Assembler container:

```bash
podman run --rm -v "$(pwd):/work:z" --workdir /work \
  quay.io/coreos-assembler/coreos-assembler:latest \
  plume cosa2stream \
    --target data/data/coreos/scos.json \
    --distro rhcos \
    --no-signatures \
    --name c10s \
    --url https://rhcos.mirror.openshift.com/art/storage/prod/streams \
    "x86_64=${BUILD_ID}" \
    "aarch64=${BUILD_ID}" \
    "s390x=${BUILD_ID}" \
    "ppc64le=${BUILD_ID}"
```

> **Critical flags** (confirmed by ART team):
> - `--distro rhcos` — SCOS uses the same distro flag as RHCOS
> - `--no-signatures` — SCOS builds are unsigned
> - `--name c10s` — CentOS Stream 10 stream name

If `podman` is unavailable, try `docker` with the same arguments.

If `rhcos.mirror.openshift.com` is unreachable, use the internal mirror:
```bash
--url https://releases-rhcos--prod-pipeline.apps.int.prod-stable-spoke1-dc-iad2.itup.redhat.com/storage/prod/streams
```

### Step 4: Verify the result

```bash
# 1. Valid JSON
python3 -c "import json; json.load(open('data/data/coreos/scos.json'))"

# 2. All architectures present
python3 -c "
import json
d = json.load(open('data/data/coreos/scos.json'))
arches = sorted(d['architectures'].keys())
assert arches == ['aarch64', 'ppc64le', 's390x', 'x86_64'], f'Missing arches: {arches}'
print('Architectures OK:', arches)
"

# 3. Build ID updated everywhere
echo "New build ID occurrences:"
grep -c "${BUILD_ID}" data/data/coreos/scos.json

echo "Old build ID occurrences (should be 0):"
grep -c "${OLD_BUILD_ID}" data/data/coreos/scos.json || echo "0 — clean"

# 4. Release fields all match
python3 -c "
import json
d = json.load(open('data/data/coreos/scos.json'))
for arch, info in d['architectures'].items():
    for atype, adata in info.get('artifacts', {}).items():
        rel = adata.get('release', '')
        if rel and rel != '${BUILD_ID}':
            print(f'MISMATCH: {arch}/{atype} has release={rel}')
print('Release field check complete')
"
```

### Step 5: Commit and open a PR

```bash
git add data/data/coreos/scos.json
git commit -m "Update SCOS bootimage metadata to ${BUILD_ID}"
git push origin "okd-scos-bootimage-bump-${BUILD_ID}"

gh pr create \
  --repo openshift/installer \
  --title "Update SCOS bootimage metadata to ${BUILD_ID}" \
  --body "Updates \`data/data/coreos/scos.json\` to SCOS build \`${BUILD_ID}\`.

**Previous build**: ${OLD_BUILD_ID}
**New build**: ${BUILD_ID}
**Architectures**: x86_64, aarch64, s390x, ppc64le

Build source: https://rhcos.mirror.openshift.com/art/storage/prod/streams/c10s/builds/${BUILD_ID}/

/cc @Prashanth684

---
AI-assisted response via okd-scos plugin"
```

### Step 6: Report

Print the PR URL and a summary of what changed.

## Arguments
- `--build-id` — specific SCOS build ID to pin (optional; auto-detected if omitted)

## Return Value
- **PR URL**: the URL of the newly created pull request
- **Build ID**: the SCOS build that was pinned
- **Old Build ID**: the previous pinned build

## Examples

1. **Auto-detect latest build and create PR**:
   ```text
   /okd-scos:bump-scos-bootimage
   ```

2. **Pin a specific build**:
   ```text
   /okd-scos:bump-scos-bootimage --build-id 10.0.20260819-0
   ```

## Guidelines

- Only pick builds that have ALL 4 architectures (x86_64, aarch64, s390x, ppc64le)
- Always use `--distro rhcos --no-signatures --name c10s` with `plume cosa2stream`
- `scos.json` is SCOS-only (OKD) — do NOT modify `coreos-rhel-9.json` or `coreos-rhel-10.json`
- The SCOS stream name is `c10s` (CentOS Stream 10), NOT `c9s`
- Always include the AI-generated footer in the PR body
- After the PR merges to `main`, cherry-pick to active release branches if needed
- Frequency: approximately every 4 months, or on demand

## Network Notes

- Both endpoints require Red Hat VPN from a developer laptop
- The internal endpoint `releases-rhcos--prod-pipeline.apps.int.prod-stable-spoke1-dc-iad2.itup.redhat.com` **is accessible from the RWS workspace pod**
- Use the JSON API path (`/storage/prod/streams/c10s/builds/builds.json`), NOT the HTML UI (`?stream=...&arch=...`)
- `rhcos.mirror.openshift.com` mirrors the same data but may not be reachable from the workspace
- If neither endpoint is reachable, report the failure and ask the user to provide the build ID and/or meta.json files manually
