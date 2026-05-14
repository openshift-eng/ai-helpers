"""
Custom skillsaw rules for ai-helpers marketplace
"""

import subprocess
from pathlib import Path
from typing import Any, List

try:
    from src.rule import Rule, AutofixConfidence, AutofixResult, RuleViolation, Severity
    from src.context import RepositoryContext
except ImportError:
    from skillsaw import Rule, AutofixConfidence, AutofixResult, RuleViolation, Severity, RepositoryContext


class PluginsDocUpToDateRule(Rule):
    """Check that PLUGINS.md and docs/data.json are up-to-date by running 'make update'"""

    autofix_confidence = AutofixConfidence.SAFE

    @property
    def rule_id(self) -> str:
        return "plugins-doc-up-to-date"

    @property
    def description(self) -> str:
        return "PLUGINS.md and docs/data.json must be up-to-date with plugin metadata. Run 'make update' to regenerate."

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def _run_generators(self, context: RepositoryContext):
        """Run doc generation scripts. Returns (original_plugins_md, generated_plugins_md,
        original_data_json, generated_data_json) or raises on failure."""
        plugins_md_path = context.root_path / "PLUGINS.md"
        data_json_path = context.root_path / "docs" / "data.json"
        script_path = context.root_path / "scripts" / "generate_plugin_docs.py"

        original_plugins_md = plugins_md_path.read_text()
        original_data_json = data_json_path.read_text() if data_json_path.exists() else None

        result = subprocess.run(
            ["python3", str(script_path)],
            cwd=str(context.root_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"generate_plugin_docs.py failed: {result.stderr}")

        website_script_path = context.root_path / "scripts" / "build-website.py"
        if website_script_path.exists():
            result = subprocess.run(
                ["python3", str(website_script_path)],
                cwd=str(context.root_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"build-website.py failed: {result.stderr}")

        generated_plugins_md = plugins_md_path.read_text()
        generated_data_json = data_json_path.read_text() if data_json_path.exists() else None

        return (
            original_plugins_md, generated_plugins_md,
            original_data_json, generated_data_json,
        )

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        if not context.has_marketplace():
            return violations

        plugins_md_path = context.root_path / "PLUGINS.md"
        data_json_path = context.root_path / "docs" / "data.json"

        if not plugins_md_path.exists():
            return violations

        script_path = context.root_path / "scripts" / "generate_plugin_docs.py"
        if not script_path.exists():
            return violations

        try:
            (
                original_plugins_md, generated_plugins_md,
                original_data_json, generated_data_json,
            ) = self._run_generators(context)

            if original_plugins_md != generated_plugins_md:
                plugins_md_path.write_text(original_plugins_md)
                violations.append(
                    self.violation(
                        "PLUGINS.md is out of sync with plugin metadata. Run 'make update' to update.",
                        file_path=plugins_md_path,
                    )
                )

            if data_json_path.exists() and original_data_json != generated_data_json:
                if original_data_json is not None:
                    data_json_path.write_text(original_data_json)
                violations.append(
                    self.violation(
                        "docs/data.json is out of sync with plugin metadata. Run 'make update' to update.",
                        file_path=data_json_path,
                    )
                )

        except subprocess.TimeoutExpired:
            violations.append(
                self.violation("'make update' timed out", file_path=plugins_md_path)
            )
        except Exception as e:
            violations.append(
                self.violation(
                    f"Error checking files up-to-date status: {e}",
                    file_path=plugins_md_path,
                )
            )

        return violations

    def fix(
        self,
        context: RepositoryContext,
        violations: List[RuleViolation],
        *,
        provider: Any = None,
    ) -> List[AutofixResult]:
        results: List[AutofixResult] = []
        if not violations:
            return results

        plugins_md_path = context.root_path / "PLUGINS.md"
        data_json_path = context.root_path / "docs" / "data.json"

        try:
            (
                original_plugins_md, generated_plugins_md,
                original_data_json, generated_data_json,
            ) = self._run_generators(context)
        except Exception:
            return results

        plugins_md_violations = [v for v in violations if v.file_path == plugins_md_path]
        data_json_violations = [v for v in violations if v.file_path == data_json_path]

        if plugins_md_violations and original_plugins_md != generated_plugins_md:
            results.append(
                AutofixResult(
                    rule_id=self.rule_id,
                    file_path=plugins_md_path,
                    confidence=AutofixConfidence.SAFE,
                    original_content=original_plugins_md,
                    fixed_content=generated_plugins_md,
                    description="Regenerated PLUGINS.md from plugin metadata",
                    violations_fixed=plugins_md_violations,
                )
            )

        if data_json_violations and original_data_json != generated_data_json:
            results.append(
                AutofixResult(
                    rule_id=self.rule_id,
                    file_path=data_json_path,
                    confidence=AutofixConfidence.SAFE,
                    original_content=original_data_json or "",
                    fixed_content=generated_data_json or "",
                    description="Regenerated docs/data.json from plugin metadata",
                    violations_fixed=data_json_violations,
                )
            )

        return results
