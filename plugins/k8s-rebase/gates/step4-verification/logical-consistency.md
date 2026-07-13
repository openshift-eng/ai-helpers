Read ALL fix commits (autofix + agent). For each function
modified, read the full function and trace data flow. Flag:
- Fields set but never read
- Fields compared in one code path but not another
- Struct copies that drop fields
- Variables assigned but never used
- Error values checked in one path but ignored in another

The autofix applies documented patterns (see the patterns doc)
that are intentionally targeted changes. Only flag
inconsistencies WITHIN a modified function — not missing
changes in unrelated functions or callers. Code removed in the
diff may reflect upstream changes merged before the rebase —
check the current file, not just the diff.

List each function you checked and your finding. Do not just
say "no issues" — show what you traced.

Rules: you are read-only — do not edit files. Cite file:line
for any issues.
