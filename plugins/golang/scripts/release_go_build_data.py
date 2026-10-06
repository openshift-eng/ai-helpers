#!/usr/bin/env python3
"""Dockerfile parsing and ocp-build-data correlation helpers."""

from concurrent.futures import ThreadPoolExecutor
import posixpath
import re
import shlex

from release_go_utils import (
    GO_VERSION, LookupErrorWithContext, file_content, repository_files,
)

ARG_REF = re.compile(
    r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)(?:(:-|-)([^}]*))?\}"
    r"|([A-Za-z_][A-Za-z0-9_]*))"
)
GO_IMAGE = re.compile(r"(?:^|[/_.:-])(?:go|golang)(?:[-_.:/]|\d)", re.IGNORECASE)
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


# ---------------------------------------------------------------------------
# ocp-build-data helpers
# ---------------------------------------------------------------------------

def build_data_branch(release, release_image):
    metadata = release.get("metadata") or {}
    tag = release_image.rsplit(":", 1)[-1]
    for candidate in (metadata.get("version"), release.get("version"), tag):
        if not isinstance(candidate, str):
            continue
        match = re.match(r"^(\d+)\.(\d+)(?:\.\d+)?(?:[-+].*)?$", candidate)
        if match:
            return f"openshift-{match[1]}.{match[2]}"
    raise LookupErrorWithContext(
        "cannot determine release version for ocp-build-data branch"
    )


def load_build_data(release, release_image):
    """Index images/*.yml by payload_name on the matching openshift-X.Y branch."""
    try:
        import yaml
    except ImportError as exc:
        raise LookupErrorWithContext(
            "--correlate-builder requires PyYAML (pip install PyYAML)"
        ) from exc

    branch = build_data_branch(release, release_image)
    blobs = repository_files(BUILD_DATA_REPO, branch)
    paths = sorted(
        path for path in blobs
        if path.startswith("images/") and path.endswith((".yml", ".yaml"))
    )
    if not paths:
        raise LookupErrorWithContext(
            f"no image configs found in {BUILD_DATA_REPO} at {branch}"
        )
    wanted = {
        tag.get("name") for tag in
        ((release.get("references") or {}).get("spec") or {}).get("tags", [])
    }
    configs = {}

    def fetch(path):
        try:
            data = yaml.safe_load(file_content(BUILD_DATA_REPO, branch, path))
        except yaml.YAMLError as exc:
            raise LookupErrorWithContext(f"invalid YAML in {path}: {exc}") from exc
        if data is not None and not isinstance(data, dict):
            raise LookupErrorWithContext(f"image config is not a mapping: {path}")
        if data and not isinstance(data.get("content") or {}, dict):
            raise LookupErrorWithContext(f"invalid content mapping in {path}")
        if data and not isinstance(
            ((data.get("content") or {}).get("source") or {}), dict
        ):
            raise LookupErrorWithContext(f"invalid source mapping in {path}")
        return path, data or {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for path, config in pool.map(fetch, paths):
            payload_name = (
                config.get("payload_name")
                or BUILD_DATA_CONFIG_EXCEPTIONS.get(path)
            )
            if isinstance(payload_name, str) and payload_name in wanted:
                configs.setdefault(payload_name, []).append((path, config))
    return branch, configs


def dockerfile_path(value, context_dir="", default_dir=""):
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("/"):
        raise LookupErrorWithContext(
            f"absolute Dockerfile path in build data: {value}"
        )
    if context_dir:
        value = posixpath.join(context_dir, value)
    elif "/" not in value:
        value = posixpath.join(default_dir, value)
    result = posixpath.normpath(value)
    if result == ".." or result.startswith("../"):
        raise LookupErrorWithContext(f"Dockerfile path escapes repository: {value}")
    return result


def build_args_for(config, variant):
    """Return Docker build arguments for the selected build-data variant."""
    content = config.get("content") or {}
    details = content.get("source") or {}
    sources = [config, content, details]
    if variant == "OKD":
        alignment = (
            details.get("okd_alignment")
            or content.get("okd_alignment")
            or config.get("okd_alignment")
        )
        okd = config.get("okd") or {}
        okd_content = okd.get("content") or {} if isinstance(okd, dict) else {}
        okd_source = (
            okd_content.get("source") or {} if isinstance(okd_content, dict) else {}
        )
        sources.extend((alignment, okd, okd_content, okd_source))
    args = {}
    for item in sources:
        value = item.get("build_args") if isinstance(item, dict) else None
        if isinstance(value, dict):
            pairs = value.items()
        elif isinstance(value, list):
            pairs = (
                (entry.get("name"), entry.get("value"))
                for entry in value if isinstance(entry, dict)
            )
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
    if not isinstance(details, dict) or not details:
        return [("default", None, "no source Dockerfile configured")]
    default_context = (
        details.get("path") or details.get("context_dir")
        or content.get("context_dir") or config.get("context_dir") or ""
    )
    default = dockerfile_path(
        details.get("dockerfile") or details.get("dockerfile_path")
        or config.get("dockerfile_path") or "Dockerfile",
        default_context,
    )
    alignment = (
        details.get("okd_alignment")
        or content.get("okd_alignment")
        or config.get("okd_alignment")
    )
    okd_root = config.get("okd") or {}
    okd_content = okd_root.get("content") or {} if isinstance(okd_root, dict) else {}
    okd_source = (
        okd_content.get("source") or {} if isinstance(okd_content, dict) else {}
    )
    candidates = []
    if isinstance(alignment, dict):
        if alignment.get("resolve_as"):
            candidates.append(("OKD", None, "OKD resolves external image"))
        else:
            alignment_path = alignment.get("path") or ""
            alignment_path_is_file = is_dockerfile(alignment_path)
            alignment_file_from_path = (
                not alignment.get("dockerfile")
                and not alignment.get("dockerfile_path")
                and alignment_path_is_file
            )
            alignment_context = (
                alignment.get("context_dir")
                or (alignment_path if not alignment_path_is_file else "")
                or default_context
            )
            alignment_file = (
                alignment.get("dockerfile")
                or alignment.get("dockerfile_path")
                or (alignment_path if alignment_path_is_file else "")
                or posixpath.basename(default)
            )
            alignment_file_context = (
                "" if alignment_file_from_path and "/" in alignment_file
                else alignment_context
            )
            candidates.append((
                "OKD",
                dockerfile_path(
                    alignment_file, alignment_file_context,
                    posixpath.dirname(default),
                ),
                "",
            ))
    if isinstance(okd_source, dict) and okd_source:
        okd_context = (
            okd_source.get("path") or okd_source.get("context_dir")
            or default_context
        )
        okd_file = (
            okd_source.get("dockerfile") or okd_source.get("dockerfile_path")
            or posixpath.basename(default)
        )
        candidates.append((
            "OKD",
            dockerfile_path(okd_file, okd_context, posixpath.dirname(default)),
            "",
        ))
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
        if (status or path not in seen
                or (variant == "OKD" and args_differ and path not in added_okd)):
            results.append((variant, path, status))
            seen.add(path)
            if variant == "OKD":
                added_okd.add(path)
    return results


# ---------------------------------------------------------------------------
# Dockerfile parsing
# ---------------------------------------------------------------------------

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
        resolved = args.get(name)
        operator, default = match[2], match[3]
        if operator == ":-" and not resolved:
            resolved = default
        elif operator == "-" and resolved is None:
            resolved = default
        return resolved if resolved is not None else match[0]

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
                    val = value.strip()
                    if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                        val = val[1:-1]
                    global_args[name] = resolve_args(val, global_args)
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
            matches.append(
                (line_number, image, "(unknown)", "unresolved FROM variable")
            )
        elif GO_IMAGE.search(image):
            match = GO_VERSION.search(image)
            matches.append((
                line_number, image,
                match[1] if match else "(unknown)",
                "Go builder FROM" if match else "Go builder version unknown",
            ))
    return matches


def scan_dockerfile(repo, ref, path, blobs, build_args=None):
    """Follow simple Dockerfile pointer files and return the resolved scan."""
    visited = set()
    current = path
    while True:
        if current in visited:
            raise LookupErrorWithContext(f"Dockerfile pointer cycle at {current}")
        visited.add(current)
        content = file_content(repo, ref, current)
        findings = go_builder_froms(content, build_args)
        if findings or any(
            operation.split(None, 1)[0].upper() == "FROM"
            for _, operation in instructions(content)
        ):
            return current, findings
        target = content.strip()
        if "\n" not in target and target and not target.startswith("#"):
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(current), target)
            )
            if resolved in blobs:
                current = resolved
                continue
        return current, []
