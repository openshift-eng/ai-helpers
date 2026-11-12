# Known Disruption Issues

This reference searches Jira for existing cards that may already track the disruption mechanism,
classifies each one, checks whether a matching fix already landed, and offers to file a new bug
only if nothing matches.

**Search only after the mechanism is final.** If later work changes it (a comparison against
`compare_release`, more runs, an audit-log trace), run 8.1 again with the new signals and update
the results before answering. A search built from an earlier hypothesis does not count.

## 8.1: Search Jira

Do not write JQL by hand. `known_issue_queries.py` prints the queries:

```bash
python3 "${CLAUDE_SKILL_DIR}/known_issue_queries.py" \
  --backends {exact_backend_names} \
  --keyword "{root cause term}" --keyword "{resource or error string}" \
  [--component "{component}"] [--signal etcd] [--signal ovs] [--signal cpu]
```

- `--backends`: the exact comma-separated names from the analysis. The script reduces each
  one to the API it probes (`openshift-api-http2-service-network-reused-connections` →
  `openshift-api`), so cards filed against a sibling probe (internal-lb, localhost,
  service-network, http1/http2, new/reused) also match. This applies to the Jira search
  only. Run discovery and the parser still use exact names, as `run-discovery.md` requires.
- `--keyword` (**required once a root cause is known**): what the root cause is, in the words
  a bug author would use. Use the resource, the mechanism, and the error string from the
  evidence, for example `--keyword "watch cache" --keyword imagestream`, or
  `--keyword "connection reset" --keyword conntrack`. Use two to four terms. Multi-word
  terms are matched as phrases.
- `--component`: an OCPBUGS component, only when the evidence names it (for example, the
  audit log shows the stall inside openshift-apiserver). Do not guess one from the backend
  name.
- `--signal`: add `etcd`, `ovs`, or `cpu` when the parser's `concurrent_events` show that
  mechanism (`EtcdLog` count > 0; `OVSVswitchdLog` with `max_poll_interval_ms` > 500;
  `CPUMonitor`).

The output lists queries, most specific first. Run **every** query with
`searchJiraIssuesUsingJql`, passing its `args` unchanged. If a response has
`pageInfo.hasNextPage: true`, call it again with `nextPageToken` set to `pageInfo.endCursor`
until there are no more pages. Results are sorted by update time, not by relevance, so a
match can be anywhere in the list. Read every summary.

If a response is too large for the tool output and is saved to a file instead, read the file
with one `jq` command rather than skipping it:

```bash
jq -r '.issues.nodes[] | [.key, .fields.status.name, .fields.updated[0:10], .fields.summary] | @tsv' {saved_file}
```

The queries cover open cards and cards that reached a Done status (Verified, Closed, and so
on) in the last 90 days. A bug that was just fixed is often the explanation for a regression
alert. `backend-family-history` returns older closed investigations. Classify them by their
evidence like any other card (8.1.2): an old card can still describe the mechanism the runs
show, and it may have regressed.

Deduplicate by issue key. For each card whose summary plausibly matches the mechanism, call
`getJiraIssue` with `fields: ["summary", "description", "status", "components", "comment",
"issuelinks", "labels"]` and classify it (8.1.2).

## 8.1.2: Classify Each Card

Every card goes in exactly one group. Keep the groups separate in every answer, and never present
a related card as the explanation.

- **Demonstrated mechanism match:** the card describes the same mechanism the evidence shows: the
  same component and the same failure mode (error text, resource, or trigger), seen in the analyzed
  runs. For a regression, the mechanism must also be present (or stronger) in the after cohort and
  absent or weaker in the before cohort; a mechanism that is equally present before is not what
  made it worse. A match filed against a different backend or percentile is still a match. Say so.
- **Related (context only):** the card shares the backend, the platform, or a symptom (CPU
  pressure, etcd slowness, OVS stalls, cloud disk throttling) but the evidence does not show its
  mechanism. Cards found only through `--signal` queries start here: a symptom match is a
  hypothesis to test, not an explanation. Say what evidence would move it to a match.
- **Not relevant:** different mechanism and component. Leave it out of the answer.

Record the result with the state file when there is one:

```bash
python3 "${CLAUDE_SKILL_DIR}/known_issue_queries.py" --record {state_file} \
  --demonstrated OCPBUGS-1111 --related OCPBUGS-1234,OCPBUGS-999
```

## 8.1.1: Check Whether a Matching Fix Already Landed

Do this for every matching card in MODIFIED, ON_QA, Verified, or Closed.

1. Find the first payload with the fix. Look in the card's comments (bots post "Fixed in
   payload ..." or the release controller link) and linked PRs. If only a merge date is
   known, use the first nightly built after the merge, and say it is an estimate.
2. Get every run for the series over a window that starts at least a week before the fix
   (disruption-trend has 0s runs too; the finder lists only disrupted runs):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/../disruption-trend/disruption_series.py" {the same --alert-file, --grafana-url, or series fields} \
     --days {days back to a week before the fix, max 90} \
     --runs-out {investigation_dir}/fix-check-runs.json --format json > /dev/null
   ```

   If the window has no runs from before the fix payload, say that a before-and-after
   comparison is not possible, and widen `--days` (at most 90) if the user wants one.

3. Download timelines for every disrupted run in that window (`seconds` > 0 in
   `fix-check-runs.json`) with one call to the `disruption-analyze-run` skill's downloader,
   passing each run's `job` and `prow_id` (its **Timeline download** section in
   `references/artifacts.md` has the details):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/../disruption-analyze-run/download_timelines.py" \
     --runs '{job}:{prow_id},{job}:{prow_id},...' --output-dir {runs_dir}
   ```

   Then run:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/fix_payload_check.py" \
     --runs {investigation_dir}/fix-check-runs.json \
     --fix-payload {first payload with the fix} \
     --timelines-dir {runs_dir} \
     --backends {exact_backend_names} \
     --signature '{regex for the bug's error text}'
   ```

   The signature is a regex over the full disruption message, for example
   `'Client.Timeout exceeded|roundtrip=15'`. It must match the bug's failure mode and not the
   background noise you found in clean-period runs.

4. Report the result in the Known Disruption Issues section:
   - the per-payload-day table, or a short version: when the signature starts, its share of
     disrupted runs while the bug was live, and whether it is gone after the fix;
   - **fixed**: the signature is absent on payloads after the fix (allow a day or two for
     upgrades that started from an unfixed payload, and say that lag is unconfirmed);
   - **not fixed**: the signature continues at the same rate after the fix. Reopening or
     commenting on the card is the user's decision;
   - **too early**: fewer than about 10 runs on fixed payloads.
   - Whether the runs analyzed earlier in this investigation came before or after the fix.
     If they all came after it, the regression itself may not have been analyzed. Say so.

## 8.2: Present Results and Offer Actions

**If matching cards are found:**

Add a "Known Disruption Issues" section to the report. Start with the search line, then put
demonstrated matches first, with the fix check from 8.1.1 under each fixed match. Then list related
cards, each with the reason it is only related:

```markdown
## Known Disruption Issues

Searched with: backends openshift-api; keywords "watch cache", imagestream; component openshift-apiserver.

### Demonstrated mechanism match
| Key | Summary | Status | Filed against | Fix |
|-----|---------|--------|---------------|-----|
| [OCPBUGS-1111](url) | openshift-apiserver watch cache disabled | Verified | internal-lb backends, P50 | 5.1.0-0.nightly-2026-11-06-043907: fixed (signature absent on payloads from 2026-11-08) |

### Related (context only)
| Key | Summary | Status | Why only related | Updated |
|-----|---------|--------|------------------|---------|
| [OCPBUGS-1234](url) | openshift-api disruption on AWS | In Progress | same backend; describes etcd slowness, which is equally present before the step | 2026-07-28 |
| [OCPBUGS-999](url) | openshift-api disruption on Azure | Done - Errata | Azure disk throttling; these runs are on AWS | 2026-03-15 |
```

For each card missing the "disruption" label, note it:

```text
> OCPBUGS-5678 does not have the "disruption" label. Consider adding it for tracking.
```

If a match is fixed and the fix check shows the signature is gone, say plainly that the
regression is already fixed and no new bug is needed. Do not offer to file one.

Ask the user:
1. Whether they agree with the classification, especially any related card they think is a match
2. Whether to add the "disruption" label to any unlabeled cards that match — use `editJiraIssue`
   to append `"disruption"` to the existing labels array

**If no demonstrated match is found** (after every query and page in 8.1, with mechanism keywords):

Add to the report:

```markdown
## Known Disruption Issues

No existing Jira card demonstrates this mechanism.
```

List related cards under it as above. Then ask:

```text
No existing Jira cards were found tracking this disruption pattern.

Would you like to file a disruption bug? (yes/no)
```

If yes, go to 8.3.

## 8.3: File a Disruption Bug (Interactive)

Use the `jira:create` skill to file a bug. Propose the following details for the user to review
and edit before creation:

- **Project**: `OCPBUGS` (default; ask user if TRT is more appropriate)
- **Type**: Bug
- **Summary**: Derived from the analysis — e.g., `"{backend_name} disruption in {job_name} on {platform}"`
- **Description**: Populated from the analysis report including:
  - Root cause hypothesis, or, when the cause is unresolved, the open hypotheses and what would
    test each
  - Affected backends and their types (cache/non-cache)
  - Job run links (Prow and Sippy Intervals)
  - Key evidence (timeline data links, etcd signals, OVS stalls, CPU metrics)
  - Disruption counts and durations
- **Labels**: `["disruption", "ai-generated-jira"]`
- **Affects Version and Target Version**: on redhat.atlassian.net both are version arrays of
  IDs, for example `[{"id": "109996"}]`, not plain strings. Do not guess the IDs. Copy them
  from an existing OCPBUGS bug for the same release:

  ```jql
  project = OCPBUGS AND affectedVersion = "{release}" AND "Target Version" is not EMPTY ORDER BY created DESC
  ```

  Run it with `searchJiraIssuesUsingJql` and `fields: ["versions", "customfield_10855"]`. The
  first result is enough. Take its `versions[].id` for Affects Version (for example `109996`,
  named `5.1`) and its `customfield_10855[].id` for Target Version (for example `109998`, named
  `5.1.0`), and pass them in that shape when the bug is created.

Present the proposed summary and description to the user. Allow them to confirm, edit, or cancel
before creating. Follow the `jira:create` skill's interactive workflow and project conventions
(load `jira:jira-conventions` for the target project).

After creation, update the report's "Known Disruption Issues" section with the new bug's key and URL.
