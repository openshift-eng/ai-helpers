import base64
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import audit


def jload(p):
    with open(p) as f:
        return json.load(f)


def jdump(o, p):
    with open(p, 'w') as f:
        json.dump(o, f)


def snap(triages):
    return {"time": "t", "triages": triages}


def tri(regs, url="https://x/triages/1", resolved=None):
    return {"regression_ids": regs, "url": url, "resolved": resolved}


class DiffTests(unittest.TestCase):
    def test_undeclared_extension_detected(self):
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1, 2])}), [])
        self.assertEqual(r["extended"], [{"triage_id": "1", "added": [2]}])
        self.assertEqual(len(r["undeclared"]), 1)
        self.assertEqual(r["status"], "mismatch")

    def test_declared_actions_match(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [2, 3], "status": "done"}]
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1, 2])}), decl)
        self.assertEqual(r["undeclared"], [])
        self.assertEqual(r["status"], "match")

    def test_declared_create_matches_by_url_and_ids(self):
        decl = [{"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"}]
        after = snap({"7": tri([5, 6], url="https://j/browse/OCPBUGS-9")})
        r = audit.diff_triages(snap({}), after, decl)
        self.assertEqual(r["created"], ["7"])
        self.assertEqual(r["undeclared"], [])
        self.assertEqual(r["status"], "match")

    def test_catch_all_covers_extension(self):
        decl = [{"type": "catch_all", "triage_id": 1, "regression_ids": [2], "status": "done"}]
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1, 2])}), decl)
        self.assertEqual(r["status"], "match")

    def test_created_must_cover_declared_ids(self):
        decl = [{"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [5, 6], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": tri([5], url="https://j/OCPBUGS-9")}), decl)
        self.assertEqual(r["status"], "mismatch")

    def test_created_without_declaration(self):
        r = audit.diff_triages(snap({}), snap({"7": tri([5])}), [])
        self.assertEqual(r["status"], "mismatch")

    def test_removed_regressions_are_undeclared(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [1], "status": "done"}]
        r = audit.diff_triages(snap({"1": tri([1, 2])}), snap({"1": tri([1])}), decl)
        self.assertEqual(r["removed"], [{"triage_id": "1", "removed": [2]}])
        self.assertTrue(r["undeclared"])

    def test_declared_not_observed_is_mismatch(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [2], "status": "done"},
                {"type": "extend_triage", "triage_id": 9, "regression_ids": [2], "status": "failed"}]
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1])}), decl)
        self.assertEqual(len(r["declared_not_observed"]), 1)
        self.assertEqual(r["status"], "mismatch")

    def test_malformed_snapshot_is_unknown(self):
        r = audit.diff_triages({"status": "unknown", "error": "boom"}, snap({}), [])
        self.assertEqual(r["status"], "unknown")
        self.assertIn("error", r)


class SnapshotTests(unittest.TestCase):
    def test_resolved_struct_preserved_in_snapshot(self):
        res = {"Time": "2026-05-14T12:25:28.941154Z", "Valid": True}
        data = [{"id": 3, "url": "u", "resolved": res,
                 "regressions": [{"id": 10, "x": 1}, {"id": 11}]}]
        s = audit.snapshot_triages(fetch=lambda: data)
        self.assertEqual(s["triages"]["3"], {"regression_ids": [10, 11], "url": "u", "resolved": res})

    def test_fetch_failure_is_unknown(self):
        def bad():
            raise OSError("down")
        s = audit.snapshot_triages(fetch=bad)
        self.assertEqual(s["status"], "unknown")
        self.assertIn("down", s["error"])


def issue(key, created):
    return {"key": key, "fields": {"created": created, "summary": "s"}}


W = ("2026-10-12T01:00:00Z", "2026-10-12T02:00:00Z")


class JqlTests(unittest.TestCase):
    def test_jql_failure_is_unknown_not_zero(self):
        def bad(jql, tok=None):
            raise OSError("net")
        r = audit.jql_creations(*W, "bot", search=bad)
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])
        self.assertIn("net", r["error"])

    def test_anonymous_fallback_header_is_unknown_not_zero(self):
        # Jira Cloud answers 200 + X-Seraph-LoginReason: AUTHENTICATED_FAILED for bad basic auth and
        # silently falls back to anonymous; that must never count as a clean audit.
        class Resp:
            headers = {"X-Seraph-LoginReason": "AUTHENTICATED_FAILED"}
            def read(self): return b'{"issues": [], "isLast": true}'
            def __enter__(self): return self
            def __exit__(self, *a): return False
        with mock.patch.dict(os.environ, {"JIRA_USERNAME": "u", "JIRA_API_TOKEN": "t"}), \
             mock.patch("urllib.request.urlopen", return_value=Resp()):
            r = audit.jql_creations(*W, "bot")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])
        self.assertIn("authentic", r["error"].lower())

    def test_myself_401_is_unknown_not_zero(self):
        import urllib.error
        def urlopen(req, timeout=None):
            if req.full_url.endswith("/rest/api/3/myself"):
                raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
            raise AssertionError("search must not be attempted when /myself fails")
        with mock.patch.dict(os.environ, {"JIRA_USERNAME": "u", "JIRA_API_TOKEN": "t"}), \
             mock.patch("urllib.request.urlopen", side_effect=urlopen):
            r = audit.jql_creations(*W, "bot")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])
        self.assertIn("401", r["error"])

    def test_missing_credentials_unknown(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            r = audit.jql_creations(*W, "bot")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])

    def test_window_filter_and_offsets(self):
        page = {"isLast": True, "issues": [
            issue("IN-1", "2026-10-12T01:30:00.904+0000"),
            issue("IN-2", "2026-10-12T03:15:00+02:00"),
            issue("IN-3", "2026-10-12T01:45:00Z"),
            issue("OUT-1", "2026-10-11T20:00:00.5+0000")]}
        seen = []

        def search(jql, tok=None):
            seen.append(jql)
            return page
        r = audit.jql_creations(*W, "bot", search=search)
        self.assertEqual([i["key"] for i in r["issues"]], ["IN-1", "IN-2", "IN-3"])
        self.assertEqual((r["count"], r["raw_matched"], r["truncated"]), (3, 4, False))
        self.assertIn('created >= "2026-10-11 01:00"', seen[0])
        self.assertIn('created <= "2026-10-13 02:00"', seen[0])

    def test_pagination_follows_token(self):
        pages = [{"isLast": False, "nextPageToken": "t1", "issues": [issue("A-1", "2026-10-12T01:10:00Z")]},
                 {"isLast": True, "issues": [issue("A-2", "2026-10-12T01:20:00Z")]}]
        toks = []

        def search(jql, tok=None):
            toks.append(tok)
            return pages[len(toks) - 1]
        r = audit.jql_creations(*W, "bot", search=search)
        self.assertEqual(toks, [None, "t1"])
        self.assertEqual(r["count"], 2)
        self.assertFalse(r["truncated"])

    def test_pagination_cap_sets_truncated(self):
        n = []

        def search(jql, tok=None):
            n.append(1)
            return {"isLast": False, "nextPageToken": "t", "issues": [issue("A-%d" % len(n), "2026-10-12T01:10:00Z")]}
        r = audit.jql_creations(*W, "bot", search=search)
        self.assertEqual(len(n), 10)
        self.assertTrue(r["truncated"])
        self.assertEqual(r["count"], 10)

    def test_jql_builds_exact_string_and_auth_header(self):
        self.assertEqual(
            audit.build_jql("2026-10-12T01:05:59Z", "2026-10-12T02:00:00+00:00", "bot"),
            'reporter = "bot" AND created >= "2026-10-12 01:05" AND created <= "2026-10-12 02:00" ORDER BY created ASC')
        h = audit.build_auth_header("u", "t")
        self.assertEqual(h, "Basic " + base64.b64encode(b"u:t").decode())

    def test_jql_non_utc_offset_converts_and_reporter_escaped(self):
        q = audit.build_jql("2026-10-12T03:00:00+02:00", "2026-10-12T04:00:00+0200", 'a"b\\c')
        self.assertIn('reporter = "a\\"b\\\\c"', q)
        self.assertIn('created >= "2026-10-12 01:00"', q)
        self.assertIn('created <= "2026-10-12 02:00"', q)


class ReceiptTests(unittest.TestCase):
    def rc(self, jira=None, diff=None, run="r1"):
        return {"run_id": run, "audit": {
            "jira_creations": jira or {"status": "ok", "count": 0},
            "sippy_catalog_diff": diff or {"status": "match", "undeclared": []}}}

    def test_receipt_with_creation_forces_report(self):
        d, why = audit.read_receipt_decision(self.rc(jira={"status": "ok", "count": 1, "issues": [{"key": "A-1"}]}))
        self.assertEqual(d, "report")
        self.assertIn("A-1", why)

    def test_receipt_ack_restores_configured(self):
        rc = self.rc(jira={"status": "ok", "count": 1, "issues": []})
        d, why = audit.read_receipt_decision(rc, ack_run_id="r1")
        self.assertEqual(d, "configured")
        self.assertIn("r1", why)

    def test_missing_receipt_forces_report(self):
        self.assertEqual(audit.read_receipt_decision(None),
                         ("report", "no receipt from the latest preceding attempt"))

    def test_malformed_receipt(self):
        self.assertEqual(audit.read_receipt_decision({"run_id": "x"})[0], "report")
        self.assertTrue(audit.read_receipt_decision([])[1].startswith("receipt unreadable"))

    def test_receipt_unknown_audit_forces_report(self):
        d, why = audit.read_receipt_decision(self.rc(jira={"status": "unknown", "count": None, "error": "no creds"}))
        self.assertEqual((d, why), ("report", "audit unknown — no creds"))

    def test_mismatch_forces_report(self):
        d, why = audit.read_receipt_decision(self.rc(diff={"status": "mismatch", "undeclared": [{"kind": "created"}]}))
        self.assertEqual(d, "report")

    def test_receipt_truncated_jira_audit_forces_report(self):
        rc = self.rc(jira={"status": "ok", "count": 0, "truncated": True, "issues": []})
        rc["audit"]["sippy_catalog_diff"] = {"status": "match"}
        d, why = audit.read_receipt_decision(rc)
        self.assertEqual(d, "report")
        self.assertIn("truncated", why)
        rc["audit"]["jira_creations"]["truncated"] = False
        self.assertEqual(audit.read_receipt_decision(rc), ("configured", ""))
        rc["audit"]["jira_creations"]["truncated"] = True
        self.assertEqual(audit.read_receipt_decision(rc, ack_run_id="r1")[0], "configured")

    def test_ack_does_not_override_missing_or_malformed(self):
        self.assertEqual(audit.read_receipt_decision(None, "r1")[0], "report")
        self.assertEqual(audit.read_receipt_decision({"run_id": "r1"}, "r1")[0], "report")

    def test_clean_receipt_configured(self):
        self.assertEqual(audit.read_receipt_decision(self.rc()), ("configured", ""))

    def test_write_receipt_shape(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.json")
            audit.write_receipt(p, run_id="r", mode_requested="a", mode_effective="b",
                                audit={"jira_creations": {}, "sippy_catalog_diff": {}}, previous_run=None)
            d = jload(p)
        self.assertEqual(d["schema_version"], "1.0")
        self.assertEqual(set(d["audit"]), {"jira_creations", "sippy_catalog_diff"})
        self.assertIn("written_at", d)


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = audit.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_receipt_decide_cli_prints_decision_and_reason(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.json")
            jdump({"run_id": "r1", "audit": {
                "jira_creations": {"status": "ok", "count": 2, "issues": [{"key": "A-1"}]},
                "sippy_catalog_diff": {"status": "match"}}}, p)
            code, out, _ = self.run_cli(["receipt-decide", "--receipt", p])
            self.assertEqual(code, 0)
            self.assertTrue(out.startswith("report\t"))
            code, out, _ = self.run_cli(["receipt-decide", "--receipt", p, "--ack", "r1"])
            self.assertTrue(out.startswith("configured\t"))

    def test_receipt_decide_missing_file(self):
        code, out, _ = self.run_cli(["receipt-decide", "--receipt", "/nonexistent/x"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("report\t"))

    def test_diff_cli(self):
        with tempfile.TemporaryDirectory() as t:
            def w(n, o):
                p = os.path.join(t, n)
                jdump(o, p)
                return p
            b = w("b", snap({"1": tri([1])}))
            a = w("a", snap({"1": tri([1, 2])}))
            m = w("m", {"clusters": [{"actions": [
                {"type": "extend_triage", "triage_id": 1, "regression_ids": [2], "status": "done"}]}]})
            o = os.path.join(t, "o")
            code, out, _ = self.run_cli(["diff", "--before", b, "--after", a, "--manifest", m, "--out", o])
            self.assertEqual((code, out.strip()), (0, "match"))

    def test_diff_cli_tolerates_malformed_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            def w(n, o):
                p = os.path.join(t, n)
                jdump(o, p)
                return p
            b = w("b", snap({}))
            for man in ({"clusters": 5}, {"clusters": [{"actions": "x"}, 3]}, []):
                m = w("m", man)
                code, out, err = self.run_cli(["diff", "--before", b, "--after", b, "--manifest", m,
                                               "--out", os.path.join(t, "o")])
                self.assertEqual((code, out.strip()), (0, "match"))

    def test_decide_output_is_single_tab_line(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.json")
            jdump({"run_id": "r", "audit": {"jira_creations": {"status": "unknown", "error": "a\tb\nc"},
                                            "sippy_catalog_diff": {"status": "match"}}}, p)
            _, out, _ = self.run_cli(["receipt-decide", "--receipt", p])
            self.assertEqual(out.count("\t"), 1)
            self.assertEqual(len(out.splitlines()), 1)

    def test_diff_cli_bad_json_exits_1(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "bad")
            with open(p, "w") as f:
                f.write("{")
            code, _, err = self.run_cli(["diff", "--before", p, "--after", p, "--manifest", p,
                                         "--out", os.path.join(t, "o")])
            self.assertEqual(code, 1)
            self.assertEqual(len(err.strip().splitlines()), 1)

    def test_jql_cli_writes_unknown_on_failure(self):
        with tempfile.TemporaryDirectory() as t:
            o = os.path.join(t, "o")
            with mock.patch.dict(os.environ, {}, clear=True):
                code, _, _ = self.run_cli(["jql", "--start", "2026-10-12T01:00:00Z",
                                           "--end", "2026-10-12T02:00:00Z", "--reporter", "b", "--out", o])
            self.assertEqual(code, 0)
            self.assertEqual(jload(o)["status"], "unknown")


if __name__ == '__main__':
    unittest.main()
