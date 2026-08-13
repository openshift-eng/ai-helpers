"""
Custom skillsaw rules for the evals/ directory.

Eval case directory names are visible to the model under test, so they must not
leak what is being tested. These two rules enforce that:

1. eval-case-name       — every case directory is named `case-NNNN` (4 digits) only.
2. eval-case-registered — every case is registered in its eval's README index.

An "eval" is any directory directly under `evals/` that contains a `cases/`
subdirectory. Its cases are the immediate subdirectories of `cases/`.
"""

import re
from pathlib import Path
from typing import List

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity

CASE_NAME_RE = re.compile(r"^case-\d{4}$")


def _eval_roots(root_path: Path) -> List[Path]:
    """Return eval directories (children of evals/ that contain a cases/ dir)."""
    evals_dir = root_path / "evals"
    if not evals_dir.is_dir():
        return []
    return sorted(
        child
        for child in evals_dir.iterdir()
        if child.is_dir() and (child / "cases").is_dir()
    )


def _case_dirs(eval_root: Path) -> List[Path]:
    """Return the case directories for a single eval."""
    return sorted(c for c in (eval_root / "cases").iterdir() if c.is_dir())


class EvalCaseNameRule(Rule):
    """Eval case directories must be named `case-NNNN` (4 digits) with no slug."""

    @property
    def rule_id(self) -> str:
        return "eval-case-name"

    @property
    def description(self) -> str:
        return (
            "Eval case directories must be named 'case-NNNN' (four digits) only. "
            "A descriptive slug leaks what is being tested to the model under test."
        )

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        for eval_root in _eval_roots(context.root_path):
            for case_dir in _case_dirs(eval_root):
                if not CASE_NAME_RE.match(case_dir.name):
                    violations.append(
                        self.violation(
                            f"Eval case directory '{case_dir.name}' must be named "
                            f"'case-NNNN' (four digits) only, e.g. 'case-0001'.",
                            file_path=case_dir,
                        )
                    )

        return violations


class EvalCaseRegisteredRule(Rule):
    """Every eval case must be registered in its eval's README.md index."""

    @property
    def rule_id(self) -> str:
        return "eval-case-registered"

    @property
    def description(self) -> str:
        return (
            "Every eval case must be listed by name in its eval's README.md, "
            "since the case directory name is opaque."
        )

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        for eval_root in _eval_roots(context.root_path):
            readme = eval_root / "README.md"
            if not readme.is_file():
                violations.append(
                    self.violation(
                        f"Eval '{eval_root.name}' is missing a README.md to index "
                        f"its cases.",
                        file_path=readme,
                    )
                )
                continue

            text = readme.read_text(encoding="utf-8", errors="replace")
            for case_dir in _case_dirs(eval_root):
                # Match the case name as a whole token so 'case-0001' does not
                # satisfy 'case-00010', etc.
                pattern = re.compile(
                    r"(?<![\w-])" + re.escape(case_dir.name) + r"(?![\w-])"
                )
                if not pattern.search(text):
                    violations.append(
                        self.violation(
                            f"Eval case '{case_dir.name}' is not registered in "
                            f"{eval_root.name}/README.md. Add it to the case index.",
                            file_path=case_dir,
                        )
                    )

        return violations
