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
    """Check that PLUGINS.md and docs/data.json are up-to-date by running 'make update'"""

    @property
    def rule_id(self) -> str:
        return "plugins-doc-up-to-date"

    @property
    def description(self) -> str:
        return "PLUGINS.md and docs/data.json must be up-to-date with plugin metadata. Run 'make update' to regenerate."

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        # Only check marketplace repos
        if not context.has_marketplace():
            return violations

        plugins_md_path = context.root_path / "PLUGINS.md"
        data_json_path = context.root_path / "docs" / "data.json"

        if not plugins_md_path.exists():
            return violations

        # Check if generate_plugin_docs.py script exists
        script_path = context.root_path / "scripts" / "generate_plugin_docs.py"
        if not script_path.exists():
            return violations

        try:
            # Read current content of files to check
            original_plugins_md = plugins_md_path.read_text()
            original_data_json = data_json_path.read_text() if data_json_path.exists() else None

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

            # Also run build-website.py if it exists
            website_script_path = context.root_path / "scripts" / "build-website.py"
            if website_script_path.exists():
                result = subprocess.run(
                    ["python3", str(website_script_path)],
                    cwd=str(context.root_path),
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    violations.append(
                        self.violation(
                            f"build-website.py failed: {result.stderr}",
                            file_path=data_json_path if data_json_path.exists() else plugins_md_path
                        )
                    )
                    return violations

            # Check if PLUGINS.md changed
            generated_plugins_md = plugins_md_path.read_text()
            if original_plugins_md != generated_plugins_md:
                # Restore original content
                plugins_md_path.write_text(original_plugins_md)

                violations.append(
                    self.violation(
                        "PLUGINS.md is out of sync with plugin metadata. Run 'make update' to update.",
                        file_path=plugins_md_path
                    )
                )

            # Check if docs/data.json changed
            if data_json_path.exists():
                generated_data_json = data_json_path.read_text()
                if original_data_json != generated_data_json:
                    # Restore original content
                    if original_data_json is not None:
                        data_json_path.write_text(original_data_json)

                    violations.append(
                        self.violation(
                            "docs/data.json is out of sync with plugin metadata. Run 'make update' to update.",
                            file_path=data_json_path
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
                    f"Error checking files up-to-date status: {e}",
                    file_path=plugins_md_path
                )
            )

        return violations
