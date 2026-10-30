# Candidate and review contract

All paths in candidate evidence are relative to the investigation workspace. Retain the
actual text file, not a claimed excerpt alone. Files must remain within the workspace,
including after symlink resolution. Hashes and line ranges are verified before export.
Source URLs use HTTPS. Extract bounded text from compressed journals with retrieval
provenance; keep full raw bundles in scratch rather than copying them into every issue.

Each `candidates/<id>.json` object contains:

| Field | Meaning |
|---|---|
| `id` | Unique kebab-case candidate ID |
| `defect_key` | Stable kebab-case mechanism identity, shared across duplicate job findings |
| `title`, `summary` | Concrete defect and resulting behavior |
| `investigator` | Actual investigator context identity |
| `priority` | Positive integer; lower sorts first, based on impact/confidence/fix effort |
| `owner` | Team and repository responsible for the change |
| `mechanism` | Evidence-backed causal chain and incorrect behavior |
| `current_state` | Tested source versus current source and repair/adoption status |
| `currently_unfixed` | Boolean; must be true for `PROVEN_FIX` |
| `proposed_change` | Specific source/configuration change and why it addresses this defect |
| `validation` | Reproduction/control and acceptance criteria preserving real failures |
| `limitations` | Causal gaps, OS evidence gaps, cofailures, and scope of run counts |
| `verdict` | `PROVEN_FIX`, `UNRESOLVED`, `ALREADY_FIXED`, or `REJECTED` |
| `runs` | Nonempty array described below |
| `evidence` | Nonempty array described below |

A run has string `run_id`, `job`, `url`, and `result`, plus boolean `blocking_failure`.
`blocking_failure` means a failure caused this job to fail; it does **not** mean the job
itself blocks payload acceptance. Preserve the original result code. Known terminal failure codes accepted by the exporter are
`F`, `N`, `n`, `A`, `failure`, `error`, and `aborted`; unknown/nonterminal results cannot
prove a failed run. An abort or infrastructure result still needs evidence that the
claimed defect caused its blocking step failure. A run ID remains a
string to avoid losing precision. Document parent/component roles and failed phases in
the narrative; do not count the same underlying execution twice.

An evidence item has string `id`, `role`, `path`, `sha256`, `source_url`, and integer
`line_start`/`line_end` (one-based, inclusive). Roles:

- `failure`: actual blocking JUnit/step evidence and run provenance.
- `mechanism`: source or reproduction establishing the incorrect behavior.
- `current_source`: current source/configuration applicability and version provenance.
- `control`: successful same-job comparison or a justified controlled reproduction.

A proven candidate needs all four roles. One physical file can support multiple roles
with distinct IDs and line ranges. A candidate may have additional evidence in any role.
Missing controls are a reason to investigate, not to insert a placeholder attestation.

Each `reviews/<id>.json` contains:

| Field | Meaning |
|---|---|
| `candidate_id` | Exact candidate ID |
| `candidate_sha256` | Output of `reliability.py candidate-digest` |
| `reviewer` | Independent reviewer context identity; different from investigator |
| `verdict` | Same four allowed verdicts |
| `checked_evidence_ids` | Unique IDs actually inspected; all evidence for `PROVEN_FIX` |
| `reasoning` | Evidence-based conclusion, including current applicability |
| `counterargument` | Strongest alternative explanation and its disposition |
| `repair_scope` | Precisely what is established, what the change fixes, and what remains open |

Only dual `PROVEN_FIX` candidates enter the output `issues/`. The script never infers
truth from these strings: the independent review must be performed. Missing review means
unreviewed; a stale or malformed review stops export rather than silently accepting it.

## Running budgets and finalization

`config.json` freezes the candidate/issue/concurrency/time ceilings at initialization.
Check elapsed time against `started_at` before assigning more investigation work. Reserve
review/export time. The script enforces candidate and issue counts; the agent orchestrator
must enforce elapsed-time and worker limits. Collection has additional network/object/byte
ceilings and reports partial results explicitly.

Each export is a new directory. Evidence is copied into each issue with hashes checked
again. The exported finding uses issue-relative paths; `review.json` preserves the reviewed
original digest and adds `exported_candidate_sha256` to describe this path-only transformation.
The original review attests the workspace candidate; the exporter supplies the portable copy.
`unresolved.json` retains workspace evidence references for follow-up, while validated issue
folders contain their own evidence and can be handed to another agent independently.
