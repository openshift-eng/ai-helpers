"""
Validate agent color frontmatter for opencode compatibility.

opencode >= 1.16 requires color values to be either a hex code (#RRGGBB)
or a preset name (primary, secondary, accent, success, warning, error, info).
CSS color names like "cyan" or "yellow" crash opencode on startup.
"""

import re
from pathlib import Path
from typing import List

import yaml

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity
from skillsaw.lint_target import PluginNode

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_PRESET_NAMES = frozenset(
    {"primary", "secondary", "accent", "success", "warning", "error", "info"}
)


class OpencodeAgentColorRule(Rule):
    """Agent color frontmatter must be a hex code or opencode preset name."""

    @property
    def rule_id(self) -> str:
        return "opencode-agent-color"

    @property
    def description(self) -> str:
        return (
            "Agent color must be a #RRGGBB hex code or an opencode preset "
            "(primary, secondary, accent, success, warning, error, info)."
        )

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        for node in context.lint_tree.find(PluginNode):
            agents_dir = node.path / "agents"
            if not agents_dir.is_dir():
                continue

            for agent_file in sorted(agents_dir.glob("*.md")):
                violation = self._check_agent_file(agent_file)
                if violation:
                    violations.append(violation)

        return violations

    def _check_agent_file(self, path: Path):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None

        if not text.startswith("---"):
            return None

        end = text.find("---", 3)
        if end == -1:
            return None

        frontmatter_text = text[3:end]
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError:
            return None

        if not isinstance(frontmatter, dict):
            return None

        color = frontmatter.get("color")
        if color is None:
            return None

        color_str = str(color)
        if _HEX_COLOR_RE.match(color_str) or color_str in _PRESET_NAMES:
            return None

        color_line = None
        for i, line in enumerate(text.splitlines(), 1):
            if line.startswith("color:"):
                color_line = i
                break

        return self.violation(
            f"Agent '{path.name}' has invalid color '{color_str}'. "
            f"Use a #RRGGBB hex code or a preset "
            f"(primary, secondary, accent, success, warning, error, info).",
            file_path=path,
            line=color_line,
        )
