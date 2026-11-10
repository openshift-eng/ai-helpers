"""Print the Jira queries for the known-issue lookup (Step 8).

The queries come from disruption_common.known_issues. Run each one with the
Atlassian MCP searchJiraIssuesUsingJql tool, passing its "args" unchanged.

Usage:
    python3 known_issue_queries.py --backends openshift-api-http2-service-network-reused-connections
    python3 known_issue_queries.py --backends <names> --component openshift-apiserver \\
        --keyword "watch cache" --keyword imagestream --signal etcd
"""
import argparse
import json
import os
import sys

# disruption_common is in plugins/ci/lib when the whole plugin is installed, or
# beside the skill directories when a Chai persona lists it in supporting_dirs.
_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB_PARENTS = (os.path.join(_HERE, "..", "..", "lib"), os.path.join(_HERE, ".."))
for _parent in _LIB_PARENTS:
    if os.path.isfile(os.path.join(_parent, "disruption_common", "__init__.py")):
        sys.path.insert(0, os.path.abspath(_parent))
        break
else:
    sys.exit("Error: disruption_common library not found. Install the whole ci plugin, or add "
             "`supporting_dirs: [lib/disruption_common]` to the persona's ci plugin entry. Looked in: %s"
             % ", ".join(os.path.abspath(p) for p in _LIB_PARENTS))

from disruption_common import known_issues  # noqa: E402
from disruption_common.series import split_backends  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print the Jira queries for the known-issue lookup")
    parser.add_argument("--backends", required=True,
                        help="Comma-separated exact backend names from the analysis")
    parser.add_argument("--component", action="append", default=[],
                        help="OCPBUGS component named by the root cause (repeatable or comma-separated)")
    parser.add_argument("--keyword", action="append", default=[],
                        help="Root-cause term: resource, error string, or mechanism (repeatable)")
    parser.add_argument("--signal", action="append", default=[],
                        help="Preset mechanism keywords: %s (repeatable or comma-separated)"
                             % ", ".join(sorted(known_issues.SIGNAL_KEYWORDS)))
    parser.add_argument("--recent-days", type=int, default=known_issues.DEFAULT_RECENT_DAYS,
                        help="Closed cards updated within this many days are candidates "
                             "(default: %(default)s)")
    args = parser.parse_args(argv)

    backends = split_backends(args.backends)
    if not backends:
        parser.error("--backends is empty")
    if args.recent_days <= 0:
        parser.error("--recent-days must be positive")
    try:
        result = known_issues.build_queries(
            backends,
            components=[c for value in args.component for c in split_backends(value)],
            keywords=args.keyword,
            signals=[s for value in args.signal for s in split_backends(value)],
            recent_days=args.recent_days)
    except ValueError as err:
        parser.error(str(err))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
