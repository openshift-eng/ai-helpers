#!/usr/bin/env python3
"""Merge otel_env.json defaults into ~/.claude/settings.json.

Can be run standalone to re-apply defaults after editing otel_env.json:
    python3 scripts/configure_settings.py
"""

import json
import os
import sys
import tempfile

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
ENV_FILE      = os.path.join(SCRIPT_DIR, "otel_env.json")
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def read_file(path, missing_ok=False):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        if missing_ok:
            return None
        sys.exit(f"error: {path} not found")
    except PermissionError:
        sys.exit(f"error: cannot read {path}: permission denied")
    except json.JSONDecodeError as e:
        sys.exit(f"error: {path} contains invalid JSON: {e}")
    return data


def load_defaults(env_file):
    data = read_file(env_file)
    bad = {k: v for k, v in data.items() if not isinstance(v, str)}
    if bad:
        sys.exit(f"error: {env_file} values must be strings; found: {bad}")
    return data


def load_settings(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # Treat corrupt settings as empty rather than aborting — old behaviour.
        print(f"warning: {path} contains invalid JSON; treating as empty", file=sys.stderr)
        return {}
    except PermissionError:
        sys.exit(f"error: cannot read {path}: permission denied")
    if not isinstance(data, dict):
        sys.exit(f"error: {path} must be a JSON object, got {type(data).__name__}")
    return data


def merge(settings, defaults):
    existing_env = settings.get("env", {})
    if not isinstance(existing_env, dict):
        print(
            f"warning: settings.env is {type(existing_env).__name__}, not an object; ignoring it",
            file=sys.stderr,
        )
        existing_env = {}
    # Existing user keys win so manual overrides are preserved.
    settings["env"] = {**defaults, **existing_env}
    return settings


def write_atomic(path, settings):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    defaults = load_defaults(ENV_FILE)
    settings = load_settings(SETTINGS_FILE)
    settings = merge(settings, defaults)
    try:
        write_atomic(SETTINGS_FILE, settings)
    except OSError as e:
        sys.exit(f"error: could not write {SETTINGS_FILE}: {e}")
    print(f"OTel env vars written to {SETTINGS_FILE}")


if __name__ == "__main__":
    main()
