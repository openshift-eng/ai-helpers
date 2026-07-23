# Reproducer Subagent Prompt

For every finding where `reproducer_needed` is `true` AND severity
is `BLOCKING`, launch a **reproducer subagent** (up to 5 in
parallel, 10 minute timeout each). Each gets this prompt:

> Create and execute a minimal reproducer to verify this bug.
>
> **Finding**: {title} in {file}:{line} — {body}
>
> **Instructions**:
> 1. Read the file and surrounding code for full context
> 2. Design the SMALLEST test case that demonstrates the bug
> 3. Create the reproducer files (scripts, configs, inputs)
> 4. Execute it and capture the output
> 5. Report pass (bug confirmed) or fail (not reproduced)
>
> **Requirements**:
> - Must be runnable, not a thought experiment
> - Must produce a clear pass/fail result
> - Create ALL reproducer files in /tmp — do not write any files
>   to the working tree
> - If the bug requires infrastructure you can't create locally,
>   explain why and report `not_reproducible`
> - Do not run destructive operations
> - Clean up temp files when done
>
> Return a JSON object in a fenced `json` block:
> ```json
> {
>   "reproduced": "confirmed",
>   "explanation": "What happened",
>   "steps": "Exact commands and files",
>   "expected": "Correct behavior",
>   "actual": "What actually happened (real output)",
>   "files": [{"path": "name", "content": "..."}]
> }
> ```
>
> **`reproduced` values**: `"confirmed"` | `"not_confirmed"` |
> `"not_reproducible"`

## Processing results

- `reproduced: "confirmed"` — keep as BLOCKING, attach reproducer
  details
- `reproduced: "not_confirmed"` — downgrade severity to
  `SUGGESTION`, add note: "Reproducer did not confirm this bug —
  may be a false positive or require conditions not tested."
- `reproduced: "not_reproducible"` — keep severity, add note
  explaining why
