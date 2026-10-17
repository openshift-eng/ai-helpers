# Secondary manifest runner smoke eval

The second eval in the [two-eval smoke test](../manifest-smoke/README.md)
reuses the same config basename, harness name, case ID, and output filename as
the first eval. Its different expected classification makes artifact mix-ups
observable.

| Case | Description |
| --- | --- |
| case-001 | Classify a blocking nil-pointer comment as `required_change` / `logic_bug` and write a valid `classification.json`. |

This eval is expected to pass. It uses the same skill, model, deterministic
judge, permissions, and invocation limits as the first eval.
