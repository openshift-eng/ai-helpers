# Population and ranking contract

## Collection

Freeze requested and effective settings before network acquisition. Query tags
for the exact release, architecture, stream, and UTC window, newest first, then
query all associated job rows for every inspected tag. A successful response
must be a JSON array. Record URL, retrieval time, bytes, SHA256, retained path,
and whether any configured request, response, scan, or time limit was hit.

Do not add unsupported page parameters. If the deployed API later exposes a
pagination contract, exhaust and record it; otherwise a locally paginated UI is
still one array response. Join jobs to the queried tag and Sippy ID because the
nested `release_tag` value may be empty.

Preserve raw fields. Normalize only explicit `Blocking` and `Informing` roles;
all others are `UNKNOWN`. Normalize `Succeeded` and `Failed`; retain aborted,
running, missing, and other values separately. Extract the Prow run ID and
provisional actual job from a validated Prow URL, then replace the provisional
job with `spec.job` from `prowjob.json` during investigation. An alias resolving
to multiple actual jobs must split into multiple cohorts.

Deduplicate Prow runs globally while retaining all associations. Upgrade routes,
material test configuration, population role, and role changes remain distinct.
Missing jobs are absent coverage. Previous-release observations always retain
their original release and `previous-release-history` population role.

## Health selection

Completed payloads with complete terminal blocker inventories and blocker
success at or above the configured threshold are initially eligible. Acceptance
is context, not proof; forced acceptance cannot hide blocker failures. Running
payloads, nonterminal blockers, incomplete retrieval, unknown expected blocker
coverage, and zero blockers need explicit uncertainty or another authoritative
completion basis.

Use structured reason codes: `LOW_BLOCKER_HEALTH`, `INCOMPLETE_INVENTORY`,
`NONTERMINAL_RESULTS`, `CONFIRMED_SHARED_FAILURE`, and
`HEALTH_CHECK_UNCERTAIN`. A shared incident requires evidence, normally a new
mechanism across at least three independent job families plus comparison with
adjacent payloads. Labels alone do not establish a common cause.

Preserve every selection revision. Recompute all rankings if later evidence
changes eligibility. Never exclude payloads merely for poor informing results.

## Previous-release history

Trigger fallback only when a new release lacks eligible payloads or per-job
history, never to hide current widespread failures, collection errors, or an
exhausted budget. Resolve the immediately previous release from `/api/releases`
metadata/order, or use the explicit input. Use the same architecture, stream,
health, and completeness rules.

Prefer the frozen current window. If it contains no predecessor payloads, anchor
a separate window of the same duration at the predecessor's latest payload at
or before the frozen end. Record its age and reason. Do not search a second
predecessor.

Cross-release mappings need both identities, purpose/configuration evidence,
confidence, and known changes. A name with a changed release number is not proof
of equivalence. History can guide investigation but cannot alone prove a current
defect or enter the current denominator.

## Metrics and ordering

For each stable informing cohort report:

- association success: `Succeeded / (Succeeded + Failed)`;
- unique-run success with the same terminal denominator;
- distinct eligible payload exposures and terminal runs;
- failed, succeeded, aborted, running, missing, and other counts;
- last pass, consecutive failures, retry availability, recent three exposures;
- phase/signature summaries, sample sufficiency, and investigation state.

Rates are `{numerator, denominator, value}` and undefined values use `null`.
Large IDs are strings. Show release-specific metrics separately even when a
supported longitudinal mapping is present.

Order cohorts with stable tie breaking:

1. adequately sampled zero-pass cohorts by descending failing runs and payloads;
2. other adequately sampled poor performers by ascending unique-run success,
   descending failure streak, and descending evidence volume;
3. remaining adequately sampled cohorts by ascending success rate;
4. sparse cohorts by descending observed failure rate.

Publish the exact sort keys. A recovered newest run requires change/adoption
investigation before retirement. Smaller or correlated samples are provisional.
