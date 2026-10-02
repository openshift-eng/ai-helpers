"""Orchestrate ART metadata loading, upstream reconciliation, and config generation."""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .ci_operator import CiOperatorConfigs
from .dockerfiles import download_dockerfile, parse_dockerfile_froms
from .helpers import (
    ImageCoordinate,
    convert_to_imagestream_coordinate,
    deep_substitute,
    get_public_upstream,
    split_git_url,
)
from .metadata import (
    _build_relationships,
    get_needed_for_okd_payload,
    load_all_image_metadata,
    resolve_okd_from_entry,
    resolve_okd_from_stream,
)


def generate_configs(
    ocp_build_data: Path,
    okd_version: str,
    output_dir: Path,
    github_token: Optional[str],
    dry_run: bool,
):
    # ------------------------------------------------------------------
    # 1. Read group.yml
    # ------------------------------------------------------------------
    group_path = ocp_build_data / 'group.yml'
    with open(group_path) as f:
        group_config = yaml.safe_load(f)

    variables = group_config.get('vars', {})
    major = variables.get('MAJOR')
    minor = variables.get('MINOR')
    public_upstreams = group_config.get('public_upstreams', [])

    print(f'OKD version: {okd_version} (group: {major}.{minor})')
    print(f'Public upstream mappings: {len(public_upstreams)}')

    # ------------------------------------------------------------------
    # 2. Read streams.yml (substitute variables)
    # ------------------------------------------------------------------
    streams_path = ocp_build_data / 'streams.yml'
    with open(streams_path) as f:
        streams_raw = yaml.safe_load(f) or {}
    streams = deep_substitute(streams_raw, variables)
    print(f'Loaded {len(streams)} streams')

    # ------------------------------------------------------------------
    # 3. Load all image configs (substitute variables)
    # ------------------------------------------------------------------
    images_dir = ocp_build_data / 'images'
    image_map = load_all_image_metadata(images_dir, variables)
    print(f'Loaded {len(image_map)} image metadata files')

    # Pre-compute parent/builder relationships.
    children_of, builder_users_of = _build_relationships(image_map)

    # ------------------------------------------------------------------
    # 4. Process each image
    # ------------------------------------------------------------------
    ci_operator_configs = CiOperatorConfigs('origin', f'scos-{okd_version}')
    payload_cache: Dict[str, bool] = {}
    skipped: List[Tuple[str, str]] = []
    processed = 0

    for distgit_key, meta in sorted(image_map.items()):
        alignment = meta.okd_alignment  # already var-substituted

        # -- Skip: okd_alignment.enabled is explicitly False --
        if alignment and 'enabled' in alignment and not alignment['enabled']:
            skipped.append((distgit_key, 'OKD alignment disabled'))
            continue

        # -- Skip: no from config --
        from_config = meta.from_config
        if not from_config or not isinstance(from_config, dict):
            skipped.append((distgit_key, 'no from config'))
            continue

        # -- Skip: resolve_as is set (image is resolved, not built) --
        if alignment and alignment.get('resolve_as'):
            skipped.append((distgit_key, 'resolved via resolve_as'))
            continue

        # -- Skip: not needed for OKD payload construction --
        needed = get_needed_for_okd_payload(
            meta, image_map, children_of, builder_users_of, payload_cache,
        )
        if not needed:
            skipped.append((distgit_key, 'not needed for OKD payload'))
            continue

        # -- Skip: no GitHub source URL --
        source_url = meta.source_git_url
        source_branch = meta.source_git_branch
        if not source_url or 'github.com' not in (source_url or ''):
            skipped.append((distgit_key, 'no GitHub source URL'))
            continue

        # -- Resolve desired parent images --
        desired_parents: List[str] = []
        okd_from = alignment.get('from') if alignment else None

        if okd_from is not None:
            # Explicit okd_alignment.from override (list of pullspecs).
            desired_parents = list(okd_from) if isinstance(okd_from, list) else [okd_from]
        else:
            builders = from_config.get('builder', [])
            if not isinstance(builders, list):
                builders = [builders] if builders else []

            all_resolved = True
            for builder in builders:
                if isinstance(builder, dict):
                    upstream = resolve_okd_from_entry(
                        builder, meta, image_map, streams, okd_version,
                    )
                    if not upstream:
                        all_resolved = False
                        break
                    desired_parents.append(upstream)

            # Resolve the base image (from.member / from.stream / from.image).
            base_entry: dict = {}
            if from_config.get('member'):
                base_entry = {'member': from_config['member']}
            elif from_config.get('stream'):
                base_entry = {'stream': from_config['stream']}
            elif from_config.get('image'):
                base_entry = {'image': from_config['image']}

            if base_entry:
                parent_upstream = resolve_okd_from_entry(
                    base_entry, meta, image_map, streams, okd_version,
                )
                if len(desired_parents) != len(builders) or not parent_upstream:
                    skipped.append((distgit_key, 'unable to resolve all upstream images'))
                    continue
                desired_parents.append(parent_upstream)
            elif not desired_parents:
                skipped.append((distgit_key, 'no base image to resolve'))
                continue

        if not desired_parents:
            skipped.append((distgit_key, 'empty desired_parents'))
            continue

        # -- Resolve build root --
        desired_ci_build_root_coordinate: Optional[ImageCoordinate] = None
        ci_build_root = alignment.get('ci_build_root') if alignment else None
        if ci_build_root and isinstance(ci_build_root, dict):
            br_pullspec = resolve_okd_from_entry(
                ci_build_root, meta, image_map, streams, okd_version,
            )
            if br_pullspec:
                try:
                    desired_ci_build_root_coordinate = convert_to_imagestream_coordinate(br_pullspec)
                except ValueError:
                    pass
        if not desired_ci_build_root_coordinate:
            # Default: rhel-9-golang stream.
            default_br = resolve_okd_from_stream(streams, 'rhel-9-golang')
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
        ci_operator_config = ci_operator_configs.get_config(org, repo_name, public_branch or 'main')

        # -- Determine Dockerfile path --
        okd_dockerfile = alignment.get('dockerfile') if alignment else None
        source_dockerfile = meta.source_dockerfile
        dockerfile_path = okd_dockerfile or source_dockerfile or 'Dockerfile'

        okd_path = alignment.get('path') if alignment else None
        source_path = meta.source_path
        prefix_path = okd_path or source_path
        if prefix_path:
            dockerfile_path = os.path.join(prefix_path, dockerfile_path)

        # -- Download upstream Dockerfile --
        dockerfile_content = download_dockerfile(
            public_url, public_branch or 'main', dockerfile_path, github_token,
        )
        if not dockerfile_content:
            skipped.append((distgit_key, f'could not download Dockerfile at {dockerfile_path}'))
            continue

        # Follow single-line symlink-like files.
        while True:
            lines = dockerfile_content.strip().splitlines()
            if len(lines) == 1 and not lines[0].strip().upper().startswith('FROM'):
                new_path = os.path.join(os.path.dirname(dockerfile_path), lines[0].strip())
                dockerfile_content = download_dockerfile(
                    public_url, public_branch or 'main', new_path, github_token,
                )
                if not dockerfile_content:
                    break
                dockerfile_path = new_path
            else:
                break

        if not dockerfile_content:
            skipped.append((distgit_key, 'could not resolve Dockerfile (symlink?)'))
            continue

        parent_images_parsed = parse_dockerfile_froms(dockerfile_content)

        if len(desired_parents) != len(parent_images_parsed):
            skipped.append((
                distgit_key,
                f'parent count mismatch: desired={len(desired_parents)}, '
                f'dockerfile={len(parent_images_parsed)}',
            ))
            continue

        # -- Build ci-operator image config --
        ci_image_config = ci_operator_config.get_image_config(meta)
        ci_operator_config.add_release('latest', {
            'integration': {
                'namespace': 'origin',
                'name': f'scos-{okd_version}',
            },
        })

        # Process builder stages (all FROM except the last).
        builders = from_config.get('builder', [])
        if not isinstance(builders, list):
            builders = [builders] if builders else []

        for index in range(len(parent_images_parsed) - 1):
            builder_entry = builders[index] if index < len(builders) else {}
            # Skip if the builder uses a literal image (no coordinate needed).
            if isinstance(builder_entry, dict) and builder_entry.get('image'):
                continue

            replace: List[str] = []
            dockerfile_image, stage_name = parent_images_parsed[index]
            if stage_name:
                replace.append(stage_name)
            replace.append(dockerfile_image)

            try:
                coord = convert_to_imagestream_coordinate(desired_parents[index])
                ci_image_config.add_replacement(coord, replace)
            except ValueError as exc:
                print(f'  WARNING: {exc}', file=sys.stderr)

        # Set the base image (last FROM).
        try:
            base_coord = convert_to_imagestream_coordinate(desired_parents[-1])
            ci_image_config.add_from(base_coord)
        except ValueError as exc:
            print(f'  WARNING: {exc}', file=sys.stderr)

        ci_image_config.set_dockerfile_path(dockerfile_path)

        # Context dir.
        context_dir = alignment.get('context_dir') if alignment else None
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
    print(f'\nProcessed {processed} images')
    if skipped:
        print(f'Skipped {len(skipped)} images:')
        for name, reason in skipped:
            print(f'  {name}: {reason}')

    print()
    written = ci_operator_configs.write_configs(output_dir, dry_run)
    print(f'\nGenerated {len(written)} ci-operator config files')
    if written:
        print('Output files:')
        for path in written:
            print(f'  {path}')

    print(
        '\nNote: After generating, run "make ci-operator-configs" '
        'and "make jobs" on the release repository.'
    )
