"""
Custom skillsaw rule: validate promptfoo eval tests against a budget policy file.

Enforces five categories of checks:
  1. Required metadata fields (token-usage, judge-size, tier)
  2. token-usage classification accuracy (cost/latency fit, no over-classification)
  3. judge-size consistency with llm-rubric assertion presence
  4. tier classification accuracy (lowest valid tier)
  5. Per-plugin/skill budget compliance

Usage in .skillsaw.yaml:

    custom-rules:
      - evals/budget_rule.py          # or wherever you place this file

    rules:
      promptfoo-budget:
        enabled: true
        severity: error
        budget-file: evals/budget.yaml  # default
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from skillsaw import RepositoryContext, Rule, RuleViolation, Severity
from skillsaw.lint_target import PluginNode, PromptfooConfigNode, SkillNode
from skillsaw.rules.builtin.promptfoo import _collect_tests, _get_assertion_types
from skillsaw.rules.builtin.utils import (
    commented_key_line,
    read_text,
    read_yaml_commented,
)

_REQUIRED_METADATA = ("token-usage", "judge-size", "tier")


@dataclass
class _BudgetPolicy:
    orderings: Dict[str, List[str]]
    token_usage_defs: Dict[str, Dict[str, float]]
    tier_defs: Dict[str, Dict[str, str]]
    budgets: Dict[str, Dict[str, float]]


class PromptfooBudgetRule(Rule):
    """Validate promptfoo eval tests against a budget/policy file"""

    config_schema = {
        "budget-file": {
            "type": "str",
            "default": "evals/budget.yaml",
            "description": "Path to the budget/policy YAML file, relative to repository root",
        },
    }

    @property
    def rule_id(self) -> str:
        return "promptfoo-budget"

    @property
    def description(self) -> str:
        return "Validate promptfoo eval test metadata against a budget/policy file"

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        budget_rel = self.config.get(
            "budget-file",
            self.config_schema["budget-file"]["default"],
        )
        budget_path = context.root_path / budget_rel
        if not budget_path.exists():
            return violations

        budget_data, error, error_line = read_yaml_commented(budget_path)
        if error:
            violations.append(
                self.violation(f"Budget file error: {error}", file_path=budget_path, line=error_line)
            )
            return violations

        if not isinstance(budget_data, dict):
            violations.append(
                self.violation("Budget file must be a YAML mapping", file_path=budget_path)
            )
            return violations

        policy = self._parse_budget(budget_data, budget_path, violations)
        if policy is None:
            return violations

        aggregated_costs: Dict[str, float] = {}

        for node in context.lint_tree.find(PromptfooConfigNode):
            if node.is_fragment:
                continue

            data, err, _ = read_yaml_commented(node.path)
            if err or not isinstance(data, dict):
                continue

            default_test = data.get("defaultTest") if isinstance(data.get("defaultTest"), dict) else None
            tests = _collect_tests(node, context)

            entity = self._entity_name(context, node)

            for i, info in enumerate(tests):
                test = info.test
                desc = test.get("description", f"tests[{i}]")

                metadata = test.get("metadata")
                if not isinstance(metadata, dict):
                    violations.append(
                        self.violation(
                            f"Test '{desc}' missing metadata "
                            f"(required: {', '.join(_REQUIRED_METADATA)})",
                            file_path=info.file_path,
                            line=info.line,
                        )
                    )
                    continue

                missing = [k for k in _REQUIRED_METADATA if k not in metadata]
                if missing:
                    violations.append(
                        self.violation(
                            f"Test '{desc}' missing budget metadata: {', '.join(missing)}",
                            file_path=info.file_path,
                            line=commented_key_line(test, "metadata") or info.line,
                        )
                    )
                    continue

                thresholds = self._get_thresholds(test, default_test)

                self._validate_token_usage(
                    metadata["token-usage"], thresholds, policy, desc, info, violations
                )
                self._validate_judge_size(
                    metadata["judge-size"], test, default_test, policy, desc, info, violations
                )
                self._validate_tier(metadata, policy, desc, info, violations)

                cost = thresholds.get("cost")
                if cost is not None and entity is not None:
                    aggregated_costs[entity] = aggregated_costs.get(entity, 0.0) + cost

        self._validate_budgets(policy, aggregated_costs, budget_path, budget_data, violations)
        return violations

    # ------------------------------------------------------------------
    # Budget file parsing
    # ------------------------------------------------------------------

    def _parse_budget(
        self, data: dict, path: Path, violations: List[RuleViolation]
    ) -> Optional[_BudgetPolicy]:
        orderings = data.get("orderings")
        if not isinstance(orderings, dict):
            violations.append(
                self.violation("Budget file missing 'orderings' mapping", file_path=path)
            )
            return None

        tu_defs = data.get("token-usage")
        if not isinstance(tu_defs, dict):
            violations.append(
                self.violation(
                    "Budget file missing 'token-usage' mapping",
                    file_path=path,
                    line=commented_key_line(data, "token-usage"),
                )
            )
            return None

        tier_defs = data.get("tiers")
        if not isinstance(tier_defs, dict):
            violations.append(
                self.violation(
                    "Budget file missing 'tiers' mapping",
                    file_path=path,
                    line=commented_key_line(data, "tiers"),
                )
            )
            return None

        budgets = data.get("budgets", {})
        if not isinstance(budgets, dict):
            budgets = {}

        return _BudgetPolicy(
            orderings={k: list(v) for k, v in orderings.items() if isinstance(v, list)},
            token_usage_defs={k: dict(v) for k, v in tu_defs.items() if isinstance(v, dict)},
            tier_defs={k: dict(v) for k, v in tier_defs.items() if isinstance(v, dict)},
            budgets={k: dict(v) for k, v in budgets.items() if isinstance(v, dict)},
        )

    # ------------------------------------------------------------------
    # Threshold extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _get_thresholds(test: dict, default_test: Optional[dict]) -> Dict[str, Optional[float]]:
        result: Dict[str, Optional[float]] = {"cost": None, "latency": None}

        if isinstance(default_test, dict):
            for a in default_test.get("assert", []):
                if isinstance(a, dict):
                    a_type = a.get("type")
                    if a_type in result and isinstance(a.get("threshold"), (int, float)):
                        result[a_type] = a["threshold"]

        for a in test.get("assert", []):
            if isinstance(a, dict):
                a_type = a.get("type")
                if a_type in result and isinstance(a.get("threshold"), (int, float)):
                    result[a_type] = a["threshold"]

        return result

    # ------------------------------------------------------------------
    # Entity name for budget aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _entity_name(context: RepositoryContext, node: PromptfooConfigNode) -> Optional[str]:
        parent_skill = context.lint_tree.find_parent(node, SkillNode)
        if parent_skill is not None:
            return parent_skill.path.name

        parent_plugin = context.lint_tree.find_parent(node, PluginNode)
        if parent_plugin is not None:
            return parent_plugin.path.name

        return None

    # ------------------------------------------------------------------
    # token-usage validation
    # ------------------------------------------------------------------

    def _validate_token_usage(
        self,
        value: Any,
        thresholds: Dict[str, Optional[float]],
        policy: _BudgetPolicy,
        desc: str,
        info: Any,
        violations: List[RuleViolation],
    ) -> None:
        ordering = policy.orderings.get("token-usage", [])
        if value not in ordering:
            violations.append(
                self.violation(
                    f"Test '{desc}' has invalid token-usage '{value}' "
                    f"(valid: {', '.join(ordering)})",
                    file_path=info.file_path,
                    line=info.line,
                )
            )
            return

        definition = policy.token_usage_defs.get(value, {})
        max_cost = definition.get("max-cost")
        max_latency = definition.get("max-latency")
        test_cost = thresholds.get("cost")
        test_latency = thresholds.get("latency")

        if test_cost is not None and max_cost is not None and test_cost > max_cost:
            violations.append(
                self.violation(
                    f"Test '{desc}' cost threshold {test_cost} exceeds "
                    f"token-usage '{value}' max-cost {max_cost}",
                    file_path=info.file_path,
                    line=info.line,
                )
            )

        if test_latency is not None and max_latency is not None and test_latency > max_latency:
            violations.append(
                self.violation(
                    f"Test '{desc}' latency threshold {test_latency} exceeds "
                    f"token-usage '{value}' max-latency {max_latency}",
                    file_path=info.file_path,
                    line=info.line,
                )
            )

        if test_cost is None and test_latency is None:
            return

        current_idx = ordering.index(value)
        for smaller_idx in range(current_idx):
            smaller = ordering[smaller_idx]
            smaller_def = policy.token_usage_defs.get(smaller, {})
            s_cost = smaller_def.get("max-cost")
            s_latency = smaller_def.get("max-latency")

            cost_fits = test_cost is None or (s_cost is not None and test_cost <= s_cost)
            latency_fits = test_latency is None or (s_latency is not None and test_latency <= s_latency)

            if cost_fits and latency_fits:
                violations.append(
                    self.violation(
                        f"Test '{desc}' classified as '{value}' but fits in '{smaller}' "
                        f"(over-classified)",
                        file_path=info.file_path,
                        line=info.line,
                        severity=Severity.WARNING,
                    )
                )
                break

    # ------------------------------------------------------------------
    # judge-size validation
    # ------------------------------------------------------------------

    def _validate_judge_size(
        self,
        value: Any,
        test: dict,
        default_test: Optional[dict],
        policy: _BudgetPolicy,
        desc: str,
        info: Any,
        violations: List[RuleViolation],
    ) -> None:
        ordering = policy.orderings.get("judge-size", [])
        if value not in ordering:
            violations.append(
                self.violation(
                    f"Test '{desc}' has invalid judge-size '{value}' "
                    f"(valid: {', '.join(ordering)})",
                    file_path=info.file_path,
                    line=info.line,
                )
            )
            return

        test_types = _get_assertion_types(test.get("assert", []))
        default_types = _get_assertion_types(
            default_test.get("assert", []) if isinstance(default_test, dict) else []
        )
        has_llm_rubric = "llm-rubric" in (test_types | default_types)

        if not has_llm_rubric and value != "none":
            violations.append(
                self.violation(
                    f"Test '{desc}' judge-size is '{value}' but has no llm-rubric assertions "
                    f"(should be 'none')",
                    file_path=info.file_path,
                    line=info.line,
                )
            )
        elif has_llm_rubric and value == "none":
            violations.append(
                self.violation(
                    f"Test '{desc}' judge-size is 'none' but has llm-rubric assertions",
                    file_path=info.file_path,
                    line=info.line,
                )
            )

    # ------------------------------------------------------------------
    # tier validation
    # ------------------------------------------------------------------

    def _validate_tier(
        self,
        metadata: dict,
        policy: _BudgetPolicy,
        desc: str,
        info: Any,
        violations: List[RuleViolation],
    ) -> None:
        tier_value = metadata.get("tier")
        tu_value = metadata.get("token-usage")
        js_value = metadata.get("judge-size")

        tier_ordering = policy.orderings.get("tier", [])
        tu_ordering = policy.orderings.get("token-usage", [])
        js_ordering = policy.orderings.get("judge-size", [])

        if tier_value not in tier_ordering:
            violations.append(
                self.violation(
                    f"Test '{desc}' has invalid tier '{tier_value}' "
                    f"(valid: {', '.join(tier_ordering)})",
                    file_path=info.file_path,
                    line=info.line,
                )
            )
            return

        if tu_value not in tu_ordering or js_value not in js_ordering:
            return

        tu_idx = tu_ordering.index(tu_value)
        js_idx = js_ordering.index(js_value)

        for candidate in tier_ordering:
            tier_def = policy.tier_defs.get(candidate, {})
            max_tu = tier_def.get("max-token-usage")
            max_js = tier_def.get("max-judge-size")

            if max_tu not in tu_ordering or max_js not in js_ordering:
                continue

            tu_fits = tu_idx <= tu_ordering.index(max_tu)
            js_fits = js_idx <= js_ordering.index(max_js)

            if tu_fits and js_fits:
                if candidate != tier_value:
                    violations.append(
                        self.violation(
                            f"Test '{desc}' classified as tier '{tier_value}' "
                            f"but fits in '{candidate}' (over-classified)",
                            file_path=info.file_path,
                            line=info.line,
                            severity=Severity.WARNING,
                        )
                    )
                break

    # ------------------------------------------------------------------
    # Budget aggregation
    # ------------------------------------------------------------------

    def _validate_budgets(
        self,
        policy: _BudgetPolicy,
        aggregated_costs: Dict[str, float],
        budget_path: Path,
        budget_data: dict,
        violations: List[RuleViolation],
    ) -> None:
        budgets_node = budget_data.get("budgets")

        for entity, total_cost in aggregated_costs.items():
            budget_entry = policy.budgets.get(entity)
            if budget_entry is None:
                violations.append(
                    self.violation(
                        f"No budget entry for '{entity}' in budget file",
                        file_path=budget_path,
                    )
                )
                continue

            allowed = budget_entry.get("allowed")
            if isinstance(allowed, (int, float)) and total_cost > allowed:
                violations.append(
                    self.violation(
                        f"'{entity}' total cost {total_cost:.2f} exceeds "
                        f"budget of {allowed:.2f}",
                        file_path=budget_path,
                        line=commented_key_line(budgets_node, entity) if budgets_node else None,
                    )
                )

            current = budget_entry.get("current")
            if isinstance(current, (int, float)) and abs(total_cost - current) > 0.001:
                violations.append(
                    self.violation(
                        f"'{entity}' budget.current is {current:.2f} but computed "
                        f"total is {total_cost:.2f} (stale)",
                        file_path=budget_path,
                        line=commented_key_line(budgets_node, entity) if budgets_node else None,
                        severity=Severity.WARNING,
                    )
                )
