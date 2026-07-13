Read the autofix commit diff. For each Go function it modified:

(a) Read the FULL function after the change (not just the diff).
(b) Trace every added statement — if a value is assigned, is it
    later read? If it's read in one code path, is it read in ALL
    paths?
(c) Check for logical gaps: a field set but not compared, a field
    compared but not propagated when the struct is copied, a
    variable assigned but never used.

The autofix script applies documented patterns (see the patterns
doc) that modify specific code paths. These are intentional
targeted changes, not incomplete fixes. Only flag a function as
"partial" if the change is logically inconsistent within the
function itself — not just because it doesn't touch every caller.
Code that appears deleted in the diff may have been removed on
master before the rebase — check the current file state, not
just the diff, before flagging a removal as a regression.

List each function you checked and your finding. Count functions
with genuinely partial changes. Report count.

Rules: report specific counts, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
