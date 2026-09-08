---
description: Investigate recent release and presubmit failures and export independently validated reliability issue handoffs
argument-hint: "<release> [--hours 24] [--scope all|release|presubmits|blocking] [--max-issues 10] [--job NAME] [--job-contains TEXT] [--variant KEY:VALUE] [--output PATH]"
---

## Name
ci-extras:find-reliability-issues

## Synopsis
```
/ci-extras:find-reliability-issues <release> [--hours 24] [--scope all|release|presubmits|blocking] [--max-issues 10] [--job NAME] [--job-contains TEXT] [--variant KEY:VALUE] [--output PATH]
```

## Description
Find actionable CI reliability defects, prove their mechanisms against run artifacts and
current source, and create portable handoffs for another agent. Defaults cover any job run
in the chosen release plus presubmits during the last 24 hours. Successful runs remain in
the corpus as controls. Payload-blocking-only selection is opt-in.

## Implementation
Use the bundled [investigate-ci-reliability skill](../skills/investigate-ci-reliability/SKILL.md) with the supplied
arguments. Interpret optional UTC start/end, candidate/time/concurrency budgets, and scratch
location from the request. Preserve defaults for unspecified inputs.

Collect the bounded corpus, investigate recurring failures, and apply the independent
[review-ci-reliability skill](../skills/review-ci-reliability/SKILL.md). Export only currently
applicable defects that pass both substantive proof review and deterministic evidence checks.
The maximum issue count is a ceiling; fewer proven issues is a valid result. Keep unresolved,
already-fixed, and duplicate findings outside the validated `issues/` directory.

## Return Value
A local output directory containing ranked `issues/<slug>/README.md` handoffs and their
retained evidence, an HTML index, machine-readable manifest, and excluded findings. Report
validated count and coverage limits. This command does not open external issues or modify CI.

## Examples
```
/ci-extras:find-reliability-issues 5.1 --max-issues 5
/ci-extras:find-reliability-issues 5.1 --scope blocking --hours 48 --max-issues 3
/ci-extras:find-reliability-issues 5.1 --scope presubmits --job-contains hypershift
```
