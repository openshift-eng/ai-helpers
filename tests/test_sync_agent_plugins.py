import importlib.util
import json
from pathlib import Path


_SYNC_SCRIPT = Path(__file__).parent.parent / "scripts" / "sync_agent_plugins.py"
_SYNC_SPEC = importlib.util.spec_from_file_location("sync_agent_plugins", _SYNC_SCRIPT)
_SYNC_MODULE = importlib.util.module_from_spec(_SYNC_SPEC)
assert _SYNC_SPEC.loader is not None
_SYNC_SPEC.loader.exec_module(_SYNC_MODULE)
sync_agent_plugins = _SYNC_MODULE.sync_agent_plugins


PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _make_plugin(temp_dir, name="test-plugin", portable=True, claude=True):
    plugin_dir = temp_dir / "plugins" / name
    plugin_dir.mkdir(parents=True)
    if claude:
        claude_dir = plugin_dir / ".claude-plugin"
        claude_dir.mkdir()
        (claude_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "version": "0.0.1",
                    "description": "test",
                    "author": {"name": "test"},
                }
            )
        )
    if portable:
        (plugin_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "$schema": PLUGIN_SCHEMA,
                    "name": name,
                    "version": "0.0.1",
                    "description": "test",
                    "author": {"name": "test"},
                }
            )
        )
    return plugin_dir


def _add_marketplace(temp_dir, *names):
    marketplace_dir = temp_dir / ".claude-plugin"
    marketplace_dir.mkdir(exist_ok=True)
    marketplace_dir.joinpath("marketplace.json").write_text(
        json.dumps(
            {
                "plugins": [
                    {"name": name, "source": f"./plugins/{name}"} for name in names
                ]
            }
        )
    )


def test_sync_agent_plugins_preserves_portable_extensions(temp_dir):
    plugin_dir = _make_plugin(temp_dir)
    _add_marketplace(temp_dir, "test-plugin")
    portable = json.loads((plugin_dir / "plugin.json").read_text())
    portable["extensions"] = {"com.example": {"enabled": True}}
    (plugin_dir / "plugin.json").write_text(json.dumps(portable))

    assert sync_agent_plugins(temp_dir, check=False) == 0
    synced = json.loads((plugin_dir / "plugin.json").read_text())
    assert synced["extensions"] == {"com.example": {"enabled": True}}


def test_sync_agent_plugins_creates_manifest_and_translates_mcp(temp_dir):
    plugin_dir = _make_plugin(temp_dir, portable=False)
    _add_marketplace(temp_dir, "test-plugin")
    (plugin_dir / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local": {"command": "example", "args": ["--stdio"]},
                    "remote": {"type": "http", "url": "https://example.test/mcp"},
                }
            }
        )
    )

    assert sync_agent_plugins(temp_dir, check=False) == 0
    assert (plugin_dir / "plugin.json").is_file()
    portable_mcp = json.loads((plugin_dir / "mcp.json").read_text())
    assert portable_mcp["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    )
    assert portable_mcp["mcpServers"]["local"]["type"] == "stdio"
    assert portable_mcp["mcpServers"]["remote"]["type"] == "streamable-http"
