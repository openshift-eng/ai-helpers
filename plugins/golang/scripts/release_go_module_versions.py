#!/usr/bin/env python3
"""Report declared Go module or Go language versions across a release payload."""

import argparse
import re
import sys

from release_go_utils import (
    LookupErrorWithContext, file_content, oc_json, repository_files,
    source_for_tag,
)

MODULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~+/-]*$")


def module_files(repo, ref):
    return sorted(
        path for path in repository_files(repo, ref)
        if path.split("/")[-1] == "go.mod"
    )


def declared_version(content, module):
    """Find a required module's version, accounting for matching replacements."""
    required = None
    replacements = {}
    in_block = None
    for raw_line in content.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        parts = line.split()
        if len(parts) == 2 and parts[0] in ("require", "replace") and parts[1] == "(":
            in_block = parts[0]
            continue
        if in_block and parts == [")"]:
            in_block = None
            continue
        if in_block:
            kind = in_block
        else:
            if not parts or parts[0] not in ("require", "replace"):
                continue
            kind, parts = parts[0], parts[1:]
        if kind == "require" and len(parts) == 2 and parts[0] == module:
            required = parts[1]
        elif kind == "replace" and parts and parts[0] == module and "=>" in parts:
            arrow = parts.index("=>")
            source, target = parts[:arrow], parts[arrow + 1:]
            if len(source) in (1, 2) and len(target) in (1, 2):
                source_version = source[1] if len(source) == 2 else None
                replacements[source_version] = " ".join(target)
    if required is None:
        return None
    replacement = replacements.get(required, replacements.get(None))
    if replacement is None:
        return required
    target = replacement.split()
    if len(target) == 2 and target[0] == module:
        replacement = target[1]
    return f"{replacement} (replaced)"


def declared_go_version(content):
    for raw_line in content.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        parts = line.split()
        if len(parts) == 2 and parts[0] == "go":
            return parts[1]
    return None


def inspect_release(release, module, go_version=False, on_result=None):
    if not go_version and not module:
        raise ValueError("module is required when go_version is False")
    tags = ((release.get("references") or {}).get("spec") or {}).get("tags") or []
    if not tags:
        raise LookupErrorWithContext("release contains no component images")
    cache = {}
    version_cache = {}
    results = []

    def record(row):
        results.append(row)
        if on_result:
            on_result(row)

    for tag in tags:
        name = tag.get("name") or "(unnamed)"
        image = (tag.get("from") or {}).get("name") or "(missing image)"
        repo = branch = ref = "(unknown)"
        try:
            if image == "(missing image)":
                raise LookupErrorWithContext(
                    "component image reference missing from release metadata"
                )
            repo, branch, ref = source_for_tag(tag, branch_from_image=True)
            key = (repo, ref)
            if key not in cache:
                cache[key] = module_files(repo, ref)
            files = cache[key]
            if not files:
                record((name, image, repo, branch, ref, "(none)", "no go.mod files"))
                continue
            found = False
            file_errors = False
            for path in files:
                try:
                    version_key = (repo, ref, path)
                    if version_key not in version_cache:
                        content = file_content(repo, ref, path)
                        version_cache[version_key] = (
                            declared_go_version(content)
                            if go_version
                            else declared_version(content, module)
                        )
                    version = version_cache[version_key]
                except LookupErrorWithContext as exc:
                    file_errors = True
                    record((name, image, repo, branch, ref, path,
                            f"error: {path}: {exc}"))
                    continue
                if go_version:
                    record((name, image, repo, branch, ref, path,
                            version or "go directive absent"))
                elif version:
                    found = True
                    record((name, image, repo, branch, ref, path, version))
            if not go_version and not found and not file_errors:
                record((name, image, repo, branch, ref, "(none)",
                        "package absent from all go.mod files"))
        except LookupErrorWithContext as exc:
            record((name, image, repo, branch, ref, "(unavailable)",
                    f"error: {exc}"))
    return results


def format_result(row):
    return "\t".join((row[0], row[2], row[6]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_image", help="OpenShift release image pullspec")
    parser.add_argument(
        "module", nargs="?",
        help="exact Go module path, e.g. google.golang.org/protobuf",
    )
    parser.add_argument(
        "--go-version", action="store_true",
        help="report each go.mod's go directive instead of a module version",
    )
    args = parser.parse_args(argv)
    if args.go_version and args.module:
        parser.error("provide either a module or --go-version, not both")
    if not args.go_version and not args.module:
        parser.error("provide a module or --go-version")
    if args.module and not MODULE.fullmatch(args.module):
        parser.error("module must be an exact Go module path")

    try:
        print("Reading release metadata...", file=sys.stderr, flush=True)
        release = oc_json(
            "adm", "release", "info", args.release_image, "-o", "json"
        )
        print(
            "component\trepository\tgo version/status"
            if args.go_version
            else "component\trepository\tmodule version/status",
            flush=True,
        )
        rows = inspect_release(
            release, args.module, go_version=args.go_version,
            on_result=lambda row: print(format_result(row), flush=True),
        )
    except LookupErrorWithContext as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1 if any(row[-1].startswith("error:") for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
