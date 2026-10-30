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

    generate_configs(
        ocp_build_data=args.ocp_build_data,
        okd_version=args.okd_version,
        output_dir=args.output_dir,
        github_token=args.github_token,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
