#!/usr/bin/env python3
"""Run the hermetic fix-go-cves shell suite from `make test`."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Oldest Go the suite passes on with GOTOOLCHAIN=local; Go 1.22 fails the
# packed-binary checks.
MIN_GO = (1, 24)


def missing_prerequisite():
    for tool in ("bash", "git", "go", "jq", "make"):
        if shutil.which(tool) is None:
            return f"{tool} not found"
    version = subprocess.run(["go", "env", "GOVERSION"], capture_output=True, text=True,
                             env={**os.environ, "GOTOOLCHAIN": "local"}).stdout
    match = re.match(r"go(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < MIN_GO:
        return f"Go {MIN_GO[0]}.{MIN_GO[1]}+ required, found {version.strip() or 'unknown'}"
    return None


def main():
    reason = missing_prerequisite()
    if reason:
        # In CI a missing prerequisite would silently drop the suite; fail instead.
        if os.environ.get("CI"):
            print(f"FAIL: fix-go-cves shell suite cannot run in CI: {reason}")
            return 1
        print(f"SKIP: fix-go-cves shell suite: {reason}")
        return 0
    suite = Path(__file__).with_name("test-lib.sh")
    return subprocess.run(["bash", str(suite)], stdin=subprocess.DEVNULL).returncode


if __name__ == "__main__":
    sys.exit(main())
