"""Require Claude and portable Agent Plugins metadata for first-party plugins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity
from skillsaw.lint_target import PluginNode


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


class AgentPluginManifestsRequiredRule(Rule):
    """Every first-party marketplace plugin has both supported manifests."""

    @property
    def rule_id(self) -> str:
        return "agent-plugin-manifests-required"

    @property
    def description(self) -> str:
        return (
            "Every first-party plugin must have Claude and Agent Plugins manifests, "
            "with portable metadata synchronized"
        )

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        for plugin_dir in self._plugin_dirs(context):
            violations.extend(self._check_plugin(plugin_dir))
        return violations

    def _plugin_dirs(self, context: RepositoryContext) -> Iterable[Path]:
        """Use marketplace registration so missing Claude manifests are visible."""
        marketplace_path = context.root_path / ".claude-plugin" / "marketplace.json"
        if marketplace_path.is_file():
            try:
                marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                marketplace = None
            if isinstance(marketplace, dict):
                paths = []
                for entry in marketplace.get("plugins", []):
                    if not isinstance(entry, dict):
                        continue
                    source = entry.get("source")
                    if not isinstance(source, str) or not source.startswith("./plugins/"):
                        continue
                    path = (context.root_path / source[2:]).resolve()
                    if path.parent == (context.root_path / "plugins").resolve():
                        paths.append(path)
                if paths:
                    return sorted(set(paths))

        return sorted(node.path for node in context.lint_tree.find(PluginNode))

    def _check_plugin(self, plugin_dir: Path) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        claude_path = plugin_dir / ".claude-plugin" / "plugin.json"
        portable_path = plugin_dir / "plugin.json"

        if not claude_path.is_file():
            violations.append(
                self.violation(
                    f"Plugin '{plugin_dir.name}' is missing its Claude manifest "
                    "at .claude-plugin/plugin.json",
                    file_path=claude_path,
                )
            )

        if not portable_path.is_file():
            violations.append(
                self.violation(
                    f"Plugin '{plugin_dir.name}' is missing its Agent Plugins "
                    "manifest at plugin.json",
                    file_path=portable_path,
                )
            )

        claude = self._load_object(claude_path)
        portable = self._load_object(portable_path)
        if claude_path.is_file() and claude is None:
            violations.append(
                self.violation(
                    "Claude plugin.json must contain a JSON object",
                    file_path=claude_path,
                )
            )
        if portable_path.is_file() and portable is None:
            violations.append(
                self.violation(
                    "Agent Plugins plugin.json must contain a JSON object",
                    file_path=portable_path,
                )
            )
        if claude is not None and portable is not None:
            violations.extend(self._check_manifest_pair(plugin_dir, claude, portable))

        if (plugin_dir / ".mcp.json").is_file() and not (plugin_dir / "mcp.json").is_file():
            violations.append(
                self.violation(
                    f"Plugin '{plugin_dir.name}' has .mcp.json but no portable mcp.json",
                    file_path=plugin_dir / "mcp.json",
                )
            )
        # skillsaw 0.18.0's native agent-plugin-mcp-valid rule owns schema
        # and server-entry validation; this rule enforces the paired file.

        return violations

    def _load_object(self, path: Path) -> Any:
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _check_manifest_pair(
        self, plugin_dir: Path, claude: dict[str, Any], portable: dict[str, Any]
    ) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        portable_path = plugin_dir / "plugin.json"

        for field in PORTABLE_METADATA_FIELDS:
            if field in claude and portable.get(field) != self._portable_value(field, claude[field]):
                violations.append(
                    self.violation(
                        f"Plugin '{plugin_dir.name}' has unsynchronized '{field}' metadata",
                        file_path=portable_path,
                    )
                )

        return violations

    @staticmethod
    def _portable_value(field: str, value: Any) -> Any:
        if field == "author" and isinstance(value, str):
            return {"name": value}
        if field == "author" and isinstance(value, dict):
            return {key: value[key] for key in ("name", "email", "url") if key in value}
        return value
