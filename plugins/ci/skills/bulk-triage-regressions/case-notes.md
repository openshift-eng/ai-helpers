# Case Notes: Mechanism Mis-Diagnoses from Real Duty Runs

Full narratives behind the compressed Phase 3/Phase 4 rules in `SKILL.md`. Read the relevant case when a rule's one-line summary is not enough to apply it.

## Case 1: VAP `paramKind` denial mis-filed as a CRD-ordering race (OCPBUGS-100316)

A duty run investigating install failures found ValidatingAdmissionPolicy denials (`paramKind ... not found`) blocking machine status patches. It filed the mechanism as "CRDs not yet established during install — an install-ordering race" and proposed (and opened a PR for) `failurePolicy: Ignore` on the policy — i.e., removing its fail-closed behavior.

The owning team's artifact review ([cluster-capi-operator#640](https://github.com/openshift/cluster-capi-operator/pull/640), closed) refuted every element:

- The CRD was `Established` **20 seconds before** the first denial — no ordering race. The timestamps were already in the gathered artifacts.
- The operator already sequenced CRDs → providers → policies via `installOrder` phases gated on an established-CRD probe — the "missing safeguard" existed in the repo and had never been read.
- The actual denial window was **~2 seconds** of apiserver VAP-informer warmup during an apiserver rollout. A permanent behavior change (fail-open) was proposed for a 2-second transient.
- The real product bug was elsewhere: control-plane and worker machines hit **identical** denials; masters retried and recovered, workers stayed permanently wedged because the vSphere actuator lost its in-flight vCenter task ID after one failed status patch and had no rediscovery path. The survivors proved the trigger transient; the component that failed to recover owned the bug. The analysis had noted this but demoted it to a "defense-in-depth" footnote.

Rules this case produced: timestamp proof for race theories; measure the failure window's duration; differential recovery check; read the owning repo's source before claiming a missing safeguard; fix proportionality; never lead with weakening a safety mechanism; triage duty never opens fix PRs.

## Case 2: kubelet ID-allocator boundary mis-filed as a CRI-O "malformed GID mapping" (OCPBUGS-99918)

A duty run saw pinns emit `Cannot write gid mappings: 0-4294901760-65536: Invalid argument` on a single pod and filed "CRI-O pinns computes a malformed GID mapping" against CRI-O, describing `4294901760` as "looks malformed (0xFFFF0000), suggesting overflow / wrong base computation".

The owning team's analysis showed:

- **pinns and CRI-O were pass-throughs**: pinns writes what CRI-O gives it; CRI-O passes through what kubelet sends over CRI. The producer was **kubelet's** user-namespace ID allocator randomly picking the top 65536-ID block of the 32-bit space. Fixed upstream in kubelet ([kubernetes/kubernetes#140190](https://github.com/kubernetes/kubernetes/pull/140190)), not CRI-O. The error-emitter was the messenger, not the owner.
- The "suspicious" constant decoded trivially: `4294901760 + 65536 = 2^32` — exactly the last 65536-ID block of the uint32 space. The kernel rejects mappings that include ID `2^32−1`, which hands you the entire mechanism (allocator boundary condition), not corruption.
- The filed "computation bug" theory predicted every-pod failure, but the observed rate was n=1 across many runs. The real mechanism (random block selection) predicted ~1/65535 per pod — exactly matching n=1. The report had flagged "single occurrence so far" as a caveat but never confronted the contradiction.

Rules this case produced: trace bad values to their producer; decode suspicious constants before writing "malformed"/"overflow"; the claimed mechanism must predict the observed frequency; mark unverified mechanism prose as an explicit hypothesis.
