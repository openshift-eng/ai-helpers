"""Prohibit command directories in plugins unless explicitly allowlisted."""

from typing import List

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity
from skillsaw.lint_target import PluginNode


class PluginCommandsProhibitedRule(Rule):
    """Plugins must not provide commands unless explicitly allowlisted."""

    default_enabled = False

    config_schema = {
        "allowlist": {
            "type": "list",
            "default": [],
            "description": "Plugin names permitted to contain a commands directory",
        },
    }

    @property
    def rule_id(self) -> str:
        return "plugin-commands-prohibited"

    @property
    def description(self) -> str:
        return "Plugins must not provide commands unless explicitly allowlisted."

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        allowlist = set(self.config.get("allowlist", []))

        for node in context.lint_tree.find(PluginNode):
            commands_path = node.path / "commands"
            if not commands_path.is_dir() or node.path.name in allowlist:
                continue

            violations.append(
                self.violation(
                    f"Plugin '{node.path.name}' has a non-allowlisted commands directory",
                    file_path=commands_path,
                )
            )

        return violations
