---
name: disruption-known-issues
description: Use when checking whether a disruption mechanism is already tracked in Jira — searches TRT and OCPBUGS by API family, mechanism keywords, and component, separates cards whose mechanism the evidence demonstrates from cards that are only related by backend or symptom, and checks whether a matching fix already landed. Usually the last step of a disruption investigation (see investigate-disruption).
---

# Disruption Known Issues

This skill answers **is this already tracked**. It classifies every candidate card as a **demonstrated mechanism match** or **related (context only)**, and never presents a related card as the explanation.

## Prerequisites

1. **Jira access** through the Atlassian MCP tools (`searchJiraIssuesUsingJql`, `getJiraIssue`). If they are unavailable or authentication fails, say "Jira search skipped (MCP unavailable)" and stop; the rest of the investigation does not depend on Jira.
2. **Python 3.7+.** The fix check (8.1.1 in `references/known-issues.md`) also needs network access to `sippy.dptools.openshift.org` and the gcloud CLI for anonymous reads from the public `test-platform-results-public` bucket, because it runs the `disruption-trend` and `disruption-analyze-run` scripts.
3. **The `disruption_common` library**: the `disruption` plugin's `scripts/disruption_common`, installed with the plugin. If it is missing, the scripts exit and say so. Report the message; do not work around it.

The scripts are in this skill's directory: `${CLAUDE_SKILL_DIR}` in Claude Code, or the directory containing this `SKILL.md` elsewhere.

## Rules shared by the disruption skills

- **Backend names are exact** everywhere except the Jira search itself, which deliberately widens each backend to its API family (cards are often filed against a sibling probe).
- **Platform.** A card about the alert's platform is not a match because the platform is the same. The mechanism must match.
- **State.** `{investigation_dir}` is the state file's directory; `{runs_dir}` is `{investigation_dir}/runs`.
- **One block.** Do not run another disruption skill yourself. End with the checkpoint below.

## Inputs

- **The mechanism**: component, resource, failure mode, and error text, from `{investigation_dir}/comparison.md`, a run's `{runs_dir}/{build_id}/analysis.md`, or the request. Search only once it is final. If later work changes it, search again.
- **The exact backends**, from the request or the state file's `series.backends`.
- For a regression: which candidates are new or stronger in the after cohort (`comparison.md`). A card describing a mechanism that is equally present before the step is related, not a match for the regression.

## Steps

Read `references/known-issues.md` and follow it:

1. **8.1 Search:** `known_issue_queries.py` prints the queries, most specific first. Run every query and every page. Do not write JQL by hand.
2. **8.1.2 Classify** each plausible card as a demonstrated mechanism match, related (context only), or not relevant, and record the result with `known_issue_queries.py --record`.
3. **8.1.1 Fix check** for every demonstrated match in MODIFIED, ON_QA, Verified, or Closed: did the failure signature disappear after the fix payload? It uses `disruption-trend`'s `disruption_series.py` for the runs and `fix_payload_check.py` for the per-payload signature table.
4. **8.2 Present** demonstrated matches first, then related cards each with why it is only related.

Do not file or edit a Jira issue unless the user asks in this conversation (8.3). When the investigation left the cause unresolved, a new card states the open hypotheses and what would test each, not a root cause.

## Output

Write `{investigation_dir}/known-issues.md` with the Known Disruption Issues section as 8.2 shows it. Answer with the demonstrated matches (and their fix status) and the related cards in separate lists. If a demonstrated match is fixed and the signature is gone, say plainly that the regression is already fixed and no new bug is needed.

End the turn with:

````text
```disruption-checkpoint
stage: jira
state_file: <path to investigation.json>
summary: <one line: demonstrated matches and fix status, or "no card demonstrates this mechanism">
next:
  - file a bug for <mechanism> (the user decides; 8.3)
  - add the disruption label to <cards>
  - assemble the investigation report (investigate-disruption)
```
````

List only the options that fit. Then **stop and wait** for the user's choice. Filing or editing Jira always waits for the user, even with `--auto`.
