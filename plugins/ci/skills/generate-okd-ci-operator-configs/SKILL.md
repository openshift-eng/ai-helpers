---
name: generate-okd-ci-operator-configs
description: Use when you need to generate OKD/SCOS ci-operator configuration YAML files from ART ocp-build-data. Replicates the logic of doozer's `images:okd prs open` command as a standalone tool.
argument-hint: "<ocp-build-data-path> <okd-version> [--output-dir <path>] [--release-repo <path>] [--base-stream <9|10>] [--github-token <token>] [--dry-run]"
---

Generate OKD/SCOS ci-operator configuration YAML files for the openshift/release repository from ART image metadata using the bundled Python generator.

## Arguments

Parse from: $ARGUMENTS

- First argument: path to the ocp-build-data directory (must contain `group.yml`, `streams.yml`, `images/`).
- Second argument: OKD version string (e.g. `4.18`, `5.0`).
- `--output-dir <path>`: Directory to write ci-operator configs (default for this skill: `./okd-ci-configs`). In an openshift/release checkout, use its `ci-operator/config/` directory.
- `--release-repo <path>`: Path to an openshift/release checkout. Pass it whenever one is available. The generator then checks each repo's OCP config for the branch name, image `capabilities` and builder versions, and reads the content mirror's RPM repo names from `core-services/release-controller/_repos/`. Without it, those checks are skipped, repo names fall back to a hardcoded rule, and the run prints a warning.
- `--base-stream <9|10>`: CentOS Stream for the scos base images. Defaults to 10 for OKD 5.1 and later and 9 for earlier versions. Override it only when the user asks.
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

### 2. Clone ocp-build-data (if not already present)

If the ocp-build-data directory is not provided or does not exist locally, clone it from GitHub:

```bash
git clone https://github.com/openshift-eng/ocp-build-data.git --branch openshift-$OKD_VERSION
```

The branch should match the target OKD version (e.g. `openshift-5.0` for OKD 5.0, `openshift-4.18` for OKD 4.18).

### 3. Validate inputs and run the generator

Verify the build-data directory contains `group.yml`, `streams.yml`, and `images/`. Resolve the arguments into `OCP_BUILD_DATA_PATH`, `OKD_VERSION`, and `OUTPUT_DIR`; pass `./okd-ci-configs` explicitly when the skill's output default is used, since the Python CLI requires `--output-dir`.

```bash
python3 "$SKILL_DIR/generate_okd_ci_configs.py" \
    --ocp-build-data "$OCP_BUILD_DATA_PATH" \
    --okd-version "$OKD_VERSION" \
    --output-dir "$OUTPUT_DIR"
```

Append `--github-token` with the provided token or `--dry-run` when requested. Append `--release-repo "$RELEASE_REPO"` when an openshift/release checkout is available. If `--output-dir` is inside a release checkout, pass that checkout's root.

The generator reads and substitutes ART metadata, resolves payload dependencies, downloads upstream Dockerfiles, and writes one config per `(org, repo, branch)` to:

```text
{output-dir}/{org}/{repo}/{org}-{repo}-{branch}__okd-scos.yaml
```

It handles `okd_alignment` overrides for parent images, Dockerfiles, source paths, context directories, build arguments, build roots, and RPM repository injection.

### 4. Report results

Report the generated config count, output paths, skipped images with reasons, and warnings or errors. A successful invocation can still skip images or refuse incomplete repository configs; include those limitations in the report.

The run ends with two lists. `FIX:` lines are corrections the generator applied from the known-fixes rules below. `CHECK:` lines need a person to look. Copy every `CHECK:` line into the report, and summarize the `FIX:` lines by rule (for example, "160 images: base-stream9 changed to base-stream10").

For configs generated into an openshift/release checkout, the follow-up generation commands are `make ci-operator-configs` and `make jobs`.

### 5. Post-generation checklist

The generator can't decide these from ART metadata. Go through them before calling the output ready, and report each one that applies:

1. **Missing payload components.** Compare the generated repos with the payload's components. New components (for example kube-vip, karpenter-operator and agentic-skills in 5.1) were left out before and had to be added in openshift/release#85803. Every skipped `for_payload` image belongs in the report.
2. **openshift/os.** Its okd-scos config must promote only to `origin/scos-X.Y`, never to `scos-X.Y-art` (#87110, #87847). `OPENSHIFT_VERSION` and the `server-ose-X.Y` entries in `YUM_REPO_NAMES` must match the target version (#84660).
3. **openshift/images.** When the target builds on stream10, the images config must build `base-stream10` from a stream10 RPM cache step, and the mirror mapping needs an `origin_scos-X.Y_base-stream10` entry (#84562).
4. **Hand-maintained images.** For the router (`haproxy-router-base`, `haproxy32`, `haproxy28`) and any other image named in a `CHECK:` line, diff the generated entry against the existing okd-scos config. If the existing config holds a deliberate hand edit, keep it.
5. **Bumping the dev tip.** Never move main/master configs to a new version with a find-and-replace on version strings. #84431 did that, which kept stream9 and stale `ocp/4.22` aliases that #85990 and #85940 had to fix. Regenerate from build data for the new version.
6. **Release controller configs.** `openshift-release-main__okd-scos-X.Y.yaml` isn't generated here. Upgrade jobs can't use a `X-scos-stable` stream until it exists, so point them at the nightly stream until then (#85137).

## Known fixes applied automatically

Every rule below exists because a generated 5.0 or 5.1 config was later fixed by hand in openshift/release. Fixes made only to 4.22 configs are deliberately left out. The code is in [fixups.py](okd_ci_configs/fixups.py). When a new hand fix lands upstream, add a rule there and a line here.

| Rule | What the generator does | Source |
| --- | --- | --- |
| Base stream | For OKD 5.1 and later, `origin/scos-X.Y:base-stream9` parents become `base-stream10`, builder stages included | #85990 |
| dhclient pin | `agent-installer-node-agent` uses `origin/scos-4.22:base-stream9` for 5.0 and later, because CS10 has no `dhclient` | #84562 |
| UPI | `upi-installer` is skipped. UPI isn't tested on OKD | #87242 |
| Mirror host | `base-A-B-rhelN.ocp.svc` in injected RPM repos is rewritten to the target version | #84562 |
| Repo path | The mirror serves each repo at a path equal to its id. With `--release-repo`, the id is checked against `_repos/ocp-X.Y-rhelN.repo` and corrected to the versioned or unversioned name the mirror defines. If neither is there, the image is flagged. Without `--release-repo`, or if that file is missing, RHEL 10 and later get `-X.Y` and RHEL 9 doesn't | #86112 |
| Installer capabilities | Every openshift/installer image gets `capabilities: [intranet]` | #84305 |
| Image list format | Configs use `images: {items: [...]}`, which determinize requires | openshift/release tooling |
| Branch name (`--release-repo`) | If no OCP config exists for the branch, `release-X.Y` and `openshift-X.Y` (and `master` and `main`) are tried, and the one with an OCP config is used | #86173, #85816 |
| Capabilities (`--release-repo`) | Capabilities on the OCP image with the same `dockerfile_path` are copied | #84305 |
| Builder version (`--release-repo`) | Flags a builder tag whose golang or openshift version is older than the OCP config's | #84589, #88570 |
| `.rhel10` Dockerfile (`--release-repo`) | Flags an image when the OCP config also builds a `.rhel10` Dockerfile in the same directory | #88570 |
| Hand-maintained router images | Flags `haproxy-router-base`, `haproxy-router-haproxy32` and `haproxy-router-haproxy28` | #84562, #86771, #87955 |

## Helper layout

The entry point owns argument parsing and input validation. Read the relevant module when diagnosing or changing a specific part of generation:

| Module | Responsibility |
| --- | --- |
| [helpers.py](okd_ci_configs/helpers.py) | Git URL normalization, public upstream mappings, variable substitution, and CI image coordinates |
| [metadata.py](okd_ci_configs/metadata.py) | Load image metadata, resolve OKD tags and pullspecs, and find payload dependencies |
| [dockerfiles.py](okd_ci_configs/dockerfiles.py) | Download upstream Dockerfiles and parse FROM instructions |
| [ci_operator.py](okd_ci_configs/ci_operator.py) | Build image/repository configurations and serialize ci-operator YAML |
| [generator.py](okd_ci_configs/generator.py) | Orchestrate loading, reconciliation, generation, and result reporting |
| [fixups.py](okd_ci_configs/fixups.py) | Rules learned from upstream hand fixes, the cross-check against OCP configs, and the FIX/CHECK report |

When copying this skill into ai-helpers, use `plugins/ci/skills/generate-okd-ci-operator-configs/` and set the frontmatter name to `generate-okd-ci-operator-configs` to match that directory. The helper package needs no plugin manifest registration.

## Key resolution rules

- Streams resolve in order: `okd.resolve_as.image`, `upstream_image`, then `image`.
- Images with `okd_alignment.resolve_as.stream` or `.image` use the resolved pullspec and are not built by this generator.
- Otherwise, images use `registry.ci.openshift.org/origin/scos-{version}:{tag}`. The tag comes from `okd_alignment.tag_name`, or `payload_name`/`name` with the `ose-` prefix stripped.
- Public upstream URLs use the longest matching `public_upstreams` mapping in `group.yml`. A mapping's `public_branch` overrides the source branch; otherwise the source branch is used, with `main` as the fallback when absent.
- Images explicitly disabled for OKD, lacking usable source or parent metadata, or unnecessary for the payload are skipped. Dockerfile download failures and parent-count mismatches also skip images.
