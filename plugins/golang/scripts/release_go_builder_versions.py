#!/usr/bin/env python3
"""List Go builder FROM images or CI build-root versions across a release."""

import argparse
import sys

from release_go_utils import (
    GO_VERSION, LookupErrorWithContext, file_content, github_repo, oc_json,
    repository_files, source_for_tag,
)
from release_go_build_data import (
    SOURCE_DOCKERFILE_EXCEPTIONS, build_args_for, is_dockerfile,
    load_build_data, scan_dockerfile, selected_dockerfiles,
)

CI_OPERATOR_YAML = ".ci-operator.yaml"


# ---------------------------------------------------------------------------
# .ci-operator.yaml build-root helpers
# ---------------------------------------------------------------------------

def parse_build_root(content):
    """Extract build-root image tag and source kind from .ci-operator.yaml."""
    try:
        import yaml
    except ImportError as exc:
        raise LookupErrorWithContext(
            "--build-root requires PyYAML (pip install PyYAML)"
        ) from exc
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise LookupErrorWithContext(
            f"invalid YAML in {CI_OPERATOR_YAML}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        return None, None
    bri = data.get("build_root_image")
    if isinstance(bri, dict):
        tag = bri.get("tag")
        if isinstance(tag, str) and tag:
            return tag, "build_root_image"
    br = data.get("build_root")
    if isinstance(br, dict):
        ist = br.get("image_stream_tag")
        if isinstance(ist, dict):
            tag = ist.get("tag")
            if isinstance(tag, str) and tag:
                return tag, "image_stream_tag"
        if br.get("from_repository"):
            return None, "from_repository"
        if isinstance(br.get("project_image"), dict):
            return None, "project_image"
    return None, None


def _resolve_build_root(repo, ref, br_cache):
    """Return (build_root_tag, go_version) for a repo, caching results."""
    key = (repo, ref)
    if key not in br_cache:
        try:
            content = file_content(repo, ref, CI_OPERATOR_YAML)
            tag, kind = parse_build_root(content)
            if kind and kind not in ("from_repository", "project_image"):
                go_match = GO_VERSION.search(tag)
                br_cache[key] = (tag, go_match[1] if go_match else "(unknown)")
            elif kind:
                br_cache[key] = (f"({kind})", "(n/a)")
            else:
                br_cache[key] = ("(none)", "(none)")
        except LookupErrorWithContext:
            br_cache[key] = ("(none)", "(none)")
    return br_cache[key]


# ---------------------------------------------------------------------------
# Dockerfile-based release inspection (with optional build-root enrichment)
# ---------------------------------------------------------------------------

def inspect_release(release, correlate=False, release_image=None,
                    build_root=False, on_result=None):
    tags = ((release.get("references") or {}).get("spec") or {}).get("tags") or []
    if not tags:
        raise LookupErrorWithContext("release contains no component images")
    build_branch, configs = (
        load_build_data(release, release_image) if correlate else (None, {})
    )
    tree_cache = {}
    scan_cache = {}
    br_cache = {}
    br_unavail = ("(unavailable)", "(unavailable)") if build_root else ()
    br_fields = br_unavail
    rows = []

    def record(row):
        full = row + br_fields
        rows.append(full)
        if on_result:
            on_result(full)

    for tag in tags:
        name = tag.get("name") or "(unnamed)"
        image = (tag.get("from") or {}).get("name") or "(missing image)"
        repo = branch = ref = "(unknown)"
        br_fields = br_unavail
        try:
            if image == "(missing image)":
                raise LookupErrorWithContext(
                    "component image reference missing from release metadata"
                )
            repo, branch, ref = source_for_tag(tag)
            if build_root:
                br_fields = _resolve_build_root(repo, ref, br_cache)
            if correlate:
                matches = configs.get(name, [])
                selections = []
                config_for_evidence = {}
                if not matches:
                    fallback = SOURCE_DOCKERFILE_EXCEPTIONS.get((name, repo.lower()))
                    if fallback:
                        evidence = f"{repo}@{ref}"
                        selections.append((evidence, "source repo", fallback, ""))
                        config_for_evidence[evidence] = {}
                    else:
                        record((
                            name, image, repo, branch, ref, "(none)", "-", "(none)",
                            "-", "(not checked)", "-",
                            f"warning: no matching ocp-build-data image config on "
                            f"{build_branch} for this payload component; "
                            "builder not checked",
                        ))
                        continue
                for config_path, config in matches:
                    evidence = f"{config_path}@{build_branch}"
                    config_for_evidence[evidence] = config
                    git = (
                        (config.get("content") or {}).get("source") or {}
                    ).get("git") or {}
                    public_url = git.get("web") if isinstance(git, dict) else None
                    if public_url:
                        try:
                            config_repo = github_repo(public_url)
                        except LookupErrorWithContext as exc:
                            selections.append(
                                (evidence, "-", None, f"error: {exc}")
                            )
                            continue
                        if config_repo.lower() != repo.lower():
                            selections.append((
                                evidence, "-", None,
                                f"error: source repo mismatch: "
                                f"{config_repo} vs {repo}",
                            ))
                            continue
                    try:
                        selections.extend(
                            (evidence, variant, path, status)
                            for variant, path, status
                            in selected_dockerfiles(config)
                        )
                    except LookupErrorWithContext as exc:
                        selections.append((evidence, "-", None, f"error: {exc}"))
            else:
                selections = None
            key = (repo, ref)
            if key not in tree_cache:
                tree_cache[key] = repository_files(repo, ref)
            blobs = tree_cache[key]
            if selections is None:
                selections = [
                    ("-", "-", path, "")
                    for path in sorted(blobs) if is_dockerfile(path)
                ]
                if not selections:
                    record((
                        name, image, repo, branch, ref, "-", "-", "(none)",
                        "-", "(none)", "-", "no Dockerfiles",
                    ))
                    continue
            for evidence, variant, path, selection_status in selections:
                if not path or selection_status:
                    record((
                        name, image, repo, branch, ref, evidence, variant,
                        path or "(none)", "-", "(none)", "-", selection_status,
                    ))
                    continue
                if path not in blobs:
                    record((
                        name, image, repo, branch, ref, evidence, variant, path,
                        "-", "(unavailable)", "-",
                        "error: configured Dockerfile not found at source ref",
                    ))
                    continue
                try:
                    args = (
                        build_args_for(config_for_evidence[evidence], variant)
                        if correlate else {}
                    )
                    scan_key = (repo, ref, path, tuple(sorted(args.items())))
                    if scan_key not in scan_cache:
                        scan_cache[scan_key] = scan_dockerfile(
                            repo, ref, path, blobs, args
                        )
                    resolved, findings = scan_cache[scan_key]
                    display_path = (
                        path if resolved == path else f"{path} -> {resolved}"
                    )
                    if findings:
                        for line, builder, version, status in findings:
                            record((
                                name, image, repo, branch, ref, evidence, variant,
                                display_path, str(line), builder, version, status,
                            ))
                    else:
                        record((
                            name, image, repo, branch, ref, evidence, variant,
                            display_path, "-", "(none)", "-", "no Go builder FROM",
                        ))
                except LookupErrorWithContext as exc:
                    record((
                        name, image, repo, branch, ref, evidence, variant,
                        path, "-", "(unavailable)", "-", f"error: {exc}",
                    ))
        except LookupErrorWithContext as exc:
            record((
                name, image, repo, branch, ref, "-", "-", "(unavailable)",
                "-", "(unavailable)", "-", f"error: {exc}",
            ))
    return rows


def format_result(row):
    builder = row[9]
    if row[11] in ("unresolved FROM variable", "unparseable FROM"):
        builder = f"(unknown: {row[11]} {builder})"
    fields = [row[0], row[2], row[5], row[6], row[7], builder, row[10]]
    if len(row) > 12:
        fields.extend((row[12], row[13]))
    return "\t".join(fields)


# ---------------------------------------------------------------------------
# Standalone .ci-operator.yaml build-root inspection
# ---------------------------------------------------------------------------

def inspect_release_build_root(release, on_result=None):
    tags = ((release.get("references") or {}).get("spec") or {}).get("tags") or []
    if not tags:
        raise LookupErrorWithContext("release contains no component images")
    br_cache = {}
    rows = []

    def record(row):
        rows.append(row)
        if on_result:
            on_result(row)

    for tag_entry in tags:
        name = tag_entry.get("name") or "(unnamed)"
        image = (tag_entry.get("from") or {}).get("name") or "(missing image)"
        repo = branch = ref = "(unknown)"
        try:
            if image == "(missing image)":
                raise LookupErrorWithContext(
                    "component image reference missing from release metadata"
                )
            repo, branch, ref = source_for_tag(tag_entry)
            br_tag, br_go = _resolve_build_root(repo, ref, br_cache)
            record((name, image, repo, branch, ref, br_tag, br_go, ""))
        except LookupErrorWithContext as exc:
            record((
                name, image, repo, branch, ref,
                "(unavailable)", "(unavailable)", f"error: {exc}",
            ))
    return rows


def format_result_build_root(row):
    return "\t".join((row[0], row[2], row[5], row[6]))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_image", help="OpenShift release image pullspec")
    parser.add_argument(
        "--correlate-builder", action="store_true",
        help="limit Dockerfiles to ocp-build-data image configs, "
             "including distinct OKD overrides",
    )
    parser.add_argument(
        "--build-root", action="store_true",
        help="report Go versions from .ci-operator.yaml build root images "
             "(standalone, or combined with --correlate-builder)",
    )
    args = parser.parse_args(argv)

    if args.build_root:
        try:
            import yaml  # noqa: F401
        except ImportError:
            print("error: --build-root requires PyYAML (pip install PyYAML)",
                  file=sys.stderr)
            return 1

    try:
        release = oc_json(
            "adm", "release", "info", args.release_image, "-o", "json"
        )
        if args.build_root and not args.correlate_builder:
            print(
                "component\trepository\tbuild root tag\tgo version",
                flush=True,
            )

            def print_br_result(row):
                print(format_result_build_root(row), flush=True)
                if row[-1].startswith("error:"):
                    print(f"{row[0]}: {row[-1]}", file=sys.stderr, flush=True)

            rows = inspect_release_build_root(release, on_result=print_br_result)
        else:
            header = (
                "component\trepository\tbuild config\tvariant\t"
                "Dockerfile\tbuilder image\tgo version"
            )
            if args.build_root:
                header += "\tbuild root tag\tbuild root go version"
            print(header, flush=True)
            if args.correlate_builder:
                print(
                    "Loading ocp-build-data image configs...",
                    file=sys.stderr, flush=True,
                )

            def print_result(row):
                print(format_result(row), flush=True)
                status = row[11]
                if status.startswith(("error:", "warning:")):
                    print(f"{row[0]}: {status}", file=sys.stderr, flush=True)

            rows = inspect_release(
                release, args.correlate_builder, args.release_image,
                build_root=args.build_root,
                on_result=print_result,
            )
    except LookupErrorWithContext as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.build_root and not args.correlate_builder:
        has_errors = any(row[-1].startswith("error:") for row in rows)
    else:
        has_errors = any(row[11].startswith("error:") for row in rows)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
