"""
Require an OWNERS file in each plugin directory.
"""

from typing import List

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity
from skillsaw.lint_target import PluginNode


class PluginOwnersRequiredRule(Rule):
    """Every plugin must have a non-empty OWNERS file."""

    config_schema = {
        "legacy-exceptions": {
            "type": "list",
            "default": [],
            "description": "Plugin names to exclude from the OWNERS file requirement",
        },
    }

    @property
    def rule_id(self) -> str:
        return "plugin-owners-required"

    @property
    def description(self) -> str:
        return "Every plugin must have a non-empty OWNERS file in its root directory."

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        excluded = set(self.config.get("legacy-exceptions", []))

        for node in context.lint_tree.find(PluginNode):
            plugin_name = node.path.name
            owners_path = node.path / "OWNERS"
            has_owners = owners_path.exists() and owners_path.stat().st_size > 0

            if plugin_name in excluded:
                if has_owners:
                    violations.append(
                        self.violation(
                            f"Plugin '{plugin_name}' has an OWNERS file but is still in the exclude list — remove it from the exclusion",
                            file_path=owners_path,
                        )
                    )
                continue

            if not owners_path.exists():
                violations.append(
                    self.violation(
                        f"Plugin '{plugin_name}' is missing an OWNERS file",
                        file_path=node.path / ".claude-plugin" / "plugin.json",
                    )
                )
            elif not has_owners:
                violations.append(
                    self.violation(
                        f"Plugin '{plugin_name}' has an empty OWNERS file",
                        file_path=owners_path,
                    )
                )

        return violations
