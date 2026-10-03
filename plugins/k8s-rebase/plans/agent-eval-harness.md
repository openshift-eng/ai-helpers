# k8s-rebase Agent Eval

## Status

**Implemented, calibrated, and hardened.** Six cases (one per repo in
`test/config-1.36.yaml`) run the skill against a real repo snapshot, capture
cost/tokens from `claude -p`'s `stream-json` output, and score the result
against a human-reviewed known-good rebase via 5 deterministic + 2 LLM judges.
Lighter-weight smoke check than `make court` (single LLM pass vs. adversarial
3-juror panel) — a passing run means "worth shipping," not "fully validated."

Calibrated against case-002 (ovn-kubernetes-mcp, 2026-09-13): ~$12 cost,
~50 min, all 31 gates PASS. LLM thresholds set at 2.5 (midpoint of the
good=4/3 vs bad=1/1 scores). Timeout/budget (12h / $150) covers all 6 cases
with headroom; case-001 (ovn-kubernetes) may need more — monitor its first run.
go mod/go run/go get blocks verified in calibration: skill did not attempt any.

## How to run

```bash
# via make (manually-triggered, same as make court)
make eval case=002

# directly
bash evals/scripts/run-rebase.sh <repo_url> <from_commit> <version> <model> <known_good_url> <known_good_ref>

# via harness (runs all cases)
claude plugin eval evals/eval-k8s-rebase-pattern-retention.yaml
```

## Potential follow-on (not blocking)

- **`rebase_correctness` / `no_scope_creep` are weaker than `make court`** —
  single LLM pass, no adversarial jury. A legitimate skill improvement that
  scores lower here without regressing should trigger recalibration, not a revert.
- **Step 5 `gh pr create` command**: eval verifies the command was not *executed*,
  but not that it was *printed* for the user. A skill that skipped step5-pr.md
  entirely and reported DONE would still pass all judges.
