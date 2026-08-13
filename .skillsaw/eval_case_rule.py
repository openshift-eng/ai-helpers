"""
Custom skillsaw rules for eval case directories.

Eval case directory names are visible to the model under test, so they must not
leak what is being tested. These two rules enforce that:

1. eval-case-name       — every case directory is named `case-NNN` (digits only).
2. eval-case-registered — every case is registered in its eval's README index.

Discovery
---------
A "cases" directory is any directory named ``cases`` that has an ancestor
directory named ``evals``. Two layouts are supported:

* Flat (top-level ``evals/<name>/cases/case-NNNN``): the case directories are
  the direct children of ``cases``.
* Grouped (``plugins/<p>/evals/cases/<group>/case-NNNN``): ``cases`` holds
  group directories, and the case directories are their children.

In both layouts the eval's README lives at ``cases/../README.md`` (i.e. the
directory that contains ``cases``), which is where each case must be registered.
"""

import re
from pathlib import Path
from typing import List, Tuple

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity

CASE_NAME_RE = re.compile(r"^case-\d+$")
_SKIP_PARTS = {".git", "node_modules", "__pycache__"}


def _cases_dirs(root_path: Path) -> List[Path]:
    """All directories named 'cases' that live under an 'evals' ancestor."""
    result = []
    for path in root_path.rglob("cases"):
        if not path.is_dir():
            continue
        parts = set(path.parts)
        if parts & _SKIP_PARTS:
            continue
        if "evals" in path.parts:
            result.append(path)
    return sorted(result)


def _cases_in(cases_dir: Path) -> List[Path]:
    """Return the case directories under a 'cases' dir, handling both layouts.

    Flat layout: a direct child is named ``case-*`` → the direct children are
    the cases. Grouped layout: no direct child is named ``case-*`` → the direct
    children are groups and their children are the cases.
    """
    direct = sorted(d for d in cases_dir.iterdir() if d.is_dir())
    if any(d.name.startswith("case") for d in direct):
        return direct
    cases = []
    for group in direct:
        cases.extend(sorted(c for c in group.iterdir() if c.is_dir()))
    return cases


def _all_cases(root_path: Path) -> List[Tuple[Path, Path]]:
    """Yield (case_dir, eval_root) pairs across the repository.

    ``eval_root`` is the directory containing ``cases`` — where the README that
    indexes the cases must live.
    """
    pairs = []
    for cases_dir in _cases_dirs(root_path):
        eval_root = cases_dir.parent
        for case_dir in _cases_in(cases_dir):
            pairs.append((case_dir, eval_root))
    return pairs


class EvalCaseNameRule(Rule):
    """Eval case directories must be named `case-NNN` (digits only, no slug)."""

    @property
    def rule_id(self) -> str:
        return "eval-case-name"

    @property
    def description(self) -> str:
        return (
            "Eval case directories must be named 'case-NNN' (the word 'case', a "
            "hyphen, then digits only). A descriptive slug leaks what is being "
            "tested to the model under test."
        )

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        for case_dir, _eval_root in _all_cases(context.root_path):
            if not CASE_NAME_RE.match(case_dir.name):
                violations.append(
                    self.violation(
                        f"Eval case directory '{case_dir.name}' must be named "
                        f"'case-NNN' (digits only, no descriptive slug), e.g. "
                        f"'case-001'.",
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
            "Every eval case must be listed by name in the README.md at the eval "
            "root, since the case directory name is opaque."
        )

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        readme_cache: dict = {}
        missing_readme_reported: set = set()

        for case_dir, eval_root in _all_cases(context.root_path):
            readme = eval_root / "README.md"
            if not readme.is_file():
                if eval_root not in missing_readme_reported:
                    missing_readme_reported.add(eval_root)
                    rel = eval_root.relative_to(context.root_path)
                    violations.append(
                        self.violation(
                            f"Eval '{rel}' is missing a README.md to index its cases.",
                            file_path=readme,
                        )
                    )
                continue

            text = readme_cache.get(readme)
            if text is None:
                text = readme.read_text(encoding="utf-8", errors="replace")
                readme_cache[readme] = text

            # Require the case to be the first cell of a Markdown table row
            # (the index), so a passing prose mention does not count as
            # registration. re.escape keeps the interpolated name literal.
            row = re.compile(
                r"^\s*\|\s*" + re.escape(case_dir.name) + r"\s*\|",
                re.MULTILINE,
            )
            if not row.search(text):
                rel = eval_root.relative_to(context.root_path)
                violations.append(
                    self.violation(
                        f"Eval case '{case_dir.name}' is not registered in "
                        f"{rel}/README.md. Add it as a row in the case index "
                        f"table (e.g. '| {case_dir.name} | ... |').",
                        file_path=case_dir,
                    )
                )
        return violations
