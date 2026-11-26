#!/usr/bin/env python3
"""Generate OKD/SCOS ci-operator configurations from ART ocp-build-data.

Dependencies: Python stdlib + PyYAML + requests.
Keep the sibling okd_ci_configs package alongside this CLI entry point.
"""

import argparse
import sys
from pathlib import Path

from okd_ci_configs.generator import generate_configs


def main():
    parser = argparse.ArgumentParser(
        description='Generate OKD/SCOS ci-operator configuration YAML files '
                    'from ART ocp-build-data.',
    )
    parser.add_argument(
        '--ocp-build-data',
        required=True,
        type=Path,
        help='Path to ocp-build-data directory (contains group.yml, streams.yml, images/)',
    )
    parser.add_argument(
        '--okd-version',
        required=True,
        help='OKD version string, e.g. "4.18" or "5.0"',
    )
    parser.add_argument(
        '--output-dir',
        required=True,
        type=Path,
        help='Output directory for ci-operator config files '
             '(the ci-operator/config/ directory inside an openshift/release clone)',
    )
    parser.add_argument(
        '--github-token',
        default=None,
        help='GitHub token for downloading Dockerfiles from upstream repos. '
             'If not provided, uses unauthenticated requests.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Print what would be generated without writing files.',
    )

    parser.add_argument(
        '--base-stream',
        type=int,
        choices=(9, 10),
        default=None,
        help='CentOS Stream for scos base images. Defaults to 10 for OKD 5.1 '
             'and later, 9 otherwise.',
    )
    parser.add_argument(
        '--release-repo',
        type=Path,
        default=None,
        help='Path to an openshift/release checkout. When set, branch names, '
             'image capabilities and builder versions are checked '
             'against each repo\'s OCP ci-operator config.',
    )

    args = parser.parse_args()

    # Validate input paths.
    if not args.ocp_build_data.is_dir():
        print(f'ERROR: ocp-build-data directory not found: {args.ocp_build_data}', file=sys.stderr)
        sys.exit(1)
    for required in ('group.yml', 'streams.yml'):
        if not (args.ocp_build_data / required).is_file():
            print(f'ERROR: {required} not found in {args.ocp_build_data}', file=sys.stderr)
            sys.exit(1)
    if not (args.ocp_build_data / 'images').is_dir():
        print(f'ERROR: images/ directory not found in {args.ocp_build_data}', file=sys.stderr)
        sys.exit(1)
    if args.release_repo and not (args.release_repo / 'ci-operator' / 'config').is_dir():
        print(f'ERROR: ci-operator/config not found in {args.release_repo}', file=sys.stderr)
        sys.exit(1)

    generate_configs(
        ocp_build_data=args.ocp_build_data,
        okd_version=args.okd_version,
        output_dir=args.output_dir,
        github_token=args.github_token,
        dry_run=args.dry_run,
        base_stream=args.base_stream,
        release_repo_path=args.release_repo,
    )


if __name__ == '__main__':
    main()
