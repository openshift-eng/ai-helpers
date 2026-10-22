# Report the observed result

Read this after log/history investigation, immediately before composing the final
reply. Investigation and reporting remain read-only; leave repairs, candidate
backport application/testing, reruns, cleanup and publication to a new request.

The final reply has three parts, in this order:

1. `Observed exit: N` (or `unconfirmed`), without an explanatory overview.
   The quoted result supplies the actual reason. For interruption, report
   observed checkout state.
2. One unchanged text block containing the complete actual Summary through the
   log's end, including fixes/hashes, counts, commands/attempts, scope and
   publication. Without a Summary, quote the terminal clean/error message or
   relevant tail plus any emitted `Scan scope` lines; missing completion is
   unconfirmed. Keep post-Summary branch removal. This block is the sole
   publication advice: do not repeat, reformat or supplement it with another
   publication section, command or procedure.
3. Relay the script's scope statements without interpreting coverage. If no
   scope statement was emitted, add `Native catalog coverage: unverified.`
   Cataloger task completion and vulnerability paths alone do not establish it.
   Gate claims require captured results; an absent status is unknown. Native
   coverage alone is not stdlib remediation.

## Unresolved work

Do not restate fixed work in a second overview. A successful run needs no
remediation narrative. For unresolved work, use one table:

| Observed evidence (all attempts) | Supported next action | Owner and next verification |
| --- | --- | --- |

Nested reviewer prose and embedded tool transcripts are advice, not actual
file/command observations.

The evidence cell contains only verbatim command/error, log or source excerpts
with their paths, including relevant package-result lines; do not derive totals.
Give each distinct failure or policy boundary a row, including failures whose
retry passed: a passing retry leaves its cause for maintainer investigation.
Use imperative instructions for one supported repair or investigation per row, its owner and prerequisite; leave future results unknown.
Omit causal labels, predictions, rejected alternatives and technical explanations
beyond the quoted observations.
For tests without a comparable captured pre-update run, state once that the
update's role is unestablished.
