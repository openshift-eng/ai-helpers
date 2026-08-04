# Case Notes: Real Duty-Run Incidents Behind the Rules

Full narratives behind the compressed rules in `SKILL.md`. Every rule in the skill that cites a case points here; read the relevant case when the one-line summary is not enough to apply the rule. Each case ends with the rules it produced.

## Case 1: VAP `paramKind` denial mis-filed as a CRD-ordering race (OCPBUGS-100316)

A duty run investigating install failures found ValidatingAdmissionPolicy denials (`paramKind ... not found`) blocking machine status patches. It filed the mechanism as "CRDs not yet established during install — an install-ordering race" and proposed (and opened a PR for) `failurePolicy: Ignore` on the policy — i.e., removing its fail-closed behavior.

The owning team's artifact review ([cluster-capi-operator#640](https://github.com/openshift/cluster-capi-operator/pull/640), closed) refuted every element:

- The CRD was `Established` **20 seconds before** the first denial — no ordering race. The timestamps were already in the gathered artifacts.
- The operator already sequenced CRDs → providers → policies via `installOrder` phases gated on an established-CRD probe — the "missing safeguard" existed in the repo and had never been read.
- The actual denial window was **~2 seconds** of apiserver VAP-informer warmup during an apiserver rollout. A permanent behavior change (fail-open) was proposed for a 2-second transient.
- The real product bug was elsewhere: control-plane and worker machines hit **identical** denials; masters retried and recovered, workers stayed permanently wedged because the vSphere actuator lost its in-flight vCenter task ID after one failed status patch and had no rediscovery path. The survivors proved the trigger transient; the component that failed to recover owned the bug. The analysis had noted this but demoted it to a "defense-in-depth" footnote.

Rules: timestamp proof for race theories; measure the failure window's duration; differential recovery check; read the owning repo's source before claiming a missing safeguard; fix proportionality; never lead with weakening a safety mechanism; triage duty never opens fix PRs.

## Case 2: kubelet ID-allocator boundary mis-filed as a CRI-O "malformed GID mapping" (OCPBUGS-99918)

A duty run saw pinns emit `Cannot write gid mappings: 0-4294901760-65536: Invalid argument` on a single pod and filed "CRI-O pinns computes a malformed GID mapping" against CRI-O, describing `4294901760` as "looks malformed (0xFFFF0000), suggesting overflow / wrong base computation".

The owning team's analysis showed:

- **pinns and CRI-O were pass-throughs**: pinns writes what CRI-O gives it; CRI-O passes through what kubelet sends over CRI. The producer was **kubelet's** user-namespace ID allocator randomly picking the top 65536-ID block of the 32-bit space. Fixed upstream in kubelet ([kubernetes/kubernetes#140190](https://github.com/kubernetes/kubernetes/pull/140190)), not CRI-O. The error-emitter was the messenger, not the owner.
- The "suspicious" constant decoded trivially: `4294901760 + 65536 = 2^32` — exactly the last 65536-ID block of the uint32 space. The kernel rejects mappings that include ID `2^32−1`, which hands you the entire mechanism (allocator boundary condition), not corruption.
- The filed "computation bug" theory predicted every-pod failure, but the observed rate was n=1 across many runs. The real mechanism (random block selection) predicted ~1/65535 per pod — exactly matching n=1. The report had flagged "single occurrence so far" as a caveat but never confronted the contradiction.

Rules: trace bad values to their producer; decode suspicious constants before writing "malformed"/"overflow"; the claimed mechanism must predict the observed frequency; mark unverified mechanism prose as an explicit hypothesis.

## Case 3: etcd cipherSuites bootstrap failure mis-attributed to the crash-looping router

Azure and GCP bootstrap timeouts were attributed to two different theories: an etcd-operator "cipherSuites not found" race (Azure) and "monitoring can't create Routes — Route API not registered" (GCP). An initial refutation of the etcd theory used `pods.json`: "workload pods are running, therefore etcd is fine", and pinned the failure on crash-looping router pods instead. `clusteroperators.json` later proved the refutation wrong: etcd was at `0 nodes active / revision 0` in **every** run — the etcd theory was correct all along. The router was a victim: it looped on `failed to list *v1.Route: the server could not find the requested resource`, i.e. the Route API was never registered because cluster etcd/apiserver never deployed. The bug stayed mis-attributed to the router change for weeks.

Compounding it: a validated router probe-loop symptom fired on 30/33 runs of the bucket — a *true* detection (the loop really happens) that still attributed victim runs to the router, because the signature is producible downstream of a different defect.

During bootstrap the bootstrap-node etcd/apiserver serve the control plane, so pods schedule and run happily while cluster etcd never deploys — pod existence proves nothing about cluster etcd.

Rules: the end-state oracle for bootstrap failures is `clusteroperators.json`, not pod existence; a crash-looper whose error names a missing upstream dependency is a victim, not an owner; a symptom detects a signature, not a cause — when the signature can occur downstream of a different defect, add an upstream-discriminator symptom to adjudicate.

## Case 4: ~1 Hz operator condition flap mislabeled "self-resolved slow rollout"

`not stable: [baremetal]` was classified "slow rollout, self-resolved" from 3 sampled runs that looked healthy at gather time, plus one FailedMount event. The install log actually showed the operator re-transitioning `Progressing` every ~1 second — **1600+ transitions in 30 minutes** — a permafail sync-loop product bug present in 19 of 20 runs including the newest. "Healthy at gather time" and a small sample produced the opposite classification (flaky/resolved) from the truth (permafail).

Rules: count condition transitions (`LastTransitionTime`/`DurationSinceTransition`) before choosing flap vs. slow rollout; enumerate all run dates before claiming cessation; small samples cannot prove "resolved".

## Case 5: image-registry rollout flap — the harness was the mutator

`verify the cluster readiness and stability` failed with "Cluster operator image-registry is not available" on vSphere; the draft disposition was a product bug against Image Registry. The operator log showed the trigger: the job's test harness replaced the cluster pull secret mid-run, the operator re-synced `installation-pull-secrets` and rolled its single-replica deployment (RWO storage — flaps Available by design during any rollout). Correct disposition: `test` bug against the harness.

Rules: a rollout-flap disposition must name the mutator (which object changed, who wrote it — audit logs or harness step logs), not stop at "the operator detected a configuration change"; single-replica deployments flap by design.

## Case 6: CBO duplicate bug — developer vocabulary defeats keyword search

A cluster-baremetal-operator Progressing-flap bucket had no related triage and no JIRA keyword hits, so a new bug was filed — duplicating an 8-day-old bug on the owning component titled "Do not require metal3-static-ip-manager to progress in vmedia" (zero keyword overlap with the CI-side symptom "baremetal CO flaps Progressing / Applying metal3 resources"), whose fix had merged at exactly the bucket's cessation date. Both the component-scoped JIRA listing and the owning-repo merge-history check would have caught it.

Rules: after determining the owning component, list its recent bugs regardless of keywords and read the summaries; check the owning repo's merges at onset and cessation boundaries; "resolved by unidentified payload change" is banned unless the merge-history check ran and came back empty; an unexplained cessation strongly hints a fix already landed.

## Case 7: SecurityPenetration interference — wrong gating claim, then wrongly left untriaged

A QoS-invariant regression appeared only under `metal/techpreview`. The report claimed the interfering SecurityPenetration tests were "techpreview-gated" — reading `penetration.go` showed they are gated on **baremetal platform** (`skipIfNotBaremetal`), so every metal job in any featureset was exposed; the variant slice reflected job scheduling, not the blast radius. The same bucket was then dispositioned "leave untriaged — mass-failure collateral" despite an accurate root cause: deterministic test interference is an independent mechanism and gets a `test` triage regardless of surrounding noise.

Rules: never write "X-only" about a test/tool unless its source-code skip/gates confirm it; identifying a root cause and leaving the bucket untriaged is a contradiction.

## Case 8: the symptom catalog as first oracle — and as refuter of "new mechanism" claims

Two parallel duty runs handled the same regression wave. One opened with a single dry-run `reevaluate` call: a payload-blocker label fired on all sampled runs across all platforms, attributing the entire board in seconds. The other skipped the catalog probe and spent **264 shell commands and 7 subagents** re-deriving the same known cause per bucket, then timed out before writing its report.

Separately: a bootstrap failure flooding the etcd-operator log with `TargetConfigController missing env var values` (5,471×) was flagged as a *new* mechanism because a grep for the known bug's `getCipherSuites` string found nothing — but a dry-run `reevaluate` fired the existing OCPBUGS-94106 symptom: the flood was a downstream consequence of the same defect (empty observedConfig → cipherSuites lookup fails → EnvVarController publishes nothing → TargetConfigController starves).

Rules: dry-run the symptom catalog before any artifact dive; a negative grep for one error string does not make a signature new — known causes surface through several messenger strings, and the armed catalog encodes the reliable ones.

## Case 9: a 100% triaged board hiding three live defects

A stale-triage sweep found three "triaged" metal regressions pointing at a **Closed** toolchain bug while actively failing daily from two entirely new causes — a build-cluster capacity outage and a same-day console regression. Invisible in every untriaged-count metric.

Rule: for every open already-triaged regression, compare `last_failure` against the triage's JIRA resolution date; failures after resolution mean a failed fix or a new cause hiding behind the stale record.

## Case 10: one wrapper regression, four causes

A long-lived install-wrapper regression accumulated four separately-verified causes over its lifetime: toolchain era → operator-flap window → CRI-O node bug → console startup fatal. Each window was separately triaged.

Rule: long-lived wrapper regressions are cause *timelines*; when `last_failure` advances, re-verify the new window from scratch.

## Case 11: the orchestrator that ended its turn "waiting" — $12, no report

A duty run dispatched AWS/GCP subagents and ended its assistant turn with "waiting for analysis to complete" and no tool call. The session terminated at that instant (there is no background execution across turns); the CI harness tore the process down. 15 minutes and $12 of analysis produced **no report file at all**.

Rules: never end a turn to "wait"; collect subagent results within the turn that needs them; write intermediate report versions early — if the run dies after any given message, the report must already exist on disk.

## Case 12: symptoms paying for themselves — and their traps

- **Adjudication**: a validated symptom settled a disputed root-cause attribution — two competing theories for the same runs; the matcher proved which signature was actually present.
- **Machine-verified split**: retro-applying two symptoms to one regression's 20 runs verified a 19-vs-1 bucket split.
- **Duplicate creation**: a duty run proposed a console-crash symptom whose label *and* both matchers already existed; the duplicate-key 400 from the label POST was what revealed it — the catalog had not been checked first.
- **Benign-transient false positive**: a healthy install's etcd-operator log contained a proposed match string **120 times** as a normal bootstrap warm-up transient; the failed run differed only in that the line persisted to log-end. String matchers cannot count or check persistence.

Rules: check catalog coverage before creating; grep the target file in a healthy run before finalizing a matcher; prefer end-state artifacts that are failure-only by construction.

## Case 13: audit-scale lessons — the 21% payload wave and the substring trap

In a closed-set audit, **one bad nightly payload explained 21% of the entire closed set**: the installer stamped version "0.0" and panicked on every platform for one day, opening and closing a same-day wave across platforms. Separately, a signature catalog mis-binned 31 regressions because the pattern `lease` matched inside the word `release`.

Rules: look for same-day open/close waves across platforms before analyzing anything individually; order signature catalogs most-specific-first and guard against substring traps.

## Case 14: vague wrapper output masking a CVO controller error (UDN mis-attribution)

Runs failing with bare `clusterversion not available: False` (empty reason) were drafted as "UDN CRD breakage" because UDN tests co-failed in the same techpreview jobs. The monitor intervals actually showed `Failing=True: failed to list agentic runs: no matches for kind "AgenticRun"` — a CVO controller bug with a merged fix, unrelated to UDN.

Rules: when junit output has an empty reason, grep build-log/monitor-intervals for the condition-change messages before attributing; never attribute a vague-output run from its co-failing tests.

## Case 15: connectivity tests failing on etcd — the setup error names the owner

Pod-to-service and host-to-service connectivity tests (attributed to Networking) failed because the *test preparation* poller pods could not be created: `etcdserver: request timed out` — an etcd-on-Azure product issue, not a networking bug.

Rule: read the actual error text including setup/preparation errors before trusting the test's subject area.

## Case 16: three confidently wrong root causes from out-of-population sampling

A shift analyzed "3 random jobs" from a broad Sippy job-filter URL ("all jobs failing test X") instead of the regression's own `job_runs` list. The sample swept in unrelated jobs and post-fix eras and produced three confidently wrong root causes in one shift.

Rule: every run cited must be a member of the regression's `job_runs` (and predate any candidate fix).

## Case 17: chained defects — different per-run mechanisms, one upstream cause

In one incident, runs died variously of maxPods saturation, memory livelock, and an OVS flow storm — all downstream of a single namespace-deletion blockage, which also amplified an otherwise-transient network defect into node death. A symptom later vanished without its component's fix merging, because the *interacting* defect got fixed instead.

Rules: when run-level root causes look "completely different", look one level up (what leaked, what was stuck, what accumulated); when a symptom vanishes without its fix merging, suspect an interacting defect.
