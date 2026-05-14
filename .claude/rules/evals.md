When modifying plugin commands or skills, add or update evals in `plugins/<name>/evals/`.

Every eval test must have per-test metadata:
```yaml
metadata:
  token-usage: small | medium | large
  judge-size: none | sonnet | opus
  tier: fast | medium | heavy
```

Use YAML anchors (`&meta-fast` / `*meta-fast`) to avoid repetition.

After adding or modifying evals:
1. Run `make lint` — the skillsaw linter validates metadata, tier classification, and budget compliance against `evals/budget.yaml`
2. If lint fails, run `make lint-fix` to auto-fix what it can
3. Run `make eval-plugins EVAL_PLUGIN=<name>` to verify tests pass
4. Update `evals/budget.yaml` budgets.current if cost thresholds changed

See `evals/AGENTS.md` for the full tiering model and budget rules.
