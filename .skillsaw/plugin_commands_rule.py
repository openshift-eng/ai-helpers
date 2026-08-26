"""Prohibit plugin commands unless each command is explicitly allowlisted."""

from typing import List

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity
from skillsaw.blocks import CommandBlock
from skillsaw.lint_target import PluginNode


class PluginCommandsProhibitedRule(Rule):
    """Plugins must not provide non-allowlisted commands."""

    default_enabled = False

    config_schema = {
        "allowlist": {
            "type": "list",
            "default": [],
            "description": "Qualified command names to permit (plugin:command)",
        },
    }

    @property
    def rule_id(self) -> str:
        return "plugin-commands-prohibited"

    @property
    def description(self) -> str:
        return "Plugins must not provide commands unless each command is allowlisted."

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        allowlist = set(self.config.get("allowlist", []))

        for block in context.lint_tree.find(CommandBlock):
            plugin = context.lint_tree.find_parent(block, PluginNode)
            if plugin is None:
                continue

            command_name = f"{plugin.path.name}:{block.path.stem}"
            if command_name in allowlist:
                continue

            violations.append(
                self.violation(
                    f"Command '{command_name}' is not allowlisted; new plugin commands "
                    "are prohibited",
                    block=block,
                )
            )

        return violations
