"""
Custom skillsaw rules for ai-helpers marketplace
"""

import subprocess
from pathlib import Path
from typing import List

try:
    from src.rule import Rule, RuleViolation, Severity
    from src.context import RepositoryContext
except ImportError:
    from skillsaw import Rule, RuleViolation, Severity, RepositoryContext


class PluginsDocUpToDateRule(Rule):
    """Check that docs/ is up-to-date by running 'skillsaw docs'"""

    @property
    def rule_id(self) -> str:
        return "plugins-doc-up-to-date"

    @property
    def description(self) -> str:
        return "docs/ must be up-to-date with plugin metadata. Run 'make update' to regenerate."

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        if not context.has_marketplace():
            return violations

        docs_path = context.root_path / "docs"
        index_path = docs_path / "index.html"

        if not index_path.exists():
            violations.append(
                self.violation(
                    "docs/index.html is missing. Run 'make update' to generate.",
                    file_path=docs_path,
                )
            )
            return violations

        original_content = index_path.read_text()
        try:
            result = subprocess.run(
                ["skillsaw", "docs", "-o", "docs/"],
                cwd=str(context.root_path),
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                violations.append(
                    self.violation(
                        f"'make update' failed: {result.stderr}",
                        file_path=index_path
                    )
                )
                return violations

            generated_content = index_path.read_text()
            if original_content != generated_content:
                violations.append(
                    self.violation(
                        "docs/ is out of sync with plugin metadata. Run 'make update' to update.",
                        file_path=index_path
                    )
                )

        except subprocess.TimeoutExpired:
            violations.append(
                self.violation(
                    "'make update' timed out",
                    file_path=index_path
                )
            )
        except Exception as e:
            violations.append(
                self.violation(
                    f"Error checking docs up-to-date status: {e}",
                    file_path=index_path
                )
            )
        finally:
            if index_path.exists() and index_path.read_text() != original_content:
                index_path.write_text(original_content)

        return violations
