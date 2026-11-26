#!/usr/bin/env python3
"""Offline CVE coverage checks using real Git histories and injected OSV replies."""

import importlib.util
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cve_evidence", PLUGIN / "scripts/cve-evidence.py")
CVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CVE)
GATE = PLUGIN / "gates/step4-verification/dep-cve-check.sh"
CHECKSUM = "h1:" + base64.b64encode(bytes(32)).decode()


def advisory(identifier):
    return {"id": identifier, "modified": "2026-09-24T00:00:00Z", "affected": [],
            "summary": "Reviewer must assess severity and reachability"}


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k8s-cve-evidence-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo with spaces"
        self.repo.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("GIT_", "BASH_FUNC_"))}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        BASH_ENV="", ENV="")
        self.run_cmd("git", "init", "-qb", "main")
        self.run_cmd("git", "config", "user.name", "Gate Fixture")
        self.run_cmd("git", "config", "user.email", "gate@example.invalid")

    def run_cmd(self, *args):
        return subprocess.run(args, cwd=self.repo, env=self.env, text=True,
                              capture_output=True, check=True, timeout=20)

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def sums(self, path, *entries):
        self.write(path, "".join(f"{module} {version} {CHECKSUM}\n" for module, version in entries))

    def module(self, content, path="go.mod"):
        self.write(path, "module example.invalid/fixture\ngo 1.20\n" + content)

    def collect_empty(self):
        head = self.commit()
        requested = []

        def fetch(path, payload=None):
            self.assertEqual(path, "querybatch")
            requested.extend((q["package"]["name"], q["version"]) for q in payload["queries"])
            return {"results": [{} for _ in payload["queries"]]}

        result = CVE.collect(self.repo, self.base, head, fetch)
        self.assertEqual(self.run_cmd("git", "status", "--porcelain").stdout, "")
        return result, set(requested)

    def commit(self):
        self.run_cmd("git", "add", ".")
        self.run_cmd("git", "commit", "-qm", "fixture")
        return self.run_cmd("git", "rev-parse", "HEAD").stdout.strip()

    def baseline(self):
        self.base = self.commit()
        self.run_cmd("git", "switch", "-qc", "rebase")


class InventoryTests(GitFixture):
    def setUp(self):
        super().setUp()
        # These tests isolate declarations/checksum history. Real graph loading
        # and integration with the union are covered by GraphInventoryTests.
        patch = mock.patch.object(CVE, "graph_inventory", return_value=([], [], []))
        patch.start()
        self.addCleanup(patch.stop)

    def test_nested_modules_added_removed_retained_versions_and_vendor_exclusion(self):
        self.sums("go.sum", ("example.invalid/shared", "v1.0.0"),
                  ("example.invalid/shared", "v1.1.0"), ("example.invalid/drop", "v2.0.0"))
        self.sums("nested space/go.sum", ("example.invalid/shared", "v3.0.0"))
        self.sums("vendor/tool/go.sum", ("example.invalid/ignored", "v1.0.0"))
        self.sums("nested/vendor/go.sum", ("example.invalid/ignored", "v1.0.0"))
        self.sums("deleted/go.sum", ("example.invalid/deleted", "v1.0.0"))
        self.baseline()
        self.sums("go.sum", ("example.invalid/shared", "v1.0.0"),
                  ("example.invalid/shared", "v1.2.0"), ("example.invalid/new", "v1.0.0"),
                  ("example.invalid/metadata", "v5.0.0/go.mod"))
        self.sums("nested space/go.sum", ("example.invalid/shared", "v3.1.0"))
        self.sums("vendor/tool/go.sum", ("example.invalid/ignored", "v2.0.0"))
        self.sums("nested/vendor/go.sum", ("example.invalid/ignored", "v2.0.0"))
        (self.repo / "deleted/go.sum").unlink()
        self.sums("added/go.sum", ("example.invalid/new", "v1.0.0"))
        head = self.commit()
        requested = []

        def fetch(path, payload=None):
            self.assertEqual(path, "querybatch")
            requested.extend((q["package"]["name"], q["version"]) for q in payload["queries"])
            return {"results": [{} for _ in payload["queries"]]}

        result = CVE.collect(self.repo, self.base, head, fetch)
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(result["files"], ["added/go.sum", "deleted/go.sum", "go.sum", "nested space/go.sum"])
        self.assertEqual(len(result["inventory"]), 7)
        root = next(item for item in result["inventory"]
                    if item["go_sum"] == "go.sum" and item["module"] == "example.invalid/shared")
        self.assertEqual(root["old_versions"], ["v1.0.0", "v1.1.0"])
        self.assertEqual(root["new_versions"], ["v1.0.0", "v1.2.0"])
        self.assertEqual(root["added_versions"], ["v1.2.0"])
        self.assertEqual(root["removed_versions"], ["v1.1.0"])
        self.assertEqual(len(requested), len(set(requested)))
        self.assertEqual(len(requested), 9)
        self.assertIn(("example.invalid/deleted", "v1.0.0"), requested)
        self.assertNotIn("ignored", json.dumps(result))
        self.assertIn(("example.invalid/metadata", "v5.0.0"), requested)

    def test_require_bump_with_unchanged_historical_checksums_is_queried(self):
        self.module("require example.invalid/dep v1.0.0\n")
        self.sums("go.sum", ("example.invalid/dep", "v1.0.0"), ("example.invalid/dep", "v1.1.0"))
        self.baseline()
        self.module("require example.invalid/dep v1.1.0\n")
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(requested, {("example.invalid/dep", "v1.0.0"), ("example.invalid/dep", "v1.1.0")})
        self.assertEqual(len(result["inventory"]), 1)
        self.assertEqual(result["inventory"][0]["go_mod"], "go.mod")
        self.assertEqual(result["inventory"][0]["old_versions"], ["v1.0.0"])
        self.assertEqual(result["inventory"][0]["new_versions"], ["v1.1.0"])

    def test_require_bump_without_go_sum_still_queries_both_versions(self):
        self.module("require example.invalid/dep v1.0.0\n")
        self.baseline()
        self.module("require example.invalid/dep v1.1.0\n")
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(len(requested), 2)
        self.assertEqual(result["files"], [])
        self.assertEqual(result["manifest_files"], ["go.mod"])

    def test_metadata_only_checksum_versions_are_included(self):
        self.module("require example.invalid/dep v1.0.0\n")
        self.sums("go.sum", ("example.invalid/dep", "v1.0.0/go.mod"),
                  ("example.invalid/dep", "v1.1.0/go.mod"))
        self.baseline()
        self.module("require example.invalid/dep v1.1.0\n")
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(requested, {("example.invalid/dep", "v1.0.0"), ("example.invalid/dep", "v1.1.0")})

    def test_changed_replacement_target_with_retained_checksums(self):
        requirement = "require example.invalid/upstream v1.0.0\n"
        self.module(requirement + "replace example.invalid/upstream => example.invalid/fork v1.0.0\n")
        self.sums("go.sum", ("example.invalid/fork", "v1.0.0"), ("example.invalid/fork", "v1.1.0"))
        self.baseline()
        self.module(requirement + "replace example.invalid/upstream => example.invalid/fork v1.1.0\n")
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(requested, {("example.invalid/fork", "v1.0.0"), ("example.invalid/fork", "v1.1.0")})
        self.assertEqual(result["declarations"][0]["old"]["replace"],
                         [["example.invalid/upstream", "", "example.invalid/fork", "v1.0.0"]])

    def test_removed_replacement_queries_original_required_version(self):
        requirement = "require example.invalid/upstream v1.0.0\n"
        self.module(requirement + "replace example.invalid/upstream => example.invalid/fork v2.0.0+incompatible\n")
        self.baseline()
        self.module(requirement)
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(requested, {("example.invalid/fork", "v2.0.0+incompatible"),
                                     ("example.invalid/upstream", "v1.0.0")})

    def test_nested_module_require_and_replacement_scopes_do_not_mix(self):
        self.module("require example.invalid/dep v1.0.0\n")
        self.module('require "example.invalid/dep" v1.5.0\n', "nested/go.mod")
        self.write("vendor/go.mod", "invalid ignored vendor manifest\n")
        self.baseline()
        self.module("require example.invalid/dep v1.1.0\n")
        self.module('require (\n "example.invalid/dep" v1.6.0 // indirect\n)\n'
                    'replace (\n example.invalid/dep => example.invalid/fork v1.9.0\n)\n', "nested/go.mod")
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(requested, {("example.invalid/dep", "v1.0.0"), ("example.invalid/dep", "v1.1.0"),
                                     ("example.invalid/dep", "v1.5.0"), ("example.invalid/fork", "v1.9.0")})
        self.assertEqual(result["manifest_files"], ["go.mod", "nested/go.mod"])

    def test_local_replacement_or_ambiguous_selection_stays_incomplete(self):
        self.module("require example.invalid/dep v1.0.0\n")
        self.baseline()
        self.module('require example.invalid/dep v1.0.0\nreplace example.invalid/dep => "../local space"\n')
        result, _ = self.collect_empty()
        self.assertEqual(result["coverage"], "INCOMPLETE")
        self.assertIn("local replacement", " ".join(result["errors"]))
        self.module("require example.invalid/dep v1.0.0\n"
                    "replace example.invalid/transitive v1.2.0 => example.invalid/fork v1.3.0\n")
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "INCOMPLETE")
        self.assertIn(("example.invalid/fork", "v1.3.0"), requested)
        self.assertIn("selected graph unresolved", " ".join(result["errors"]))

    def test_changed_exclusion_cannot_claim_unchanged_dependency_graph(self):
        self.module("require example.invalid/dep v1.0.0\n")
        self.baseline()
        self.module("require example.invalid/dep v1.0.0\nexclude example.invalid/transitive v1.2.0\n")
        result, _ = self.collect_empty()
        self.assertEqual(result["coverage"], "INCOMPLETE")
        self.assertIn("exclude directives changed", " ".join(result["errors"]))

    def test_unavailable_or_rejecting_native_parser_is_incomplete(self):
        self.module("require example.invalid/dep v1.0.0\n")
        self.baseline()
        self.module("require example.invalid/dep v1.1.0\n")
        head = self.commit()
        with mock.patch.object(CVE, "manifest", side_effect=OSError("native Go parser unavailable")):
            result = CVE.collect(self.repo, self.base, head, mock.Mock(side_effect=AssertionError))
        self.assertEqual(result["coverage"], "INCOMPLETE")
        self.assertIn("native Go parser unavailable", result["errors"][0])
        self.module("require this is malformed\n")
        result, _ = self.collect_empty()
        self.assertEqual(result["coverage"], "INCOMPLETE")
        self.assertIn("cannot parse go.mod", result["errors"][0])

    def test_checksum_only_change_does_not_invent_version_change(self):
        self.sums("go.sum", ("example.invalid/a", "v1.0.0"))
        self.baseline()
        other_checksum = "h1:" + base64.b64encode(bytes([1]) * 32).decode()
        self.write("go.sum", f"example.invalid/a v1.0.0 {other_checksum}\n")
        transport = mock.Mock(side_effect=AssertionError("no network needed"))
        result = CVE.collect(self.repo, self.base, self.commit(), transport)
        self.assertEqual(result["coverage"], "COMPLETE")
        self.assertEqual(result["inventory"], [])

    def test_missing_base_and_malformed_sum_remain_incomplete(self):
        self.sums("go.sum", ("example.invalid/a", "v1.0.0"))
        self.baseline()
        self.write("go.sum", "not a valid checksum line\n")
        head = self.commit()
        for base in ("", self.base, "missing-revision"):
            with self.subTest(base=base):
                result = CVE.collect(self.repo, base, head, mock.Mock(side_effect=AssertionError))
                self.assertEqual(result["coverage"], "INCOMPLETE")
                self.assertTrue(result["errors"])
                self.assertIn("COVERAGE: INCOMPLETE", CVE.render(result))

    def test_malformed_versions_and_hashes_are_not_silently_queried(self):
        for line in (f"example.invalid/a vgarbage {CHECKSUM}",
                     "example.invalid/a v1.0.0 h1:bad-base64",
                     "example.invalid/a v1.0.0 h1:YWJj"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                CVE.checksums(line, "nested/go.sum")

    def test_partial_query_or_advisory_failure_sets_overall_incomplete(self):
        self.sums("go.sum", ("example.invalid/a", "v1.0.0"))
        self.baseline()
        self.sums("go.sum", ("example.invalid/a", "v2.0.0"))
        head = self.commit()
        for replies in ([{"results": [{}]}],
                        [{"results": [{}, {"vulns": [{"id": "GO-missing"}]}]}, OSError("HTTP 404")]):
            with self.subTest(replies=replies):
                result = CVE.collect(self.repo, self.base, head, mock.Mock(side_effect=replies))
                self.assertEqual(result["coverage"], "INCOMPLETE")
                text = CVE.render(result)
                self.assertIn("EXPECTED_QUERIES: 2", text)
                self.assertIn("COVERAGE: INCOMPLETE", text)
                self.assertNotIn("VERDICT:", text)

    def test_companion_writes_fresh_evidence_but_never_a_verdict(self):
        self.sums("go.sum", ("example.invalid/a", "v1.0.0"))
        self.baseline()
        self.write("README", "No changed module versions\n")
        head = self.commit()
        output = self.run_cmd("bash", str(GATE), str(self.repo)).stdout
        directory = self.repo / ".rebase-tmp/gates"
        evidence = (directory / "step4-dep-cve-check.evidence").read_text()
        self.assertTrue(evidence.startswith(f"HEAD: {head}\n"))
        self.assertIn(f"SCAN_HEAD: {head}\n", evidence)
        self.assertIn("COVERAGE: COMPLETE", evidence)
        self.assertIn("EXPECTED_QUERIES: 0", evidence)
        self.assertIn("PENDING: step4-dep-cve-check", output)
        self.assertNotIn("VERDICT:", evidence)
        self.assertFalse((directory / "step4-dep-cve-check.report").exists())
        self.assertEqual(self.run_cmd("git", "diff", "HEAD").stdout, "")


class GraphInventoryTests(GitFixture):
    def setUp(self):
        super().setUp()
        self.proxy = Path(self.temp.name) / "proxy"
        self.proxy.mkdir()
        self.mod_sums = []
        patch = mock.patch.dict(os.environ, GOPROXY=self.proxy.as_uri(), GOSUMDB="off",
                                GOMODCACHE=str(Path(self.temp.name) / "module-cache"))
        patch.start()
        self.addCleanup(patch.stop)

    def release(self, module, version, requires=""):
        directory = self.proxy / module / "@v"
        directory.mkdir(parents=True, exist_ok=True)
        content = f"module {module}\ngo 1.20\n{requires}"
        (directory / (version + ".mod")).write_text(content)
        (directory / (version + ".info")).write_text(json.dumps(
            {"Version": version, "Time": "2026-01-01T00:00:00Z"}))
        digest = hashlib.sha256(content.encode()).hexdigest() + "  go.mod\n"
        checksum = "h1:" + base64.b64encode(hashlib.sha256(digest.encode()).digest()).decode()
        self.mod_sums.append(f"{module} {version}/go.mod {checksum}\n")

    def history(self):
        for version in ("v1.0.0", "v1.1.0"):
            self.release("example.invalid/transitive", version)
            self.release("example.invalid/direct", version,
                         f"require example.invalid/transitive {version}\n")
        self.module("require example.invalid/direct v1.0.0\n")
        # Both transitive versions already exist in checksum history. Neither
        # go.sum diff nor the root's require diff reveals their selected bump.
        self.write("go.sum", "".join(self.mod_sums))
        self.baseline()
        self.module("require example.invalid/direct v1.1.0\n")

    def test_real_go_graph_finds_transitive_bump_in_unchanged_checksum_history(self):
        self.history()
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "COMPLETE", result["errors"])
        self.assertIn(("example.invalid/transitive", "v1.0.0"), requested)
        self.assertIn(("example.invalid/transitive", "v1.1.0"), requested)
        self.assertEqual(len(requested), 4)
        self.assertEqual([g["status"] for g in result["graphs"]], ["COMPLETE", "COMPLETE"])
        self.assertIn("EXPECTED_GRAPHS: 2", CVE.render(result))
        self.assertTrue(any(i.get("selected_graph") == "go.mod" and
                            i["module"] == "example.invalid/transitive" for i in result["inventory"]))

    def test_nested_module_graphs_remain_independent_and_removed_modules_are_queried(self):
        self.history()
        self.module("require example.invalid/direct v1.0.0\n", "nested space/go.mod")
        self.write("nested space/go.sum", "".join(self.mod_sums))
        base = self.commit()
        self.module("")
        changes, graphs, errors = CVE.graph_inventory(self.repo, base, self.commit())
        self.assertEqual(errors, [])
        self.assertEqual(len(graphs), 4)
        self.assertTrue(changes)
        self.assertTrue(all(i["selected_graph"] == "go.mod" and not i["new_versions"] for i in changes))

    def test_missing_metadata_retains_partial_facts_and_blocks_complete(self):
        self.history()
        (self.proxy / "example.invalid/transitive/@v/v1.1.0.mod").unlink()
        (self.proxy / "example.invalid/transitive/@v/v1.1.0.info").unlink()
        result, requested = self.collect_empty()
        self.assertEqual(result["coverage"], "INCOMPLETE")
        self.assertTrue(result["errors"])
        self.assertEqual([g["status"] for g in result["graphs"]], ["COMPLETE", "INCOMPLETE"])
        self.assertIn(("example.invalid/direct", "v1.1.0"), requested)

    def test_local_replacement_graph_is_explicitly_unresolved(self):
        self.module("")
        self.module("", "local/go.mod")
        self.baseline()
        self.module("require example.invalid/local v1.0.0\nreplace example.invalid/local => ./local\n")
        result, _ = self.collect_empty()
        self.assertEqual(result["coverage"], "INCOMPLETE")
        self.assertIn("local replacement", " ".join(result["errors"]))

    def test_timeout_or_manifest_mutation_never_claims_graph_complete(self):
        self.history()
        head = self.commit()
        def mutation(directory):
            (directory / "go.mod").write_text("changed\n")
            return {}
        for resolver in (mock.Mock(side_effect=subprocess.TimeoutExpired("go list", 180)), mutation):
            with self.subTest(resolver=resolver):
                _, graphs, errors = CVE.graph_inventory(self.repo, self.base, head, resolve=resolver)
                self.assertEqual(len(errors), 2)
                self.assertTrue(all(g["status"] == "INCOMPLETE" for g in graphs))
                self.assertEqual(self.run_cmd("git", "status", "--porcelain").stdout, "")


class OSVCoverageTests(unittest.TestCase):
    PAIRS = [("example.invalid/a", "v1.0.0"), ("example.invalid/a", "v2.0.0")]

    def test_batch_missing_extra_and_error_results_are_not_clean(self):
        replies = [{}, {"error": "unavailable"}, {"results": []},
                   {"results": [{}]}, {"results": [{}, {}, {}]},
                   {"results": [None, {"vulns": None}]},
                   {"results": [{"error": "rate limited"}, {"unexpected": True}]},
                   {"results": [{"vulns": [{}]}, {"next_page_token": 4}]}]
        for reply in replies:
            with self.subTest(reply=reply):
                queries, _ = CVE.osv_evidence(self.PAIRS, lambda *args: reply)
                self.assertTrue(all(item["status"] == "INCOMPLETE" for item in queries))
                self.assertTrue(all(item.get("error") for item in queries))

    def test_http_and_malformed_json_errors_do_not_stop_other_batches(self):
        for error in (OSError("HTTP 503"), json.JSONDecodeError("invalid", "<html>", 0),
                      CVE.http.client.IncompleteRead(b"partial", 40)):
            with self.subTest(error=error):
                fetch = mock.Mock(side_effect=[error, {"results": [{}]}])
                queries, _ = CVE.osv_evidence(self.PAIRS, fetch, batch_size=1)
                self.assertEqual([q["status"] for q in queries], ["INCOMPLETE", "COMPLETE"])

    def test_pagination_and_full_advisories_preserve_old_new_findings(self):
        calls = []

        def fetch(path, payload=None):
            calls.append((path, payload))
            if path.startswith("vulns/"):
                return advisory(path.split("/", 1)[1])
            if len(calls) == 1:
                return {"results": [{"vulns": [{"id": "GO-old"}], "next_page_token": "next"},
                                    {"vulns": [{"id": "GO-new"}]}]}
            self.assertEqual(payload["queries"], [{"package": {"name": "example.invalid/a", "ecosystem": "Go"},
                                                   "version": "v1.0.0", "page_token": "next"}])
            return {"results": [{"vulns": [{"id": "GO-shared"}, {"id": "GO-old"}]}]}

        queries, advisories = CVE.osv_evidence(self.PAIRS + self.PAIRS, fetch)
        self.assertEqual(len(queries), 2)
        self.assertTrue(all(q["status"] == "COMPLETE" for q in queries))
        self.assertEqual(queries[0]["advisory_ids"], ["GO-old", "GO-shared"])
        self.assertEqual(queries[1]["advisory_ids"], ["GO-new"])
        self.assertEqual(len(advisories), 3)
        self.assertTrue(all(a["status"] == "COMPLETE" and "record" in a for a in advisories))

    def test_failed_or_repeating_later_page_retains_finding_and_incomplete_status(self):
        for second in (OSError("timeout"), {"results": [{"next_page_token": "again"}]}):
            with self.subTest(second=second):
                fetch = mock.Mock(side_effect=[{"results": [{"vulns": [{"id": "GO-known"}],
                                                             "next_page_token": "again"}]},
                                              second, advisory("GO-known")])
                queries, advisories = CVE.osv_evidence(self.PAIRS[:1], fetch)
                self.assertEqual(queries[0]["status"], "INCOMPLETE")
                self.assertEqual(queries[0]["advisory_ids"], ["GO-known"])
                self.assertEqual(advisories[0]["status"], "COMPLETE")

    def test_page_limit_is_explicit_incomplete(self):
        fetch = mock.Mock(return_value={"results": [{"next_page_token": "more"}]})
        queries, _ = CVE.osv_evidence(self.PAIRS[:1], fetch, max_pages=1)
        self.assertEqual(queries[0]["status"], "INCOMPLETE")
        self.assertIn("page limit", queries[0]["error"])

    def test_missing_or_wrong_advisory_details_are_incomplete(self):
        for reply in (OSError("HTTP 404"), {"id": "GO-found"}, advisory("GO-other")):
            with self.subTest(reply=reply):
                fetch = mock.Mock(side_effect=[{"results": [{"vulns": [{"id": "GO-found"}]}]}, reply])
                queries, advisories = CVE.osv_evidence(self.PAIRS[:1], fetch)
                self.assertEqual(queries[0]["status"], "COMPLETE")
                self.assertEqual(advisories[0]["status"], "INCOMPLETE")

    def test_http_transport_rejects_non_json_and_uses_read_only_query_endpoint(self):
        with mock.patch.object(CVE.urllib.request, "urlopen", return_value=io.BytesIO(b"<html>")) as opened:
            with self.assertRaises(json.JSONDecodeError):
                CVE.fetch_json("querybatch", {"queries": []})
            request = opened.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.osv.dev/v1/querybatch")
            self.assertEqual(json.loads(request.data), {"queries": []})
            self.assertEqual(opened.call_args.kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
