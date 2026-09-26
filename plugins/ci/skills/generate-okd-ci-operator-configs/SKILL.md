---
name: generate-okd-ci-operator-configs
description: Generate OKD/SCOS ci-operator configuration YAML files from ART ocp-build-data. Replicates doozer's images:okd prs open command as a standalone tool.
user-invocable: true
---

# Generate OKD/SCOS ci-operator Configs

Generate ci-operator configuration YAML files for the openshift/release repository
from ART image metadata in ocp-build-data. This replicates the logic of doozer's
`images:okd prs open` command without requiring the doozer runtime.

## Prerequisites

- A clone of `openshift-eng/ocp-build-data` (the branch matching your target version)
- Python 3.11+ with `PyYAML` and `requests` installed
- Optional: a GitHub token for downloading upstream Dockerfiles (avoids rate limits)

## Usage

The helper script is at:
`generate-okd-ci-operator-configs/generate_okd_ci_configs.py`
(relative to this skill's directory).

### Step 1: Clone ocp-build-data

```bash
git clone https://github.com/openshift-eng/ocp-build-data.git --branch openshift-{VERSION}
```

Replace `{VERSION}` with the target OCP version (e.g. `4.18`, `5.0`).

### Step 2: Run the generator

```bash
python3 generate_okd_ci_configs.py \
    --version {VERSION} \
    --ocp-build-data ./ocp-build-data \
    --output-dir ./output \
    [--github-token TOKEN] \
    [--dry-run]
```

### Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--version` | Yes | — | OKD version string (e.g. `4.18`, `5.0`) |
| `--ocp-build-data` | No | `./ocp-build-data` | Path to ocp-build-data checkout |
| `--output-dir` | No | `./output` | Directory for generated ci-operator configs |
| `--ocp-build-data-branch` | No | `openshift-{version}` | Branch to use if cloning ocp-build-data |
| `--github-token` | No | — | GitHub token for downloading upstream Dockerfiles |
| `--dry-run` | No | `false` | Print what would be generated without writing files |

### Step 3: Review output

The script writes ci-operator configs to:
`{output-dir}/{org}/{repo}/{org}-{repo}-{branch}__okd-scos.yaml`

It also prints a JSON summary to stdout with:
- Number of configs generated
- List of output files
- Skipped images and reasons
- Any errors encountered

### Step 4: Next steps

After generating configs, copy them into an openshift/release clone and run:

```bash
make ci-operator-configs
make jobs
```

## What the Script Does

1. Reads ART ocp-build-data (`group.yml`, `streams.yml`, `images/*.yml`)
2. Substitutes `{MAJOR}`, `{MINOR}`, and other group variables
3. Builds the image dependency graph (payload images + their builders/parents)
4. Resolves OKD pullspecs via stream resolution and `okd_alignment` config
5. Maps private repos to public upstreams using `public_upstreams` from `group.yml`
6. Downloads upstream Dockerfiles to parse FROM statements
7. Generates ci-operator YAML configs with proper `base_images`, `build_root`,
   `images`, `promotion`, and `releases` sections

## Key Resolution Rules

### Stream Resolution

- `okd.resolve_as.image` -> use that pullspec
- `upstream_image` -> use that
- Otherwise -> use stream's `image` field

### Image OKD Pullspec

- `okd_alignment.resolve_as.stream` -> resolve via stream rules
- `okd_alignment.resolve_as.image` -> use literal pullspec
- `okd_alignment.tag_name` -> `registry.ci.openshift.org/origin/scos-{version}:{tag_name}`
- Otherwise -> strip `ose-` prefix, use as tag

### Public Upstream URL

Maps private URLs using `public_upstreams` from `group.yml` (longest-match semantics).
