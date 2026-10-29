#!/usr/bin/env python3
"""Exercise real script container launches with an offline runtime stand-in."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
CLAUDE = "Assisted-by: Claude Code <noreply@anthropic.com>"
CODEX = "Assisted-by: Codex <noreply@openai.com>"


class ContainerAttributionTests(unittest.TestCase):
    def setUp(self):
        work = PLUGIN.parents[1] / ".work/container-attribution-tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith(("GIT_", "BASH_FUNC_")) or key in (
                "AI_TRAILER", "K8S_REBASE_IN_CONTAINER", "BASH_ENV", "ENV"
            ):
                del self.env[key]
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        BASH_ENV="", ENV="", ATTRIBUTION_ROOT=str(self.root),
                        ATTRIBUTION_GIT=shutil.which("git"))
        self.git("init", "-q", "-b", "rebase")
        self.git("config", "user.name", "Attribution Fixture")
        self.git("config", "user.email", "attribution@example.invalid")
        (self.repo / "go.mod").write_text(
            "module example.invalid/fixture\ngo 1.26.0\n"
            "require (\n k8s.io/api v0.36.2\n)\n")
        self.git("add", "go.mod")
        self.git("commit", "-qm", "baseline")
        self.stub("go", '''import os, sys
from pathlib import Path
if sys.argv[1:] == ["env", "GOVERSION"]:
    print("go1.25.0")
elif sys.argv[1:] == ["env", "GOMODCACHE"]:
    print(Path(os.environ["ATTRIBUTION_ROOT"]) / "modules")
else:
    raise SystemExit("Unexpected Go operation: " + repr(sys.argv[1:]))
''')
        self.stub("curl", '''import sys
url = sys.argv[-1]
if url.endswith("/go.mod"):
    print("module k8s.io/kubernetes\\ngo 1.26.0")
elif url.endswith("/v0.37.1.info"):
    print("{}")
else:
    raise SystemExit("Unexpected network request: " + url)
''')
        self.stub("podman", '''import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
# Model the container boundary: only explicit -e values cross it.
environment = {"PATH": os.environ["PATH"], "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_NOSYSTEM": "1"}
forwarded = {}
for i, arg in enumerate(args):
    if arg == "-e":
        key, value = args[i + 1].split("=", 1)
        forwarded[key] = value
        environment[key] = value
root = Path(os.environ["ATTRIBUTION_ROOT"])
(root / "container.json").write_text(json.dumps({"argv": args,
                                               "forwarded": forwarded}))
trailer = environment.get("AI_TRAILER") or "Assisted-by: Claude Code <noreply@anthropic.com>"
subprocess.run([os.environ["ATTRIBUTION_GIT"], "commit", "--allow-empty", "-s",
                "--trailer", trailer, "-qm", "fixture container commit"],
               env=environment, check=True)
''')
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env python3\n" + body)
        path.chmod(0o755)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                              text=True, capture_output=True, check=True,
                              timeout=20).stdout

    def exercise(self, script, supplied=None):
        if supplied is not None:
            self.env["AI_TRAILER"] = supplied
        expected = supplied or CLAUDE
        argv = ["bash", str(PLUGIN / "scripts" / script)]
        if script == "k8s-rebase.sh":
            argv.append("1.37.1")
        result = subprocess.run(argv, cwd=self.repo, env=self.env, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        invocation = json.loads((self.root / "container.json").read_text())
        self.assertEqual(invocation["forwarded"].get("AI_TRAILER"), expected)
        message = self.git("log", "-1", "--format=%B")
        trailers = [line for line in message.splitlines()
                    if line.startswith("Assisted-by:")]
        self.assertEqual(trailers, [expected])
        self.assertEqual(sum(line.startswith("Signed-off-by:")
                             for line in message.splitlines()), 1)

    def test_rebase_forwards_codex_trailer(self):
        self.exercise("k8s-rebase.sh", CODEX)

    def test_rebase_preserves_default_trailer(self):
        self.exercise("k8s-rebase.sh")

    def test_autofix_forwards_codex_trailer(self):
        self.exercise("k8s-rebase-autofix.sh", CODEX)

    def test_autofix_preserves_default_trailer(self):
        self.exercise("k8s-rebase-autofix.sh")


if __name__ == "__main__":
    unittest.main()
