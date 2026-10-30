"""ART image metadata, OKD pullspec resolution, and payload dependencies."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .helpers import _remove_prefix, deep_get, deep_substitute


class ImageMetaInfo:
    """Thin wrapper around a parsed image YAML dict."""

    def __init__(self, distgit_key: str, config: Dict[str, Any]):
        self.distgit_key = distgit_key
        self.config = config
        self.children: List['ImageMetaInfo'] = []

    @property
    def for_payload(self) -> bool:
        return self.config.get('for_payload', False)

    @property
    def image_name_short(self) -> str:
        name = self.config.get('name', '')
        return name.split('/')[-1]

    @property
    def payload_name(self) -> Optional[str]:
        return self.config.get('payload_name')

    @property
    def okd_alignment(self) -> Dict:
        return deep_get(self.config, 'content', 'source', 'okd_alignment', default={})

    @property
    def from_config(self) -> Dict:
        return self.config.get('from') or {}

    @property
    def source_git_url(self) -> Optional[str]:
        return deep_get(self.config, 'content', 'source', 'git', 'url')

    @property
    def source_git_branch(self) -> Optional[str]:
        return deep_get(self.config, 'content', 'source', 'git', 'branch', 'target')

    @property
    def source_dockerfile(self) -> Optional[str]:
        return deep_get(self.config, 'content', 'source', 'dockerfile')

    @property
    def source_path(self) -> Optional[str]:
        return deep_get(self.config, 'content', 'source', 'path')


# ---------------------------------------------------------------------------
# Payload tag name resolution
# ---------------------------------------------------------------------------

def get_okd_payload_tag_name(meta: ImageMetaInfo) -> str:
    """
    Determine the OKD payload tag name for an image.
    Matches ``get_okd_payload_tag_name`` in the original.
    """
    tag = deep_get(meta.okd_alignment, 'tag_name')
    if tag:
        return tag
    if meta.for_payload:
        name = meta.payload_name or meta.config.get('name', '')
        image_name = name.split('/')[-1]
        return _remove_prefix(image_name, 'ose-')
    # Non-payload (builder / base): use image_name_short stripped of ose-
    return _remove_prefix(meta.image_name_short, 'ose-')


# ---------------------------------------------------------------------------
# OKD pullspec resolution
# ---------------------------------------------------------------------------

def resolve_okd_from_stream(streams: Dict, stream_name: str) -> str:
    """Resolve a stream name to an OKD pullspec (vars must already be substituted)."""
    stream = streams.get(stream_name, {})
    okd_resolve = deep_get(stream, 'okd', 'resolve_as', 'image')
    if okd_resolve:
        return okd_resolve
    upstream = stream.get('upstream_image')
    if upstream:
        return upstream
    img = stream.get('image', '')
    return img


def resolve_okd_from_image_meta(
    meta: ImageMetaInfo,
    image_map: Dict[str, ImageMetaInfo],
    streams: Dict,
    okd_version: str,
) -> str:
    """
    Return the OKD pullspec that represents *meta* in the CI registry.
    Matches ``resolve_okd_from_image_meta`` in the original.
    """
    alignment = meta.okd_alignment
    resolve_as = alignment.get('resolve_as')
    if resolve_as:
        if isinstance(resolve_as, dict):
            if resolve_as.get('stream'):
                return resolve_okd_from_stream(streams, resolve_as['stream'])
            if resolve_as.get('image'):
                return resolve_as['image']
        raise ValueError(f'Unable to interpret resolve_as for {meta.distgit_key}')

    tag_name = alignment.get('tag_name')
    if tag_name:
        return f'registry.ci.openshift.org/origin/scos-{okd_version}:{tag_name}'

    name = meta.payload_name or meta.config.get('name', '')
    image_name = name.split('/')[-1]
    image_name = _remove_prefix(image_name, 'ose-')
    return f'registry.ci.openshift.org/origin/scos-{okd_version}:{image_name}'


def resolve_okd_from_entry(
    entry: Dict,
    meta: ImageMetaInfo,
    image_map: Dict[str, ImageMetaInfo],
    streams: Dict,
    okd_version: str,
) -> Optional[str]:
    """Resolve a single ``from`` / ``builder`` entry to an OKD pullspec."""
    if entry.get('member'):
        target = image_map.get(entry['member'])
        if not target:
            print(
                f'  WARNING: Could not find member {entry["member"]} '
                f'referenced by {meta.distgit_key}',
                file=sys.stderr,
            )
            return None
        return resolve_okd_from_image_meta(target, image_map, streams, okd_version)
    if entry.get('stream'):
        return resolve_okd_from_stream(streams, entry['stream'])
    if entry.get('image'):
        return entry['image']
    return None


# ---------------------------------------------------------------------------
# Payload-need computation
# ---------------------------------------------------------------------------

def _build_relationships(
    image_map: Dict[str, ImageMetaInfo],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Pre-compute parent->children and builder_member->users maps so that
    ``get_needed_for_okd_payload`` does not need O(n) per call.
    """
    children_of: Dict[str, List[str]] = {}  # parent dgk -> list of child dgks
    builder_users_of: Dict[str, List[str]] = {}  # builder dgk -> list of user dgks

    for dgk, meta in image_map.items():
        from_cfg = meta.from_config
        if not isinstance(from_cfg, dict):
            continue

        parent_member = from_cfg.get('member')
        if parent_member:
            children_of.setdefault(parent_member, []).append(dgk)

        builders = from_cfg.get('builder', [])
        if isinstance(builders, list):
            for b in builders:
                if isinstance(b, dict) and b.get('member'):
                    builder_users_of.setdefault(b['member'], []).append(dgk)

    return children_of, builder_users_of


def get_needed_for_okd_payload(
    meta: ImageMetaInfo,
    image_map: Dict[str, ImageMetaInfo],
    children_of: Dict[str, List[str]],
    builder_users_of: Dict[str, List[str]],
    cache: Dict[str, bool],
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
        if child and get_needed_for_okd_payload(child, image_map, children_of, builder_users_of, cache):
            cache[dgk] = True
            return True

    # Check builder users
    for user_dgk in builder_users_of.get(dgk, []):
        user = image_map.get(user_dgk)
        if user and get_needed_for_okd_payload(user, image_map, children_of, builder_users_of, cache):
            cache[dgk] = True
            return True

    cache[dgk] = False
    return False


def load_all_image_metadata(
    images_dir: Path,
    variables: dict,
) -> Dict[str, ImageMetaInfo]:
    """Load and variable-substitute all image YAML files."""
    image_map: Dict[str, ImageMetaInfo] = {}
    for yml_path in sorted(images_dir.glob('*.yml')):
        distgit_key = yml_path.stem
        with open(yml_path) as f:
            try:
                config = yaml.safe_load(f) or {}
            except yaml.YAMLError as exc:
                print(f'  WARNING: Failed to parse {yml_path}: {exc}', file=sys.stderr)
                continue
        config = deep_substitute(config, variables)
        image_map[distgit_key] = ImageMetaInfo(distgit_key, config)

    # Build parent-child relationships.
    for meta in image_map.values():
        from_cfg = meta.from_config
        if isinstance(from_cfg, dict):
            parent_member = from_cfg.get('member')
            if parent_member and parent_member in image_map:
                image_map[parent_member].children.append(meta)

    return image_map
