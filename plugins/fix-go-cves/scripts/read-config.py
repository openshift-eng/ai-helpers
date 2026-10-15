#!/usr/bin/env python3
"""Strict parser for the small YAML subset used by cve-fix configuration.

This avoids sourcing configuration and avoids ad-hoc grep parsing. It supports
plain or quoted scalar values, inline comments, reordered repository fields,
and paths containing spaces. Nested values, aliases, and multiline scalars are
rejected explicitly instead of being misinterpreted.
"""

import argparse
import json
import re
from pathlib import Path


def fail(message: str) -> "None":
    raise SystemExit(f"ERROR: {message}")


def strip_comment(value: str) -> str:
    # Quotes embedded in a plain YAML scalar are literal characters, even
    # when they look like shell quoting. Only a leading quote starts YAML
    # quoted style; otherwise an apostrophe in a path must remain ordinary text.
    value = value.lstrip()
    quote = value[:1] if value[:1] in ("'", '"') else None
    quoted = quote is not None
    escaped = False
    out = []
    for index, char in enumerate(value):
        if quoted and index == 0:
            out.append(char)
            continue
        if escaped:
            out.append(char)
            escaped = False
            continue
        if quote == '"' and char == "\\":
            out.append(char)
            escaped = True
            continue
        if char in "'\"" and quoted:
            if quote == char:
                quote = None
            elif quote is None and char == value[0]:
                # Doubled single quotes remain inside the scalar. Any other
                # trailing quoted text is rejected by the scalar decoder.
                quote = char
            out.append(char)
            continue
        # YAML plain scalars only start an inline comment when # is the first
        # character or is separated from the value by whitespace. Preserve URL
        # fragments and tokens such as "release#candidate".
        if char == "#" and quote is None and (not out or out[-1].isspace()):
            break
        out.append(char)
    if quote is not None:
        fail("unterminated quoted scalar")
    return "".join(out).rstrip()


def single_quoted(raw: str) -> str:
    if len(raw) < 2 or raw[-1] != "'":
        fail(f"invalid quoted scalar: {raw}")
    value = raw[1:-1]
    if re.search(r"(^|[^'])'([^']|$)", value):
        fail(f"invalid quoted scalar: {raw}")
    return value.replace("''", "'")


def double_quoted(raw: str) -> str:
    if len(raw) < 2 or raw[-1] != '"':
        fail(f"invalid quoted scalar: {raw}")
    escapes = {
        "0": "\0", "a": "\a", "b": "\b", "t": "\t", "n": "\n",
        "v": "\v", "f": "\f", "r": "\r", "e": "\x1b", " ": " ",
        '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0",
        "L": "\u2028", "P": "\u2029",
    }
    value = raw[1:-1]
    out = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == '"':
            fail(f"invalid quoted scalar: {raw}")
        if char != "\\":
            out.append(char)
            index += 1
            continue
        index += 1
        if index >= len(value):
            fail(f"invalid quoted scalar: {raw}")
        escape = value[index]
        if escape in escapes:
            out.append(escapes[escape])
            index += 1
            continue
        widths = {"x": 2, "u": 4, "U": 8}
        width = widths.get(escape)
        digits = value[index + 1:index + 1 + (width or 0)]
        if (width is None or len(digits) != width or
                not re.fullmatch(r"[0-9a-fA-F]+", digits)):
            fail(f"invalid quoted scalar: {raw}")
        codepoint = int(digits, 16)
        if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            fail(f"invalid Unicode escape in scalar: {raw}")
        out.append(chr(codepoint))
        index += width + 1
    return "".join(out)


def scalar(raw: str):
    raw = strip_comment(raw).strip()
    if not raw:
        return ""
    if raw[0] == "'":
        return single_quoted(raw)
    if raw[0] == '"':
        return double_quoted(raw)
    if raw in ("true", "false"):
        return raw == "true"
    if raw in ("~", "null", "Null", "NULL"):
        fail(f"null is not a valid value: {raw}")
    if raw[0] in "[{&*!>|":
        fail(f"unsupported YAML construct: {raw}")
    if re.search(r":(?:[ \t]|$)", raw):
        fail(f"unsupported YAML mapping in scalar: {raw}")
    return raw


def mapping_line(text: str, lineno: int):
    if ":" not in text:
        fail(f"line {lineno}: expected key: value")
    key, value = text.split(":", 1)
    key = key.strip()
    if not re.fullmatch(r"[a-z][a-z0-9-]*", key):
        fail(f"line {lineno}: invalid key {key!r}")
    return key, scalar(value)


def parse_config(path: Path):
    allowed = {
        "build-image", "build-command", "clean-command", "test-command",
        "unset-env", "k8s-version-guard", "upstream-org",
    }
    result = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.strip() in ("---", "..."):
            continue
        if raw[:1].isspace():
            fail(f"line {lineno}: nested configuration is not supported")
        key, value = mapping_line(raw, lineno)
        if key not in allowed:
            fail(f"line {lineno}: unknown configuration key {key!r}")
        if key in result:
            fail(f"line {lineno}: duplicate configuration key {key!r}")
        if key == "k8s-version-guard" and not isinstance(value, bool):
            fail(f"line {lineno}: k8s-version-guard must be true or false")
        if key != "k8s-version-guard" and not isinstance(value, str):
            fail(f"line {lineno}: {key} must be a string")
        result[key] = value
    return result


def parse_repos(path: Path):
    repos = []
    current = None
    in_repos = False
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        text = raw.rstrip()
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        if strip_comment(text.strip()) in ("---", "..."):
            continue
        indent = len(text) - len(text.lstrip())
        stripped = text.strip()
        if indent == 0 and not (in_repos and stripped.startswith("-")):
            if strip_comment(stripped) != "repos:":
                fail(f"line {lineno}: only a top-level repos: key is supported")
            if in_repos:
                fail(f"line {lineno}: duplicate repos: key")
            in_repos = True
            continue
        if not in_repos:
            fail(f"line {lineno}: repository entry appears before repos:")
        if stripped.startswith("-"):
            if current is not None:
                repos.append(current)
            current = {}
            remainder = stripped[1:].strip()
            if remainder and not remainder.startswith("#"):
                key, value = mapping_line(remainder, lineno)
                current[key] = value
            continue
        if current is None:
            fail(f"line {lineno}: expected '- name: ...' repository entry")
        key, value = mapping_line(stripped, lineno)
        if key in current:
            fail(f"line {lineno}: duplicate repository field {key!r}")
        current[key] = value
    if current is not None:
        repos.append(current)
    names = set()
    for index, repo in enumerate(repos, 1):
        unknown = set(repo) - {"name", "path"}
        if unknown:
            fail(f"repository {index}: unknown fields: {', '.join(sorted(unknown))}")
        name, repo_path = repo.get("name"), repo.get("path")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            fail(f"repository {index}: name must match [a-z0-9][a-z0-9_-]*")
        if name in names:
            fail(f"duplicate repository name: {name}")
        names.add(name)
        if not isinstance(repo_path, str) or not repo_path:
            fail(f"repository {name}: path must be a non-empty string")
    return repos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("config-json", "repos-list", "repo-path"))
    parser.add_argument("file", type=Path)
    parser.add_argument("name", nargs="?")
    args = parser.parse_args()
    if not args.file.is_file():
        fail(f"file not found: {args.file}")
    if args.mode == "config-json":
        print(json.dumps(parse_config(args.file), separators=(",", ":")))
        return
    repos = parse_repos(args.file)
    if args.mode == "repos-list":
        print("\n".join(repo["name"] for repo in repos))
        return
    if args.name is None:
        fail("repo-path requires a repository name")
    for repo in repos:
        if repo["name"] == args.name:
            print(repo["path"])
            return
    fail(f"unknown repository: {args.name}")


if __name__ == "__main__":
    main()
