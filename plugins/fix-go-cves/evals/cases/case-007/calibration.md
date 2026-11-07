# Multi-failure recording

Preserved from `cve-live-admiral-reporting-20261020`, recorded at `a6c8e5a0`.
The retained result is `aaaeea3261be3fa4375ce23ae46c6f09b72c78dc`, whose sole
parent is the pinned `da3ce251` release base. The literal Summary still names
live case-001; case-007 is this separate replay, not a rewritten measurement.

The full two-attempt log replaces the checkout path with `{{REPO}}`; three
historical tool-install/state paths use the deliberately opaque
`<recorded-helpers-root>` label. Failure text and terminal results are preserved.
The original log SHA-256 is
`c210df2beab8a37b0166566c083231a497eed8ded2d57a8b0f71031d8306a1a3`.
The plugin archive preserves the recorded scripts and excludes downloaded tools.
Preparation substitutes today's skill using the existing replay mechanism.

The reference preserves both test outcomes and leaves syncer causality unknown.
Its negative changes only the inference from the passing retry; both retain
correct backport advice. Recorded dependency facts come from the pinned
base/result, not a baseline test or an operator attribution experiment.

The current handoff scope permits a supported repair or investigation without
requiring historical repair discovery. Replay 005/007 retain the CVE-fix commit
assertion and repair witnesses, but no longer require the reporter backport hash;
live 001 likewise no longer requires that discovery. Case 005's unchanged
[missed-backport control](../case-005/negatives/missed-backport.md) is therefore a
prospective positive: it supplies a standalone repair, maintainer and remote
landing prerequisite. Its original negative label and scores remain historical.
The fix-branch-only and unsupported-causality controls remain negative. This
scope change supplies no new calibration or actor result; affected rendered
requests need calibration, including outcome requests changed by required_commits.
The repair witness now includes the complete unfiltered patch for `8234df00`,
establishing its single-file scope without attributing either historical failure
or predicting a successful rerun. Earlier evidence and grades remain unchanged.

Calibration at `fbda167a` used pinned harness `1a980e7` and judge
`claude-opus-4-6`: three samples per judge/reply, all 12 matching expected labels without errors.

| Reply | backport | action_owner |
| --- | --- | --- |
| Reference | true ×3 | true ×3 |
| Retry-causality negative | true ×3 | false ×3 |

All 12 judge calls were unpriced. Frozen inputs, rendered prompts, verdicts and
usage remain under `.work/fix-go-cves-multifailure-implementation/calibration/`.
A preliminary launch stopped before model calls because Vertex was disabled;
its log is preserved separately. This is reference calibration, not a skill run.
Summary/exit/count/original-ref fidelity still needs the planned manual review.

The later `contradictory-overview.md` negative adds one unsupported global
causal claim to the reference, retaining its explicit local uncertainty. It isolates the whole-reply
scope gap exposed at `f3b12fd3`; its separate oracle calibration does not change
the original admission labels or stored skill scores.

At `eb44d2f1`, the single whole-reply calibration passes all 21 samples without
errors: both case-005/007 references accepted, this negative and four existing
causal/prerequisite negatives rejected. This does not rescore the natural
retained reply or measure new skill behavior.
