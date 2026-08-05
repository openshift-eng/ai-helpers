# Case Notes: Real Duty-Run Incidents Behind the Rules

Full narratives behind the compressed rules in `SKILL.md`. Every rule in the skill that cites a case points here; read the relevant case when the one-line summary is not enough to apply the rule. Each case ends with the rules it produced.

*(Cases 1 and 2 — the OCPBUGS-100316 VAP/actuator and OCPBUGS-99918 GID-mapping incidents — were removed from this catalog: a baseline-vs-variant eval run showed the generic Phase 3 rules and mechanism self-review checklist catch both without the narratives. They live on as eval cases under `plugins/ci/evals/cases/bulk-triage-regressions/` (case-001, case-002), which is also the process for future candidates: prefer an eval case over a new narrative here.)*


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
