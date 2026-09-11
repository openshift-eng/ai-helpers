#!/usr/bin/env python3
"""
Standalone OKD/SCOS ci-operator configuration generator.

Replicates the logic of doozer's ``images:okd prs open`` command
without requiring the doozer runtime.  Reads ART ocp-build-data
YAML files and generates ci-operator configuration YAML files.

Dependencies: Python stdlib + PyYAML + requests
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, NamedTuple

import requests
import yaml

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class ImageCoordinate(NamedTuple):
    """Represents a registry.ci.openshift.org/namespace/name:tag coordinate."""

    namespace: str
    name: str
    tag: str

    def unique_key(self) -> str:
        return f"{self.namespace}_{self.name}_{self.tag}"

    def as_dict(self) -> dict:
        return {
            "namespace": self.namespace,
            "name": self.name,
            "tag": self.tag,
        }


# ---------------------------------------------------------------------------
# Pure-Python helpers (replicate artcommonlib utilities)
# ---------------------------------------------------------------------------


def _remove_prefix(s: str, prefix: str) -> str:
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def _remove_prefixes(s: str, *prefixes: str) -> str:
    for p in prefixes:
        s = _remove_prefix(s, p)
    return s


def _remove_suffix(s: str, suffix: str) -> str:
    if suffix and s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def convert_remote_git_to_https(source_url: str) -> str:
    """Normalize any git remote URL to ``https://host/org/repo``."""
    url = source_url.strip().rstrip("/")
    url = _remove_prefixes(url, "http://", "https://", "git://", "git@", "ssh://")
    url = _remove_suffix(url, ".git")
    url = url.split("@", 1)[-1]  # strip username@

    if ":" in url:
        server, org_repo = url.rsplit(":", 1)
    elif "/" in url:
        server, org_repo = url.rsplit("/", 1)
    else:
        return f"https://{url}"

    return f"https://{server}/{org_repo}"


def split_git_url(url: str) -> tuple[str, str, str]:
    """Return ``(host, org, repo)`` from any git URL."""
    https = convert_remote_git_to_https(url)
    rest = https[len("https://") :]
    server, remainder = rest.split("/", 1)
    org, repo_name = remainder.split("/", 1)
    return server, org, repo_name


def deep_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Safely navigate nested dicts."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key)
            if d is None:
                return default
        else:
            return default
    return d if d is not None else default


def substitute_vars(value: str, variables: dict) -> str:
    """Replace ``{VAR}`` placeholders in *value* using *variables*."""
    if not isinstance(value, str):
        return value
    for k, v in variables.items():
        value = value.replace("{" + k + "}", str(v))
    return value


def deep_substitute(obj: Any, variables: dict) -> Any:
    """Recursively substitute {VAR} placeholders in a nested data structure."""
    if isinstance(obj, str):
        return substitute_vars(obj, variables)
    if isinstance(obj, dict):
        return {k: deep_substitute(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_substitute(item, variables) for item in obj]
    return obj


def get_public_upstream(remote_git: str, public_upstreams: list) -> tuple[str, str | None, bool]:
    """
    Map a private git URL to its public equivalent using the group.yml
    ``public_upstreams`` list.

    Uses longest-match semantics to match the original
    ``SourceResolver.get_public_upstream``.

    Returns ``(url, public_branch_or_None, has_public_upstream)``.
    """
    remote_https = convert_remote_git_to_https(remote_git)

    if public_upstreams:
        target_priv_prefix: str | None = None
        target_pub_prefix: str | None = None
        target_pub_branch: str | None = None

        for mapping in public_upstreams:
            priv = mapping["private"]
            pub = mapping["public"]
            https_priv = convert_remote_git_to_https(priv)
            https_pub = convert_remote_git_to_https(pub)

            if remote_https.startswith(f"{https_priv}/") or remote_https == https_priv:
                # Prefer the longest matching prefix
                if target_priv_prefix is None or len(https_priv) > len(target_priv_prefix):
                    target_priv_prefix = https_priv
                    target_pub_prefix = https_pub
                    target_pub_branch = mapping.get("public_branch")

        if target_priv_prefix and target_pub_prefix:
            return (
                f"{target_pub_prefix}{remote_https[len(target_priv_prefix) :]}",
                target_pub_branch,
                True,
            )

    return remote_https, None, False


def convert_to_imagestream_coordinate(pullspec: str) -> ImageCoordinate:
    """Split ``registry.ci.openshift.org/ns/is:tag`` into an ``ImageCoordinate``."""
    if not pullspec.startswith("registry.ci.openshift.org/"):
        raise ValueError(
            f"OKD images must be sourced from registry.ci.openshift.org; cannot use {pullspec}"
        )
    parts = pullspec.split("/")
    namespace = parts[1]
    name_tag = parts[2]
    name, tag = name_tag.split(":", 1)
    return ImageCoordinate(namespace=namespace, name=name, tag=tag)


# ---------------------------------------------------------------------------
# Dockerfile parsing
# ---------------------------------------------------------------------------

_FROM_VALUE_RE = re.compile(
    r"""(?xi)
    \s*
    (?P<image>\S+)
    (?:\s+AS\s+(?P<name>\S+))?
    """,
)


def _image_from(from_value: str) -> tuple[str | None, str | None]:
    m = _FROM_VALUE_RE.match(from_value)
    return m.group("image", "name") if m else (None, None)


def parse_dockerfile_froms(content: str) -> list[tuple[str, str | None]]:
    """Parse ``FROM`` instructions.  Returns ``[(image, stage_name_or_None), ...]``."""
    results: list[tuple[str, str | None]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("FROM "):
            image, stage = _image_from(stripped[5:])
            if image:
                results.append((image, stage))
    return results


# ---------------------------------------------------------------------------
# Downloading files from GitHub
# ---------------------------------------------------------------------------


def download_dockerfile(
    public_url: str,
    branch: str,
    path: str,
    token: str | None = None,
) -> str | None:
    """Download a file from GitHub via raw.githubusercontent.com."""
    _, org, repo = split_git_url(public_url)
    raw_url = f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        resp = requests.get(raw_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text
        print(
            f"  WARNING: HTTP {resp.status_code} downloading {raw_url}",
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        print(f"  WARNING: Error downloading {raw_url}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Lightweight image metadata wrapper
# ---------------------------------------------------------------------------


class ImageMetaInfo:
    """Thin wrapper around a parsed image YAML dict."""

    def __init__(self, distgit_key: str, config: dict[str, Any]):
        self.distgit_key = distgit_key
        self.config = config
        self.children: list[ImageMetaInfo] = []

    @property
    def for_payload(self) -> bool:
        return self.config.get("for_payload", False)

    @property
    def image_name_short(self) -> str:
        name = self.config.get("name", "")
        return name.split("/")[-1]

    @property
    def payload_name(self) -> str | None:
        return self.config.get("payload_name")

    @property
    def okd_alignment(self) -> dict:
        return deep_get(self.config, "content", "source", "okd_alignment", default={})

    @property
    def from_config(self) -> dict:
        return self.config.get("from") or {}

    @property
    def source_git_url(self) -> str | None:
        return deep_get(self.config, "content", "source", "git", "url")

    @property
    def source_git_branch(self) -> str | None:
        return deep_get(self.config, "content", "source", "git", "branch", "target")

    @property
    def source_dockerfile(self) -> str | None:
        return deep_get(self.config, "content", "source", "dockerfile")

    @property
    def source_path(self) -> str | None:
        return deep_get(self.config, "content", "source", "path")


# ---------------------------------------------------------------------------
# Payload tag name resolution
# ---------------------------------------------------------------------------


def get_okd_payload_tag_name(meta: ImageMetaInfo) -> str:
    """
    Determine the OKD payload tag name for an image.
    Matches ``get_okd_payload_tag_name`` in the original.
    """
    tag = deep_get(meta.okd_alignment, "tag_name")
    if tag:
        return tag
    if meta.for_payload:
        name = meta.payload_name or meta.config.get("name", "")
        image_name = name.split("/")[-1]
        return _remove_prefix(image_name, "ose-")
    # Non-payload (builder / base): use image_name_short stripped of ose-
    return _remove_prefix(meta.image_name_short, "ose-")


# ---------------------------------------------------------------------------
# OKD pullspec resolution
# ---------------------------------------------------------------------------


def resolve_okd_from_stream(streams: dict, stream_name: str) -> str:
    """Resolve a stream name to an OKD pullspec (vars must already be substituted)."""
    stream = streams.get(stream_name, {})
    okd_resolve = deep_get(stream, "okd", "resolve_as", "image")
    if okd_resolve:
        return okd_resolve
    upstream = stream.get("upstream_image")
    if upstream:
        return upstream
    img = stream.get("image", "")
    return img


def resolve_okd_from_image_meta(
    meta: ImageMetaInfo,
    image_map: dict[str, ImageMetaInfo],
    streams: dict,
    okd_version: str,
) -> str:
    """
    Return the OKD pullspec that represents *meta* in the CI registry.
    Matches ``resolve_okd_from_image_meta`` in the original.
    """
    alignment = meta.okd_alignment
    resolve_as = alignment.get("resolve_as")
    if resolve_as:
        if isinstance(resolve_as, dict):
            if resolve_as.get("stream"):
                return resolve_okd_from_stream(streams, resolve_as["stream"])
            if resolve_as.get("image"):
                return resolve_as["image"]
        raise ValueError(f"Unable to interpret resolve_as for {meta.distgit_key}")

    tag_name = alignment.get("tag_name")
    if tag_name:
        return f"registry.ci.openshift.org/origin/scos-{okd_version}:{tag_name}"

    name = meta.payload_name or meta.config.get("name", "")
    image_name = name.split("/")[-1]
    image_name = _remove_prefix(image_name, "ose-")
    return f"registry.ci.openshift.org/origin/scos-{okd_version}:{image_name}"


def resolve_okd_from_entry(
    entry: dict,
    meta: ImageMetaInfo,
    image_map: dict[str, ImageMetaInfo],
    streams: dict,
    okd_version: str,
) -> str | None:
    """Resolve a single ``from`` / ``builder`` entry to an OKD pullspec."""
    if entry.get("member"):
        target = image_map.get(entry["member"])
        if not target:
            print(
                f"  WARNING: Could not find member {entry['member']} "
                f"referenced by {meta.distgit_key}",
                file=sys.stderr,
            )
            return None
        return resolve_okd_from_image_meta(target, image_map, streams, okd_version)
    if entry.get("stream"):
        return resolve_okd_from_stream(streams, entry["stream"])
    if entry.get("image"):
        return entry["image"]
    return None


# ---------------------------------------------------------------------------
# Payload-need computation
# ---------------------------------------------------------------------------


def _build_relationships(
    image_map: dict[str, ImageMetaInfo],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Pre-compute parent->children and builder_member->users maps so that
    ``get_needed_for_okd_payload`` does not need O(n) per call.
    """
    children_of: dict[str, list[str]] = {}  # parent dgk -> list of child dgks
    builder_users_of: dict[str, list[str]] = {}  # builder dgk -> list of user dgks

    for dgk, meta in image_map.items():
        from_cfg = meta.from_config
        if not isinstance(from_cfg, dict):
            continue

        parent_member = from_cfg.get("member")
        if parent_member:
            children_of.setdefault(parent_member, []).append(dgk)

        builders = from_cfg.get("builder", [])
        if isinstance(builders, list):
            for b in builders:
                if isinstance(b, dict) and b.get("member"):
                    builder_users_of.setdefault(b["member"], []).append(dgk)

    return children_of, builder_users_of


def get_needed_for_okd_payload(
    meta: ImageMetaInfo,
    image_map: dict[str, ImageMetaInfo],
    children_of: dict[str, list[str]],
    builder_users_of: dict[str, list[str]],
    cache: dict[str, bool],
) -> bool:
    """
    Return True if the image is ``for_payload`` or is a parent / builder of
    a payload image.  Uses *cache* to avoid repeated work.
    """
    dgk = meta.distgit_key
    if dgk in cache:
        return cache[dgk]

    if meta.for_payload:
        cache[dgk] = True
        return True

    # Check children (parent images)
    for child_dgk in children_of.get(dgk, []):
        child = image_map.get(child_dgk)
        if child and get_needed_for_okd_payload(
            child, image_map, children_of, builder_users_of, cache
        ):
            cache[dgk] = True
            return True

    # Check builder users
    for user_dgk in builder_users_of.get(dgk, []):
        user = image_map.get(user_dgk)
        if user and get_needed_for_okd_payload(
            user, image_map, children_of, builder_users_of, cache
        ):
            cache[dgk] = True
            return True

    cache[dgk] = False
    return False


# ---------------------------------------------------------------------------
# ci-operator image config (per-image within a repo config)
# ---------------------------------------------------------------------------


class CiOperatorImageConfig:
    def __init__(
        self,
        meta: ImageMetaInfo,
        promotion_namespace: str,
        promotion_imagestream: str,
    ):
        self.meta = meta
        self.promotion_namespace = promotion_namespace
        self.promotion_imagestream = promotion_imagestream
        self.dockerfile_path: str = "Dockerfile"
        self.context_dir: str | None = None
        self.payload_tag = get_okd_payload_tag_name(meta)
        self.base_image: ImageCoordinate | None = None
        self.coordinate = ImageCoordinate(
            namespace=promotion_namespace,
            name=promotion_imagestream,
            tag=self.payload_tag,
        )
        self.replacements: dict[ImageCoordinate, list[str]] = {}

    def add_replacement(self, coord: ImageCoordinate, replace_list: list[str]):
        self.replacements[coord] = replace_list

    def add_from(self, coord: ImageCoordinate):
        self.base_image = coord

    def set_dockerfile_path(self, path: str):
        self.dockerfile_path = path.lstrip("/")

    def set_context_dir(self, context_dir: str):
        self.context_dir = context_dir

    def get_obj(
        self,
        ci_operator_image_names: dict[ImageCoordinate, str],
    ) -> tuple[dict, dict]:
        """
        Produce the image entry dict and optional raw_step dict.
        Matches ``CiOperatorImageConfig.get_obj`` in the original.
        """
        meta = self.meta
        base_obj: dict = {}
        raw_step: dict = {}

        build_args: list[dict] = [{"name": "TAGS", "value": "scos"}]
        extra_args = deep_get(meta.okd_alignment, "build_args")
        if extra_args and isinstance(extra_args, list):
            build_args.extend(extra_args)

        inject_repos = deep_get(meta.okd_alignment, "inject_rpm_repositories")
        if inject_repos:
            intermediate_tag = f"pre-repo-{self.payload_tag}"
            repo_def_lines: list[str] = []
            for entry in inject_repos:
                repo_id = entry.get("id", "")
                baseurl = entry.get("baseurl", "")
                if not repo_id or not baseurl:
                    raise ValueError(
                        f"Incomplete repo injection data for {meta.distgit_key}: "
                        f"{repo_id} / {baseurl}"
                    )
                repo_def_lines.extend(
                    [
                        f"[{repo_id}]",
                        f"id = {repo_id}",
                        f"name = {repo_id}",
                        f"baseurl = {baseurl}",
                        "enabled = 1",
                        "gpgcheck = 0",
                        "sslverify = false",
                        "skip_if_unavailable = true",
                        "",
                    ]
                )
            repo_lines = "\n".join(repo_def_lines)
            raw_step = {
                "pipeline_image_cache_step": {
                    "commands": (f"cat << EOF > /etc/yum.repos.d/art.repo\n{repo_lines}\nEOF\n"),
                    "from": ci_operator_image_names[self.base_image],
                    "to": intermediate_tag,
                },
            }
            base_obj = {
                "build_args": build_args,
                "from": intermediate_tag,
                "to": self.payload_tag,
            }
        else:
            base_obj = {
                "build_args": build_args,
                "to": self.payload_tag,
            }
            if self.base_image:
                base_obj["from"] = ci_operator_image_names[self.base_image]

        prowjob_dockerfile_path = self.dockerfile_path
        if self.context_dir:
            base_obj["context_dir"] = self.context_dir
            if prowjob_dockerfile_path.startswith(self.context_dir):
                prowjob_dockerfile_path = prowjob_dockerfile_path[len(self.context_dir) :].lstrip(
                    "/"
                )
            else:
                raise ValueError("Expected dockerfile path to start with context_dir")

        if self.dockerfile_path:
            base_obj["dockerfile_path"] = prowjob_dockerfile_path

        inputs: dict = {}
        for coord, replacements in self.replacements.items():
            inputs[ci_operator_image_names[coord]] = {"as": replacements}
        if inputs:
            base_obj["inputs"] = inputs

        return base_obj, raw_step


# ---------------------------------------------------------------------------
# ci-operator config (per-repo)
# ---------------------------------------------------------------------------


class CiOperatorConfig:
    def __init__(
        self,
        org: str,
        repo: str,
        branch: str,
        promotion_namespace: str,
        promotion_imagestream: str,
    ):
        self.org = org
        self.repo = repo
        self.branch = branch
        self.promotion_namespace = promotion_namespace
        self.promotion_imagestream = promotion_imagestream
        self.image_configs: OrderedDict[str, CiOperatorImageConfig] = OrderedDict()
        self.promotion = {
            "to": [
                {
                    "namespace": promotion_namespace,
                    "name": promotion_imagestream,
                },
            ],
        }
        self.build_root: dict | None = None
        self.releases: dict = {}
        self.complete = False

    def get_image_config(self, meta: ImageMetaInfo) -> CiOperatorImageConfig:
        if meta.distgit_key not in self.image_configs:
            self.image_configs[meta.distgit_key] = CiOperatorImageConfig(
                meta,
                self.promotion_namespace,
                self.promotion_imagestream,
            )
        return self.image_configs[meta.distgit_key]

    def add_release(self, name: str, release_def: dict):
        self.releases[name] = release_def

    def set_build_root(self, coord: ImageCoordinate):
        self.build_root = coord.as_dict()

    def get_config_path(self, output_dir: Path) -> Path:
        return (
            output_dir
            / self.org
            / self.repo
            / f"{self.org}-{self.repo}-{self.branch}__okd-scos.yaml"
        )

    def write_config(self, output_dir: Path, dry_run: bool = False) -> Path | None:
        output_path = self.get_config_path(output_dir)

        if not self.complete:
            print(
                f"  Refusing to write: {output_path} (reconciliation did not complete)",
                file=sys.stderr,
            )
            return None

        # Build the name mapping.
        # Start by assuming all dependencies are base images.
        ci_names: dict[ImageCoordinate, str] = {}
        base_image_defs: OrderedDict[ImageCoordinate, bool] = OrderedDict()

        for _, img_cfg in self.image_configs.items():
            for coord in img_cfg.replacements:
                base_image_defs[coord] = True
                ci_names[coord] = coord.unique_key()
            if img_cfg.base_image:
                base_image_defs[img_cfg.base_image] = True
                ci_names[img_cfg.base_image] = img_cfg.base_image.unique_key()

        # Remove images we build ourselves from base_image_defs.
        for _, img_cfg in self.image_configs.items():
            if img_cfg.coordinate in base_image_defs:
                base_image_defs.pop(img_cfg.coordinate)
            ci_names[img_cfg.coordinate] = img_cfg.payload_tag

        images: list[dict] = []
        raw_steps: list[dict] = []
        for _, img_cfg in self.image_configs.items():
            image_obj, raw_step = img_cfg.get_obj(ci_names)
            images.append(image_obj)
            if raw_step:
                raw_steps.append(raw_step)

        base_images: dict[str, dict] = {}
        for coord in base_image_defs:
            base_images[ci_names[coord]] = coord.as_dict()

        config: dict = {
            "images": images,
            "promotion": self.promotion,
            "resources": {
                "*": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "200Mi",
                    },
                },
            },
        }
        if raw_steps:
            config["raw_steps"] = raw_steps
        if base_images:
            config["base_images"] = base_images
        if self.build_root:
            config["build_root"] = {"image_stream_tag": self.build_root}
        if self.releases:
            config["releases"] = self.releases

        if dry_run:
            print(f"\n--- DRY RUN: {output_path} ---", file=sys.stderr)
            print(yaml.safe_dump(config, default_flow_style=False), file=sys.stderr)
            return output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml.safe_dump(config, default_flow_style=False))
        print(f"  Wrote: {output_path}", file=sys.stderr)
        return output_path


# ---------------------------------------------------------------------------
# ci-operator configs collection (all repos)
# ---------------------------------------------------------------------------


class CiOperatorConfigs:
    def __init__(self, promotion_namespace: str, promotion_imagestream: str):
        self.configs: dict[str, CiOperatorConfig] = {}
        self.promotion_namespace = promotion_namespace
        self.promotion_imagestream = promotion_imagestream

    def get_config(self, org: str, repo: str, branch: str) -> CiOperatorConfig:
        key = f"{org}:{repo}:{branch}"
        if key not in self.configs:
            self.configs[key] = CiOperatorConfig(
                org,
                repo,
                branch,
                self.promotion_namespace,
                self.promotion_imagestream,
            )
        return self.configs[key]

    def write_configs(self, output_dir: Path, dry_run: bool = False) -> list[Path]:
        written: list[Path] = []
        for _, config in self.configs.items():
            path = config.write_config(output_dir, dry_run)
            if path:
                written.append(path)
        return written


# ---------------------------------------------------------------------------
# Load all image metadata
# ---------------------------------------------------------------------------


def load_all_image_metadata(
    images_dir: Path,
    variables: dict,
) -> dict[str, ImageMetaInfo]:
    """Load and variable-substitute all image YAML files."""
    image_map: dict[str, ImageMetaInfo] = {}
    for yml_path in sorted(images_dir.glob("*.yml")):
        distgit_key = yml_path.stem
        with open(yml_path) as f:
            try:
                config = yaml.safe_load(f) or {}
            except yaml.YAMLError as exc:
                print(
                    f"  WARNING: Failed to parse {yml_path}: {exc}",
                    file=sys.stderr,
                )
                continue
        config = deep_substitute(config, variables)
        image_map[distgit_key] = ImageMetaInfo(distgit_key, config)

    # Build parent-child relationships.
    for meta in image_map.values():
        from_cfg = meta.from_config
        if isinstance(from_cfg, dict):
            parent_member = from_cfg.get("member")
            if parent_member and parent_member in image_map:
                image_map[parent_member].children.append(meta)

    return image_map


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------


def generate_configs(
    ocp_build_data: Path,
    okd_version: str,
    output_dir: Path,
    github_token: str | None,
    dry_run: bool,
) -> dict:
    """Generate ci-operator configs and return a structured summary dict."""
    errors: list[str] = []

    # ------------------------------------------------------------------
    # 1. Read group.yml
    # ------------------------------------------------------------------
    group_path = ocp_build_data / "group.yml"
    with open(group_path) as f:
        group_config = yaml.safe_load(f)

    variables = group_config.get("vars", {})
    major = variables.get("MAJOR")
    minor = variables.get("MINOR")
    public_upstreams = group_config.get("public_upstreams", [])

    print(f"OKD version: {okd_version} (group: {major}.{minor})", file=sys.stderr)
    print(f"Public upstream mappings: {len(public_upstreams)}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 2. Read streams.yml (substitute variables)
    # ------------------------------------------------------------------
    streams_path = ocp_build_data / "streams.yml"
    with open(streams_path) as f:
        streams_raw = yaml.safe_load(f) or {}
    streams = deep_substitute(streams_raw, variables)
    print(f"Loaded {len(streams)} streams", file=sys.stderr)

    # ------------------------------------------------------------------
    # 3. Load all image configs (substitute variables)
    # ------------------------------------------------------------------
    images_dir = ocp_build_data / "images"
    image_map = load_all_image_metadata(images_dir, variables)
    print(f"Loaded {len(image_map)} image metadata files", file=sys.stderr)

    # Pre-compute parent/builder relationships.
    children_of, builder_users_of = _build_relationships(image_map)

    # ------------------------------------------------------------------
    # 4. Process each image
    # ------------------------------------------------------------------
    ci_operator_configs = CiOperatorConfigs("origin", f"scos-{okd_version}")
    payload_cache: dict[str, bool] = {}
    skipped: list[tuple[str, str]] = []
    processed = 0

    for distgit_key, meta in sorted(image_map.items()):
        alignment = meta.okd_alignment  # already var-substituted

        # -- Skip: okd_alignment.enabled is explicitly False --
        if alignment and "enabled" in alignment and not alignment["enabled"]:
            skipped.append((distgit_key, "OKD alignment disabled"))
            continue

        # -- Skip: no from config --
        from_config = meta.from_config
        if not from_config or not isinstance(from_config, dict):
            skipped.append((distgit_key, "no from config"))
            continue

        # -- Skip: resolve_as is set (image is resolved, not built) --
        if alignment and alignment.get("resolve_as"):
            skipped.append((distgit_key, "resolved via resolve_as"))
            continue

        # -- Skip: not needed for OKD payload construction --
        needed = get_needed_for_okd_payload(
            meta,
            image_map,
            children_of,
            builder_users_of,
            payload_cache,
        )
        if not needed:
            skipped.append((distgit_key, "not needed for OKD payload"))
            continue

        # -- Skip: no GitHub source URL --
        source_url = meta.source_git_url
        source_branch = meta.source_git_branch
        if not source_url or "github.com" not in (source_url or ""):
            skipped.append((distgit_key, "no GitHub source URL"))
            continue

        # -- Resolve desired parent images --
        desired_parents: list[str] = []
        okd_from = alignment.get("from") if alignment else None

        if okd_from is not None:
            # Explicit okd_alignment.from override (list of pullspecs).
            desired_parents = list(okd_from) if isinstance(okd_from, list) else [okd_from]
        else:
            builders = from_config.get("builder", [])
            if not isinstance(builders, list):
                builders = [builders] if builders else []

            for builder in builders:
                if isinstance(builder, dict):
                    upstream = resolve_okd_from_entry(
                        builder,
                        meta,
                        image_map,
                        streams,
                        okd_version,
                    )
                    if not upstream:
                        break
                    desired_parents.append(upstream)

            # Resolve the base image (from.member / from.stream / from.image).
            base_entry: dict = {}
            if from_config.get("member"):
                base_entry = {"member": from_config["member"]}
            elif from_config.get("stream"):
                base_entry = {"stream": from_config["stream"]}
            elif from_config.get("image"):
                base_entry = {"image": from_config["image"]}

            if base_entry:
                parent_upstream = resolve_okd_from_entry(
                    base_entry,
                    meta,
                    image_map,
                    streams,
                    okd_version,
                )
                if len(desired_parents) != len(builders) or not parent_upstream:
                    skipped.append(
                        (
                            distgit_key,
                            "unable to resolve all upstream images",
                        )
                    )
                    continue
                desired_parents.append(parent_upstream)
            elif not desired_parents:
                skipped.append((distgit_key, "no base image to resolve"))
                continue

        if not desired_parents:
            skipped.append((distgit_key, "empty desired_parents"))
            continue

        # -- Resolve build root --
        desired_ci_build_root_coordinate: ImageCoordinate | None = None
        ci_build_root = alignment.get("ci_build_root") if alignment else None
        if ci_build_root and isinstance(ci_build_root, dict):
            br_pullspec = resolve_okd_from_entry(
                ci_build_root,
                meta,
                image_map,
                streams,
                okd_version,
            )
            if br_pullspec:
                try:
                    desired_ci_build_root_coordinate = convert_to_imagestream_coordinate(
                        br_pullspec
                    )
                except ValueError:
                    pass
        if not desired_ci_build_root_coordinate:
            # Default: rhel-9-golang stream.
            default_br = resolve_okd_from_stream(streams, "rhel-9-golang")
            if default_br:
                try:
                    desired_ci_build_root_coordinate = convert_to_imagestream_coordinate(default_br)
                except ValueError:
                    pass

        # -- Map to public upstream --
        public_url, public_branch, _ = get_public_upstream(source_url, public_upstreams)
        if not public_branch:
            public_branch = source_branch

        _, org, repo_name = split_git_url(public_url)
        ci_operator_config = ci_operator_configs.get_config(org, repo_name, public_branch or "main")

        # -- Determine Dockerfile path --
        okd_dockerfile = alignment.get("dockerfile") if alignment else None
        source_dockerfile = meta.source_dockerfile
        dockerfile_path = okd_dockerfile or source_dockerfile or "Dockerfile"

        okd_path = alignment.get("path") if alignment else None
        source_path = meta.source_path
        prefix_path = okd_path or source_path
        if prefix_path:
            dockerfile_path = os.path.join(prefix_path, dockerfile_path)

        # -- Download upstream Dockerfile --
        dockerfile_content = download_dockerfile(
            public_url,
            public_branch or "main",
            dockerfile_path,
            github_token,
        )
        if not dockerfile_content:
            skipped.append(
                (
                    distgit_key,
                    f"could not download Dockerfile at {dockerfile_path}",
                )
            )
            continue

        # Follow single-line symlink-like files.
        while True:
            lines = dockerfile_content.strip().splitlines()
            if len(lines) == 1 and not lines[0].strip().upper().startswith("FROM"):
                new_path = os.path.join(os.path.dirname(dockerfile_path), lines[0].strip())
                dockerfile_content = download_dockerfile(
                    public_url,
                    public_branch or "main",
                    new_path,
                    github_token,
                )
                if not dockerfile_content:
                    break
                dockerfile_path = new_path
            else:
                break

        if not dockerfile_content:
            skipped.append((distgit_key, "could not resolve Dockerfile (symlink?)"))
            continue

        parent_images_parsed = parse_dockerfile_froms(dockerfile_content)

        if len(desired_parents) != len(parent_images_parsed):
            skipped.append(
                (
                    distgit_key,
                    f"parent count mismatch: desired={len(desired_parents)}, "
                    f"dockerfile={len(parent_images_parsed)}",
                )
            )
            continue

        # -- Build ci-operator image config --
        ci_image_config = ci_operator_config.get_image_config(meta)
        ci_operator_config.add_release(
            "latest",
            {
                "integration": {
                    "namespace": "origin",
                    "name": f"scos-{okd_version}",
                },
            },
        )

        # Process builder stages (all FROM except the last).
        builders = from_config.get("builder", [])
        if not isinstance(builders, list):
            builders = [builders] if builders else []

        for index in range(len(parent_images_parsed) - 1):
            builder_entry = builders[index] if index < len(builders) else {}
            # Skip if the builder uses a literal image (no coordinate needed).
            if isinstance(builder_entry, dict) and builder_entry.get("image"):
                continue

            replace: list[str] = []
            dockerfile_image, stage_name = parent_images_parsed[index]
            if stage_name:
                replace.append(stage_name)
            replace.append(dockerfile_image)

            try:
                coord = convert_to_imagestream_coordinate(desired_parents[index])
                ci_image_config.add_replacement(coord, replace)
            except ValueError as exc:
                print(f"  WARNING: {exc}", file=sys.stderr)

        # Set the base image (last FROM).
        try:
            base_coord = convert_to_imagestream_coordinate(desired_parents[-1])
            ci_image_config.add_from(base_coord)
        except ValueError as exc:
            print(f"  WARNING: {exc}", file=sys.stderr)

        ci_image_config.set_dockerfile_path(dockerfile_path)

        # Context dir.
        context_dir = alignment.get("context_dir") if alignment else None
        if context_dir:
            ci_image_config.set_context_dir(context_dir)

        # Build root.
        if desired_ci_build_root_coordinate:
            ci_operator_config.set_build_root(desired_ci_build_root_coordinate)

        ci_operator_config.complete = True
        processed += 1

    # ------------------------------------------------------------------
    # 5. Write output
    # ------------------------------------------------------------------
    print(f"\nProcessed {processed} images", file=sys.stderr)
    if skipped:
        print(f"Skipped {len(skipped)} images:", file=sys.stderr)
        for name, reason in skipped:
            print(f"  {name}: {reason}", file=sys.stderr)

    print("", file=sys.stderr)
    written = ci_operator_configs.write_configs(output_dir, dry_run)
    print(f"\nGenerated {len(written)} ci-operator config files", file=sys.stderr)
    if written:
        print("Output files:", file=sys.stderr)
        for path in written:
            print(f"  {path}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 6. Build structured summary
    # ------------------------------------------------------------------
    repos_covered = set()
    for path in written:
        # Extract org/repo from the path structure
        parts = path.relative_to(output_dir).parts
        if len(parts) >= 2:
            repos_covered.add(f"{parts[0]}/{parts[1]}")

    summary = {
        "okd_version": okd_version,
        "ocp_build_data": str(ocp_build_data),
        "output_dir": str(output_dir),
        "dry_run": dry_run,
        "total_images_loaded": len(image_map),
        "images_processed": processed,
        "images_skipped": len(skipped),
        "configs_generated": len(written),
        "repos_covered": sorted(repos_covered),
        "output_files": [str(p) for p in written],
        "skipped": [{"image": name, "reason": reason} for name, reason in skipped],
        "errors": errors,
    }

    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Generate OKD/SCOS ci-operator configuration YAML files "
        "from ART ocp-build-data.",
    )
    parser.add_argument(
        "--version",
        required=True,
        dest="okd_version",
        help='OKD version string, e.g. "4.18" or "5.0"',
    )
    parser.add_argument(
        "--ocp-build-data",
        default=Path("./ocp-build-data"),
        type=Path,
        help="Path to ocp-build-data directory "
        "(contains group.yml, streams.yml, images/). "
        "Default: ./ocp-build-data",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("./output"),
        type=Path,
        help="Output directory for ci-operator config files. Default: ./output",
    )
    parser.add_argument(
        "--ocp-build-data-branch",
        default=None,
        help="Branch of ocp-build-data to use if cloning. Default: openshift-{version}",
    )
    parser.add_argument(
        "--github-token",
        default=None,
        help="GitHub token for downloading Dockerfiles from upstream repos. "
        "If not provided, uses unauthenticated requests.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be generated without writing files.",
    )

    args = parser.parse_args()

    # Derive branch name if not provided.
    if not args.ocp_build_data_branch:
        args.ocp_build_data_branch = f"openshift-{args.okd_version}"

    # Validate input paths.
    if not args.ocp_build_data.is_dir():
        print(
            f"ERROR: ocp-build-data directory not found: {args.ocp_build_data}",
            file=sys.stderr,
        )
        sys.exit(1)
    for required in ("group.yml", "streams.yml"):
        if not (args.ocp_build_data / required).is_file():
            print(
                f"ERROR: {required} not found in {args.ocp_build_data}",
                file=sys.stderr,
            )
            sys.exit(1)
    if not (args.ocp_build_data / "images").is_dir():
        print(
            f"ERROR: images/ directory not found in {args.ocp_build_data}",
            file=sys.stderr,
        )
        sys.exit(1)

    summary = generate_configs(
        ocp_build_data=args.ocp_build_data,
        okd_version=args.okd_version,
        output_dir=args.output_dir,
        github_token=args.github_token,
        dry_run=args.dry_run,
    )

    # Print structured JSON summary to stdout for agent consumption.
    print(json.dumps(summary, indent=2))

    # Exit with error code if no configs were generated but images existed.
    if summary["configs_generated"] == 0 and summary["total_images_loaded"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
