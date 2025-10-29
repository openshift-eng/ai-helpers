"""
Custom claudelint rules for ai-helpers marketplace
"""

import subprocess
from pathlib import Path
from typing import List

try:
    from src.rule import Rule, RuleViolation, Severity
    from src.context import RepositoryContext
except ImportError:
    # Fallback for when running as a custom rule
    from claudelint import Rule, RuleViolation, Severity, RepositoryContext


class PluginsDocUpToDateRule(Rule):
    """Check that PLUGINS.md is up-to-date by running 'make update'"""

    @property
    def rule_id(self) -> str:
        return "plugins-doc-up-to-date"

    @property
    def description(self) -> str:
        return "PLUGINS.md must be up-to-date with plugin metadata. Run 'make update' to regenerate."

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        # Only check marketplace repos
        if not context.has_marketplace():
            return violations

        plugins_md_path = context.root_path / "PLUGINS.md"
        if not plugins_md_path.exists():
            return violations

        # Check if generate_plugin_docs.py script exists
        script_path = context.root_path / "scripts" / "generate_plugin_docs.py"
        if not script_path.exists():
            return violations

        try:
            # Read current PLUGINS.md content
            original_content = plugins_md_path.read_text()

            # Run the docs generation script
            result = subprocess.run(
                ["python3", str(script_path)],
                cwd=str(context.root_path),
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                violations.append(
                    self.violation(
                        f"'make update' failed: {result.stderr}",
                        file_path=plugins_md_path
                    )
                )
                return violations

            # Read the generated PLUGINS.md content
            generated_content = plugins_md_path.read_text()

            # Compare
            if original_content != generated_content:
                # Restore original content
                plugins_md_path.write_text(original_content)

                violations.append(
                    self.violation(
                        "PLUGINS.md is out of sync with plugin metadata. Run 'make update' to update.",
                        file_path=plugins_md_path
                    )
                )

        except subprocess.TimeoutExpired:
            violations.append(
                self.violation(
                    "'make update' timed out",
                    file_path=plugins_md_path
                )
            )
        except Exception as e:
            violations.append(
                self.violation(
                    f"Error checking PLUGINS.md up-to-date status: {e}",
                    file_path=plugins_md_path
                )
            )

        return violations
