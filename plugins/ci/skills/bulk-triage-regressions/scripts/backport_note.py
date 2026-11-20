#!/usr/bin/env python3
"""Build a post-GA backport-candidate entry from fresh release evidence. It never writes to Jira.

When regressions on release R match a bug whose fix shipped in another release, the release check
(plugins/ci/scripts/release_target.py) decides where they may be linked. ``no-matching-clone`` means the
search was complete and no issue in the bug's clone family is targeted at R: the regressions stay
untriaged (report-only, never routed to the other-release bug) and the duty report lists a backport
candidate. This helper re-runs the check and, only for a complete ``no-matching-clone`` on every release,
prints the ``backport_candidates[]`` entries (with their ``release_check`` evidence) and a draft note for the
report. Any other decision (a matching clone or the bug itself is the target, ambiguous, unknown or
incomplete lookups) is refused.

  backport_note.py ISSUE --regression-ids 1,2 --fixed-in 4.31 --fix-ref org/repo#123 [--cluster-id C]

Exit 0 evidence produced, 3 refused, 1 error. Requires Jira credentials in the environment for the check.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import jira_auth  # noqa: E402
import release_target  # noqa: E402


def draft(releases, fixed_in, fix_ref, check):
    """Plain-text note for the duty report (not for posting)."""
    rels = ", ".join(releases)
    return ("Backport candidate: Component Readiness regressions on %s match a defect fixed in %s via %s, and no "
            "issue in this bug's clone family (%d checked over Cloners links at %s) has Target Version %s. The "
            "regressions stay untriaged until a release-specific bug exists." % (
                rels, fixed_in, fix_ref, len(check.get("family") or []), check.get("checked_at"), rels))


def backport_note(issue, regression_ids, fixed_in, fix_ref, cluster_id=None, check=None):
    """Decide and render. ``check`` is injectable for tests; nothing is ever sent to Jira."""
    rec = (check or release_target.check_regressions)(issue, regression_ids)
    key = release_target.issue_key(issue)
    releases = sorted(r for r in (rec.get("releases") or {}) if r != "unknown")
    errs = release_target.validate_record(rec, issue=key, purpose="no-clone")
    if errs or not releases:
        return {"status": "refused", "issue": key, "reasons": errs or ["no releases"], "release_check": rec}
    candidates = [{"cluster_id": cluster_id, "fixed_in": {"key": key, "fix_version": fixed_in, "fix_ref": fix_ref},
                   "this_release": r, "clone_exists": False, "release_check": rec} for r in releases]
    return {"status": "candidate", "issue": key, "backport_candidates": candidates,
            "draft": draft(releases, fixed_in, fix_ref, rec), "release_check": rec}


def main(argv=None):
    p = argparse.ArgumentParser(prog="backport_note.py", description=__doc__.split("\n\n")[0])
    p.add_argument("issue")
    p.add_argument("--regression-ids", required=True)
    p.add_argument("--fixed-in", required=True, help="release the fix shipped in, e.g. 4.31")
    p.add_argument("--fix-ref", required=True, help="PR or issue that carried the fix, e.g. org/repo#123")
    p.add_argument("--cluster-id")
    args = p.parse_args(argv)
    try:
        ids = [int(x) for x in args.regression_ids.split(",") if x.strip()]
        res = backport_note(args.issue, ids, args.fixed_in, args.fix_ref, args.cluster_id)
    except (ValueError, OSError, jira_auth.JiraAuthError) as e:
        print(json.dumps({"status": "error", "error": "%s: %s" % (type(e).__name__, e)}))
        return 1
    print(json.dumps(res, indent=2))
    return 3 if res["status"] == "refused" else 0


if __name__ == "__main__":
    sys.exit(main())
