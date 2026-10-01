---
name: generate-okd-ci-operator-configs
description: Use when you need to generate OKD/SCOS ci-operator configuration YAML files from ART ocp-build-data. Replicates the logic of doozer's `images:okd prs open` command as a standalone tool.
argument-hint: "<ocp-build-data-path> <okd-version> [--output-dir <path>] [--github-token <token>] [--dry-run]"
---

Generate OKD/SCOS ci-operator configuration YAML files for the openshift/release repository from ART image metadata using the bundled Python generator.

## Arguments

Parse from: $ARGUMENTS

- First argument: path to the ocp-build-data directory (must contain `group.yml`, `streams.yml`, `images/`).
- Second argument: OKD version string (e.g. `4.18`, `5.0`).
- `--output-dir <path>`: Directory to write ci-operator configs (default for this skill: `./okd-ci-configs`). In an openshift/release checkout, use its `ci-operator/config/` directory.
- `--github-token <token>`: Optional GitHub token for downloading upstream Dockerfiles. Requests are unauthenticated when omitted.
- `--dry-run`: Print generated YAML without writing files. Upstream Dockerfiles are still downloaded.

If no arguments are provided, look for ocp-build-data at `./tmp-dir/ocp-build-data/` or `../ocp-build-data/`, and derive the OKD version from `group.yml` vars (`MAJOR.MINOR`). Use build data for the requested release; the OKD version argument controls the destination imagestream and does not change the metadata's branches.

## Execution

### 1. Locate the bundled helper

Set `SKILL_DIR` to the absolute directory containing this `SKILL.md`. The entry point is [generate_okd_ci_configs.py](generate_okd_ci_configs.py) alongside this file.

- In this repository, the skill directory is `.claude/skills/generate-okd-ci-operator-configs-with-helper-script/`.
- In the ai-helpers CI plugin, it is `${CLAUDE_PLUGIN_ROOT}/skills/generate-okd-ci-operator-configs/`.

The entry point imports the sibling [okd_ci_configs package](okd_ci_configs/__init__.py). Keep the whole skill directory together when installing or copying it. Running the entry point by its absolute path works from any working directory without setting `PYTHONPATH` or installing the helper package.

Python 3, PyYAML, and requests are required. Use the project's virtual environment if available. Check dependencies with:

```bash
python3 -c 'import yaml, requests'
```

### 2. Validate inputs and run the generator

Verify the build-data directory contains `group.yml`, `streams.yml`, and `images/`. Resolve the arguments into `OCP_BUILD_DATA_PATH`, `OKD_VERSION`, and `OUTPUT_DIR`; pass `./okd-ci-configs` explicitly when the skill's output default is used, since the Python CLI requires `--output-dir`.

```bash
python3 "$SKILL_DIR/generate_okd_ci_configs.py" \
    --ocp-build-data "$OCP_BUILD_DATA_PATH" \
    --okd-version "$OKD_VERSION" \
    --output-dir "$OUTPUT_DIR"
```

Append `--github-token` with the provided token or `--dry-run` when requested.

The generator reads and substitutes ART metadata, resolves payload dependencies, downloads upstream Dockerfiles, and writes one config per `(org, repo, branch)` to:

```text
{output-dir}/{org}/{repo}/{org}-{repo}-{branch}__okd-scos.yaml
```

It handles `okd_alignment` overrides for parent images, Dockerfiles, source paths, context directories, build arguments, build roots, and RPM repository injection.

### 3. Report results

Report the generated config count, output paths, skipped images with reasons, and warnings or errors. A successful invocation can still skip images or refuse incomplete repository configs; include those limitations in the report.

For configs generated into an openshift/release checkout, the follow-up generation commands are `make ci-operator-configs` and `make jobs`.

## Helper layout

The entry point owns argument parsing and input validation. Read the relevant module when diagnosing or changing a specific part of generation:

| Module | Responsibility |
| --- | --- |
| [helpers.py](okd_ci_configs/helpers.py) | Git URL normalization, public upstream mappings, variable substitution, and CI image coordinates |
| [metadata.py](okd_ci_configs/metadata.py) | Load image metadata, resolve OKD tags and pullspecs, and find payload dependencies |
| [dockerfiles.py](okd_ci_configs/dockerfiles.py) | Download upstream Dockerfiles and parse FROM instructions |
| [ci_operator.py](okd_ci_configs/ci_operator.py) | Build image/repository configurations and serialize ci-operator YAML |
| [generator.py](okd_ci_configs/generator.py) | Orchestrate loading, reconciliation, generation, and result reporting |

When copying this skill into ai-helpers, use `plugins/ci/skills/generate-okd-ci-operator-configs/` and set the frontmatter name to `generate-okd-ci-operator-configs` to match that directory. The helper package needs no plugin manifest registration.

## Key resolution rules

- Streams resolve in order: `okd.resolve_as.image`, `upstream_image`, then `image`.
- Images with `okd_alignment.resolve_as.stream` or `.image` use the resolved pullspec and are not built by this generator.
- Otherwise, images use `registry.ci.openshift.org/origin/scos-{version}:{tag}`. The tag comes from `okd_alignment.tag_name`, or `payload_name`/`name` with the `ose-` prefix stripped.
- Public upstream URLs use the longest matching `public_upstreams` mapping in `group.yml`. A mapping's `public_branch` overrides the source branch; otherwise the source branch is used, with `main` as the fallback when absent.
- Images explicitly disabled for OKD, lacking usable source or parent metadata, or unnecessary for the payload are skipped. Dockerfile download failures and parent-count mismatches also skip images.
