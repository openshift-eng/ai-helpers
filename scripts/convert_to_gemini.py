#!/usr/bin/env python3
"""Convert Claude Code plugins to a single Gemini CLI extension.

Reads all plugins under plugins/ and generates a Gemini CLI extension at the
repo root. Directory-based namespacing preserves the /plugin:command pattern
(e.g. commands/ci/analyze-payload.toml -> /ci:analyze-payload).

Generated files at repo root:
  gemini-extension.json   # Extension manifest (version auto-bumped)
  GEMINI.md               # Aggregated context file
  commands/               # Converted commands (TOML)
    {plugin}/
      {command}.toml
  skills/                 # Copied skills (nested by plugin)
    {plugin}/
      {skill}/
        SKILL.md

Conversion details:
  - commands/*.md frontmatter -> TOML description field (via yaml.safe_load)
  - commands/*.md body -> TOML prompt field (triple-quoted ''')
  - "Claude" references replaced with "Gemini" in commands and skills
  - Skills nested under plugin name to preserve path structure

Version management:
  The version in gemini-extension.json starts at 0.1.0 on first generation.
  - Minor version is bumped when a new plugin is added (e.g. 0.1.0 -> 0.2.0)
  - Patch version is bumped when an existing plugin is updated (e.g. 0.1.0 -> 0.1.1)
  - Major version is only bumped manually.
"""

import filecmp
import json
import os
import re
import shutil
import sys
import tempfile

import yaml

try:
    import tomllib
except ImportError:
    import tomli as tomllib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS_DIR = os.path.join(REPO_ROOT, "plugins")

# Files/directories managed by this script at the repo root
MANAGED_PATHS = ["gemini-extension.json", "GEMINI.md", "commands", "skills", "plugin-scripts"]

# Text replacement mapping: Claude-specific references -> Gemini equivalents.
# Uses single-pass regex to avoid recursive replacement issues where an earlier
# replacement's output could match a later replacement's input.
# "Claude agent text" is a real pattern used in plugin output descriptions
# (e.g. git/branch-cleanup.md, yaml/docs.md).
_REPLACEMENTS = {
    "Claude agent text": "Gemini agent text",
    "Claude Code plugin": "Gemini CLI extension",
    "Claude Code": "Gemini CLI",
    "Claude plugin": "Gemini extension",
    "Claude": "Gemini",
    "https://claude.com/claude-code": "https://github.com/google-gemini/gemini-cli",
    "$HOME/.config/claude-code/": "$HOME/.gemini/",
    "~/.config/claude-code/": "~/.gemini/",
    "CLAUDE.md": "GEMINI.md",
    "claude-code": "gemini-cli",
    ".claude/": ".gemini/",
    "claude": "gemini",
}

# Build a single regex that matches any key (longest first to prefer specific
# matches over generic ones). Each matched segment is replaced exactly once.
_REPLACEMENTS_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(_REPLACEMENTS, key=len, reverse=True))
)


def parse_md_frontmatter(content):
    """Extract YAML frontmatter and body from a markdown file."""
    frontmatter = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            parsed = yaml.safe_load(parts[1])
            if isinstance(parsed, dict):
                frontmatter = {
                    k: str(v) if v is not None else ""
                    for k, v in parsed.items()
                }
            body = parts[2].lstrip("\n")
    return frontmatter, body


def adapt_text(text, plugin_name=None):
    """Replace Claude-specific references with Gemini equivalents.

    Uses single-pass regex so each matched segment is replaced exactly once,
    avoiding recursive replacement issues.
    """
    if plugin_name:
        text = text.replace(
            "${CLAUDE_PLUGIN_ROOT}/skills/",
            f"${{extensionPath}}/skills/{plugin_name}/",
        )
        text = text.replace(
            "${CLAUDE_PLUGIN_ROOT}/scripts/",
            f"${{extensionPath}}/plugin-scripts/{plugin_name}/",
        )
        text = text.replace("${CLAUDE_PLUGIN_ROOT}", "${extensionPath}")
    text = _REPLACEMENTS_RE.sub(lambda m: _REPLACEMENTS[m.group()], text)
    # Escape @{VAR} patterns that Gemini CLI would interpret as file
    # injection directives. Drop the braces to produce @VAR instead.
    text = re.sub(r'@\{([A-Za-z_][A-Za-z0-9_]*)\}', r'@\1', text)
    return text


def convert_command_to_toml(md_path, plugin_name, plugin_version):
    """Convert a Claude command .md file to a Gemini command .toml file."""
    with open(md_path, "r") as f:
        content = f.read()

    frontmatter, body = parse_md_frontmatter(content)
    description = adapt_text(frontmatter.get("description", ""), plugin_name)

    body = adapt_text(body, plugin_name)

    # Replace Claude-style positional arguments ($1, $2, $ARGUMENTS, etc.)
    # with Gemini CLI's {{args}} placeholder. Gemini CLI provides the entire
    # argument string as {{args}} — the model parses individual args.
    body = re.sub(r'\$\{(\d+)\}', '{{args}}', body)
    body = re.sub(r'(?<!\$)\$(\d+)', '{{args}}', body)
    body = re.sub(r'\$ARGUMENTS', '{{args}}', body)
    # Clean up converted argument list patterns like "{{args}}, {{args}}, ..., $N"
    body = re.sub(
        r'\{\{args\}\}(?:,\s*\{\{args\}\})*(?:,\s*\.\.\.,\s*\$N)?',
        '{{args}}',
        body,
    )

    lines = [f"# Autogenerated from plugins/{plugin_name} v{plugin_version}"]
    if description:
        lines.append(f"description = '''\n{description}'''")
    lines.append(
        "prompt = '''\n"
        "You are executing a command. Follow the implementation section "
        "below and return the result to the user.\n"
        "User arguments: {{args}}\n\n"
        f"{body}'''"
    )
    toml_content = "\n".join(lines) + "\n"

    # Validate generated TOML is parseable
    try:
        tomllib.loads(toml_content)
    except Exception as exc:
        raise ValueError(
            f"Generated invalid TOML for {plugin_name}/{os.path.basename(md_path)}: {exc}"
        )

    return toml_content


def get_plugin_names():
    """Get sorted list of valid plugin directory names."""
    plugins = []
    for name in sorted(os.listdir(PLUGINS_DIR)):
        plugin_dir = os.path.join(PLUGINS_DIR, name)
        plugin_json = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
        if os.path.isdir(plugin_dir) and os.path.isfile(plugin_json):
            plugins.append(name)
    return plugins


def read_existing_version():
    """Read the current version from the existing gemini-extension.json."""
    manifest_path = os.path.join(REPO_ROOT, "gemini-extension.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r") as f:
            data = json.load(f)
        return data.get("version", "0.1.0")
    return "0.1.0"


def bump_patch(version_str):
    """Bump the patch component of a semver string."""
    try:
        parts = [int(x) for x in version_str.split(".")]
    except ValueError:
        parts = [0, 0, 0]
    while len(parts) < 3:
        parts.append(0)
    parts[2] += 1
    return ".".join(str(x) for x in parts)


def bump_minor(version_str):
    """Bump the minor component of a semver string, resetting patch to 0."""
    try:
        parts = [int(x) for x in version_str.split(".")]
    except ValueError:
        parts = [0, 0, 0]
    while len(parts) < 3:
        parts.append(0)
    parts[1] += 1
    parts[2] = 0
    return ".".join(str(x) for x in parts)


def has_new_plugins(changed_plugins):
    """Check if any changed plugins are new (not yet converted)."""
    for plugin_name in changed_plugins:
        if not any(
            os.path.isdir(os.path.join(REPO_ROOT, subdir, plugin_name))
            for subdir in ["commands", "skills", "plugin-scripts"]
        ):
            return True
    return False


def has_removed_plugins(changed_plugins, new_content_dir):
    """Check if any changed plugins are being fully removed.

    A plugin is removed when it exists at the repo root but the new
    conversion produces no commands, skills, or scripts for it.
    Must be called before syncing files to repo root.
    """
    for plugin_name in changed_plugins:
        has_existing = any(
            os.path.isdir(os.path.join(REPO_ROOT, subdir, plugin_name))
            for subdir in ["commands", "skills", "plugin-scripts"]
        )
        if not has_existing:
            continue
        has_new = any(
            os.path.isdir(os.path.join(new_content_dir, subdir, plugin_name))
            for subdir in ["commands", "skills", "plugin-scripts"]
        )
        if not has_new:
            return True
    return False


def compute_new_version(changed_plugins, current_version, new_content_dir=None):
    """Compute the new version based on what changed.

    - New plugin added: bump minor (e.g. 0.1.0 -> 0.2.0)
    - Plugin fully removed: bump minor (e.g. 0.1.0 -> 0.2.0)
    - Existing plugin updated: bump patch (e.g. 0.1.0 -> 0.1.1)
    - No changes: return current version unchanged

    Must be called before syncing files to repo root, so that
    has_new_plugins()/has_removed_plugins() can compare against
    the existing state.
    """
    if not changed_plugins:
        return current_version
    if has_new_plugins(changed_plugins):
        return bump_minor(current_version)
    if new_content_dir and has_removed_plugins(changed_plugins, new_content_dir):
        return bump_minor(current_version)
    return bump_patch(current_version)


def write_manifest(output_dir, version):
    """Write gemini-extension.json with the given version."""
    manifest = {
        "name": "ai-helpers",
        "version": version,
        "description": (
            "A collection of Gemini CLI commands and skills for CI, Jira, "
            "Git, OpenShift, and more."
        ),
        "contextFileName": "GEMINI.md",
    }
    with open(os.path.join(output_dir, "gemini-extension.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def generate_context_file(output_dir, plugin_names):
    """Generate GEMINI.md aggregating plugin descriptions."""
    lines = [
        "# AI Helpers - Gemini CLI Extension",
        "",
        "This extension provides commands and skills for various development tasks.",
        "Commands are organized by topic using directory-based namespacing",
        "(e.g. `/ci:analyze-payload`, `/git:commit-suggest`, `/jira:create`).",
        "",
        "## Available command groups",
        "",
    ]

    for name in plugin_names:
        plugin_json = os.path.join(
            PLUGINS_DIR, name, ".claude-plugin", "plugin.json"
        )
        with open(plugin_json, "r") as f:
            meta = json.load(f)
        desc = meta.get("description", "")
        lines.append(f"- **{name}**: {desc}")

    lines.append("")
    with open(os.path.join(output_dir, "GEMINI.md"), "w") as f:
        f.write("\n".join(lines))


def get_plugin_version(plugin_dir):
    """Read version from a plugin's plugin.json."""
    plugin_json = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
    with open(plugin_json, "r") as f:
        return json.load(f).get("version", "0.0.0")


def convert_commands(plugin_name, plugin_dir, output_dir):
    """Convert plugin commands to TOML files under commands/{plugin_name}/."""
    commands_dir = os.path.join(plugin_dir, "commands")
    if not os.path.isdir(commands_dir):
        return

    plugin_version = get_plugin_version(plugin_dir)
    out_dir = os.path.join(output_dir, "commands", plugin_name)
    os.makedirs(out_dir, exist_ok=True)

    for cmd_file in sorted(os.listdir(commands_dir)):
        if cmd_file.endswith(".md"):
            toml_name = cmd_file[:-3] + ".toml"
            toml_content = convert_command_to_toml(
                os.path.join(commands_dir, cmd_file),
                plugin_name,
                plugin_version,
            )
            with open(os.path.join(out_dir, toml_name), "w") as f:
                f.write(toml_content)


def copy_skills(plugin_name, plugin_dir, output_dir):
    """Copy plugin skills into skills/{plugin}/{skill}/, adapting text."""
    skills_dir = os.path.join(plugin_dir, "skills")
    if not os.path.isdir(skills_dir):
        return

    for skill_name in sorted(os.listdir(skills_dir)):
        skill_src = os.path.join(skills_dir, skill_name)
        if not os.path.isdir(skill_src):
            continue
        # Nest under plugin name to avoid collisions and preserve path structure
        skill_dst = os.path.join(output_dir, "skills", plugin_name, skill_name)
        if os.path.exists(skill_dst):
            shutil.rmtree(skill_dst)
        shutil.copytree(skill_src, skill_dst)
        # Apply text replacements to markdown files in copied skills
        for root, _dirs, files in os.walk(skill_dst):
            for fname in files:
                if fname.endswith(".md"):
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r") as f:
                        content = f.read()
                    adapted = adapt_text(content, plugin_name)
                    if adapted != content:
                        with open(fpath, "w") as f:
                            f.write(adapted)


def copy_scripts(plugin_name, plugin_dir, output_dir):
    """Copy plugin scripts into plugin-scripts/{plugin_name}/.

    Text files have adapt_text() applied to replace Claude-specific references.
    """
    scripts_dir = os.path.join(plugin_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return

    dst_dir = os.path.join(output_dir, "plugin-scripts", plugin_name)
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    shutil.copytree(scripts_dir, dst_dir)

    # Apply adapt_text() to all text files in the copied scripts
    for root, _dirs, files in os.walk(dst_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                adapted = adapt_text(content, plugin_name)
                if adapted != content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(adapted)
            except (UnicodeDecodeError, ValueError):
                # Skip binary files
                pass


def generate_content(output_dir):
    """Generate commands, skills, and GEMINI.md (everything except manifest)."""
    plugin_names = get_plugin_names()

    generate_context_file(output_dir, plugin_names)

    for plugin_name in plugin_names:
        plugin_dir = os.path.join(PLUGINS_DIR, plugin_name)
        convert_commands(plugin_name, plugin_dir, output_dir)
        copy_skills(plugin_name, plugin_dir, output_dir)
        copy_scripts(plugin_name, plugin_dir, output_dir)

    return len(plugin_names)


def get_changed_plugins(new_dir):
    """Return a sorted list of plugin names whose generated output changed."""
    # First generation: no managed files exist yet, nothing changed
    if not any(
        os.path.exists(os.path.join(REPO_ROOT, name)) for name in MANAGED_PATHS
    ):
        return []

    changed = set()
    plugin_names = set(get_plugin_names())

    # Also include plugins that exist at the repo root but are no longer
    # in plugins/ (i.e. fully removed plugins).
    for subdir in ["commands", "skills", "plugin-scripts"]:
        root = os.path.join(REPO_ROOT, subdir)
        if os.path.isdir(root):
            for name in os.listdir(root):
                if os.path.isdir(os.path.join(root, name)):
                    plugin_names.add(name)

    for plugin_name in plugin_names:
        # Check commands/{plugin}/, skills/{plugin}/, scripts/{plugin}/
        for subdir in ["commands", "skills", "plugin-scripts"]:
            new_path = os.path.join(new_dir, subdir, plugin_name)
            existing_path = os.path.join(REPO_ROOT, subdir, plugin_name)

            if os.path.isdir(new_path):
                if not os.path.isdir(existing_path):
                    changed.add(plugin_name)
                else:
                    dcmp = filecmp.dircmp(new_path, existing_path)
                    if _has_diffs(dcmp):
                        changed.add(plugin_name)
            elif os.path.isdir(existing_path):
                changed.add(plugin_name)

    return sorted(changed)


def has_content_changes(new_dir):
    """Compare generated content with existing files at repo root."""
    # First generation: no managed files exist yet, no bump needed
    if not any(
        os.path.exists(os.path.join(REPO_ROOT, name)) for name in MANAGED_PATHS
    ):
        return False

    for name in MANAGED_PATHS:
        if name == "gemini-extension.json":
            continue  # Version is handled separately
        new_path = os.path.join(new_dir, name)
        existing_path = os.path.join(REPO_ROOT, name)

        new_exists = os.path.exists(new_path)
        existing_exists = os.path.exists(existing_path)

        if new_exists != existing_exists:
            return True

        if not new_exists:
            continue

        if os.path.isfile(new_path):
            if not os.path.isfile(existing_path):
                return True
            if open(new_path).read() != open(existing_path).read():
                return True
        elif os.path.isdir(new_path):
            if not os.path.isdir(existing_path):
                return True
            dcmp = filecmp.dircmp(new_path, existing_path)
            if _has_diffs(dcmp):
                return True

    return False


def _has_diffs(dcmp):
    """Recursively check if a dircmp has any differences."""
    if dcmp.left_only or dcmp.right_only or dcmp.diff_files:
        return True
    for sub_dcmp in dcmp.subdirs.values():
        if _has_diffs(sub_dcmp):
            return True
    return False


def sync_to_root(temp_dir):
    """Sync generated files from temp dir to repo root.

    Uses a two-phase approach: first copy new files to .tmp destinations,
    then swap them into place. This avoids data loss if the script is
    interrupted between deleting old files and copying new ones.
    """
    # Phase 1: copy new content to .tmp destinations
    staged = []
    for name in MANAGED_PATHS:
        src = os.path.join(temp_dir, name)
        if not os.path.exists(src):
            continue
        tmp_dst = os.path.join(REPO_ROOT, name + ".tmp")
        if os.path.isdir(tmp_dst):
            shutil.rmtree(tmp_dst)
        elif os.path.isfile(tmp_dst):
            os.remove(tmp_dst)
        if os.path.isdir(src):
            shutil.copytree(src, tmp_dst)
        else:
            shutil.copy2(src, tmp_dst)
        staged.append(name)

    # Phase 2: swap .tmp into place
    for name in staged:
        dst = os.path.join(REPO_ROOT, name)
        tmp_dst = os.path.join(REPO_ROOT, name + ".tmp")
        backup = os.path.join(REPO_ROOT, name + ".bak")
        # Move old out of the way
        if os.path.exists(dst):
            os.rename(dst, backup)
        # Move new into place
        os.rename(tmp_dst, dst)
        # Remove old backup
        if os.path.exists(backup):
            if os.path.isdir(backup):
                shutil.rmtree(backup)
            else:
                os.remove(backup)


def report_content_diffs(temp_dir):
    """Report differences between generated content and repo root."""
    diffs = False
    for name in MANAGED_PATHS:
        if name == "gemini-extension.json":
            continue
        new_path = os.path.join(temp_dir, name)
        existing_path = os.path.join(REPO_ROOT, name)

        if not os.path.exists(existing_path) and os.path.exists(new_path):
            print(f"  Missing: {name}", file=sys.stderr)
            diffs = True
        elif os.path.exists(existing_path) and not os.path.exists(new_path):
            print(f"  Extra: {name}", file=sys.stderr)
            diffs = True
        elif os.path.isfile(new_path) and os.path.isfile(existing_path):
            if open(new_path).read() != open(existing_path).read():
                print(f"  Changed: {name}", file=sys.stderr)
                diffs = True
        elif os.path.isdir(new_path) and os.path.isdir(existing_path):
            dcmp = filecmp.dircmp(new_path, existing_path)
            if _report_diffs(dcmp, name):
                diffs = True

    # Check manifest separately
    manifest_new = os.path.join(temp_dir, "gemini-extension.json")
    manifest_existing = os.path.join(REPO_ROOT, "gemini-extension.json")
    if not os.path.isfile(manifest_existing):
        print("  Missing: gemini-extension.json", file=sys.stderr)
        diffs = True
    elif open(manifest_new).read() != open(manifest_existing).read():
        print("  Changed: gemini-extension.json", file=sys.stderr)
        diffs = True

    return diffs


def _report_diffs(dcmp, path_prefix):
    """Recursively report differences."""
    diffs = False
    if dcmp.left_only:
        for name in dcmp.left_only:
            print(f"  Missing: {path_prefix}/{name}", file=sys.stderr)
        diffs = True
    if dcmp.right_only:
        for name in dcmp.right_only:
            print(f"  Extra: {path_prefix}/{name}", file=sys.stderr)
        diffs = True
    if dcmp.diff_files:
        for name in dcmp.diff_files:
            print(f"  Changed: {path_prefix}/{name}", file=sys.stderr)
        diffs = True
    for sub_name, sub_dcmp in dcmp.subdirs.items():
        if _report_diffs(sub_dcmp, f"{path_prefix}/{sub_name}"):
            diffs = True
    return diffs


def parse_args():
    """Parse command-line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Claude Code plugins to Gemini CLI extensions."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if generated files are in sync (exit 1 if not).",
    )
    parser.add_argument(
        "--plugin",
        type=str,
        help="Convert one or more plugins by name, comma-separated (e.g. --plugin ci,git).",
    )
    return parser.parse_args()


def convert_selected_plugins(plugin_names):
    """Convert one or more plugins and write output to the repo root."""
    # Validate all plugins first
    for plugin_name in plugin_names:
        plugin_dir = os.path.join(PLUGINS_DIR, plugin_name)
        if not os.path.isdir(plugin_dir):
            print(f"Error: plugin not found: {plugin_name}", file=sys.stderr)
            sys.exit(1)
        plugin_json = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
        if not os.path.isfile(plugin_json):
            print(f"Error: not a valid plugin (missing plugin.json): {plugin_name}", file=sys.stderr)
            sys.exit(1)

    # Convert all plugins to a temp dir and detect changes
    temp_dir = tempfile.mkdtemp(prefix="gemini-selected-")
    changed_plugins = []
    try:
        for plugin_name in plugin_names:
            plugin_dir = os.path.join(PLUGINS_DIR, plugin_name)
            convert_commands(plugin_name, plugin_dir, temp_dir)
            copy_skills(plugin_name, plugin_dir, temp_dir)
            copy_scripts(plugin_name, plugin_dir, temp_dir)

            # Check if commands, skills, or scripts changed
            has_changes = False
            for subdir in ["commands", "skills", "plugin-scripts"]:
                new_path = os.path.join(temp_dir, subdir, plugin_name)
                existing_path = os.path.join(REPO_ROOT, subdir, plugin_name)
                if os.path.isdir(new_path):
                    if not os.path.isdir(existing_path):
                        has_changes = True
                    else:
                        dcmp = filecmp.dircmp(new_path, existing_path)
                        if _has_diffs(dcmp):
                            has_changes = True
                elif os.path.isdir(existing_path):
                    has_changes = True

            if has_changes:
                changed_plugins.append(plugin_name)
            else:
                print(f"Plugin '{plugin_name}': no changes detected, skipping.")

        if not changed_plugins:
            return

        # Compute version before copying files to repo root, so that
        # has_new_plugins() can compare against the existing state.
        current_version = read_existing_version()
        manifest_path = os.path.join(REPO_ROOT, "gemini-extension.json")
        is_first_gen = not os.path.isfile(manifest_path)
        if not is_first_gen:
            new_version = compute_new_version(changed_plugins, current_version, temp_dir)

        # Copy changed files to repo root (and remove stale content)
        for plugin_name in changed_plugins:
            for subdir in ["commands", "skills", "plugin-scripts"]:
                new_path = os.path.join(temp_dir, subdir, plugin_name)
                dst_path = os.path.join(REPO_ROOT, subdir, plugin_name)
                if os.path.isdir(dst_path):
                    shutil.rmtree(dst_path)
                if os.path.isdir(new_path):
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copytree(new_path, dst_path)
    finally:
        shutil.rmtree(temp_dir)

    # Update GEMINI.md with all converted plugins
    converted_plugins = set()
    for subdir in ["commands", "skills", "plugin-scripts"]:
        root = os.path.join(REPO_ROOT, subdir)
        if os.path.isdir(root):
            converted_plugins.update(
                d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))
            )
    generate_context_file(REPO_ROOT, sorted(converted_plugins))

    # Write manifest version (computed before copying files)
    if is_first_gen:
        write_manifest(REPO_ROOT, current_version)
        print(f"Created gemini-extension.json (v{current_version})")
    else:
        write_manifest(REPO_ROOT, new_version)
        print(f"Bumped version v{current_version} -> v{new_version}")

    # Report
    for plugin_name in changed_plugins:
        cmd_count = 0
        cmds_dir = os.path.join(REPO_ROOT, "commands", plugin_name)
        if os.path.isdir(cmds_dir):
            toml_files = sorted(os.listdir(cmds_dir))
            cmd_count = len(toml_files)
            print(f"Commands ({cmd_count}):")
            for f in toml_files:
                print(f"  commands/{plugin_name}/{f}")

        skill_count = 0
        skills_dir = os.path.join(REPO_ROOT, "skills", plugin_name)
        if os.path.isdir(skills_dir):
            skill_dirs = sorted(os.listdir(skills_dir))
            skill_count = len(skill_dirs)
            if skill_dirs:
                print(f"Skills ({skill_count}):")
                for d in skill_dirs:
                    print(f"  skills/{plugin_name}/{d}/")

        script_count = 0
        scripts_dir = os.path.join(REPO_ROOT, "plugin-scripts", plugin_name)
        if os.path.isdir(scripts_dir):
            script_files = sorted(os.listdir(scripts_dir))
            script_count = len(script_files)
            if script_files:
                print(f"Scripts ({script_count}):")
                for f in script_files:
                    print(f"  plugin-scripts/{plugin_name}/{f}")

        print(f"\nConverted plugin '{plugin_name}': {cmd_count} commands, {skill_count} skills, {script_count} scripts.")


def main():
    args = parse_args()

    if not os.path.isdir(PLUGINS_DIR):
        print(f"Error: plugins directory not found: {PLUGINS_DIR}", file=sys.stderr)
        sys.exit(1)

    if args.plugin:
        plugin_names = [p.strip() for p in args.plugin.split(",") if p.strip()]
        convert_selected_plugins(plugin_names)
        return

    if args.check:
        temp_dir = tempfile.mkdtemp(prefix="gemini-check-")
        try:
            converted = generate_content(temp_dir)
            existing_version = read_existing_version()
            write_manifest(temp_dir, existing_version)

            changed_plugins = get_changed_plugins(temp_dir)
            if changed_plugins:
                print(
                    "\nFAIL: Gemini extension files are out of sync with "
                    "plugins/. Run 'make convert-to-gemini' to regenerate "
                    "(version will be bumped automatically).",
                    file=sys.stderr,
                )
                print("Changed plugins:", file=sys.stderr)
                for p in changed_plugins:
                    print(f"  - {p}", file=sys.stderr)
                sys.exit(1)

            diffs_found = report_content_diffs(temp_dir)
            if diffs_found:
                print(
                    "\nFAIL: Gemini extension files are out of sync with "
                    "plugins/. Run 'make convert-to-gemini' to regenerate.",
                    file=sys.stderr,
                )
                sys.exit(1)
            else:
                print(
                    f"OK: Gemini extension is in sync "
                    f"(v{existing_version}, {converted} plugins verified)."
                )
        finally:
            shutil.rmtree(temp_dir)
    else:
        temp_dir = tempfile.mkdtemp(prefix="gemini-gen-")
        try:
            converted = generate_content(temp_dir)

            current_version = read_existing_version()
            changed_plugins = get_changed_plugins(temp_dir)
            if changed_plugins:
                new_version = compute_new_version(changed_plugins, current_version, temp_dir)
            elif has_content_changes(temp_dir):
                new_version = bump_patch(current_version)
            else:
                new_version = current_version

            write_manifest(temp_dir, new_version)
            sync_to_root(temp_dir)

            if new_version != current_version:
                print(
                    f"Converted {converted} plugins "
                    f"(v{current_version} -> v{new_version})"
                )
                print(f"Changed plugins:")
                for p in changed_plugins:
                    print(f"  - {p}")
            else:
                print(
                    f"Converted {converted} plugins "
                    f"(v{new_version}, no changes)"
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
