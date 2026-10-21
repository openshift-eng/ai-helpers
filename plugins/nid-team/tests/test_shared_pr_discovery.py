"""Exercise dashboard discovery without contacting GitHub or Jira."""

import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts/pr-dashboard/sync-dashboard.sh"

FAKE_CLI = r'''
import datetime
import json
import os
from pathlib import Path
import re
import sys

args = sys.argv[1:]
store = Path(os.environ["NID_TEST_STATE"])
data = json.loads(store.read_text())

def value(flag):
    return args[args.index(flag) + 1]

def save():
    store.write_text(json.dumps(data))

if Path(sys.argv[0]).name == "acli":
    print(json.dumps({"key": "OCPBUGS-86709", "fields": {}})
          if "view" in args else "key")
elif args[:2] == ["auth", "status"]:
    pass
elif args[:2] == ["api", "/rate_limit"]:
    print(json.dumps({"resources": {"graphql": {"remaining": 5000}}}))
elif args[:2] == ["api", "graphql"]:
    print("{}")
elif args[:2] == ["project", "item-list"]:
    print(json.dumps({"items": data["items"]}))
elif args[:2] == ["project", "item-add"]:
    url = value("--url")
    pr = next(pr for pr in data["prs"] if pr["url"] == url)
    item = {"id": "ITEM_" + str(len(data["items"])),
            "content": {"type": "PullRequest", "repository": pr["repo"],
                        "number": pr["number"], "title": "Component change",
                        "url": url}, "edits": {}}
    data["items"].append(item)
    data["added"].append(url)
    save()
    print(item["id"])
elif args[:2] == ["project", "item-edit"]:
    item = next(item for item in data["items"] if item["id"] == value("--id"))
    item["edits"][value("--field-id")] = value(
        "--text" if "--text" in args else "--single-select-option-id")
    save()
elif args[:2] == ["pr", "list"]:
    query = value("--search")
    cutoff = re.search(r"merged:>=(\d{4}-\d{2}-\d{2})", query)
    for pr in data["prs"]:
        if pr["repo"] != value("--repo"):
            continue
        if not any(f"{role}:{user}" in query for role, user in pr["roles"]):
            continue
        if pr["state"] == "MERGED":
            if value("--state") != "all" or not cutoff or pr["merged"] < cutoff[1]:
                continue
        elif pr["state"] != "OPEN":
            continue
        print(pr["url"] + "|" + pr["state"])
elif args[:2] == ["pr", "view"]:
    if value("--json") == "title,files":
        pr = next(pr for pr in data["prs"] if pr["url"] == args[2])
        print(json.dumps({"title": pr["title"],
                          "files": [{"path": path} for path in pr["files"]]}))
    else:
        pr = next(pr for pr in data["prs"]
                  if pr["repo"] == value("-R") and str(pr["number"]) == args[2])
        print(pr["author"])
else:
    data.setdefault("unhandled", []).append(args)
    save()
    raise SystemExit("Unexpected command: " + repr(args))
'''


class SharedPRDiscoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="nid-dashboard-test-")
        cls.root = Path(cls.temp.name)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.constants = dict(re.findall(
            r'^([A-Z_]+)="([^"\n]+)"$',
            (PLUGIN / "scripts/pr-dashboard/config.sh").read_text(), re.MULTILINE))
        today = datetime.datetime.now(datetime.timezone.utc).date()
        recent = str(today - datetime.timedelta(days=1))
        old = str(today - datetime.timedelta(days=30))

        def pr(repo, number, state="OPEN", roles=(), merged=recent, author="external-author",
               title="Component change", files=("ci-operator/config/openshift/router/main.yaml",)):
            return {"repo": repo, "number": number, "state": state,
                    "url": f"https://github.com/{repo}/pull/{number}",
                    "roles": roles, "merged": merged, "author": author,
                    "title": title, "files": files}

        bgp = "openshift/bgp-cloud-connector"
        release = "openshift/release"
        prs = [
            pr(bgp, 187, "MERGED", [("assignee", "aswinsuryan"),
                                    ("review-requested", "pedjak")]),
            pr(release, 87291, "MERGED", [("assignee", "aswinsuryan")], files=[
                "ci-operator/config/openshift/bgp-cloud-connector/main.yaml"]),
            pr(bgp, 125, roles=[("author", "aswinsuryan")], author="aswinsuryan"),
            pr(bgp, 126, roles=[("author", "aswinsuryan")], author="aswinsuryan"),
            pr(release, 99901, roles=[("reviewed-by", "grzpiotrowski")]),
            pr(bgp, 99902, roles=[("author", "external-author")]),
            pr(bgp, 99903, "MERGED", [("assignee", "aswinsuryan")], merged=old),
            pr(bgp, 99904, "CLOSED", [("assignee", "aswinsuryan")]),
            pr(bgp, 99905, roles=[("review-requested", "aswinsuryan")]),
            pr(bgp, 99906, roles=[("assignee", "aswinsuryan")], merged=old),
            pr(release, 84226, roles=[("review-requested", "pedjak")],
               title="olm,operator-controller: remove unmonitored compact s390x periodics",
               files=["ci-operator/config/openshift/operator-framework-olm/main.yaml"]),
            pr("openshift/enhancements", 2153, "MERGED", [("review-requested", "Miciah")],
               title="Update KMS health reporting to match typed encryptionStatus aggregation",
               files=["enhancements/kube-apiserver/kms-encryption-foundations.md"]),
            pr("openshift/api", 2435, roles=[("assignee", "Miciah")],
               title="Support custom list of services in cluster DNS",
               files=["operator/v1/types_dns.go"]),
            pr("openshift/api", 99908, roles=[("review-requested", "Miciah")],
               files=["operator/v1/types_storage.go"]),
            pr(release, 99909, roles=[("review-requested", "aswinsuryan")],
               files=["ci-operator/config/openshift/bgp-cloud-connector-unrelated/main.yaml"]),
            pr("openshift/library-go", 99910, roles=[("assignee", "pedjak")],
               title="NE-1234: improve shared helper", files=["pkg/operator/shared.go"]),
        ]
        existing = {"id": "EXISTING", "edits": {}, "content": {
            "type": "PullRequest", "repository": bgp, "number": 125,
            "title": "Existing team PR", "url": prs[2]["url"]}}
        state = cls.root / "state.json"
        state.write_text(json.dumps({"prs": prs, "items": [existing], "added": []}))
        bin_dir = cls.root / "bin"
        bin_dir.mkdir()
        for name in ("gh", "acli"):
            path = bin_dir / name
            path.write_text(f"#!{sys.executable}\n" + FAKE_CLI)
            path.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                   NID_TEST_STATE=str(state))
        cls.result = subprocess.run(
            [os.environ.get("NID_TEST_BASH", "/bin/bash"), str(SCRIPT)],
            cwd=cls.root, env=env, text=True, capture_output=True, timeout=90)
        if cls.result.returncode:
            raise AssertionError(cls.result.stdout + cls.result.stderr)
        cls.state = json.loads(state.read_text())
        if cls.state.get("unhandled"):
            raise AssertionError(cls.state["unhandled"])

    def test_discovers_external_authors_assigned_to_the_team(self):
        self.assertIn("https://github.com/openshift/bgp-cloud-connector/pull/187",
                      self.state["added"])
        self.assertIn("https://github.com/openshift/release/pull/87291",
                      self.state["added"])

    def test_preserves_authors_and_finds_reviewers_and_requested_reviewers(self):
        for repo, number in (("bgp-cloud-connector", 126), ("release", 99901),
                             ("bgp-cloud-connector", 99905), ("bgp-cloud-connector", 99906)):
            with self.subTest(number=number):
                self.assertIn(f"https://github.com/openshift/{repo}/pull/{number}",
                              self.state["added"])

    def test_excludes_unrelated_closed_and_old_merged_prs(self):
        for number in (99902, 99903, 99904):
            self.assertNotIn(f"https://github.com/openshift/bgp-cloud-connector/pull/{number}",
                             self.state["added"])

    def test_existing_items_and_multiple_team_members_do_not_duplicate_prs(self):
        self.assertNotIn("https://github.com/openshift/bgp-cloud-connector/pull/125",
                         self.state["added"])
        self.assertEqual(len(self.state["added"]), len(set(self.state["added"])))

    def test_recently_merged_prs_are_done_and_authors_remain_external(self):
        for item in self.state["items"]:
            if item["content"]["number"] in (187, 87291):
                with self.subTest(number=item["content"]["number"]):
                    edits = item["edits"]
                    self.assertEqual(edits[self.constants["FIELD_STATUS"]],
                                     self.constants["STATUS_DONE"])
                    self.assertEqual(edits[self.constants["FIELD_AUTHOR_TYPE"]],
                                     self.constants["AUTHOR_TYPE_EXTERNAL"])

    def test_bgp_repo_gets_its_dedicated_area(self):
        item = next(item for item in self.state["items"]
                    if item["content"]["number"] == 187)
        self.assertEqual(item["edits"][self.constants["FIELD_AREA"]],
                         self.constants["AREA_BGP"])

    def test_review_requests_without_component_evidence_do_not_add_prs(self):
        for repo, number in (("release", 84226), ("enhancements", 2153),
                             ("api", 99908), ("release", 99909)):
            with self.subTest(repo=repo, number=number):
                self.assertNotIn(f"https://github.com/openshift/{repo}/pull/{number}",
                                 self.state["added"])
        self.assertIn("SCOPE REVIEW:", self.result.stdout)

    def test_component_files_and_linked_team_issues_preserve_relevant_prs(self):
        self.assertIn("https://github.com/openshift/api/pull/2435", self.state["added"])
        self.assertIn("https://github.com/openshift/library-go/pull/99910", self.state["added"])


if __name__ == "__main__":
    unittest.main()
