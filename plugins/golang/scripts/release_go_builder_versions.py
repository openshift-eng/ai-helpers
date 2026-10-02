#!/usr/bin/env python3
"""List Go builder FROM images in every source Dockerfile of a release."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import posixpath
import re
import shlex
import sys

import release_go_module_versions as source


ARG_REF = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)(?:(:-|-)([^}]*))?\}|([A-Za-z_][A-Za-z0-9_]*))")
GO_IMAGE = re.compile(r"(?:^|[/_.:-])(?:go|golang)(?:[-_.:/]|\d)", re.IGNORECASE)
GO_VERSION = re.compile(r"(?:^|[/_.:-])(?:go|golang)(?:[-_.]builder)?[-_:]?v?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
BUILD_DATA_REPO = "openshift-eng/ocp-build-data"
BUILD_DATA_CONFIG_EXCEPTIONS = {
    "images/ose-installer-etcd-artifacts.yml": "installer-etcd-artifacts",
    "images/ose-installer-kube-apiserver-artifacts.yml": "installer-kube-apiserver-artifacts",
}
SOURCE_DOCKERFILE_EXCEPTIONS = {
    ("nutanix-cluster-api-controllers", "openshift/cluster-api-provider-nutanix"):
        "openshift/Dockerfile.openshift",
}


def is_dockerfile(path):
    name = posixpath.basename(path).lower()
    return (name.startswith("containerfile") or name.endswith(".containerfile")
            or name == "dockerfile"
            or name.startswith("dockerfile.") or name.endswith(".dockerfile")
            or ".dockerfile." in name)


def repository_tree(repo, ref):
    return source.repository_files(repo, ref)


def build_data_branch(release, release_image):
    metadata = release.get("metadata") or {}
    tag = release_image.rsplit(":", 1)[-1]
    for candidate in (metadata.get("version"), release.get("version"), tag):
        if not isinstance(candidate, str):
            continue
        match = re.match(r"^(\d+)\.(\d+)(?:\.\d+)?(?:[-+].*)?$", candidate)
        if match:
            return f"openshift-{match[1]}.{match[2]}"
    raise source.LookupErrorWithContext("cannot determine release version for ocp-build-data branch")


def load_build_data(release, release_image):
    """Index images/*.yml by payload_name on the matching openshift-X.Y branch."""
    try:
        import yaml
    except ImportError as exc:
        raise source.LookupErrorWithContext("--correlate-builder requires PyYAML (pip install PyYAML)") from exc

    branch = build_data_branch(release, release_image)
    blobs = repository_tree(BUILD_DATA_REPO, branch)
    paths = sorted(path for path in blobs if path.startswith("images/")
                   and path.endswith((".yml", ".yaml")))
    if not paths:
        raise source.LookupErrorWithContext(f"no image configs found in {BUILD_DATA_REPO} at {branch}")
    wanted = {tag.get("name") for tag in
              ((release.get("references") or {}).get("spec") or {}).get("tags", [])}
    configs = {}

    def fetch(path):
        try:
            data = yaml.safe_load(source.module_content(BUILD_DATA_REPO, branch, path))
        except yaml.YAMLError as exc:
            raise source.LookupErrorWithContext(f"invalid YAML in {path}: {exc}") from exc
        if data is not None and not isinstance(data, dict):
            raise source.LookupErrorWithContext(f"image config is not a mapping: {path}")
        if data and not isinstance(data.get("content") or {}, dict):
            raise source.LookupErrorWithContext(f"invalid content mapping in {path}")
        if data and not isinstance(((data.get("content") or {}).get("source") or {}), dict):
            raise source.LookupErrorWithContext(f"invalid source mapping in {path}")
        return path, data or {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for path, config in pool.map(fetch, paths):
            payload_name = config.get("payload_name") or BUILD_DATA_CONFIG_EXCEPTIONS.get(path)
            if isinstance(payload_name, str) and payload_name in wanted:
                configs.setdefault(payload_name, []).append((path, config))
    return branch, configs


def dockerfile_path(value, context_dir="", default_dir=""):
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("/"):
        raise source.LookupErrorWithContext(f"absolute Dockerfile path in build data: {value}")
    if "/" not in value:
        value = posixpath.join(context_dir or default_dir, value)
    result = posixpath.normpath(value)
    if result == ".." or result.startswith("../"):
        raise source.LookupErrorWithContext(f"Dockerfile path escapes repository: {value}")
    return result


def build_args_for(config, variant):
    """Return Docker build arguments for the selected build-data variant."""
    content = config.get("content") or {}
    details = content.get("source") or {}
    sources = [config, content, details]
    if variant == "OKD":
        alignment = details.get("okd_alignment") or content.get("okd_alignment") or config.get("okd_alignment")
        okd = config.get("okd") or {}
        okd_content = okd.get("content") or {} if isinstance(okd, dict) else {}
        okd_source = okd_content.get("source") or {} if isinstance(okd_content, dict) else {}
        sources.extend((alignment, okd, okd_content, okd_source))
    args = {}
    for item in sources:
        value = item.get("build_args") if isinstance(item, dict) else None
        if isinstance(value, dict):
            pairs = value.items()
        elif isinstance(value, list):
            pairs = ((entry.get("name"), entry.get("value"))
                     for entry in value if isinstance(entry, dict))
        else:
            continue
        for name, setting in pairs:
            if isinstance(name, str) and setting is not None:
                args[name] = str(setting)
    return args


def selected_dockerfiles(config):
    """Return variant, path, status for the default and distinct OKD Dockerfiles."""
    content = config.get("content") or {}
    details = content.get("source") or {}
    if not isinstance(details, dict):
        return [("default", None, "no source Dockerfile configured")]
    if not details:
        return [("default", None, "no source Dockerfile configured")]
    default_context = (details.get("path") or details.get("context_dir")
                       or content.get("context_dir") or config.get("context_dir") or "")
    default = dockerfile_path(
        details.get("dockerfile") or details.get("dockerfile_path")
        or config.get("dockerfile_path") or "Dockerfile", default_context,
    )
    alignment = details.get("okd_alignment") or content.get("okd_alignment") or config.get("okd_alignment")
    okd_root = config.get("okd") or {}
    okd_content = okd_root.get("content") or {} if isinstance(okd_root, dict) else {}
    okd_source = okd_content.get("source") or {} if isinstance(okd_content, dict) else {}
    candidates = []
    if isinstance(alignment, dict):
        if alignment.get("resolve_as"):
            candidates.append(("OKD", None, "OKD resolves external image"))
        else:
            alignment_context = (alignment.get("context_dir") or
                                 (alignment.get("path") if not is_dockerfile(alignment.get("path") or "") else "")
                                 or default_context)
            alignment_file = (alignment.get("dockerfile") or alignment.get("dockerfile_path")
                              or (alignment.get("path") if is_dockerfile(alignment.get("path") or "") else "")
                              or posixpath.basename(default))
            candidates.append(("OKD", dockerfile_path(alignment_file, alignment_context,
                                                         posixpath.dirname(default)), ""))
    if isinstance(okd_source, dict) and okd_source:
        okd_context = okd_source.get("path") or okd_source.get("context_dir") or default_context
        okd_file = okd_source.get("dockerfile") or okd_source.get("dockerfile_path") or posixpath.basename(default)
        candidates.append(("OKD", dockerfile_path(okd_file, okd_context,
                                                     posixpath.dirname(default)), ""))
    if not candidates:
        return [("default", default, "")]
    args_differ = build_args_for(config, "default") != build_args_for(config, "OKD")
    if (all(path == default for _, path, status in candidates if not status)
            and not any(status for _, _, status in candidates)
            and not args_differ):
        return [("default/OKD", default, "")]
    results = [("default", default, "")]
    seen = {default}
    added_okd = set()
    for variant, path, status in candidates:
        if status or path not in seen or (variant == "OKD" and args_differ and path not in added_okd):
            results.append((variant, path, status))
            seen.add(path)
            if variant == "OKD":
                added_okd.add(path)
    return results


def instructions(content):
    """Yield (line number, instruction) with backslash continuations joined."""
    pending = ""
    start = 0
    for number, raw in enumerate(content.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not pending:
            start = number
        continuation = line.endswith("\\")
        pending += line[:-1].rstrip() + " " if continuation else line
        if not continuation:
            yield start, pending.strip()
            pending = ""
    if pending:
        yield start, pending.strip()


def resolve_args(value, args):
    def substitute(match):
        name = match[1] or match[4]
        value = args.get(name)
        operator, default = match[2], match[3]
        if operator == ":-" and not value:
            value = default
        elif operator == "-" and value is None:
            value = default
        return value if value is not None else match[0]

    result = value
    for _ in range(10):
        next_result = ARG_REF.sub(substitute, result)
        if next_result == result:
            break
        result = next_result
    return result


def go_builder_froms(content, build_args=None):
    """Return (line, image, version, status) for Go or unresolved FROMs."""
    global_args = {}
    provided_args = build_args or {}
    seen_from = False
    matches = []
    for line_number, instruction in instructions(content):
        parts = instruction.split(None, 1)
        operation = parts[0]
        rest = parts[1] if len(parts) == 2 else ""
        if operation.upper() == "ARG" and not seen_from:
            name, separator, value = rest.strip().partition("=")
            if name and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                if name in provided_args:
                    global_args[name] = provided_args[name]
                elif separator:
                    global_args[name] = resolve_args(value.strip().strip('"\''), global_args)
                else:
                    global_args[name] = None
            continue
        if operation.upper() != "FROM":
            continue
        seen_from = True
        try:
            tokens = shlex.split(rest, comments=False)
        except ValueError:
            matches.append((line_number, rest.strip(), "(unknown)", "unparseable FROM"))
            continue
        candidates = [token for token in tokens if not token.startswith("--")]
        if not candidates:
            matches.append((line_number, rest.strip(), "(unknown)", "unparseable FROM"))
            continue
        image = resolve_args(candidates[0], global_args)
        if "$" in image:
            matches.append((line_number, image, "(unknown)", "unresolved FROM variable"))
        elif GO_IMAGE.search(image):
            match = GO_VERSION.search(image)
            matches.append((line_number, image, match[1] if match else "(unknown)",
                            "Go builder FROM" if match else "Go builder version unknown"))
    return matches


def scan_dockerfile(repo, ref, path, blobs, build_args=None):
    """Follow simple Dockerfile pointer files and return the resolved scan."""
    visited = set()
    current = path
    while True:
        if current in visited:
            raise source.LookupErrorWithContext(f"Dockerfile pointer cycle at {current}")
        visited.add(current)
        content = source.module_content(repo, ref, current)
        findings = go_builder_froms(content, build_args)
        if findings or any(operation.split(None, 1)[0].upper() == "FROM"
                           for _, operation in instructions(content)):
            return current, findings
        target = content.strip()
        if "\n" not in target and target and not target.startswith("#"):
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(current), target))
            if resolved in blobs:
                current = resolved
                continue
        return current, []


def inspect_release(release, correlate=False, release_image=None, on_result=None):
    tags = ((release.get("references") or {}).get("spec") or {}).get("tags") or []
    if not tags:
        raise source.LookupErrorWithContext("release contains no component images")
    build_branch, configs = load_build_data(release, release_image) if correlate else (None, {})
    tree_cache = {}
    scan_cache = {}
    rows = []

    def record(row):
        rows.append(row)
        if on_result:
            on_result(row)

    for tag in tags:
        name = tag.get("name") or "(unnamed)"
        image = (tag.get("from") or {}).get("name") or "(missing image)"
        repo = branch = ref = "(unknown)"
        try:
            if image == "(missing image)":
                raise source.LookupErrorWithContext("component image reference missing from release metadata")
            repo, branch, ref = source.source_for_tag(tag)
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
                        record((name, image, repo, branch, ref, "(none)", "-", "(none)",
                                "-", "(not checked)", "-",
                                f"warning: no matching ocp-build-data image config on {build_branch} "
                                "for this payload component; builder not checked"))
                        continue
                for config_path, config in matches:
                    evidence = f"{config_path}@{build_branch}"
                    config_for_evidence[evidence] = config
                    git = ((config.get("content") or {}).get("source") or {}).get("git") or {}
                    public_url = git.get("web") if isinstance(git, dict) else None
                    if public_url:
                        try:
                            config_repo = source.github_repo(public_url)
                        except source.LookupErrorWithContext as exc:
                            selections.append((evidence, "-", None, f"error: {exc}"))
                            continue
                        if config_repo.lower() != repo.lower():
                            selections.append((evidence, "-", None,
                                               f"error: source repo mismatch: {config_repo} vs {repo}"))
                            continue
                    try:
                        selections.extend((evidence, variant, path, status)
                                          for variant, path, status in selected_dockerfiles(config))
                    except source.LookupErrorWithContext as exc:
                        selections.append((evidence, "-", None, f"error: {exc}"))
            else:
                selections = None
            key = (repo, ref)
            if key not in tree_cache:
                tree_cache[key] = repository_tree(repo, ref)
            blobs = tree_cache[key]
            if selections is None:
                selections = [("-", "-", path, "") for path in sorted(blobs) if is_dockerfile(path)]
                if not selections:
                    record((name, image, repo, branch, ref, "-", "-", "(none)",
                            "-", "(none)", "-", "no Dockerfiles"))
                    continue
            for evidence, variant, path, selection_status in selections:
                if not path or selection_status:
                    record((name, image, repo, branch, ref, evidence, variant,
                            path or "(none)", "-", "(none)", "-", selection_status))
                    continue
                if path not in blobs:
                    record((name, image, repo, branch, ref, evidence, variant, path,
                            "-", "(unavailable)", "-", "error: configured Dockerfile not found at source ref"))
                    continue
                try:
                    args = build_args_for(config_for_evidence[evidence], variant) if correlate else {}
                    scan_key = (repo, ref, path, tuple(sorted(args.items())))
                    if scan_key not in scan_cache:
                        scan_cache[scan_key] = scan_dockerfile(repo, ref, path, blobs, args)
                    resolved, findings = scan_cache[scan_key]
                    display_path = path if resolved == path else f"{path} -> {resolved}"
                    if findings:
                        for line, builder, version, status in findings:
                            record((name, image, repo, branch, ref, evidence, variant,
                                    display_path, str(line), builder, version, status))
                    else:
                        record((name, image, repo, branch, ref, evidence, variant,
                                display_path, "-", "(none)", "-", "no Go builder FROM"))
                except source.LookupErrorWithContext as exc:
                    record((name, image, repo, branch, ref, evidence, variant,
                            path, "-", "(unavailable)", "-", f"error: {exc}"))
        except source.LookupErrorWithContext as exc:
            record((name, image, repo, branch, ref, "-", "-", "(unavailable)",
                    "-", "(unavailable)", "-", f"error: {exc}"))
    return rows


def format_result(row):
    builder = row[9]
    if row[11] in ("unresolved FROM variable", "unparseable FROM"):
        builder = f"(unknown: {row[11]} {builder})"
    return "\t".join((row[0], row[2], row[5], row[6], row[7], builder))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_image", help="OpenShift release image pullspec")
    parser.add_argument("--correlate-builder", action="store_true",
                        help="limit Dockerfiles to ocp-build-data image configs, including distinct OKD overrides")
    args = parser.parse_args(argv)

    def print_result(row):
        print(format_result(row), flush=True)
        if row[-1].startswith(("error:", "warning:")):
            print(f"{row[0]}: {row[-1]}", file=sys.stderr, flush=True)

    try:
        release = source.oc_json("adm", "release", "info", args.release_image, "-o", "json")
        print("component\trepository\tbuild config\tvariant\tDockerfile\tbuilder image", flush=True)
        if args.correlate_builder:
            print("Loading ocp-build-data image configs...", file=sys.stderr, flush=True)
        rows = inspect_release(
            release, args.correlate_builder, args.release_image,
            on_result=print_result,
        )
    except source.LookupErrorWithContext as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1 if any(row[-1].startswith("error:") for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
