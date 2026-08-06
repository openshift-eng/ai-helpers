#!/usr/bin/env python3
"""Synchronize Claude and Agent Plugins manifests.

The repository keeps Claude Code metadata in ``.claude-plugin/plugin.json``
and portable Agent Plugins metadata in ``plugin.json``.  The latter is a
deliberately smaller manifest: Agent Plugins v1 does not define Claude
commands, hooks, agents, or plugin dependencies.

This command only creates missing files and reports conflicting files.  That
makes it safe to run as part of plugin development without silently replacing
client-specific metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

PORTABLE_METADATA_FIELDS = (
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
)
STDIO_FIELDS = ("command", "args", "env", "cwd")
REMOTE_FIELDS = ("url", "headers")


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from *path*."""
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write a formatted JSON object with a trailing newline."""
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def marketplace_plugin_dirs(repo_root: Path) -> list[Path]:
    """Return first-party plugin directories registered in the marketplace."""
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace = load_json(marketplace_path)
    plugins_dir = (repo_root / "plugins").resolve()
    result: list[Path] = []

    for entry in marketplace.get("plugins", []):
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        if not isinstance(source, str) or not source.startswith("./plugins/"):
            continue
        plugin_dir = (repo_root / source[2:]).resolve()
        if plugin_dir.parent != plugins_dir:
            raise ValueError(f"Marketplace source escapes plugins directory: {source}")
        result.append(plugin_dir)

    return sorted(set(result))


def normalize_author(value: Any) -> Any:
    """Normalize Claude's string author shorthand to Agent Plugins metadata."""
    if isinstance(value, str):
        return {"name": value}
    if isinstance(value, dict):
        return {key: value[key] for key in ("name", "email", "url") if key in value}
    return value


def portable_manifest_from_claude(claude: dict[str, Any]) -> dict[str, Any]:
    """Build an Agent Plugins manifest from Claude manifest metadata."""
    if not isinstance(claude.get("name"), str) or not claude["name"]:
        raise ValueError("Claude manifest must define a non-empty name")

    portable: dict[str, Any] = {"$schema": PLUGIN_SCHEMA}
    for field in PORTABLE_METADATA_FIELDS:
        if field not in claude:
            continue
        value = normalize_author(claude[field]) if field == "author" else claude[field]
        portable[field] = value
    return portable


def claude_manifest_from_portable(portable: dict[str, Any]) -> dict[str, Any]:
    """Build Claude-compatible metadata from an Agent Plugins manifest."""
    if not isinstance(portable.get("name"), str) or not portable["name"]:
        raise ValueError("Agent Plugins manifest must define a non-empty name")

    claude: dict[str, Any] = {}
    for field in PORTABLE_METADATA_FIELDS:
        if field in portable:
            claude[field] = portable[field]
    return claude


def portable_mcp_from_claude(claude_mcp: dict[str, Any]) -> dict[str, Any]:
    """Translate Claude MCP server entries to the Agent Plugins v1 schema."""
    servers = claude_mcp.get("mcpServers")
    if not isinstance(servers, dict):
        raise ValueError("Claude MCP configuration must define an mcpServers object")

    portable_servers: dict[str, Any] = {}
    for name, server in servers.items():
        if not isinstance(server, dict):
            raise ValueError(f"MCP server {name!r} must be a JSON object")

        source_type = server.get("type")
        if source_type in (None, "stdio"):
            server_type = "stdio"
            fields = STDIO_FIELDS
        elif source_type == "http":
            server_type = "streamable-http"
            fields = REMOTE_FIELDS
        elif source_type == "sse":
            server_type = "sse"
            fields = REMOTE_FIELDS
        else:
            raise ValueError(f"Unsupported Claude MCP transport {source_type!r} for {name!r}")

        translated: dict[str, Any] = {"type": server_type}
        for field in fields:
            if field in server:
                translated[field] = server[field]
        portable_servers[name] = translated

    return {"$schema": MCP_SCHEMA, "mcpServers": portable_servers}


def sync_plugin_manifest(plugin_dir: Path, check: bool) -> list[str]:
    """Create or validate the two plugin manifests for one plugin."""
    errors: list[str] = []
    claude_path = plugin_dir / ".claude-plugin" / "plugin.json"
    portable_path = plugin_dir / "plugin.json"

    claude_exists = claude_path.is_file()
    portable_exists = portable_path.is_file()

    try:
        claude = load_json(claude_path) if claude_exists else None
        portable = load_json(portable_path) if portable_exists else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"{plugin_dir.name}: {exc}")
        return errors

    if claude is None and portable is None:
        errors.append(f"{plugin_dir.name}: missing both plugin manifests")
        return errors

    if claude is None:
        assert portable is not None
        if check:
            errors.append(f"{plugin_dir.name}: missing {claude_path}")
        else:
            claude_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(claude_path, claude_manifest_from_portable(portable))
            print(f"created {claude_path}")
        return errors

    if portable is None:
        if check:
            errors.append(f"{plugin_dir.name}: missing {portable_path}")
        else:
            write_json(portable_path, portable_manifest_from_claude(claude))
            print(f"created {portable_path}")
        portable = portable_manifest_from_claude(claude)

    assert portable is not None
    expected = portable_manifest_from_claude(claude)
    if portable != expected:
        errors.append(
            f"{plugin_dir.name}: {portable_path} differs from the Claude manifest; "
            "run the sync after resolving the conflicting metadata"
        )

    return errors


def sync_mcp_config(plugin_dir: Path, check: bool) -> list[str]:
    """Create or validate a portable MCP configuration when Claude has one."""
    claude_path = plugin_dir / ".mcp.json"
    portable_path = plugin_dir / "mcp.json"
    if not claude_path.is_file():
        return []

    errors: list[str] = []
    try:
        expected = portable_mcp_from_claude(load_json(claude_path))
        existing = load_json(portable_path) if portable_path.is_file() else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"{plugin_dir.name}: {exc}"]

    if existing is None:
        if check:
            errors.append(f"{plugin_dir.name}: missing {portable_path}")
        else:
            write_json(portable_path, expected)
            print(f"created {portable_path}")
    elif existing != expected:
        errors.append(
            f"{plugin_dir.name}: {portable_path} differs from {claude_path}; "
            "resolve the transport or server differences explicitly"
        )
    return errors


def sync_agent_plugins(repo_root: Path, check: bool) -> int:
    """Synchronize all first-party marketplace plugins."""
    try:
        plugin_dirs = marketplace_plugin_dirs(repo_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for plugin_dir in plugin_dirs:
        errors.extend(sync_plugin_manifest(plugin_dir, check))
        errors.extend(sync_mcp_config(plugin_dir, check))

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    action = "validated" if check else "synchronized"
    print(f"Agent Plugins: {action} {len(plugin_dirs)} first-party plugins")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate manifests without creating missing files",
    )
    args = parser.parse_args()
    return sync_agent_plugins(Path(__file__).resolve().parent.parent, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
