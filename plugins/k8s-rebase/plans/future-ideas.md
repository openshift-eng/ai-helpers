# Future Ideas

Ideas for after the skill is reliable and general. Not planned —
just tracked so they don't get lost.

## Scale (after pass rate is 90%+)

- Testing tiers: Court (6-10 canary repos, full gates + adversarial
  review), Gates-only (20-30 repos), Smoke (steps 1-2 only)
- Batch execution: MAX_CONCURRENT, flock, pre-pull Go image,
  GOMODCACHE warm-up
- Multi-repo coordinator (dependency-ordered batch, `depends_on`
  in config.yaml)
- Fleet dashboard (blocked/in-progress/pass/fail per repo)

## Generality

- Downstream handling (openshift/ovn-kubernetes OTE module)
- Operator-sdk/controller-tools automation
- Feature gate auto-discovery (replace GATE_DEPS map with runtime
  parsing of known_features.go — reviewed and DEFERRED: the map
  has only 2 entries, one line per release is simpler than a
  fragile parser. The script already parses known_features.go for
  LockToDefault detection. Revisit if GATE_DEPS grows past ~5.)
- GOTOOLCHAIN=local (reviewed and DEFERRED: auto-containerize
  already handles Go version mismatches, adding this could cause
  hard failures where container fallback would have worked)

## Quality

- Discovery procedures (replace version-specific recipes with
  runtime detection)
- Model-version coupling (log model ID, watch pass rates, pin
  on regression)
- License scan gate (`go-licenses` before PR)
- Feature gate policy layer (flag for human review vs silently
  disable)
- Builder image validation (check ART availability before
  updating Dockerfile refs)
