---
description: Execute opm (Operator Package Manager) commands for building and managing operator catalogs
argument-hint: <action> [arguments...]
---

## Name
olm:opm

## Synopsis
```bash
/olm:opm build-index-image <catalog-path> <index-image-tag> [--cacheless] [--arch=<arch>] [--base-image=<image>] [--builder-image=<image>]
/olm:opm build-semver-index-image <semver-template-file> <index-image-tag> [--cacheless] [--arch=<arch>] [--base-image=<image>] [--builder-image=<image>]
/olm:opm generate-semver-template <bundle-list> [--output=<file>] [--major=true|false] [--minor=true|false]
/olm:opm list packages <index-ref>
/olm:opm list channels <index-ref> [package-name]
/olm:opm list bundles <index-ref> [package-name]
```

## Description
The `olm:opm` command provides a unified interface to `opm` (Operator Package Manager) operations for building and managing operator catalog indexes. It supports building catalog indexes, generating semver templates, and querying catalog contents.

## Arguments
- `$1`: **action** - The action to perform:
  - `build-index-image`: Build an index from an existing catalog directory
  - `build-semver-index-image`: Build an index from a semver template
  - `generate-semver-template`: Generate a semver template file
  - `list`: List catalog contents (requires second argument: `packages`, `channels`, or `bundles`)
- `$2+`: Additional arguments specific to each action (see Actions section below)

## Actions

### build-index-image
Build an operator catalog index image from an existing catalog directory.

**Synopsis:**
```bash
/olm:opm build-index-image <catalog-path> <index-image-tag> [--cacheless] [--arch=<arch>] [--base-image=<image>] [--builder-image=<image>]
```

**Arguments:**
- `$2`: **catalog-path** - Path to the catalog directory containing the index configuration
- `$3`: **index-image-tag** - Full image tag for the resulting index image (e.g., `quay.io/myorg/mycatalog:v1.0.0`)
- `--cacheless`: Optional flag to build a cacheless image (uses `scratch` as base image; `--base-image` and `--builder-image` are ignored when this is set)
- `--arch=<arch>`: Optional architecture specification (default: `multi` for multi-arch build; can specify single arch like `amd64`, `arm64`, `ppc64le`, `s390x`)
- `--base-image=<image>`: Optional base image for the index (default: `quay.io/operator-framework/opm:latest`; ignored if `--cacheless` is set)
- `--builder-image=<image>`: Optional builder image (default: `quay.io/operator-framework/opm:latest`; ignored if `--cacheless` is set)

**Examples:**
```bash
/olm:opm build-index-image catalog quay.io/myorg/mycatalog:v1.0.0
/olm:opm build-index-image catalog quay.io/myorg/mycatalog:v1.0.0 --cacheless
/olm:opm build-index-image catalog quay.io/myorg/mycatalog:v1.0.0 --arch=amd64
```

### build-semver-index-image
Build a multi-architecture operator catalog index image using the semver template format.

**Synopsis:**
```bash
/olm:opm build-semver-index-image <semver-template-file> <index-image-tag> [--cacheless] [--arch=<arch>] [--base-image=<image>] [--builder-image=<image>]
```

**Arguments:**
- `$2`: **semver-template-file** - Path to the semver template configuration file (e.g., `catalog-config.yaml`)
- `$3`: **index-image-tag** - Full image tag for the resulting index image (e.g., `quay.io/myorg/mycatalog:v1.0.0`)
- `--cacheless`: Optional flag to build a cacheless image (uses `scratch` as base image; `--base-image` and `--builder-image` are ignored when this is set)
- `--arch=<arch>`: Optional architecture specification (default: `multi` for multi-arch build; can specify single arch like `amd64`, `arm64`, `ppc64le`, `s390x`)
- `--base-image=<image>`: Optional base image for the index (default: `quay.io/operator-framework/opm:latest`; ignored if `--cacheless` is set)
- `--builder-image=<image>`: Optional builder image (default: `quay.io/operator-framework/opm:latest`; ignored if `--cacheless` is set)

**Examples:**
```bash
/olm:opm build-semver-index-image catalog-config.yaml quay.io/myorg/mycatalog:v1.0.0
/olm:opm build-semver-index-image catalog-config.yaml quay.io/myorg/mycatalog:v1.0.0 --cacheless
/olm:opm build-semver-index-image catalog-config.yaml quay.io/myorg/mycatalog:v1.0.0 --arch=amd64
/olm:opm build-semver-index-image catalog-config.yaml quay.io/myorg/mycatalog:v1.0.0 --arch=multi
```

### generate-semver-template
Generate a semver template configuration file for building operator catalogs.

**Synopsis:**
```bash
/olm:opm generate-semver-template <bundle-list> [--output=<file>] [--major=true|false] [--minor=true|false]
```

**Arguments:**
- `$2`: **bundle-list** - Comma-separated list of bundle image references (e.g., `quay.io/org/bundle:v1.0.0,quay.io/org/bundle:v1.0.1`)
- `--output=<file>`: Optional output file path (default: `catalog-semver-config.yaml` in current directory)
- `--major=true|false`: Optional flag to generate major version channels (default: `true`)
- `--minor=true|false`: Optional flag to generate minor version channels (default: `false`)

**Examples:**
```bash
/olm:opm generate-semver-template quay.io/org/bundle:v1.0.0,quay.io/org/bundle:v1.0.1
/olm:opm generate-semver-template quay.io/org/bundle:v1.0.0,quay.io/org/bundle:v1.0.1 --output=my-catalog.yaml
/olm:opm generate-semver-template quay.io/org/bundle:v1.0.0,quay.io/org/bundle:v1.1.0 --minor=true
```

### list packages
List all operator packages available in a catalog index.

**Synopsis:**
```bash
/olm:opm list packages <index-ref>
```

**Arguments:**
- `$2`: **list** - Must be "list"
- `$3`: **packages** - Must be "packages"
- `$4`: **index-ref** - Catalog index reference, either:
  - Image tag: `quay.io/myorg/mycatalog:v1.0.0`
  - Directory path: `./catalog` or `/path/to/catalog`

**Examples:**
```bash
/olm:opm list packages quay.io/olmqe/nginx8518-index-test:v1
/olm:opm list packages ./catalog
```

### list channels
List channels for operator packages in a catalog index.

**Synopsis:**
```bash
/olm:opm list channels <index-ref> [package-name]
```

**Arguments:**
- `$2`: **list** - Must be "list"
- `$3`: **channels** - Must be "channels"
- `$4`: **index-ref** - Catalog index reference (image tag or directory path)
- `$5`: **package-name** (Optional) - Name of a specific package to list channels for

**Examples:**
```bash
/olm:opm list channels quay.io/olmqe/nginx8518-index-test:v1
/olm:opm list channels quay.io/olmqe/nginx8518-index-test:v1 nginx85187
/olm:opm list channels ./catalog
```

### list bundles
List bundles for operator packages in a catalog index.

**Synopsis:**
```bash
/olm:opm list bundles <index-ref> [package-name]
```

**Arguments:**
- `$2`: **list** - Must be "list"
- `$3`: **bundles** - Must be "bundles"
- `$4`: **index-ref** - Catalog index reference (image tag or directory path)
- `$5`: **package-name** (Optional) - Name of a specific package to list bundles for

**Examples:**
```bash
/olm:opm list bundles quay.io/olmqe/nginx8518-index-test:v1
/olm:opm list bundles quay.io/olmqe/nginx8518-index-test:v1 nginx85187
/olm:opm list bundles ./catalog
```

## Implementation

### Step 1: Parse Action
- Extract the action from `$1`
- Validate the action is one of: `build-index-image`, `build-semver-index-image`, `generate-semver-template`, `list`
- If invalid action, display error with available actions

### Step 2: Check Prerequisites
Verify required tools are installed:
- Check for `opm`: `which opm`
  - If not found, provide installation instructions: <https://github.com/operator-framework/operator-registry/releases>
- For build actions, also check for `podman`: `which podman`
  - If not found, provide installation instructions based on user's platform

### Step 3: Route to Action Handler
Based on the action, call the appropriate implementation:

#### For `build-index-image`:
1. **Parse Arguments and Set Defaults**
   - Extract catalog path from `$2`
   - Extract index image tag from `$3`
   - Parse optional flags: `--cacheless`, `--arch`, `--base-image`, `--builder-image`
   - Set defaults: arch=`multi`, base-image=`quay.io/operator-framework/opm:latest`, builder-image=`quay.io/operator-framework/opm:latest`

2. **Verify Catalog Directory**
   - Check catalog directory exists: `test -d <catalog-path>`

3. **Validate Catalog**
   ```bash
   opm validate <catalog-path>
   ```

4. **Generate Dockerfile**
   - If cacheless: `opm generate dockerfile <catalog-path> --base-image=scratch`
   - If normal: `opm generate dockerfile <catalog-path> -b <builder-image> -i <base-image>`

5. **Determine Build Platform**
   - If arch=`multi`: `linux/amd64,linux/arm64,linux/ppc64le,linux/s390x`
   - Otherwise: `linux/<arch>`

6. **Create Podman Manifest**
   ```bash
   podman manifest rm <index-image-tag> 2>/dev/null || true
   podman manifest create <index-image-tag>
   ```

7. **Build Image**
   ```bash
   podman build --platform <platform-list> --manifest <index-image-tag> . -f catalog.Dockerfile
   ```

8. **Push Manifest**
   ```bash
   podman manifest push <index-image-tag>
   ```

9. **List Bundles in Index**
   ```bash
   opm alpha list bundles <index-image-tag>
   ```

10. **Display Success Message**

#### For `build-semver-index-image`:
1. **Parse Arguments and Set Defaults**
   - Extract semver template file from `$2`
   - Extract index image tag from `$3`
   - Parse optional flags: `--cacheless`, `--arch`, `--base-image`, `--builder-image`
   - Set defaults: arch=`multi`, base-image=`quay.io/operator-framework/opm:latest`, builder-image=`quay.io/operator-framework/opm:latest`

2. **Verify Template File**
   - Check file exists: `test -f <semver-template-file>`

3. **Create Catalog and Render Template**
   ```bash
   mkdir -p catalog
   opm alpha render-template semver <semver-template-file> -o yaml > catalog/index.yaml
   ```

4. **Validate Catalog**
   ```bash
   opm validate catalog
   ```

5. **Generate Dockerfile**
   - If cacheless: `opm generate dockerfile catalog --base-image=scratch`
   - If normal: `opm generate dockerfile catalog -b <builder-image> -i <base-image>`

6. **Determine Build Platform**
   - If arch=`multi`: `linux/amd64,linux/arm64,linux/ppc64le,linux/s390x`
   - Otherwise: `linux/<arch>`

7. **Create Podman Manifest**
   ```bash
   podman manifest rm <index-image-tag> 2>/dev/null || true
   podman manifest create <index-image-tag>
   ```

8. **Build Image**
   ```bash
   podman build --platform <platform-list> --manifest <index-image-tag> . -f catalog.Dockerfile
   ```

9. **Push Manifest**
   ```bash
   podman manifest push <index-image-tag>
   ```

10. **List Bundles in Index**
   ```bash
   opm alpha list bundles <index-image-tag>
   ```

11. **Display Success Message**

#### For `generate-semver-template`:
1. **Parse Arguments and Set Defaults**
   - Extract bundle list from `$2`
   - Parse optional flags: `--output`, `--major`, `--minor`
   - Set defaults: output=`catalog-semver-config.yaml`, major=`true`, minor=`false`

2. **Validate Bundle List**
   - Split by commas
   - Validate each bundle is a valid image reference

3. **Generate YAML Content**
   ```yaml
   Schema: olm.semver
   GenerateMajorChannels: <major-value>
   GenerateMinorChannels: <minor-value>
   Candidate:
     Bundles:
     - Image: <bundle-1>
     - Image: <bundle-2>
   ```

4. **Write Template File**
   - Check if file exists and confirm overwrite if needed
   - Write YAML content

5. **Validate Generated File**
   - Read back and verify YAML is well-formed

6. **Display Success Message**
   - Show file path, bundles included, settings
   - Suggest next step: `/olm:opm build-semver-index-image <output-file> <image-tag>`

#### For `list`:
1. **Parse List Type**
   - Extract list type from `$2` (must be `packages`, `channels`, or `bundles`)
   - If invalid, display error with available types

2. **Parse Index Reference and Optional Package**
   - Extract index-ref from `$3`
   - Extract optional package-name from `$4` (for channels and bundles)

3. **Determine Reference Type**
   - Check if directory: `test -d <index-ref>`

4. **Execute List Command**
   - For packages: `opm alpha list packages <index-ref>`
   - For channels: `opm alpha list channels <index-ref> [package-name]`
   - For bundles: `opm alpha list bundles <index-ref> [package-name]`

5. **Display Results**
   - Show the output with appropriate formatting
   - Display count of items found

## Return Value

**Format**: Varies by action

- **build-index-image / build-semver-index-image**: Success message with image tag, architectures, and bundle list
- **generate-semver-template**: Success message with file path and configuration details
- **list**: Table or list of catalog contents

On failure, displays:
- Clear error message indicating which step/action failed
- Relevant tool output for debugging
- Suggestions for resolution

## Notes

- Ensure you are authenticated to container registries before building/pushing images (use `podman login`)
- For build operations, the `catalog.Dockerfile` is created in the current working directory
- Multi-architecture builds can be time-consuming
- Cacheless builds result in smaller images and use `scratch` as the base image
- When using `--cacheless`, the `--base-image` and `--builder-image` options are ignored (scratch is always used as base)
- Index references can be either image tags or local directory paths
- Bundle images must be accessible from where you build the catalog
- Image tags should include the full registry hostname (e.g., `quay.io/org/image:tag` not `quay/org/image:tag`)

## Related Commands

- `/olm:install` - Install an operator using OLM
- `/olm:catalog` - Manage catalog sources
- `/olm:debug` - Debug OLM issues
