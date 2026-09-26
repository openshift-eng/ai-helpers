import os
from pathlib import Path

import pytest
import yaml
from skillsaw import RepositoryContext


ROOT = Path(__file__).parent.parent


def make_case(root, relative, registered=False):
    case = root / relative
    case.mkdir(parents=True)
    (case / "input.yaml").write_text("description: fixture\n")
    if registered:
        eval_root = next(parent for parent in case.parents if parent.name == "cases").parent
        (eval_root / "README.md").write_text(f"| {case.name} | Fixture |\n")
    return case


def repo_context(root):
    config = yaml.safe_load((ROOT / ".skillsaw.yaml").read_text())
    return RepositoryContext(root, exclude_patterns=config["exclude"])


@pytest.mark.parametrize("prefix", ["", "packages/example/"])
def test_ignored_worktrees_are_not_linted(temp_dir, eval_case_rule, prefix):
    make_case(temp_dir, "evals/real/cases/case-001", registered=True)
    make_case(temp_dir, f"{prefix}.claude/worktrees/review/evals/copied/cases/case-answer")

    assert eval_case_rule.check(repo_context(temp_dir)) == []


@pytest.mark.parametrize("prefix", [".work/scratch", "templates", "plugins/sample/templates"])
def test_existing_excludes_are_honored(temp_dir, eval_case_rule, prefix):
    make_case(temp_dir, f"{prefix}/evals/copied/cases/case-answer")

    assert eval_case_rule.check(repo_context(temp_dir)) == []


@pytest.mark.parametrize("relative", [
    "evals/example/cases/case-001",
    "plugins/sample/evals/cases/group/case-001",
])
def test_registered_cases_pass_in_both_layouts(temp_dir, eval_case_rule, relative):
    make_case(temp_dir, relative, registered=True)

    assert eval_case_rule.check(repo_context(temp_dir)) == []


@pytest.mark.parametrize("relative", [
    "evals/real/cases/payment-regression",
    "plugins/sample/evals/cases/group/case-answer",
    ".claude/evals/real/cases/case-answer",
])
def test_real_violations_are_not_hidden(temp_dir, eval_case_rule, relative):
    make_case(temp_dir, relative)
    make_case(temp_dir, ".claude/worktrees/review/evals/copied/cases/case-answer")

    violations = eval_case_rule.check(repo_context(temp_dir))

    assert len(violations) == 1
    assert "worktrees" not in str(violations[0].file_path)


@pytest.mark.parametrize(("relative", "excluded"), [
    ("evals/example/cases/case-answer", "evals/example/cases/case-answer"),
    ("plugins/sample/evals/cases/ignored/case-answer", "plugins/sample/evals/cases/ignored"),
])
def test_case_and_group_excludes_are_honored(temp_dir, eval_case_rule, relative, excluded):
    make_case(temp_dir, relative)
    context = RepositoryContext(temp_dir, exclude_patterns=[excluded])

    assert eval_case_rule.check(context) == []


def test_excluded_subtrees_are_not_traversed(temp_dir, eval_case_rule, monkeypatch):
    make_case(temp_dir, "scratch/evals/copied/cases/case-answer")
    context = RepositoryContext(temp_dir, exclude_patterns=["scratch"])
    scandir = os.scandir

    def checked_scandir(path):
        assert Path(path) != temp_dir / "scratch", "entered an excluded subtree"
        return scandir(path)

    monkeypatch.setattr(os, "scandir", checked_scandir)
    assert eval_case_rule.check(context) == []
