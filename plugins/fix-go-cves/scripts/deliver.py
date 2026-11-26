#!/usr/bin/env python3
"""Run prepared CVE operations from a native PostToolUse hook, without model relay."""
import json
import os
from pathlib import Path
import shlex
import signal
import stat
import subprocess
import sys
import tempfile

HELPER = Path(__file__).resolve()
SCRIPTS = {"fix": "fix-all.sh", "report": "report.sh"}
OVERRIDES = set("""CVE_FIX_BUILD_CMD CVE_FIX_BUILD_IMAGE CVE_FIX_BUILD_TIMEOUT
CVE_FIX_CLEAN_CMD CVE_FIX_EVIDENCE_DIR CVE_FIX_GO_MINOR_GUARD CVE_FIX_GRYPE_IMAGE
CVE_FIX_GRYPE_VERSION CVE_FIX_IMAGE_TIMEOUT CVE_FIX_K8S_VERSION_GUARD
CVE_FIX_LICENSE_TIMEOUT CVE_FIX_REPOS CVE_FIX_SCAN_TIMEOUT CVE_FIX_TEST_CMD
CVE_FIX_TEST_TIMEOUT""".split())
INHERITED = OVERRIDES | set("""PATH HOME TMPDIR XDG_CONFIG_HOME XDG_CACHE_HOME
DOCKER_HOST DOCKER_CONTEXT DAPPER_ENV DAPPER_ARGS GOENV GOEXPERIMENT GOMAXPROCS
GOMODCACHE GOCACHE GOPATH GOTOOLCHAIN GOWORK GOFLAGS""".split())


def parse_runs(arguments):
    runs, chunk = [], []
    for value in [*arguments, "--next"]:
        if value != "--next":
            chunk.append(value)
            continue
        overrides = {}
        while chunk[:1] == ["--env"]:
            if len(chunk) < 2 or "=" not in chunk[1]:
                raise ValueError("--env requires NAME=value")
            name, setting = chunk[1].split("=", 1)
            if name not in OVERRIDES or name in overrides:
                raise ValueError("unsupported or duplicate environment override")
            overrides[name] = setting
            chunk = chunk[2:]
        if not chunk or chunk[0] not in SCRIPTS:
            raise ValueError("expected fix or report operation")
        mode, args = chunk[0], chunk[1:]
        if (not args or len(args) > (2 if mode == "fix" else 1)
                or not Path(args[0]).is_absolute() or any(v.startswith("-") for v in args)):
            raise ValueError("expected absolute repository path, then optional fix branch")
        if any("\0" in v for v in [*args, *overrides.values()]):
            raise ValueError("NUL in engine input")
        runs.append({"mode": mode, "args": args, "env": overrides})
        chunk = []
    return runs


def prepare(arguments):
    runs = parse_runs(arguments[1:])
    temporary = Path(tempfile.gettempdir()).resolve()
    for run in runs:
        target = subprocess.run(["git", "-C", run["args"][0], "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, check=True).stdout.removesuffix("\n")
        if temporary.is_relative_to(Path(target).resolve()):
            raise ValueError("temporary delivery files must be outside repository worktrees")
    directory = Path(tempfile.mkdtemp(prefix="fix-go-cves-")).resolve()
    request = directory / "request.json"
    request.write_text(json.dumps({"cwd": os.getcwd(), "argv": arguments, "runs": runs,
                                   "env": {name: os.environ[name] for name in INHERITED if name in os.environ}}))
    print(json.dumps({"fix_go_cves_request": str(request)}))


def owned(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or (not directory and info.st_nlink != 1)):
        raise ValueError("request ownership/type/mode changed")
    return info


def claim(event, command):
    response = json.loads(event["tool_response"]["stdout"])
    request = Path(response["fix_go_cves_request"])
    if (not request.is_absolute() or request.name != "request.json"
            or request.resolve(strict=True) != request
            or not request.parent.name.startswith("fix-go-cves-")):
        raise ValueError("invalid request path")
    owned(request.parent, directory=True)
    original = owned(request)
    content = request.read_bytes()
    data = json.loads(content)
    inherited = data["env"]
    if (not isinstance(inherited, dict) or inherited.keys() - INHERITED
            or any(not isinstance(value, str) or "\0" in value for value in inherited.values())):
        raise ValueError("invalid inherited execution settings")
    if (data["argv"] != command[2:] or data["runs"] != parse_runs(command[3:])
            or data["cwd"] != str(Path(event["cwd"]).resolve())):
        raise ValueError("request does not match current invocation")
    claimed = request.with_name("running.json")
    os.link(request, claimed)
    request.unlink()
    current = owned(claimed)
    if ((current.st_dev, current.st_ino) != (original.st_dev, original.st_ino)
            or claimed.read_bytes() != content):
        raise ValueError("request changed while claiming")
    return claimed.parent, data


def run_engine(command, directory, environment, log):
    child, interrupted = None, 0

    def cancel(number, _frame):
        nonlocal interrupted
        interrupted = number
        if child is not None:
            raise InterruptedError("operation interrupted")

    previous = {number: signal.signal(number, cancel) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        child = subprocess.Popen(command, cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        if interrupted:
            raise InterruptedError("operation interrupted during startup")
        return child.wait()
    except InterruptedError:
        if child is not None:
            try:
                os.killpg(child.pid, interrupted)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        raise RuntimeError("operation interrupted; retained logs may be partial") from None
    finally:
        try:
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


def hook(event):
    try:
        command = shlex.split(event.get("tool_input", {}).get("command", ""))
    except ValueError:
        return {}
    if (event.get("hook_event_name") != "PostToolUse" or event.get("tool_name") != "Bash"
            or len(command) < 3 or command[0] != "python3" or command[2] != "prepare"
            or not Path(command[1]).is_absolute() or Path(command[1]).resolve() != HELPER):
        return {}
    results = []
    try:
        if (event["tool_input"].get("run_in_background")
                or event.get("tool_response", {}).get("interrupted")):
            raise ValueError("prepare must complete in the foreground without interruption")
        directory, data = claim(event, command)
        environment = {name: value for name, value in os.environ.items() if name not in INHERITED}
        environment.update(data["env"])
        for index, run in enumerate(data["runs"], 1):
            path = directory / f"runtime-{index}.log"
            with path.open("x") as log:
                results.append(f"LOG={path}")
                code = run_engine(["bash", str(HELPER.parent / SCRIPTS[run["mode"]]), *run["args"]],
                                  data["cwd"], {**environment, **run["env"]}, log)
                code = code if code >= 0 else 128 - code
                log.write(f"\nexit={code}\n")
                log.flush()
            results.append(f"exit={code}")
            if code not in (0, 2):
                raise RuntimeError("engine did not complete normally; later operations were not started")
    except Exception as error:
        results.append(f"CVE fix completion unconfirmed: {error}")
    return {"continue": False, "stopReason": "\n".join(results)}


def main():
    os.umask(0o077)
    if sys.argv[1:2] == ["prepare"]:
        prepare(sys.argv[1:])
    elif sys.argv[1:] == ["hook"]:
        print(json.dumps(hook(json.load(sys.stdin))))
    else:
        raise ValueError("usage: deliver.py prepare [--env NAME=value] fix|report ABS_REPO [fix-branch] [--next ...], or hook")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if sys.argv[1:] == ["hook"]:
            print(json.dumps({"continue": False, "stopReason": f"CVE fix completion unconfirmed: {error}"}))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
            sys.exit(1)
