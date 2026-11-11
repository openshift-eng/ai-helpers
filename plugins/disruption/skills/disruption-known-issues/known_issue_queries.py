"""Print the Jira queries for the known-issue lookup, and record the classified cards.

The queries come from disruption_common.known_issues. Run each one with the
Atlassian MCP searchJiraIssuesUsingJql tool, passing its "args" unchanged.

With --record, nothing is queried: the classified card keys are written under
`jira` in the investigation state, demonstrated matches separate from related
cards.

Usage:
    python3 known_issue_queries.py --backends openshift-api-http2-service-network-reused-connections
    python3 known_issue_queries.py --backends <names> --component openshift-apiserver \\
        --keyword "watch cache" --keyword imagestream --signal etcd
    python3 known_issue_queries.py --record <investigation.json> \\
        --demonstrated OCPBUGS-1111 --related OCPBUGS-1234,OCPBUGS-999
"""
import argparse
import json
import os
import sys

# disruption_common is in the disruption plugin's scripts/ directory: two levels
# up when the whole plugin is installed (Claude Code), and inside each skill's
# scripts/ when Chai installs the skill, because it copies the plugin's scripts/
# tree into every skill.
_HERE = os.path.dirname(os.path.abspath(__file__))
# Search from the skill directory as reached, then from its resolved target,
# since a symlinked skill directory can sit outside the plugin checkout. abspath
# keeps ".." textual, the way sys.path entries resolve it.
_LIB_PARENTS = list(dict.fromkeys(
    os.path.abspath(os.path.join(base, *rel))
    for base in (_HERE, os.path.realpath(_HERE))
    for rel in (("scripts",), ("..", "..", "scripts"))))
for _parent in _LIB_PARENTS:
    if os.path.isfile(os.path.join(_parent, "disruption_common", "__init__.py")):
        sys.path.insert(0, _parent)
        break
else:
    sys.exit("Error: disruption_common library not found. Install the whole disruption plugin; "
             "the library is its scripts/disruption_common. Looked in: %s" % ", ".join(_LIB_PARENTS))

from disruption_common import known_issues, state  # noqa: E402
from disruption_common.series import split_backends  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print the Jira queries for the known-issue lookup")
    parser.add_argument("--backends",
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
    parser.add_argument("--record", metavar="STATE_FILE",
                        help="Record classified cards in this investigation.json instead of printing queries")
    parser.add_argument("--demonstrated", default="", help="Card keys whose mechanism the evidence shows (--record)")
    parser.add_argument("--related", default="", help="Card keys that are context only (--record)")
    args = parser.parse_args(argv)

    if args.record:
        return record(args.record, split_backends(args.demonstrated), split_backends(args.related))
    backends = split_backends(args.backends or "")
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


def record(path, demonstrated, related):
    """Write the classified card keys under `jira` in the state file."""
    overlap = sorted(set(demonstrated) & set(related))
    if overlap:
        print("Error: %s cannot be both demonstrated and related" % ", ".join(overlap), file=sys.stderr)
        return 1
    try:
        current = state.load_state(path)
        current["jira"] = {"demonstrated": demonstrated, "related": related}
        state.write_json_atomic(path, current, indent=2)
    except (state.StateError, OSError) as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(current["jira"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
