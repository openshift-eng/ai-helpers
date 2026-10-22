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
   relevant tail; missing completion is unconfirmed. Keep post-Summary branch
   removal. This block is the sole publication advice: do not repeat, reformat or
   supplement it with another publication section, command or procedure.
3. If the block already reports scan scope, add no separate coverage
   interpretation. Otherwise report positively observed scope, or
   `Native catalog coverage: unverified.` when no native catalog proof is recorded.
   Keep named catalog paths and uncertainty about other binaries distinct.
   Gate claims require captured results; an absent status is unknown. Native
   coverage alone is not stdlib remediation.

## Unresolved work

Do not restate fixed work in a second overview. A successful run needs no
remediation narrative. For unresolved work, use one table:

| Observed evidence (all attempts) | Supported next action | Owner and next verification |
| --- | --- | --- |

Quote the actual command/error and relevant package-result lines rather than
recounting derived totals. Give each distinct failure or policy boundary a row,
including failures whose retry passed. Pair the evidence with a supported repair
or investigation, its owner and prerequisite; leave future results unknown.
For tests without a comparable captured pre-update run, state once that the
update's role is unestablished. Omit causal explanations; baseline comparison
belongs to a new request.
