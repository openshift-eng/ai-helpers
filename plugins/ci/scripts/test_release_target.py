#!/usr/bin/env python3
"""Tests for release_target: Target-Version-based clone-family resolution (synthetic data only)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import release_target as rt  # noqa: E402


def link(kind, direction, key, inward=None, outward=None):
    names = {"Cloners": ("is cloned by", "clones"), "Blocks": ("is blocked by", "blocks"),
             "Depend": ("is depended on by", "depends on"), "Related": ("relates to", "relates to")}
    inw, outw = names.get(kind, (inward, outward))
    side = "inwardIssue" if direction == "in" else "outwardIssue"
    return {"type": {"name": kind, "inward": inw, "outward": outw}, side: {"key": key}}


def issue(key, target=None, links=(), status="New", affects=(), fix=(), summary="synthetic summary",
          description="synthetic description", target_field=True):
    fields = {"summary": summary, "description": description, "status": {"name": status}, "resolution": None,
              "issuelinks": list(links), "versions": [{"name": v} for v in affects],
              "fixVersions": [{"name": v} for v in fix]}
    if target_field:
        fields[rt.TARGET_VERSION_FIELD] = None if target is None else [{"name": t} for t in
                                                                       ([target] if isinstance(target, str) else target)]
    return {"key": key, "fields": fields}


def store(*issues):
    data = {i["key"]: i for i in issues}
    calls = []

    def fetch(key):
        calls.append(key)
        if key not in data:
            raise RuntimeError("HTTP 404")
        return data[key]
    fetch.calls = calls
    return fetch


# A closed parent targeted at a newer release, cloned to the older release. The clone's summary has no
# release prefix, its description is copied from a different issue, and its Affects/Fix Versions are
# inherited from the newer release: only its explicit Target Version says which release it is for.
PARENT = issue("SYNTH-100", "4.31.0", status="Closed", fix=(), affects=("4.30",),
               links=[link("Cloners", "in", "SYNTH-200"), link("Depend", "in", "SYNTH-200"),
                      link("Blocks", "out", "SYNTH-300")])
CLONE = issue("SYNTH-200", "4.30.z", status="ON_QA", affects=("4.31",), fix=("4.31.0",),
              summary="Component regressed in a test", description="This is a clone of issue SYNTH-900. Unrelated text.",
              links=[link("Cloners", "out", "SYNTH-100"), link("Depend", "out", "SYNTH-100")])
BLOCKED = issue("SYNTH-300", "4.31.0", links=[link("Blocks", "in", "SYNTH-100")])


class TestNormalize(unittest.TestCase):

    def test_versions(self):
        for raw, want in (("4.30", "4.30"), ("4.30.z", "4.30"), ("4.30.0", "4.30"), ("4.30.12", "4.30"),
                          (" 5.0 ", "5.0"), ("04.30.z", "4.30")):
            self.assertEqual(rt.normalize_release(raw), want, raw)

    def test_non_versions_are_unknown(self):
        for raw in ("release-4.30", "[release-4.30]", "openshift-4.30", "4.30-main", "", None, 4.3, "4"):
            self.assertIsNone(rt.normalize_release(raw), raw)

    def test_issue_key(self):
        self.assertEqual(rt.issue_key("https://example.atlassian.net/browse/SYNTH-7"), "SYNTH-7")
        self.assertEqual(rt.issue_key("SYNTH-7"), "SYNTH-7")
        self.assertIsNone(rt.issue_key("https://example.com/no-key"))


class TestFacts(unittest.TestCase):

    def test_links_keep_direction_and_type(self):
        f = rt.issue_facts(PARENT)
        self.assertEqual(f["target_releases"], ["4.31"])
        self.assertIn({"type": "Cloners", "direction": "inward", "relation": "is cloned by", "key": "SYNTH-200"}, f["links"])
        self.assertIn({"type": "Blocks", "direction": "outward", "relation": "blocks", "key": "SYNTH-300"}, f["links"])
        self.assertEqual(f["problems"], [])

    def test_missing_issuelinks_is_a_problem(self):
        raw = issue("SYNTH-1", "4.30.z")
        del raw["fields"]["issuelinks"]
        self.assertTrue(rt.issue_facts(raw)["problems"])

    def test_absent_target_field_is_untargeted(self):
        f = rt.issue_facts(issue("SYNTH-1", target_field=False))
        self.assertEqual((f["target_versions_raw"], f["problems"]), ([], []))


class TestResolve(unittest.TestCase):

    def check(self, candidate, releases, *issues, **kw):
        return rt.check_write(candidate, set(releases), store(*issues), **kw)

    def test_unprefixed_clone_with_copied_text_is_selected_for_its_target(self):
        rec = self.check("SYNTH-100", ["4.30"], PARENT, CLONE, BLOCKED)
        self.assertFalse(rec["allowed"])
        self.assertEqual(rec["releases"]["4.30"]["decision"], "clone")
        self.assertEqual(rec["releases"]["4.30"]["target"], "SYNTH-200")

    def test_matching_clone_target_is_allowed(self):
        rec = self.check("SYNTH-200", ["4.30"], PARENT, CLONE, BLOCKED)
        self.assertTrue(rec["allowed"], rec["reasons"])
        self.assertEqual(rec["releases"]["4.30"]["decision"], "self")

    def test_inherited_affects_and_fix_do_not_route(self):
        # The clone's Fix/Affects say 4.31, but it is not the 4.31 target: the parent is.
        rec = self.check("SYNTH-200", ["4.31"], PARENT, CLONE, BLOCKED)
        self.assertFalse(rec["allowed"])
        self.assertEqual(rec["releases"]["4.31"], dict(rec["releases"]["4.31"], decision="clone", target="SYNTH-100"))

    def test_blocks_and_depend_links_are_not_clones(self):
        rec = self.check("SYNTH-100", ["4.30"], PARENT, CLONE, BLOCKED)
        self.assertNotIn("SYNTH-300", [m["key"] for m in rec["family"]])
        reasons = {(l["type"], l["reason"]) for l in rec["ignored_links"]}
        self.assertIn(("Blocks", "not a clone link"), reasons)
        self.assertIn(("Depend", "not a clone link"), reasons)
        # a dependency-only neighbour targeted at the release is never selected
        dep = issue("SYNTH-400", "4.30.z")
        lone = issue("SYNTH-401", "4.31.0", links=[link("Depend", "in", "SYNTH-400")])
        rec = self.check("SYNTH-401", ["4.30"], lone, dep)
        self.assertEqual(rec["releases"]["4.30"]["decision"], "no-matching-clone")

    def test_closed_newer_parent_without_clone_is_denied_with_no_clone_evidence(self):
        # A complete search proves no clone targets 4.30; that is evidence, never permission to link the
        # 4.30 regressions to the 4.31 parent.
        parent = issue("SYNTH-110", "4.31.0", status="Closed")
        rec = self.check("SYNTH-110", ["4.30"], parent)
        self.assertFalse(rec["allowed"])
        d = rec["releases"]["4.30"]
        self.assertEqual((d["decision"], d["target"], d["complete"]), ("no-matching-clone", None, True))
        self.assertIn("report-only", d["reasons"][0])

    def test_multi_hop_and_cycle(self):
        a = issue("SYNTH-1", "4.33.0", links=[link("Cloners", "in", "SYNTH-2")])
        b = issue("SYNTH-2", "4.32.z", links=[link("Cloners", "out", "SYNTH-1"), link("Cloners", "in", "SYNTH-3")])
        c = issue("SYNTH-3", "4.31.z", links=[link("Cloners", "out", "SYNTH-2"), link("Cloners", "in", "SYNTH-4")])
        d = issue("SYNTH-4", "4.30.z", links=[link("Cloners", "out", "SYNTH-3"), link("Cloners", "in", "SYNTH-1")])
        fetch = store(a, b, c, d)
        rec = rt.check_write("SYNTH-1", {"4.30"}, fetch)
        self.assertEqual(rec["releases"]["4.30"]["target"], "SYNTH-4")
        self.assertEqual(sorted(fetch.calls), ["SYNTH-1", "SYNTH-2", "SYNTH-3", "SYNTH-4"])   # each once

    def test_ambiguous(self):
        p = issue("SYNTH-10", "4.31.0", links=[link("Cloners", "in", "SYNTH-11"), link("Cloners", "in", "SYNTH-12")])
        c1, c2 = issue("SYNTH-11", "4.30.z"), issue("SYNTH-12", "4.30.0")
        rec = self.check("SYNTH-10", ["4.30"], p, c1, c2)
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (False, "ambiguous"))

    def test_incomplete_lookup_is_unknown(self):
        p = issue("SYNTH-20", "4.31.0", links=[link("Cloners", "in", "SYNTH-21")])
        rec = self.check("SYNTH-20", ["4.30"], p)            # SYNTH-21 is unreadable
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (False, "unknown"))
        self.assertIn("lookup failed", " ".join(rec["reasons"]))

    def test_missing_fields_on_candidate_are_unknown(self):
        raw = issue("SYNTH-70", "4.31.0")
        del raw["fields"]["issuelinks"]               # incomplete read: links not returned
        rec = self.check("SYNTH-70", ["4.30"], raw)
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (False, "unknown"))
        rec = self.check("SYNTH-71", ["4.30"], {"key": "SYNTH-71"})   # no fields at all
        self.assertFalse(rec["allowed"])

    def test_unparseable_or_untargeted_member_is_unknown(self):
        p = issue("SYNTH-30", "4.31.0", links=[link("Cloners", "in", "SYNTH-31")])
        for clone in (issue("SYNTH-31", "rhel-9.9"), issue("SYNTH-31", None)):
            rec = self.check("SYNTH-30", ["4.30"], p, clone)
            self.assertEqual(rec["releases"]["4.30"]["decision"], "unknown", clone)
            self.assertFalse(rec["allowed"])

    def test_candidate_without_target_version_is_unknown(self):
        for raw in (issue("SYNTH-40", None), issue("SYNTH-40", target_field=False)):
            rec = self.check("SYNTH-40", ["4.30"], raw)
            self.assertFalse(rec["allowed"])
            self.assertEqual(rec["releases"]["4.30"]["decision"], "unknown")
        # a missing Target Version anywhere in the family fails closed, even when a clone matches
        p = issue("SYNTH-41", None, links=[link("Cloners", "in", "SYNTH-42")])
        rec = self.check("SYNTH-41", ["4.30"], p, issue("SYNTH-42", "4.30.z", links=[link("Cloners", "out", "SYNTH-41")]))
        self.assertEqual((rec["releases"]["4.30"]["decision"], rec["releases"]["4.30"]["target"]), ("unknown", None))

    def test_budget_exhaustion_is_unknown(self):
        p = issue("SYNTH-50", "4.31.0", links=[link("Cloners", "in", "SYNTH-51")])
        rec = self.check("SYNTH-50", ["4.30"], p, issue("SYNTH-51", "4.29.z"), max_nodes=1)
        self.assertEqual(rec["releases"]["4.30"]["decision"], "unknown")

    def test_cross_project_clone_is_not_followed(self):
        p = issue("SYNTH-60", "4.31.0", links=[link("Cloners", "in", "OTHER-1")])
        rec = self.check("SYNTH-60", ["4.30"], p)
        self.assertEqual(rec["releases"]["4.30"]["decision"], "no-matching-clone")
        self.assertEqual(rec["ignored_links"][0]["reason"], "clone in another project")

    # --- review follow-ups (synthetic) ---
    def test_failed_reads_consume_the_budget(self):          # finding 1
        p = issue("SYNTH-500", "4.31.0", links=[link("Cloners", "in", "SYNTH-5%02d" % i) for i in range(1, 11)])
        fetch = store(p)                                     # all ten clones unreadable
        rec = rt.check_write("SYNTH-500", {"4.30"}, fetch, max_nodes=3)
        self.assertLessEqual(len(fetch.calls), 3)
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (False, "unknown"))

    def test_complete_family_within_budget_still_decides(self):
        p = issue("SYNTH-510", "4.31.0", links=[link("Cloners", "in", "SYNTH-511"), link("Cloners", "in", "SYNTH-512")])
        fetch = store(p, issue("SYNTH-511", "4.30.z", links=[link("Cloners", "out", "SYNTH-510")]),
                      issue("SYNTH-512", "4.29.z", links=[link("Cloners", "out", "SYNTH-510")]))
        rec = rt.check_write("SYNTH-511", {"4.30"}, fetch, max_nodes=3)
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (True, "self"))
        self.assertEqual(len(fetch.calls), 3)

    def test_clone_link_without_a_key_is_incomplete(self):  # finding 2
        for side in ("outwardIssue", "inwardIssue"):
            raw = issue("SYNTH-520", "4.30.z")
            raw["fields"]["issuelinks"] = [{"type": {"name": "Cloners", "inward": "is cloned by", "outward": "clones"},
                                            side: {}}]
            rec = self.check("SYNTH-520", ["4.30"], raw)
            self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (False, "unknown"), side)

    def test_non_clone_link_without_a_key_is_still_ignored(self):
        raw = issue("SYNTH-521", "4.30.z")
        raw["fields"]["issuelinks"] = [{"type": {"name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
                                        "outwardIssue": {}}]
        rec = self.check("SYNTH-521", ["4.30"], raw)
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (True, "self"))

    def test_untargeted_member_blocks_even_a_matching_candidate(self):   # finding 3
        p = issue("SYNTH-530", "4.30.z", links=[link("Cloners", "in", "SYNTH-531")])
        rec = self.check("SYNTH-530", ["4.30"], p, issue("SYNTH-531", None))
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (False, "unknown"))
        rec = self.check("SYNTH-530", ["4.30"], p, issue("SYNTH-531", "4.31.0"))      # complete family: allowed
        self.assertEqual((rec["allowed"], rec["releases"]["4.30"]["decision"]), (True, "self"))

    def test_unknown_release_and_mixed_releases(self):
        rec = self.check("SYNTH-100", [None, "4.31"], PARENT, CLONE)
        self.assertFalse(rec["allowed"])
        self.assertEqual(rec["releases"]["unknown"]["decision"], "unknown")
        self.assertEqual(rec["releases"]["4.31"]["decision"], "self")


class TestRegressionsAndRecords(unittest.TestCase):

    def test_regression_release_lookup_failures_are_unknown(self):
        regs = {1: {"release": "4.30"}, 2: {"release": "weird"}}
        out = rt.regression_releases([1, 2, 3], lambda rid: regs[rid])
        self.assertEqual(out, {1: "4.30", 2: None, 3: None})

    def test_check_regressions_without_credentials_refuses(self):
        orig = rt.jira_fetcher
        rt.jira_fetcher = lambda auth=None: (_ for _ in ()).throw(rt.jira_auth.JiraAuthError("no creds"))
        try:
            rec = rt.check_regressions("SYNTH-1", [5], fetch_regression=lambda rid: {"release": "4.30"})
        finally:
            rt.jira_fetcher = orig
        self.assertFalse(rec["allowed"])
        self.assertIn("Jira unavailable", " ".join(rec["reasons"]))

    def test_validate_record(self):
        good = rt.check_write("SYNTH-200", {"4.30"}, store(PARENT, CLONE))
        self.assertEqual(rt.validate_record(good, issue="SYNTH-200", releases=["4.30"]), [])
        self.assertTrue(rt.validate_record(good, issue="SYNTH-100"))
        self.assertTrue(rt.validate_record(good, releases=["4.31"]))
        self.assertTrue(rt.validate_record(good, not_before="2999-01-01T00:00:00Z"))
        bad = rt.check_write("SYNTH-100", {"4.30"}, store(PARENT, CLONE))
        self.assertTrue(rt.validate_record(bad, issue="SYNTH-100"))
        forged = dict(bad, allowed=True)
        self.assertTrue(rt.validate_record(forged, issue="SYNTH-100"))    # per-release decision still says clone
        nomatch = rt.check_write("SYNTH-110", {"4.30"}, store(issue("SYNTH-110", "4.31.0")))
        self.assertEqual(rt.validate_record(nomatch, issue="SYNTH-110", releases=["4.30"], purpose="no-clone"), [])
        self.assertTrue(rt.validate_record(nomatch, issue="SYNTH-110"))            # evidence is not authorization
        self.assertTrue(rt.validate_record(dict(nomatch, allowed=True), issue="SYNTH-110"))
        self.assertTrue(rt.validate_record(good, purpose="no-clone"))             # a write record is not no-clone proof
        self.assertTrue(rt.validate_record(bad, purpose="no-clone"))              # "clone" exists
        self.assertTrue(rt.validate_record(nomatch, purpose="bogus"))
        self.assertEqual(rt.validate_record(None), ["release_check missing"])


class TestCli(unittest.TestCase):

    def run_main(self, argv, allowed):
        import io
        from unittest import mock
        rec = {"allowed": allowed, "reasons": []}
        with mock.patch.object(rt, "check_regressions", return_value=rec) as check, \
                mock.patch("sys.stdout", new=io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            return rt.main(argv), check

    def test_exit_codes(self):
        rc, check = self.run_main(["check", "SYNTH-1", "--regression-ids", "1,2"], True)
        self.assertEqual(rc, 0)
        check.assert_called_once_with("SYNTH-1", [1, 2])
        self.assertEqual(self.run_main(["check", "SYNTH-1", "--regression-ids", "1"], False)[0], 3)
        rc, check = self.run_main(["check", "SYNTH-1", "--regression-ids", "x"], True)
        self.assertEqual(rc, 2)
        check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
