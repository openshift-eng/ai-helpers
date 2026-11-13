# Simplification implementation and verification

## Installed Codex UX correction, 2026-11-05

The user's first installed-plugin Submariner run finished in 1,410 seconds with
exit 2. Its final Summary records two retained commits (`ad127a49`, `29124ce6`),
two packages/26 findings fixed, nine outstanding findings, and passing configured
unit, verification and license checks. The recorded x/net repair needs Go 1.26
against branch Go 1.25 policy. Native-binary coverage remains unverified, and
publication is unavailable because the base/push destination was not confirmed.
The original private log is `/tmp/fix-go-cves.4fwK3v.log`.

The invoking response hid those outcomes: the Codex instructions permitted only
reading the terminal exit and prohibited interpretation. The revision removes
that restriction, uses bounded existing log excerpts for concrete progress and
asks the same invoking agent to summarize recorded outcomes and next decisions.
It also skips absent optional policy files and separates the terminal exit marker
from unterminated engine output. No engine changes, new reporting machinery,
model workers or target-repository rerun are needed. Archived evidence checks
and fresh installed-skill discovery are separate from a future real measurement
of the revised invoking behavior; historical actor grades do not cover this UX.

The 141 runtime and 82 evaluator tests pass. The existing documented-launch
control now covers 48 Bash/Zsh, error-handling, output and exit combinations,
plus terminal-write failures. Original-output preservation and the actual final
exit are checked, including misleading intermediate exit text. Local receipts
are under `.work/fix-go-cves-codex-ux/`.

## Current design closure, 2026-11-04

The Codex-only native campaign completed across seven release-0.24 repositories,
preserving the earlier frozen protocols below. Each latest recorded run passes
all configured checks. Six overall exits remain partial for real dependency or
compatibility blockers; these are not zero-finding repair claims.
Three reproduced runtime defects are fixed without new configuration:
`2deebd03` restores tolerated generator stamps at later verification gates;
`e72cc871` rechecks checkout ownership after collecting status; `c6649279`
routes an unscoped ignore repair to its uniquely observed tracked module while
preserving the original selector for cleanup/classification. Real Git controls
cover moved HEAD/ref and substantive generated output; a native offline Go
fixture covers an unused parent requirement discarded by tidy. Current code
verification at `e4e5bd28` is **3,188 shell checks, 141 runtime tests and 82 evaluator tests**,
exact staged-tree lint, strict site build and entrypoint ShellCheck. No new
Claude/model actor or paid judge was invoked.

| Repository | Runtime source | Engine exit | Remaining review |
| --- | --- | --- | --- |
| Subctl | `16278cdf` | 0 | No Go findings; two unrelated GitHub Actions findings remain in the repeat report |
| Admiral | `16278cdf` | 2 | Seven x/net findings require Go 1.26 against Go 1.25 policy |
| Submariner | `2deebd03` | 2 | Nine x/net findings remain; tools Go 1.25 prevents complete remediation |
| Submariner Operator | `c6649279` | 2 | Crypto repair introduces vulnerable OpenPGP; the fixed Helm parent requires tools Kubernetes 0.36 |
| Lighthouse | `e4e5bd28` | 2 | 46 findings; Go 1.25 constraints and CoreDNS introducing vulnerable go-jose |
| Cloud Prepare | `e4e5bd28` | 2 | Ten Crypto/x/net findings require Go 1.26 against Go 1.25 policy |
| Shipyard | `e4e5bd28` | 2 | 14 x/net findings require Go 1.26 against Go 1.25 policy |

Admiral, Cloud Prepare and Shipyard use source-only dependency scans and maintained
unit tests; build/license commands are unconfigured. Their binary coverage is
unverified. Operator's Crypto repair remains reviewed even though its existing
ignore leaves no unignored Go matches. Every original exit, clean retained/tested
HEAD and configured gate was checked independently. Declared Go and Kubernetes
minor restrictions remain unchanged across all 13 tracked modules. The ledger is
`campaign-final-checks.json` beside private evidence. Submariner Bot has no matching
release branch. No target repository was pushed and no compatibility exception
has been authorized.

Operator's first 2deebd03 run retains five package repairs at `e67f799b` and two
genuine no-published-fix exceptions, but exposes the unused-root routing defect.
Its full c6649279 continuation starts from those real engine-produced commits
and reaches the correct tools module. Every verification gate passes, but exit
2 correctly preserves a new blocker: the x/crypto update introduces the
standalone vulnerable OpenPGP module through Operator SDK's Helm plugin. The
regression guard reverts the repair; retained HEAD remains `e67f799b`. The
first fixed Helm release v3.21.4 requires Kubernetes v0.36.2 in tools; a guarded
parent-upgrade probe returns 2 and restores clean tracked state. No policy
exception has been authorized. These are dependency/policy blockers, not passing
repair claims.

Lighthouse's c6649279 run retains OpenTelemetry SDK and gRPC package repairs;
the real scanner-driven retry from gRPC v1.83.1 to v1.83.2 succeeds. Its audits
expose two further defects: proven binary findings lose their scoped source
review classification, and merging an inherited ignore overlap writes an
illegal `fix-state: fixed` rule. The later policy audit rejects that rule with
`BAD_FIX_STATE`. The original run returns 2 after 4,560 seconds: unit tests,
final scans and licensing complete with exit 0, verification with exit 1.
Real Go/Git controls reproduce both defects, including new findings,
ambiguous/unowned binaries and unsupported fix states. Entrypoint ShellCheck and
syntax checks pass. Its full frozen `e4e5bd28` continuation starts from
the two valid package commits at `bf0bc85`, before the unsafe ignore; the original
failed branch at `e907ce18` remains unchanged. In 2,109 seconds it passes all
initial/final scan, unit, verification and license gates with exit 0, retaining
the safe policy commit `05f39f81`. Overall exit 2 preserves 46 outstanding Go
findings; the published Crypto finding stays visible. CoreDNS is attempted once,
with no redundant binary-alias retry. Independent inspection confirms all four
final binaries' SHA, clean embedded VCS revision and Go 1.26.10, all 26 binary
findings against Go metadata, and supported expiry states in every new policy
commit. The checks are in `lighthouse-final-checks.json` beside private evidence.
Cloud Prepare completes in 467 seconds, retaining three package repairs for five
findings at `0398a62a`: SDK v1.45.0, x/text v0.41.0 in tools and the real gRPC
v1.83.1-to-v1.83.2 retry. All provider-package tests and pinned mock generation
pass without tracked drift. Shipyard completes in 372 seconds at `1f82a937`,
retaining the tools x/text repair; its unit workflow builds the Dapper base image
and passes. Both preserve Go 1.25 and pass their configured scan/test/audit gates.
Only dependency files change. Independent checks are in
`cloud-prepare-final-checks.json` and `shipyard-final-checks.json`.
Private logs, per-run evidence and the parent probe are under
`.work/fix-go-cves-codex-iterate-20261104.6TZKaw/`; original runs remain under
`.work/fix-go-cves-codex-real-20261104.72a72F/`.

Three expert audits and cross-reviews guided a deletion-first follow-up at commits
`c77a3407`, `3e407b4c` and `a1dd02b6`. Compared with `7f0b2ab2`, runtime/eval/Skill
code is **148 lines smaller**, and code plus tests is **220 lines smaller**.
No paid Claude inference or semantic judges were used.

| Simplification or reproduced defect | Result and preserved boundary |
| --- | --- |
| Unused `evidence.txt` projection and repeated frozen-input read | Remove the projection; retain the original archived log/hash and one fresh input validation per check, including exact source/interpreter fences |
| Read-only detection rejected retained fix branches | Guard branch setup only for mutating runs; actual report now scans that branch without changing refs/index/tracked state |
| Dead counters/history, duplicate path normalization and eager Make checks | Reuse outcomes/shared normalization; explicit build commands avoid two Make probes |
| Audit status and dirty package names parsed separately | Parse once, emit names only after the whole result is valid; dirty iteration uses four rather than eight awk reads, with one extra bounded Bash child on clean/inconclusive paths |
| Ignore no-op/update decisions repeatedly parsed current/HEAD YAML | Parse immutable inputs once; 12-CVE no-op readers fall 24 to 2, scoped update 49 to 26; writable/transaction validation remains unchanged |
| Duplicate cancellation cleanup | Shared finally retains TERM/grace/KILL/reap and signal restoration; actual TERM-ignoring child regression passes |
| Copied selector formulas and duplicate poison-model executions | Exercise production selectors/dispatch and keep both model executables poisoned; preserve semantic policy and actual Git/Go controls |

Ignore-decision parity covers 24 old/new scenarios, including all-versus-any,
current-versus-HEAD, scope/type/fix-state and transactional state. Eager HEAD parsing
adds one read and may expose an existing diagnostic on missing/invalid current
policy; there is no persistent cache or byte-identical-stderr claim. A dirty-first,
later-invalid audit cannot leak names or dispatch repair. The deliberately leaking
control fails. Removed copied tests included a false expectation that a prerelease
threshold could invent a stable fix.

Verification at `a1dd02b6`: **3,104/3,104 shell checks**, **115/115 runtime Python
tests** (including 24 delivery and 16 transaction tests), **79/79 evaluator tests**,
exact staged-tree lint and strict site build pass. Lower counts reflect deletion of
copied/duplicate checks and the unused projection test; new assertions reach actual
selectors, report preservation, malformed audit dispatch and ignore decisions.

Final native source is commit `a1dd02b6`, Git tree
`cb9cc48bb036f4d9259a429662619ce7326f3916`. One frozen Subctl release-0.24 run
(protocol `514dde25…`, base `bf62ddf2`, initial devel `08142559`) uses both guards,
canonical Dapper build, race-enabled `make unit`, four audits and `make licensecheck`.
Findings fall **20 to 1**; actual engine exit **2** retains clean
`d4411433d34ecc38a928f9c124ffe1f12f248a43`, elapsed **358.27 seconds**.
All **69** deterministic checks pass. INITIAL/FINAL fresh native build, catalog,
SHA and clean embedded VCS agree with their respective source heads; independent
inspection of retained ELF bytes and complete Go metadata agrees. The remaining
`GO-2026-6809` needs Go 1.26.10; the frozen builder has Go 1.26.9.

A separate fresh clone of that retained fix branch runs report-only mode once
with the existing explicit release build-image override (protocol `155ba12a…`).
Actual report exit **0**, elapsed **21.49 seconds**, means completed measurement;
the outstanding finding remains visible. All **16** checks pass: one real native
scan/build, source/catalog/VCS/hash agreement, unchanged HEAD/refs/logical index/
tracked bytes and untouched original engine evidence. Earlier first-wave source
`3e407b4c` also passed its native/report protocols; those original results remain
separate. Private evidence is under `.work/fix-go-cves-design-20261104/`.

Pinned Claude Code 2.1.317 separately exercises actual UI cancellation with current
helper `cbe5cac2…` and a synthetic local engine: child stops, partial log survives,
no normal completion marker appears, and the later batch never starts. Native
debug records an unconfirmed result, but the interrupted UI suppresses the normal
LOG record. This is cancellation evidence, not visible delivery or real-engine
rollback proof; it uses no paid inference. Evidence is under
`.work/fix-go-cves-simplification-20261104/cancel-batch-317/`.

Independent reviewers validate the final native/report evidence and owned-worker
teardown. All **14** teardown checks pass; owned processes/socket are gone,
prior seven checkout heads/default Docker context/config/stable host socket
identity are preserved, and the cache remains. Raw timestamps remain observations.
Hosted CI still needs maintainer authorization. These engine/report controls do
not measure AI policy selection, statistical reliability or unattended lifecycle.
Earlier actor grades and failed protocols retain their own source identities.

## Follow-up audit closure

Delivery/evaluator fixes are committed at `70689126`; engine fixes at `b40d06d4`.
Additional invocation-witness corrections are committed at `4eb7e7e3`.
Three experts audited and cross-reviewed the changes. This follow-up used zero
real provider/model calls and no semantic judges.

| Reproduced defect | Correction |
| --- | --- |
| Rollback erased moved-checkout changes; later main/verification repairs could commit caller-staged source | Fence commit/ref ownership, stop subsequent repairs/tests on loss and preserve caller files/index |
| Failed stale-ignore amend left changes for the next repair | One shared native-policy commit boundary stops failures, including unchanged-checkout staged policy |
| Rejected ignore commit left an untracked policy and could report clean | Restore exact existing policy or remove only the new policy; retain the failed gate |
| Initial build raised a restricted Go minor before the child chose its baseline | Reject initial tracked source changes after generated-file normalization, before remediation |
| SessionStart checks/guards and Docker settings disappeared in the hook | Carry approved prepare-time settings, preserving absent/empty values; per-run settings win |
| Preparation could dirty named/nested worktrees | Resolve absolute targets and test enclosing Git roots, including newline-ending names; require foreground uninterrupted callbacks |
| Modified replay driver or invocation settings could still pass capture/check | Bind driver/metadata identities and observed arguments/settings to the consumed native request |
| Trace checks confused arguments with commands, missed absolute Git/GH and permitted extra direct engine launches | Inspect direct executable positions/basenames; reject direct engine launches outside native delivery; keep nested shell interpretation outside the heuristic |
| Evaluator rejected a legitimate persistent Bash cwd change | Bind the absolute target independently of cwd; actual native cwd/descriptor binding already works |

Final verification: **3,135/3,135 shell checks**, **112/112 runtime Python tests**
(including 23 delivery and 16 transaction tests), **80/80 evaluator tests**, syntax,
error-level ShellCheck, exact staged-tree lint and strict site build pass. The shell
run preserved all eight frozen core/test identities. Its verification-commit fixture
now changes source through the repair callback rather than mutating from an audit.
The `/proc` polling test accepts both ordinary disappearing-process errors.
The latest evaluator run takes 259.39 seconds; unchanged engine checks are reused
by exact source identity. New end-to-end controls execute a failed direct wrapper
call, truncate its witness, then prepare/deliver normally: the full retained trace
now rejects it. Actual invocation-file override forgery also fails; the separate
clean control passes. These constructed streams exercise genuine driver/helper
execution without claiming native CLI or model behavior. Pinned 2.1.317 separately
confirms persistent Bash cwd changes with helper `ee9515b6…` and a fixture engine;
no production transport change was needed.

Pinned Claude Code **2.1.317** local before/after controls demonstrate the session
environment correction with helper `cef887ba…`. Final helper `ee9515b6…` additionally
fixes Git-root trailing-newline parsing, covered by regression and fresh integration.
The final integration freezes protocol
`16f7e7b11614ef75bdff68315982c25a7917fbeb469da2d02f71324b1459bb10`, library
`63b5dacb5608b0a9f3ffd2ca6c789ecef7ab88d8251ef2bbed90e85592a72afa`
and all 95 plugin source file bytes/modes. One native prepare/hook at Admiral base
`af20d0bf` clears seven x/net findings with v0.62.0, retaining
`35638caa832cb1edeba9f34dd2f6dff371fe5b6a`. Original engine exit 0, first
race-enabled `make unit`, four audits, zero final matches/ignores and clean retained
source agree across independent receipts. Elapsed 131.14 seconds; one localhost
synthetic messages request, no post-runtime generation or real inference. All 11
independent teardown checks pass: owned daemon stopped, prior checkouts/default
Docker settings unchanged, cache retained.

That Admiral run had unconfigured build/license checks. A separate fresh direct
Subctl release-0.24 run closes native build/license coverage for the current engine:
protocol `532bf529a8a198d2e30446abce63f6ea5306a73ce00c2d3e068c76b996dc79a9`,
source `53053855` (17 engine/audit files still identical to the live tree), pinned
release `bf62ddf2` from initial devel `08142559`. Both guards remain enabled.
Actionable matches fall **20 to 1**; engine exit **2** correctly retains
`914d7f515faa4d7ab54d184fb7ed5c498f120cce` with a clean checkout. INITIAL and FINAL
fresh-build/catalog/VCS/hash proofs bind their respective source heads. The FINAL
proof also agrees with independently inspected retained ELF bytes and all 139 Go
metadata lines. First race-enabled `make unit`, four audits
and `make licensecheck` pass at the retained HEAD. All 69 deterministic and 27
independent checks pass, elapsed 566.11 seconds, zero model/provider calls.
This also exercises the bounded newer-threshold retry and a real verification-loop
stale-ignore commit through the shared ownership boundary. The remaining stdlib
finding `GO-2026-6809` needs Go 1.26.10; the frozen builder contains Go 1.26.9.
This is verified partial remediation, with native coverage limited to the named
Subctl artifacts. Evidence is under `.work/fix-go-cves-continuation-20261103/native004/`.

The new worker is stopped and cache/prior checkouts/default Docker settings are
preserved. An initial broad teardown comparison failed solely on the host socket's
access time; stable socket identity/security metadata are unchanged. Both original
failure and qualified correction remain preserved; 12 independent disposition
checks pass. No host socket restoration was performed.

Neither new integration measures AI policy selection. Registry/omitted-target and
conflicting inherited settings remain unmeasured actor coverage. Hosted CI needs
maintainer authorization.
The earlier successful integration `d8f2abf2…` remains separate because the amend
counterexample was found afterward. Unexecuted preparation and interrupted/mixed
shell runs remain preserved without final acceptance credit. Private evidence is
under `.work/fix-go-cves-audit-20261103/`; committed regressions reproduce the safety
boundaries without providers.

## Earlier bounded acceptance

The Claude Code native-artifact default passed its declared bounded acceptance
at source `9e79eacf`: two actors pass automatic contracts and independent
visible-output/policy review; local/native controls and a fresh real-engine
successful repair also passed. Those grades remain historical evidence for the
frozen source. This does not
establish statistical reliability, requested diagnosis or unattended lifecycle.
Earlier literal-report campaigns retain their original failures and cancelled
cells; no old response was reclassified. Source groups and limits remain separate.

The [plan](../plans/e2e-simplification.md) defines scope and deferred work; the
[historical matrix](live/README.md#branch-policy-matrix) retains earlier failures.
Source groups, original grades and independent review stay separate.

## Lean campaign and handoff follow-up

Frozen source `eafc6f9e` stops after its first actor, replay 007, with zero
accepted and six cells unstarted. All original stock deterministic stages pass
(driver exit 0), and independent review accepts its factual observations. Action
review fails: it requires committing the source repair on the generated CVE
branch, then separately mentions upstream landing. The conflicting mandatory
branch is unsupported; the later correct clause cannot cure it. No unsupported
historical cause remains in this reply, but that alone is insufficient.
Actor execution: 162.5 seconds, 11 turns, $0.624967 reported; no semantic-judge
calls. Original protocol, run artifacts, full review and stop receipt remain under
`.work/fix-go-cves-implementation-20261103/release/`.

The next prospective change consolidates four overlapping handoff fields into
one repair/owner field and one pending verification/prerequisite field. It explains
that each full script run starts from `origin/<branch>`; local tests remain valid
before upstream landing. This is a smaller design hypothesis, not demonstrated
behavior correction. Runtime, profiles and role-review criteria are unchanged;
reuse local evidence by exact component identity. Freeze a new source and affected
campaign before another actor. No old actor or failed campaign supplies credit.

The handoff candidate `216ea346` also stops after first replay 007: all stock
stages pass, but independent review rejects the missing observed syncer retry
pass, invented second source-repair prerequisite and unverified successful-rerun
forecast. Its source landing target is now correct. Actor: 154.0 seconds, 11
turns, $0.610560 reported; six later cells remain unstarted. Original artifacts
remain under `release-handoff-v2/` in the work directory. Neither failed campaign
supplies acceptance credit.

Transcript inspection identifies a concrete evidence-selection gap: the Skill's
prescribed grep shows failures but omits positive retries, and this actor counted
failures without reading the captured syncer pass. The next small change expands
that existing native filter to package/test passes and the retry boundary. Actual
packaged log control: 7,974 lines / 551,673 bytes reduce to 76 lines / 4,649 bytes,
including retry boundary 4050, syncer pass 6603 and package success 6606. The
original filter omits those witnesses. This supplies evidence visibility, not
proven actor correction. Runtime, profiles, criteria and review procedure stay
unchanged. Experts support one prospectively frozen affected attempt; if the
actor receives the positive witness and still invents mandatory repairs or
successful outcomes, stop paid rewording/model experiments on this approach.

## Literal default scope, after stopped verification

Source `871954cb` stops after replay 007: stock contract and all original stages
pass, but independent review rejects “Flaky; not caused by the fix.” The actor
received and accurately reported the retry pass; neither pre-update execution nor
a demonstrated causal mechanism establishes that exclusion. The source repair's
owner and upstream landing target are now supported. Six later cells remain
unstarted. Actor: 113.6 seconds, 8 turns, $0.432033 reported. Three lean attempts
total $1.667560 in reported actor cost, with no semantic-judge calls. Original
protocols, traces, reviews and stop receipts remain under `release-projection-v3/`
and its two predecessor directories in the work root.

Two experts recommend deleting default diagnosis/advice across the whole reply,
including Evidence: that is where the false claim appeared. The new default keeps
AI target-policy/check selection and authenticated completion, then quotes the
Summary/recipe, scope, complete unresolved stdlib rows and paired test outcomes.
Diagnosis and repair advice are separate requests. All seven scenarios now use
`report_scope`; required default builder-owner/backport advice is removed
prospectively, while every unsupported extra claim still fails. Historical grades
and the former 22 per-role controls are not new-scope acceptance. No paid reroll,
new grader, parser or model search validates this change. Local scope/intake
checks and a forward review can establish feasibility only; fresh behavioral and
remaining real runtime witnesses still govern production acceptance.
A fresh local Codex forward reply and separate review pass this narrower post-run
contract against the authentic 007 log. This is feasibility only, not Claude or
policy-selection acceptance. Three current-scope model-free replays and three
intake/launch/stage-failure controls pass; runtime evidence remains reusable only
where its components are unchanged.

## Direct current-runtime closure

Four direct runs use frozen `871954cb` scripts/audits, byte/mode-identical to the
runtime at `9e79eacf`, with zero model calls. Every first canonical race-enabled unit
attempt and all four audits pass. No invoking-agent acceptance is supplied.

| Case | Actual result | Required coverage |
| --- | --- | --- |
| 001 guarded | Exit 2; 7 findings remain, zero ignored, no retained changes | Both guards; tests/final scan at release base; original ref/refs/tracked bytes restored; 23 checks |
| 002 repair | Exit 0; 7 findings cleared; retained `5babbe4` | x/net 0.62.0 repair, tests/audits and clean final scan at retained HEAD; 24 checks |
| 003 native devel | Exit 2; 14/15 rows cleared; retained `a1d9561` | Initial/final native proof, tests/license/audits/final scan; 32 checks |
| 004 native release | Exit 2; 19/20 rows cleared; retained `4af7183` | Both guards, initial/final native proof, tests/license/audits/final scan; 34 checks |

Native cases retain the unsupported stdlib finding: builder Go 1.26.9 versus
published 1.26.10/1.27.3 fixes. Finding rows can repeat advisory IDs: 003 clears
9/10 IDs, 004 clears 12/13. 004 exercises the existing bounded grpc rollback/retry
from rejected 1.83.1 through restored 1.82.1 to verified 1.83.2, without an operator
rerun. Published crypto fixes also remove stale ignores.

Independent experts checked raw scans, canonical logs, source identities, receipts,
checkout preservation and all 267 evidence-file hashes. Native FINAL ELF bytes,
139 Go metadata lines, clean VCS, Linux/amd64 and catalog/file hashes agree.
Initial bytes are not retained; archived initial build/catalog/witness proof is.
Build/license are unconfigured in 001/002. Local origins withhold GitHub recipes.
Per-case records, independent audits and `direct-runtime-summary.json` remain in
`.work/fix-go-cves-implementation-20261103/`. A prelaunch identity stop invoked no
engine. Authenticated worker teardown exits 0; owned processes/socket are gone,
while default Docker context, unrelated daemons, checkouts/evidence/cache remain.

## Final fixed acceptance disposition

The source `862542fe` protocol executes only `literal-acceptance-replay007-20261103-01`.
All original stock stages complete, deterministic contract true and driver exit 0.
Independent review fails the whole reply: it adds an unsupported “flaky race
condition” diagnosis, other compile/vet interpretation, rewritten diagnostic
quotations and paraphrased outcomes despite the new literal-report boundary.
The complete Summary/exit is exact; observed fail/fail versus fail/pass, unknown
native coverage, absent recipe, one launch and read-only operations are supported.
Correct content does not offset the defect. This is not a parser/provider error.

The actor takes 111.2 seconds and reports $0.53139775. The four post-simplification
actor attempts total $2.19895775 reported, with zero semantic-judge calls; earlier
failed grading remains separately unpriced. Publication 002 and the native-report
component are cancelled before any model call. Native component preparation is
model-free and supplies no acceptance credit. No candidate rewording, reroll or
model search follows this stop. Frozen protocol, original artifacts, independent
review and `stop-receipt.json` remain in `literal-acceptance/` under the work root.

Policy-component reuse binds actual C20 policy reads/intake/launches and pins to
current unchanged instruction portions. Normal configured guards/unit forwarding
are observed; conflicting inherited settings have focused local forward-review
coverage, not new Claude empirical proof. The fresh replay read only a workflow
prefix; this limits intake coverage and does not by itself demonstrate a wrong
selected setting. No complete autonomous-policy reliability claim is made.

Final expert challenge recommends reviewing an artifact-delivery boundary: expose
the existing authenticated log/Summary directly and remove model transcription
from the product handoff. Verify the existing interface can deliver that record
independently. Calling a log authoritative while retaining false assistant prose
is insufficient. Add no formatter, claim parser or nested reviewer. Keep PR 809
draft and production blocked until a concrete reviewed delivery change has its
own required evidence; no further paid prompt tuning is selected.

## Delivery interface probes, 2026-11-03

Three independent design/testing reviews recommend retaining AI policy selection
and delivering existing runtime artifacts independently of model narration, where
the supported interface permits it. Native003's LOG is 499,594 bytes; its
1,704-byte Summary has scope, attempts, checks and publication status, but omits
the raw stdlib row's second fix alternative, 1.27.3. The whole LOG already retains
it. This is artifact-content evidence, not proof of delivery or actor acceptance.

Ten offline print-mode cases use the actual Claude Code 2.1.317 executable, SHA256
`eb224419e344575faa4a1f39b290b649425a10cd5ee2ef1d003480cd9ae57eb0`,
with fixed localhost SSE responses in isolated user/network namespaces containing
only loopback/no outbound route. Literal private environments use dummy
credentials. Real provider/model usage and CVE-engine runs are **zero**; native
cost/token fields derive from synthetic fixture usage and are not billable usage.

- Successful foreground PostToolUse stops suppress the next request but leave
  the ordinary print result empty, without the artifact. Foreground exit 2
  dispatches the registered PostToolUseFailure handler yet continues to the
  synthetic bad final.
- Both background variants resume generation from queued completion after a
  stopped result, including one whose hook waits for the terminal marker first.
  Hook-error and malformed-output controls also continue despite configured
  `onFailure:block`; the latter does not establish a JSON-parser failure. A matcher
  miss never dispatches. The no-hook control generates the expected synthetic
  bad reply.
- A synchronous Stop-owned fixture runs after one planning request with no later
  model request. Its real shell job exits 2 and writes the owned log. Native CLI
  exits 0, reports `stop_hook_prevented`/`is_error:false`, retains planning JSON as
  its final result, and omits the runtime artifact. This proves a narrow execution
  primitive, not complete delivery or engine-status propagation.

One separate bounded interactive PTY attempt exits at startup connectivity
validation before any local message request or hook. Interactive rendering,
`--include-hook-events`, real skill activation, subsequent turns and cancellation
remain unverified. All fixture servers/processes ended; cleanup receipts report
no surviving owned processes. No runtime/skill changes or paid reruns followed.

Receipts, raw requests/output, source hashes, independent hook challenge and
artifact checks remain under `.work/fix-go-cves-reliability-20261103/`, including
`native-hook-proof/{completion,completion-stop}.json` and its two cleanup
receipts. Official [hooks](https://code.claude.com/docs/en/hooks),
[skills](https://code.claude.com/docs/en/skills) and
[programmatic-use](https://code.claude.com/docs/en/headless) references informed
capability discovery; the pinned native traces establish the observations above.
The [next design steps](../plans/e2e-simplification.md#next-design-and-reliability-work)
require supported-interface proof before implementation or paid actor measurement.
Production acceptance and every original failed grade remain unchanged.

## Native artifact delivery implementation, 2026-11-03

The follow-up proves the actual interface rather than adding another reporting
prompt. A private onboarding fixture reaches native interactive Skill activation
without real credentials. Interactive Stop and successful PostToolUse callbacks
display the owned LOG path and original engine exit. Headless
`--include-hook-events` exposes the exact decision in `system/hook_response`;
ordinary final-result-only output remains insufficient. False initial assistant
text remains visible alongside the artifact and still fails factual acceptance.

The selected implementation prepares private arguments/settings as data, validates
the actual native call, exclusively consumes its request and runs existing engines
serially. The hook delivers original logs/exits without model log intake, polling
or transcription. Codex retains direct execution and log/status return; these
native proofs make no Codex model-compliance claim. No renderer, executable
request, queue, nested model or semantic grader was added. Historical frozen
graders remain; obsolete model-copy parsing is removed from the current evaluator.

Final helper SHA256 is
`142f33a19e6b29d9122d5fbf71f6c05af07824530bf7ade781709be8f9842641`;
Skill SHA256 is
`77ff7c79305399359d6776dd11878f9b67318f1c27e71420b65a483051010fb9`.
Five exact-source native controls cover persistent-hook policy-read/no-op,
distinct-setting serial fix0/report2, later unrelated Bash, missing activation,
headless delivery and retained false earlier text. A two-second prepare-tool
budget permits a callback running over three seconds. Native Ctrl-C stops the
owned engine before operator teardown and leaves the next batch job unreached;
its partial log has no completion marker. The interrupted UI hides artifact/status,
so that path remains unconfirmed, not accepted completed delivery. The four-hour
header is accepted configuration, not an empirically measured four-hour timeout.

Independent source review approves the bounded helper and passes all 18 behavioral
controls, including rollback grace, duplicates, changed/linked requests, exclusive
claim ownership, original exits and unrelated-process preservation. Full current
runtime verification passes 3,135 shell checks and 91 Python tests. All 16 prior
engine/audit files retain their bytes/modes; no new real-engine or actor acceptance
is supplied by these transport controls alone.

The fresh native-boundary integration separately passes its frozen contract and
successful-repair requirements: Admiral `af20d0bf` to retained `16af5af1`, x/net
0.62.0 clears seven findings, first canonical race-enabled unit attempt passes
all 19 packages, four audits pass, and the authoritative final scan is clean at
the retained/tested HEAD. Original engine exit 0 is delivered after 124.2 seconds,
with one localhost request and no postruntime request. Build/license remain
unconfigured and native coverage unverified. Independent raw/native/source review
passes; `real-engine/` retains the frozen protocol, receipts and evidence ledger.
Authenticated worker teardown exits 0, preserves old retained checkouts/default
Docker configuration/cache, and leaves no owned daemon/socket.

The simplified evaluator passes 75 helper tests and 27 shared-runner tests.
Actual native traces also pass runner-to-extraction composition with empty
`hook_stopped` results and retained earlier false text. Removed legacy copying
parsers and their Markdown dependency remain available in old frozen runs only.

Original controls, fixture misses, intermediate source groups and final identities
remain under `.work/fix-go-cves-delivery-20261103/`. `source-final142-audit.json`
binds the five final controls and cleanup; `independent-code-audit.md` records the
separate review. Those final controls use 13 localhost synthetic messages, zero
real inference; all owned processes/servers ended. Earlier capability probes and
their synthetic cost fields remain separate.

The unchanged `9e79eacf` source completes the prospectively frozen two-actor
protocol on CLI 2.1.317 / Opus 4.6 / requested max effort / Vertex:

| Actor | Original stock and independent review | Reported cost / duration |
| --- | --- | --- |
| `artifact-acceptance-replay007-20261103-01` | Both pass; guards true/true, `make unit`, complete original log/exit2, earlier text supported, no postruntime generation | $0.34514825 / 101.3s |
| `artifact-acceptance-publication002-20261103-01` | Both pass; same correct policy forwarding, complete recipe/stdlib alternatives and original exit2, no extra report | $0.34286850 / 74.8s |

Both original drivers exit 0, stock stages complete and regressions are zero.
The independent procedure first rejects the preserved unsupported-cause control
and accepts the artifact-only transport control without claiming CVE repair.
Every prior assistant text block remains reviewable; none is hidden by extraction.
Complete artifact bytes match the frozen recordings after prescribed path
substitutions and original wrapper-status handling. Source, private identities,
policy expectations and native init versions agree. Selected guards are forwarding
evidence; the historical engine's recorded upgrade is not current guard-enforcement
proof. Four unchanged-engine cases supply their own separate runtime evidence.

Total reported Claude actor cost is **$0.68801675**, with **zero semantic judges**.
No further Claude actors are selected. The frozen protocol, independent policy
expectations, admissions, original stock artifacts, reviews and exclusive completion
receipts remain in `acceptance/` under the same work root. This closes the bounded
default acceptance; it supplies no all-time guarantee or new historical native proof.

One separate independent Codex forward check also passes the retained direct path
over a fresh recorded case: one invocation, both guards true, `make unit`, clean
retained state and complete original log, returning only its actual link and exit2.
`acceptance/codex-forward-review.json` records the checks. It uses no additional
Claude calls and supplies forward feasibility, not native Codex frontend acceptance.

## Review-readiness follow-up, 2026-11-03

Local repair reconciles successful verification outcomes before classifying
stale failure/timeout markers. Main-loop transient package blockers are deferred
until that package/scope's surviving outcome is known; earlier build, policy and
other global blockers are never reset. Authoritative policy markers block
independently of whether their diagnostic text is already present. Test-result
classification checks the retry log for disk exhaustion while retaining both
attempts' actual exits/logs.
The maintained focused sections pass 65/65 assertions; the original runtime
passes 53/65 with twelve expected distinguishing failures. Independent review
approves the bounded runtime/docs diff. Full integration passes 3,267/3,267 shell
checks, 70/70 runtime Python tests and 86/86 eval-helper tests. All three
model-free replays pass with their expected historical outcomes. Repository lint
and strict site build pass. Raw suite logs and receipts remain under
`.work/fix-go-cves-readiness-20261103/validation/`.

The current source passes the model-free identity audit for all 117 retained
O51/A66 calibration samples and unchanged grading components. All 56 complete
mocked requests for the admitted O17/A39 contexts match their recorded hashes
with the actor override selected; no HTTP/model calls are made. This is component
evidence only; new actor replies require their own grading and whole-reply review.

The old pinned CLI 2.1.307 executable is absent. The follow-up explicitly pins
2.1.317 as a changed environment. An initial CLI probe stopped at local MCP-config
validation before native init. A separately declared corrected-config probe exited
0 on Opus 4.8 with requested `max` effort, successful Read/Bash results and no
denials/provider errors. Reported cost is $0.07892. Its original automated verdict
remains false because the final answer included spaces around the exact delimiter.
Independent raw-evidence review supports only the narrower CLI/model/tool
capability facts; it does not turn that verdict into a pass or establish internal
effort allocation, calibration, CVE behavior or live-runtime coverage. No formatting
rerun was made. The protocols, raw attempts and independent review remain under
`.work/fix-go-cves-readiness-20261103/`.

The declared source `d8455b08` uses Opus 4.8 on that pinned CLI, with existing
judge models, caps, thresholds and eleven-cell order. Its first publication actor
completed all original stock stages: contract true, Outcome FFF, Action/owner TTT,
six valid distinct samples, zero sample errors and original driver exit 1.
Independent whole-reply review also rejects the native-coverage claims. Exact
Summary/recipe relay, permitted operations and the core builder-owner handoff
pass. The native final assistant text and result match the extracted reply, so
this is actor content, not a CLI/parser aggregation defect.

The actor took 772.5 seconds and reported $3.02307575. Six unpriced judge calls
used 185,514 prompt tokens; total cost remains unknown. Stop after one actor,
zero accepted, before replay 007 or worker startup. The original protocol,
completion receipt, raw samples, independent review and stop record remain in
`eval-prep/` under the retained work directory. No unchanged rerun or old-actor
credit is used.

The scope-authority change at `2d67d397` adds two skill lines and fifteen words,
with no runtime, parser or rubric change. Four producer controls preserve positive
artifact/phase scope while leaving historical cataloger/finding/license observations
unverified. Its original campaign results are:

| Scope-authority actor | Original stock | Independent review |
| --- | --- | --- |
| `scope-publication002-20261103-01` | C true; O TTT; A FTT (majority true); driver 0 | Accepted: exact Summary/recipe, unverified native coverage, complete stdlib alternatives and supported builder handoff |
| `scope-replay007-20261103-01` | C true; O FFF; A TTT; driver 1 | Rejected: reporter failure called pre-existing/independent from source presence and repair availability, without a comparable captured pre-update outcome or establishing mechanism |

All twelve semantic samples are valid and error-free. Publication's false dissent
and bound reviews remain unchanged. A separate captured target-policy witness
checks go-get-induced Go/Kubernetes minor restrictions; it neither rewrites that
vote nor establishes a universal compiler-minor ban or guaranteed future scan.
Stop after two actors, one accepted, before worker startup/live execution. Original
receipts, dissent and witness remain under
`.work/fix-go-cves-readiness-20261103/eval-scope-v2/`.

Actor46-v3 froze source `8a1f78b8` with the skill unchanged and restored existing
Opus 4.6 with requested `max` effort on pinned CLI 2.1.317 for cost control, without
a model-effect, superiority or causal-repair claim. A separate tiny native probe
passes model/version and Read/Bash checks, exits 0 and reports $0.14843875; it
supplies no actor, calibration or live credit. All 56 complete mocked grader
requests match the admitted hashes, preserving conditional reuse of the 117
original O51/A66 samples; receipts are in `actor46-compatibility/` beside the
campaign records. Unchanged component tests remain applicable by identity.

| Actor46-v3 actor | Original stock | Independent review |
| --- | --- | --- |
| Publication 002 | C true; O TTF (majority true); A TTT; driver 0 | Accepted: raw-log line 679 records Dapper `make unit`, with 34 top-level `PASS` outcomes |
| Replay 007 | C true; O FFF; A TTT; driver 1 | Rejected: unsupported claim that both failures were pre-existing |

Both six-sample sets are valid and error-free. Publication's original false dissent
remains unchanged: the exact test-command line was absent from delivered tool
results, although the separate raw-log witness supports it. That projection limit
does not rewrite the vote. Replay's rejection concerns causal attribution; a flaky
label alone is permitted and is not a new gate. Stop after two actors, one accepted,
without worker startup, live execution or an unchanged reroll.

Publication reports $0.90207325 over 168.4 seconds; replay reports $0.949327 over
219.5 seconds, totaling $1.85140025 for these actors. Across this task's five actors,
reported cost is $10.08603025. Thirty unpriced judge calls used 795,753 prompt and
40,130 completion tokens; total cost remains unknown and probes are additional.
The work-root cost summary retains the aggregation and underlying receipts.

A later model-free planning control reproduced a native timeout limit: with a
0.25-second plain foreground timeout, a TERM-ignoring direct child remained alive
at the 1.5-second outer bound and required targeted cleanup. Adding the native
0.25-second kill reserve exited 137 in 0.503 seconds. Build/test/license callers
use the plain form. This is an isolated direct-child counterexample, not an
observed target-build failure, descendant/container cleanup proof or applied fix.
The receipt is `.work/fix-go-cves-simplification-plan-20261103/timeout-control.json`.

A fresh actual report/detect/scan/build/tee control also exceeded its outer bound
with `--foreground --kill-after`: a descendant retained the output pipe. Ordinary
timeout process groups with the kill reserve returned report exit 2, build exit 137
and partial logs in 0.73 seconds, with the owned processes gone. This uses a fixed
scanner, not a real scan or container-cleanup proof. Evidence:
`.work/fix-go-cves-implementation-20261103/timeout-producer-challenge.json`.

The current simplification candidate removes the unused scan, nested model
reviewer/provider/locator and legacy report conversion. Existing typed evidence
feeds existing handlers; scoped producer failures remain required until verified
repair, and another eligible ignore cannot clear their original diagnostics.
Default source-history research is request-driven. Initial display retains complete
fix alternatives without the deleted scan. One shared native command helper closes
owned descendant/pipe hangs and preserves deadline exits and partial evidence.

Focused production-path checks pass: 358 evidence/dispatch/YAML checks, 70 scoped/
mixed-ignore checks, actual phase ordering and advisory/provider-independence
controls, native report/cancellation/package rollback, and 29 test/license/cleanup/
complete-display checks. The eval-helper suite passes 86 tests. These focused
results do not supply actor acceptance. A mistaken license
expectation (137 versus Make's actual 124) is retained in the original failed
control log and corrected against actual receipts.

Current runtime source `5b2f48f9` passes 3,135/3,135 shell checks (original
session 33237, exit 0) and 73/73 runtime Python tests. The initial Python batch
exposed a fixture that omitted the newly shared deadline helper; sourcing the
actual library fixes its 19-test suite. The other 54 tests passed unchanged.
The shell suite does not load that Python fixture; all its consumed source bytes
and modes still match the launch record. Original failures and corrected logs
remain under `.work/fix-go-cves-implementation-20261103/validation/`.

The real report-only smoke runs current source on pinned Subctl `bf62ddf2` with
canonical Dapper build, real Grype 0.121.0 and the fresh database built
2026-11-03T06:20:47Z. Exit 0 in 314.8 seconds; 20 findings exactly match raw scan
rows/order. HEAD, refs, index entries, tracked bytes and policy are preserved;
private state is removed. Positive native Go 1.26.9 evidence is bound to the
clean pinned VCS and binary hash. Receipts remain under `.work/real-report-smoke/`.
This is reporting/build/scan preservation, not remediation or actor acceptance.

Fresh oracle review found missing complete repair scope in six controls. The
pinned unfiltered patch was added without changing the original hold artifacts.
Separately admitted V2 then executed only the first 21 of 66 planned calls:
seven Outcome controls, all responses valid/error-free with distinct IDs, six
expected majorities matched. False control 108 was accepted TTT. The producer
and log place the Go directive increase before tidy; all three rationales notice
that fact but excuse the false attribution to tidy as a combined upgrade flow.
The label stays false. This is a failed oracle, not absent evidence or parse error.

The remaining 45 calls were cancelled. Original stock exit 1, summaries, sample
rationales and append-only receipt-reader/provenance corrections remain under
`current-annotation-calibration-v2/` in the work directory. The 21 calls used
658,674 input and 27,537 output tokens; prices/total cost are unknown. No actor
ran and no past grade changes. Independent oracle/release experts recommend
prospectively deleting duplicate semantic judges and retaining stock contracts
plus one whole-reply review, checked first against the fixed role-specific controls.
The fresh prospective profiles resolve through the actual harness loader to one
deterministic contract each, with no semantic prompt judge. Current eval-helper
suite passes 86/86 (106.4 seconds); all three model-free replays pass with their
expected historical results. Exact staged-tree lint has zero errors/warnings and
strict site build passes. A root-directory lint attempt included an unrelated
ignored worktree and failed; the exported tracked tree is the review candidate.

Three fresh reviewers, blind to expected labels and prior rationales, match all
22 fixed per-role controls: Outcome 7, replay Action 9 and live Action 6. False
108 is rejected and corrected 109 accepted. Outcome-positive 105 remains
Action-negative, so no per-role positive is treated as whole acceptance. The
retained forward handoff also supplies a supported investigation/repair and
landing prerequisite, without unsupported pre-existing attribution; it is a local
Codex feasibility check, not a fresh Claude actor or efficiency measurement.
Reviews and identities remain under `independent-review/` in the work directory.

Model-free canonical preflights retain actionable findings at the existing live
pins: Admiral 7 x/net findings and Subctl devel 15 findings with positive native
proof; release retains 20 findings. No pins or findings were fabricated. Compiler
compatibility supports proceeding, without predicting build/test success. Both
native scenarios still need real INITIAL and FINAL fix-phase witnesses. See
`live-preflight/`. The [production plan](../plans/e2e-simplification.md) owns that
changed gate and remaining measurements; automatic contract exit 0 alone is
insufficient.

## Current implementation, 2026-10-24

Earlier implementation from `8c88928b` passed component integration. Current v5
verification incorporates the license ownership and LF-reader fixes below; v4
passes remain historical evidence. Historical actor grades are unchanged.

| Changed boundary | Measured evidence |
| --- | --- |
| Frozen execution and authority | 86 eval tests pass; current model-free 005/007/002 prepare/replay passes with expected historical results |
| Shared lifecycle and aggregation | 362 lifecycle/configuration checks remain applicable by identity; 429 scoring/provider/agent/pairwise checks pass in 2.88 seconds, including artifact guards, invalid-response metadata and genuine-false controls |
| Physical Go metadata | Seven actual local-proxy transaction controls passed on Go 1.24 and 1.26 |
| Artifact ownership and scan consumer | 19 focused tests pass in 4.699 seconds, including actual license producer and native Unicode consumer controls; original counterexamples preserved |
| Cleanup / report preservation | Six / seven actual-producer controls; old report producer reproduces failures |
| Policy / publication | 15 semantic reader controls; 16 real-Git recipe controls; 182 workflow checks |
| Dispatch / final evidence | 90 assertions across 14 capture cases; 473 final-evidence workflow checks |
| Earlier combined integration | 3,207/3,207 frozen shell checks with all 28 runtime/subagent/test files matching that snapshot. Frozen Python suite: 66/66 before one additional publication control, separately verified. V4: 3,207 shell and 69 Python tests passed; later Unicode counterexamples prevent treating v4 as current closure. |
| Current v5 integration | 3,207/3,207 frozen shell checks pass (exit 0); all 28 runtime/subagent/test files match current bytes/modes. Python: 70/70 in 23.062 seconds. Receipt: `combined-runtime-v5-verification.json`. |
| Action calibration evidence | V6: 20/20 expected majorities, 60/60 samples, zero errors. All 18 V5 inputs/labels remain unchanged; two added controls isolate the whole-commit alternative. Prior failures and limits: [calibration record](live/calibration.md). |

Simplification removes the separate reporting reference/publication profile,
replaces duplicate policy readers with the existing semantic loader, and uses one
final canonical test phase. Native Go file binding replaces the proposed effective-
path query system. Publication uses an explicit confirmed Git route. No supervisor,
transaction service, generic flag/shell parser or new policy serializer was added.

A fresh critical review reproduced a surviving owned CLI when group signaling
raises an OS error. The small direct-child fallback passes the new stalled-leader
control; removing it reproduces failure. Partial output/settings cleanup and an
unrelated sentinel remain checked. Descendant termination when group signaling
fails is not guaranteed.

| New pilot | Original stock result | Independent result |
| --- | --- | --- |
| `e2e-simplified-replay005-20261023-01` | C true, O TTT false positive, A FFF; actor $0.69 | O/A false: unsupported independence, missing native uncertainty, fix-branch-only repair and promised clean rerun |
| `e2e-inference-replay005-20261023-01` | C true, O FFF, A TTT; actor $0.83 | O false solely missing native uncertainty; A true. All other factual claims independently verified. |
| `e2e-scope-replay005-20261023-01` | C true, O FFF, A TTT; actor $0.87 | O false: 16 other passing packages claimed versus 17 recorded, plus wrong tidy attribution. Separate rerun-owner ambiguity retained. |
| `e2e-handoff-replay005-20261023-01` | C/O/A true, O/A TTT; actor $0.75 | O false: directive upgrade attributed to tidy despite the producer observing it before tidy. A true. |
| `e2e-actionable-replay005-20261023-01` | C true, O FFF, A TTT; actor $0.81 | O false: wrong tidy attribution and missing compiled-binary coverage limitation. A true. |
| `e2e-concrete-replay005-20261023-01` | C/O/A true, O/A TTT; actor $0.82 | A true; O not fully certified because added no-scan/no-compilation claims exceed the receipts. No opposite unknown facts invented. |
| `e2e-relay-replay005-20261023-01` | C false (literal Summary), O/A TTT; actor $0.74 | Exact Summary was blockquoted; separate unsupported vet/transitive-dependency explanation prevents acceptance. A true. |
| `e2e-final-relay-replay005-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.67 | C8 first accepted 005: O/A true after primary-evidence adjudication; original null review and stock grades retained |
| `e2e-final-relay-replay007-20261023-01` | C false (missing `8234df0`), O/A FFF, zero sample errors; actor $0.77 | O/A false: unsupported independence, wrong Go 1.25 explanation, missing existing repair commit and promised clean rerun/recipe; C8 stopped |
| `e2e-compact-relay-replay007-20261023-01` | C true, O FFF, A TTT, zero sample errors; actor $0.72 | C9 stopped: operational/A true, O false for unsupported syncer independence and reporter-predates claims; existing repair commit and all attempt outcomes correct |
| `e2e-observed-actions-replay007-20261023-01` | C true, O true (2/3), A TTT, zero sample errors; actor $0.75 | C10 individual pass: independent O/A and operations true; original dissent retained |
| `e2e-observed-actions-replay005-20261023-01` | C true, O true (2/3), A TTT, zero sample errors; actor $0.50 | C10 individual pass: independent O/A and operations true; original dissent retained |
| `e2e-observed-actions-publication002-20261023-01` | C false, O FFF, A TTT, zero sample errors; actor $0.70 | C10 stopped: independent O false, A/operations true; exact Summary followed by a duplicate rewritten recipe, missing native uncertainty and unsupported coverage |
| `e2e-scope-recipe-publication002-20261023-01` | C false, O FFF, A TTT, zero sample errors; actor $0.79 | C11 stopped after one actor: independent O false, A/operations true; exact Summary/native uncertainty and 34 test measurements verify, but a second equivalent-argv rewritten recipe fails strict relay |
| `e2e-stage-read-publication002-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.74 | C12 replay pass; exact recipe once, native uncertainty, measured facts and image-publication prerequisite verify. Effective guard forwarding remains unverified, without inferring false guards. |
| `e2e-stage-read-replay007-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.78 | C12 replay pass; independent O/A true, both attempts and origin repair prerequisite retained |
| `e2e-stage-read-replay005-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.61 | C12 replay pass; independent O/A true, single attempt and origin repair prerequisite retained |
| `e2e-stage-read-live001-20261023-01` | C true, O TTT, A FFT, zero sample errors; actor $0.62 | C12 stopped: runtime/O true, independent A false for fixable-finding ignore advice and promised compilation; original A majority rejects on an unsupported reporter-backport requirement |
| `e2e-policy-boundary-live001-20261023-01` | C true, O FFF, A TTT, zero sample errors; actor $1.43 | C13 stopped: independent runtime 29/29 and A true, O false; quoted certificate 1.052s/57.5% contradicts actual 20.059s/89.1% |
| `e2e-summary-tests-live001-20261023-01` | C true, O TTT, A FTF, zero sample errors; actor $1.44 | C14 stopped: independent runtime 27/27 and O true, A false for a tentative compilation forecast from version; same-result caveat genuine, dissent retained |
| `e2e-prerequisite-only-live001-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.71 | C15 stopped: independent runtime 27/27 and O true, A false; full candidate adds a Kubernetes-minor migration without approval, while the standalone Go option is valid |
| `e2e-commit-scope-live001-20261023-01` | C true, O/A TTT, zero sample errors; driver 0 | C16 individual pass: independent runtime 29/29, 52 evidence hashes and whole-reply O/A pass |
| `e2e-commit-scope-publication002-20261023-01` | C true, O TTT, A FFF, zero sample errors; driver 1 | C16 stopped after two actors: independent O/operations true, A false for an unobserved full-fix forecast; exact Summary/recipe and native uncertainty pass |
| C17 `e2e-verification-pending-…-20261024-01`: publication002, live001, replay007, replay005 | Each C true, O/A TTT, zero sample errors | Four individual passes; 007 accepted by separate contextual adjudication with original independent O-false review retained; 005 uses the bounded C8 Go-requirement reading |
| `e2e-verification-pending-live002-20261024-01` | C true, O TTT, A FFF, zero sample errors; driver 1 | C17 stopped before live 003: actual repair 18/18, integrity 22/22 and 51 hashes pass; independent O true, A false only for added unprinted push/PR prose |

Complete actual skill intake was confirmed for the prior pilots, all three C10
actors, C11 publication 002 and C12–C17. Earlier campaigns remain separate; no failed actor is pooled
into a revised source. Current guidance quotes runtime
observations and failed/later-attempt outcomes, then allows only supported future
actions, owners and verification prerequisites. Default-branch repair-commit
search and direct target-origin policy reads remain required. The
bounded archived-producer witness now exposes the known tidy error to judges;
original recordings, prompts, thresholds and old grades remain unchanged. V7/V8 preserved false positives despite the producer witness and a named-command
criterion. A request-boundary audit verified complete serialized input, expected
model and absence of local cache/truncation. V9 replaces holistic assessment with
a factual-error audit of complete claim/evidence relationships: 18/18 expected
majorities across 54 calls, zero execution errors, one citation dissent. Original
failed grades remain unchanged. The current actor source clarifies compiled Go
binary coverage and defaults to reporting observed state without guessing an
uncaptured producing command.

C8's first 005 initially retained a null independent outcome for the phrase
"pulled in Go 1.26 toolchain." Separate primary verification supports the minimum
Go requirement reading: x/net v0.60.0 requires Go 1.26, the captured update raises
the directive, and Go 1.26's interface-method printf inference is gated on that
directive. This matches the failing `Basic.Failure` call even with the same
installed builder. Actual compiler installation/selection history stays unknown;
the reply does not claim a download or switch. Primary verification and the
resolution addendum accept O/A without new judging or changed criteria. The
original null review and stock sample rationales, including their unsupported
tidy attribution, remain unchanged. Receipts are
`final-relay005-pilot01-{independent-review,c8-primary-adjudication,adjudication-addendum,stock-completion}.json`
under `.work/fix-go-cves-e2e-20261023/`. This accepts one replay cell, not the full
cohort or general reliability.

A valid Markdown quote envelope exposed a separate checker defect. A shared
CommonMark extractor now decodes quote/list/indented code containers for Summary
and recipe checks while preserving literal content, including `>` operators.
Counts, exits, recipe values and duplicate/invented commands still reject. The
earlier 83-test suite passed; parser version 4.2.0 remains explicit in setup and
preflight. A three-line correction now aligns source indices with CommonMark
CR/LF normalization instead of Python Unicode `splitlines`, using the same parser.
Before correction, all three LF/CRLF/CR positive controls failed; afterward all
accept and reject an appended invented push. One 12-line regression covers both
boundaries; that 84-test snapshot passed in 49.570 seconds. Snapshot helper SHA-256:
`c41e6916cc7cdb076ca634408be0c59b21b7a80fe65e50f8320817337519c001`.
The earlier model-free 005/007/002 smoke exited 0, exercised driver preflight and
retained `aa5a4fc`/`aaaeea3`/`2716c2ff`, each with historical runtime exit 2.
Original artifacts and grades remain immutable; that smoke supplied no actor credit.

C10 publication 002 omitted native uncertainty and asserted unsupported coverage.
C11 corrected that distinction, preserved the full Summary through `exit=2`, and
accurately quoted all 34 passing package measurements and nine advisory rows.
Both added a second rewritten recipe with equivalent argv and target. The strict
literal guard intentionally rejects that relay/instruction/bloat failure; no unsafe
command, changed target or invented argument difference is asserted. Supported
Shipyard ownership, published Go 1.26.9 image prerequisite and rerun with unverified
outcome keep A true. Both original drivers exited 1 after all stages and six samples
completed without errors. Original independent/stock receipts remain under
`.work/fix-go-cves-e2e-20261023/{observed-actions,scope-recipe}-publication002-pilot01-*.json`;
the independent receipts retain their narrower process-exit observation boundaries.

C12's three replays passed under frozen source `52863d9d`. Actual loaded-section
rereads were observed with later read-only inspections; neither a last-tool gate
nor reread efficacy is established. Publication's effective guard environment
remains unverified: retained snapshot directories were empty, and omitted launch
assignments do not prove false guards. Live 001 separately authenticated both
guards true.

The live 001 engine completed in 139 seconds with exit 2: five actionable findings
remained blocked, one canonical `make unit` and all four audits passed, no build or
license was configured, no commits remained, and original `devel` was restored.
Archived runtime/evidence identities and quoted outcomes verify. Independent A
rejects advice to ignore findings with published fixes and the promise that the
proposed update "will compile" based only on builder version. The manual branch
workflow does discuss compatibility ignores, but the invoked skill permits only
no-fix ignores. No ignore was executed. Original A labels FFT are preserved: the
two rejecting rationales wrongly demand a reporter backport despite passing tests;
the passing sample misses the selected ignore policy and unsupported prediction.
Receipts remain under `.work/fix-go-cves-e2e-20261023/stage-read*-{independent-review,stock-completion}.json`.

The C13 skill and action criteria preserve
no-fix-only ignores and treat compiler compatibility as a prerequisite, with
proposed build/test/rerun outcomes unverified. Policy V2 and method V3 calibration
both falsely accept isolated prediction control 104 with TTT; neither starts its
conditional replay arm. Their original failures remain in the
[calibration record](live/calibration.md). Prediction V4 passed live controls but
rejected replay positives 102/103 with FFF: rationales turned supported syncer
investigation with a named owner into a required blocker from its table placement,
without an actual verification prerequisite. No control was relabeled or retried
unchanged. V5 shortens the method and distinguishes supported advice from an
asserted prerequisite; all 54 samples match their 18 fixed labels, including the
new paired blocker negative. Component checks above remain evidence only for
unchanged bytes; no actor or historical rescoring credit follows from calibration.
C13 then stopped after its first live 001 at frozen `975e0661`. Its engine took
155 seconds, exited 2 with five policy-blocked findings, passed canonical tests
and all audits, and restored the original checkout without commits. Independent
runtime checks pass, including both guards; advice keeps policy approval separate
from future verification without promising its outcome. But the reply quotes certificate
`1.052s`/`57.5%` instead of the actual `20.059s`/`89.1%`. The wrong values do not
appear in any authenticated captured log; their origin remains unknown. This is
a response accuracy failure, not a failed engineering gate. Original stages,
samples and the independent review remain under `c13-live001*` in the scratch root.

C14 at frozen `2a3c1b27` omitted redundant successful-package measurements;
its factual reporting passed in this cell. The actor took 268 seconds; the engine
completed a 143-second blocked exit 2 with canonical tests/audits passing, both
guards enabled and no commits. Original contract/outcome pass, A samples are FTF,
and the driver exits 1. Independent runtime and outcome
pass, A fails for "Go 1.26.9, so compilation is expected to succeed." A genuine
caveat leaves the same build/test/scan outcome uncertain; it does not establish
support for the version-to-compilation forecast. This was not a guarantee,
executed-success claim or uncaveated prediction. The rejecting majority applies
that exact boundary; the dissent waives the forecast because of the caveat.
Original artifacts and reviews remain under `c14-live001*` in the scratch root.

C15's original driver exited 0 after all stages and samples completed without
errors. The actor took 261.8 seconds; its 147-second engine run remained blocked
at exit 2, passed canonical tests/audits, retained no commits, and canceled its
wakeup. Independent runtime and outcome pass; action/owner fails the alternative
"cherry-picking `2d9f5fb` or a standalone go directive bump." The complete candidate
raises Kubernetes dependencies from 0.35.5 to 0.36.2 against release 0.35.8; only
Go approval was discussed. The standalone option is valid, but does not excuse
the bundled migration's missing decision. Nothing was migrated and no API failure
is asserted. The third passing A sample notices possible broader Kubernetes scope
then excuses it because the standalone option is also offered. Preserve that
false positive and all original rationales under `c15-live001*` in the scratch root.

C16 at `b538f2f9` stopped after two actors. Live 001 passed original thresholds and
independent runtime/whole-reply review: its 145-second runtime remained blocked at
exit 2, passed canonical tests/audits and retained no commits. The actor took
282.5 seconds/$0.737293; its driver exited 0. Publication 002 took 137 seconds/
$0.70137175; its driver exited 1 after all stages. The exact Summary and recipe,
native uncertainty, Shipyard owner and published-image prerequisite verify.
“Should clear” is tentative, not itself a guarantee; “the partial PR becomes a
full fix” asserts an unobserved rerun outcome. Original samples and independent
receipts remain under `c16-{live001,publication002}*` in the scratch root.

C17 at `c380f639` stopped at its fifth actor, live 002. The 105-second engine run
exited 0, retained `7c793d9` with x/net v0.59.0 → v0.60.0 fixing five findings,
passed canonical tests/four audits and had no final findings. The actor took
180.7 seconds/$0.465941; root captured driver 31442 exit 1 after all stages.
No recipe was printed because a GitHub base and single push destination could not
be confirmed. A file-backed local fork exists; this is not evidence of a missing
fork. Added advice to push and run `gh pr create` targeting devel fails A; no
publication was executed. Original samples and reviews remain under `c17-*`.

The first four C17 cells remain individually accepted. For 007, separate
contextual adjudication reads “the CVE fix commit is sound” as the observed
five-advisory remedy, bounded by explicit failed tests, not-ready status and
pending verification. The original independent O-false review remains; this does
not certify integration or causal independence. For 005, the C8 minimum-Go
requirement reading applies; actual compiler installation/selection stays unknown.
Incidental stock rationales attributing the directive change to tidy are retained
but not adopted: the reply does not make that claim.

C18 at `75c4f574` replaced two skill publication lines with three: relay any
recipe once, otherwise report absence and the printed reason without adding
push/PR steps for the reported CVE branch. Live 002 passed original C/O/A, all six
semantic samples, zero errors and driver 93139 exit 0. Its 127-second actual
runtime fixed all five x/net findings, retained `5d06507`, passed canonical
race-enabled tests/four audits and finished with no findings. The actor took
206.4 seconds/$1.319529; six semantic calls remain unpriced. Independent review
passed 18 scenario/22 integrity checks and 51 evidence hashes. Native coverage
remains unverified; this is a dependency-repair result. Receipts are `c18-live002*`
in the scratch root. No replacement publication instructions were supplied.

C18 stopped before a second actor after a model-free validator counterexample:
with otherwise-valid native evidence, wrong GOOS, wrong GOARCH and absent target
fields all passed. `native-target-before-control.json` preserves those results.
This is a validator assurance gap, not an observed wrong actual binary. The narrow
correction parses existing build metadata and requires exactly one Linux/amd64
pair. Five focused tests pass; the full 86-test helper suite passes in 71.170
seconds. Controls cover wrong/missing/duplicate fields in both phases and accept
reversed order. No schema, runtime or semantic-prompt change is needed.

C19 at `e116154a` corrected only native GOOS/GOARCH validation. Its first three
actors passed original C/O/A, all eighteen semantic samples, zero errors and
independent review:

| C19 cell | Actual runtime | Actor | Root driver |
| --- | --- | --- | --- |
| Live 002 | 109s, exit 0; five findings cleared, retained `fc85774`, canonical race/tests/four audits passed | 222.0s / $1.00401775 | 95491, exit 0 |
| Publication 002 | Historical partial-repair replay; exact recipe, builder owner/publication prerequisite, native unknown | 152.1s / $0.76234175 | 62026, exit 0 |
| Live 001 | 131s, guarded exit 2; five unresolved, canonical tests/four audits passed, no commits, original ref restored | 272.5s / $0.74891875 | 93625, exit 0 |

Live 001's tentative five-finding remedy expectation is supported by fixed-in
v0.60.0; it does not promise compilation, whole-test/native coverage or whole-run
success. Initial independent concern and contextual adjudication remain in its
review. Publication's pending verification goal likewise does not predict a clean
rerun. A separate note rejects compensatory wording in two passing judge rationales;
correct advice elsewhere cannot excuse an actual unsupported claim.

C19 stopped at fourth actor replay 007-01. Original C=true, O=FFF, A=TTT, zero
errors; all original stages finished and root driver 7711 exited 1. The actor took
137.0s/$0.5767225. All outcome samples correctly reject “not a regression”; the
additional “not caused by” x/net assertion is also unsupported. Source presence
and a passing retry establish neither independence. Intake, evidence, operations
and complete reporter repair scope pass. The initial independent action review
rejects “tests should pass” as an unexecuted whole-suite forecast; original samples
accept it as a tentative expectation based on the specific repair and passing
retry. Root and two secondary expert reviews accept that bounded A=true reading;
the original A=false dissent remains. No verified test success or independence is
certified. A separate `c19-replay007-01-contextual-adjudication.json` binds the
original dissent and unchanged grades. The outcome failure is decisive.
Receipts and original rationales remain under `c19-*` in the scratch root. No later
C19 actor ran. Six semantic samples per cell remain unpriced; physical retries and
total cost are unknown.

C20 at `ed31ff2a` consolidated output guidance, net one line. Its first replay 007
still inserted an “Unresolved work” paragraph asserting the reporter failure was
not caused by x/net because the source file was unchanged. Original C=false,
O=FFF, A=TTT, zero errors; all stages completed and root driver 43927 exited 1.
The actor took 165.6s/$0.871992. Independent outcome rejects the same unsupported
independence; action/owner passes with correct scoped repair, roles, origin landing
and verification pending. No later C20 actor ran.

The formal contract rejection concerns a denied comment + `git stash list` +
`git show` compound. The commands are read-only in intent/effect; the existing
exact inventory allowance conservatively rejects mixed forms. Preserve that result
and known trace limitation without claiming executed mutation or publication.
Receipts are `c20-replay007-01-{independent-review,stock-completion}.json` in the
scratch root. Original labels/rationales/errors/usage and all six sample IDs remain.
Semantic samples are unpriced; physical retries and total cost remain unknown.

C21 at `050c7715` replaced section 4 with investigation followed by a closed
report: runtime quotation, evidence quotations, then supported next actions and
pending verification. It was three lines shorter than C20; no format grading gate
was added. First replay 007 passed original C/O/A, all six semantic samples, zero
errors and independent review (161.4s/$0.82707075; root 65250 exit 0).

Real live 002 also passed original C/O/A and all six valid samples plus independent
review (291.3s/$1.680468; root 19841 exit 0). Its 179-second actual repair cleared
five findings and retained `e99fc00`. The first `make unit` exited 2 after a
workqueue data race despite 21 passing Ginkgo specs; the single built-in retry
exited 0 on the same HEAD. Both attempts and exact diagnostics/timings/coverage
were preserved and reported; no causal exoneration or extra task was invented.
Four audits/final scan passed. Native coverage stays unverified. Review checked
18 repair/22 integrity conditions and 53 evidence hashes.

C21 stopped at third actor publication 002. Original C=true, O values T/T/F with
a reported majority true, A=FFF; root 89080 exited 1 after all reported stages.
The actor took 203.7s/$0.87258575. The final false O value is not a semantic verdict:
it is the producer diagnostic `Could not parse judge response: (empty)`, with
4096 output tokens and zero reported errors. Only five of six responses provide
valid feedback. Raw content/stop reason were not retained, so the cause is unknown.
The original summary, grades and failed response remain unchanged under `c21-*`.

The initial simplified column really shows 1.27.2 for four advisories. The later
direct post-fix Grype table (13098–13107, before verification audits) lists
1.26.9 for all nine, with 1.27.2 as an alternative for four. A required Go-minor
policy decision therefore has no support. Independent O/A reject it. The actor
observations supplied to O omit that complete table; the old scalar annotation
cannot establish all per-advisory alternatives. This is corrected by adding the
primary relationships to the existing fact map, without changing criteria.

C22 preparation also replaces one boolean-parser fallback with `ValueError`,
matching numeric parsing. Existing handling retains usage/IDs and records an
error rather than a false vote. Mocked provider-to-verifier proof changes
true/true/empty from errors=0/accepted to errors=1/rejected; true/true/false remains
valid. All nine mocked request bodies are identical; no HTTP calls were made.
20 focused tests and 368 relevant harness tests pass; the 86-test plugin suite
passes in 49.406s. Runtime code and its 3,207 shell/70 Python/19 artifact controls
remain unchanged. No new error type, retry, budget, schema or wrapper was added.

Retrospective audit verifies every A-V6 sample: 60 retained rationales, 60 distinct
IDs and no parse failures. Some older stable false groups discarded sample reasons;
zero errors were reported but cannot be certified from those values alone. Current
O uncertainty covers V9 controls 104/108/202, native V2 control 091 and publication
V5 control 101. Renew each whole three-sample cell once on current profiles; retain
the original counters, labels and dissent. The new publication wrong-version/
corrected-reference pair adds 12 O/A samples, for 27 configured samples total,
zero actors. All 27 original responses are valid with distinct IDs and zero errors.
Eight of nine expected majorities match. The new publication pair is FFF/FFF and
TTT/TTT; the V9 and native negatives are FFF. Publication V5 negative 101 is T/F/T:
both passing rationales identify unobserved `GOTOOLCHAIN=local` and unauthenticated
catalog coverage, then waive them as unsupported rather than contradicted.
Calibration stops without actors. Original responses and terminal exits remain in
`c22-calibration-original-completion.json` and the four groups' retained summaries.

C23 at `25f0e095` changes only the existing O rejection sentences to include
unsupported factual claims, and lets the replay rationale identify an evidence gap
as well as a conflict. This adds no citation/format requirement, new criterion or
parser. Recalibrate the changed outcome judges against retained positive and negative
controls before actors. All 51 responses are valid and distinct with zero errors,
but only 14/17 expected majorities and 45/51 samples match. V9 102 returns F/T/T
for a wrong precise citation; V9 108 returns T/T/F for the wrong named command;
publication V5 101 returns T/T/F for unsupported historical configuration/native
coverage. Passing rationales either merge relationships or locate the error and
waive it as minor, recommendation context or mostly correct reporting. Preserve
all rationales/dissent in `c23-calibration-original-completion.json` and its four
groups. No C23 actor launches.

C24 replaces that procedural checklist with one counterexample decision after
the evidence and reply. Replay observations use live's existing evaluated-material
boundary. Data payloads, labels, models, samples, limits, A and harness stay fixed.
The combined O rubric is shorter; existing interpretation boundaries remain.
Calibration gives no acceptance credit: all 51 responses are valid with distinct IDs and zero
errors, but only 14/17 expected majorities and 42/51 samples match. V9 102 is F/T/T,
V9 105 is FFF instead of true, and publication V5 101 is TTT instead of false.
V9 108 now rejects FFF. The false 102 sample and 103 dissent use an A-only objection;
105's three rationales accept O facts, then explicitly grade `criteria.action_owner`.
Publication's passing samples still waive unsupported facts. Original results,
including wrong-basis dissent, remain in `c24-calibration-original-completion.json`
and its four groups. No C24 actor launches.

C25 projects only `criteria.outcome` into O's annotation context using existing
Jinja dictionary construction; every noncriterion fact remains. Its first sentence
again says to evaluate only outcome. No annotation files, evidence, A requests,
models, caps, parser or schema change. This addresses demonstrated criterion leakage;
it does not establish citation accuracy. Its 51 valid, distinct, error-free samples
match 16/17 majorities and 47/51 values. V9 105/103 are TTT and the wrong-command
control is FFF; publication V5 101 is F/T/F with genuine dissent. V9 102 still
passes TTT, accepting text/time from line 2791 as if it were line 2788. Preserve
all results in `c25-calibration-original-completion.json` and its four groups.
No C25 actor launches.

C26 corrects one shared harness guard sentence. It told the judge to follow only
instructions in the system message, although its actual rubric is in the user
message. Captured serialized requests prove the conflict; its contribution to
past grading failures is unknown. The replacement delegates to the unfenced user
rubric, retaining all quoted-artifact exclusions and boundary escaping. Sixty-eight
mocked SDK requests differ only in that system sentence; no HTTP calls occurred.
The obsolete literal assertion is removed; marker/escaping tests remain.

A now uses the same criterion projection as O, retaining all noncriterion facts.
The shared guard changes O/A requests, so old A samples supply no current request
credit. All 117 fixed samples complete with distinct IDs and zero errors; 38/39
majorities and 114/117 values match. All 66 A responses unanimously match their
22 labels. Every O response except V9 102 also matches; its TTT rationales combine
nearby test/package lines instead of checking the exact cited record. Independent
review retains reasoning limits and every original value in
`c26-calibration-original-completion.json` and its seven groups. No actor launches.

C27 replaces the abstract relationship paragraph with explicit command and exact
line attribution. A quotation/measurement paired with an unqualified line number
must match that line; nearby text is insufficient. Accurate paraphrases, derived
facts and harmless normalization remain allowed. Citations are not mandatory.
C27's 51 responses are valid, distinct and error-free, but only 16/17 majorities
and 47/51 values match. Wrong-citation 102 still passes TTT; native 093 rejects
F/T/F with invalid hypothetical-base-image dissent retained. No actor launches.
Original results remain in `c27-calibration-original-completion.json` and its groups.

A full production-thread mock check verifies all nine replay records and 27 samples
stay bound to their exact subject; no 102/103 swap is found. The actual 102 prompt
has 77,235 characters, with reference lines near 3,200 and the bad quotation near
75,600. C28 moves only the existing O annotation block after observations, before
the final reply. It reduces reference separation to roughly 5,000 characters while
preserving every block and total length. This tests locality, not a proven cause;
provider token count or cost equality is not inferred. No text or criterion is added.

C28 completes 51 valid, distinct responses without errors: 16/17 majorities and
48/51 values match. Wrong-citation 102 is T/F/T; the minority correctly compares
the test/package text and timings. Wrong-command 108 is T/F/F with invalid process/
end-state compensation in its True dissent. Preserve all original values/rationales
in `c28-calibration-original-completion.json` and its four groups. No actor launches.

C29 uses existing `judge.model` overrides to compare O on `claude-opus-4-8`.
Actor and A stay on 4.6; prompts, data, thresholds, three samples, 4096-token cap,
SDK/backend, system/tool schema and environment remain fixed. Official
[Google-managed model documentation](https://platform.claude.com/docs/en/build-with-claude/claude-models-on-google-cloud/google-managed)
lists 4.8 on the existing global endpoint, and its
[forced-tool interface](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#forcing-tool-use)
matches this caller. One predeclared arithmetic compatibility probe returns a valid
4.8 Boolean through that caller; it has zero calibration/actor credit. Root session
18115 exits 0; request, response ID, usage and hashes remain in `c29-model-compatibility-*`.

Actual SDK mocks verify only O's model argument changes; all A requests remain
identical. The same 17 O controls/51 samples remain mandatory, and C26 A66 is
reusable only through independent acceptance and full request identity. No new
parser, schema, reviewer or grading stage is introduced. Full details belong to
the calibration records.

C29 stops: 50 valid responses and one parse error across 51 calls; 45/51 values
and 16/17 semantic majorities match, but only 15 cells are complete and error-free.
Citation 102 rejects FFF. Native 091 passes TTT because its rationales waive the
blanket unverified claim as conservative despite positive named-artifact proof.
V9 101 is T/error/T; 1186 completion tokens do not identify its missing-verdict
cause. All 51 distinct IDs and original values remain in
`c29-calibration-original-completion.json` and four independently reviewed groups.
No actor launches.

C30 adds diagnostics only to the existing parse-error path: stop fields and ordered
block/tool/input-field types, retaining the error and usage/ID without copying
response content values, retrying or salvaging a verdict. Eight SDK mocks verify
unchanged requests and valid results; 191 focused tests pass. Separate strict-tool
compatibility probes on 4.6/4.8 both fail HTTP 400 because the existing organization
policy disallows structured outputs. Strict tools are not adopted; no policy changes
or calibration credit follow from those probes.

C30 uses the existing profile boundary: replay O stays on 4.8, live O returns to
4.6; actor/A stay on 4.6. This configuration is selected from development failures,
not evidence of model superiority or a context-length cause. Require all 17 O
controls/51 fresh samples, preserving data, criteria, wording, caps and thresholds.
C26 A66 can be reused only through accepted identical requests and valid-result
behavior; the diagnostic change supplies no new judge vote. No actor launches until
independent full calibration admission and source freeze.

C30 calibration passes: 17/17 majorities, 47/51 values, 51 distinct valid
responses and zero errors. Independent review reads every rationale and preserves
four incorrect True minorities. Accepted unchanged C26 A66 completes the component
admission. The fresh publication actor then fails: C true, O FFF, A FFF, all six
samples valid. Original driver session 69888 exits 1; actor 171 seconds/$0.90.
Independent whole-reply O/A also fail the repeated Go-1.27-only premise and
unnecessary policy prerequisite. Operations, actual skill intake, source integrity,
literal recipe and native-unknown reporting pass. Stop after one actor, zero accepted;
`c30-cohort-original-completion.json` binds the original results and reviews.

A private campaign-writer assertion misreads inherited model defaults. Root's
command sequence mistakenly continues after that failure. Production `run.sh`
actually freezes clean `25a3037e`, configuration, models, caps, interpreter and
harness before the actor; all seven accepted calibration reviews already exist.
Independent adjudication preserves the original measurement without reroll, with
an explicit timing deviation: the private cohort protocol is written after launch.
Failed helpers/receipts and the separate adjudication remain immutable; no claim
that all private prelaunch checks passed is made. The actual O/A failure stops the
cohort independently of that deviation.

The trace explains a concrete retrieval gap: a full-log Read fails its size limit;
`grep | head` returns only shortened initial rows, and later `awk` strips advisory IDs
from the complete version alternatives. No full primary row reaches the actor.
C31 extends the existing terminal grep with scanner headers and intact typed stdlib
rows, replacing abstract grounding prose. Actual CLI checks on five retained logs
preserve every old flagged match and expose all nine publication rows, including
four `1.26.9, 1.27.2` alternatives. A redundant all-passed Summary-status sentence
is removed because historical Summaries may lack test status; failed-attempt and
later-attempt reporting remain required. Net Skill change: one line and 14 words
removed. This demonstrates retrieval, not prospective actor success.

C31 (`5c1b0cb7`) changes no runtime, profile, rubric, threshold, fixture, model or
harness. The 112-request mock proof confirms unchanged O17/A39 requests, models,
rendered data and valid returns; the accepted 117 original samples remain component
evidence. Private freeze and verification both exit 0 before the first actor.

| Fresh C31 actor | Original stock | Independent review |
| --- | --- | --- |
| `e2e-complete-rows-publication002-20261024-01` | C true; O TTT; A TTT; driver 0; 151 seconds/$0.73 | Accept: complete nine-row table actually delivered and quoted, all same-line fixes correct, one supported builder-publication prerequisite and pending target rerun; intake/operations/provenance pass |
| `e2e-complete-rows-replay007-20261024-01` | C false; O FFF; A TTT; driver 1; 150 seconds/$0.73 | Reject O/operations: unsupported pre-existing/independent-cause claims, an invented retry diagnostic in place of the observed 89/89 pass, and an explicitly blocked mutating `git stash` attempt. No stash executed or state mutation is inferred. A/intake/source integrity pass. |

All twelve original judge responses are valid, distinct and error-free. Both
original pipelines complete their stock stages; the second fails its original
contract and outcome thresholds. Stop with two actors started, one accepted;
`c31-cohort-original-completion.json` binds the results and separate independent
reviews. No live002 or subsequent actor launches, no reroll, regrading or old-actor
credit. The publication success demonstrates this retrieval case, not general
factual or operational reliability.

The reviewed documentation cleanup removes duplicated chronology and contracts
from the eval README, calibration pages and plan, linking their canonical owners.
Unique measurements, original grades, costs, dissent, witnesses and artifact paths
remain. This is a documentation-only follow-up after the stopped measurement;
execution components retain the measured source identity.

If work resumes, test an actor-model-only candidate through the existing setting
before adding more prohibitions, parsers or output constraints. Actor Opus 4.8 is
unproven here: it needs a separate zero-credit CLI/effort/tool/backend compatibility
probe, an exact oracle-reuse proof and a fresh predeclared eleven-actor cohort.
The prior SDK judge probe supplies no actor-CLI compatibility or behavior credit.
No candidate is implemented or measured by this finish-up commit.

After calibration and source freeze, measure publication 002 first, then 007,
live 002, live 001, 005, live 003/004 and four replay repeats. All eleven actors,
original thresholds and independent review remain required; no old actor supplies
credit. Declared models/settings/canonical gates stay fixed throughout that cohort under the same $115 nominal
actor cap. Semantic costs and physical retries remain unknown.

A sandbox actual-license-block counterexample deleted a pre-existing ignored,
non-executable caller file when a generated executable's name contained a newline;
tracked files stayed clean. Ordinary-name control preserved the caller file.
The reviewed fix replaces pathname deletion with the existing artifact helper,
using a separate license prefix and no previous-run claims. Make/logger exits
remain separate from ownership failure, which blocks publication. Actual producer,
logger and trap controls preserve native baselines, caller files, links and nested
checkouts. Partial helper I/O failure coverage is not claimed.

A subsequent actual-license-producer counterexample exposed Unicode separators
being split in the helper's serialized baseline. Two LF-only baseline reads now
preserve all 16 pre-existing-path controls (eight separators × two modes) that the
old producer could delete. A third runtime reader fix preserves the same path
identity in native scan consumption: actual Unicode-fresh/ASCII-in-place scan
controls fail with the old consumer and pass with the correction. One eval JSONL
reader likewise now splits only LF; its raw-Unicode event regression previously
raised `JSONDecodeError` and now passes. These retain existing formats and parsers;
no human-log rewrite or new framework was added. Thirty-three retained machine
files containing 2,462 rows parse unchanged, recorded in
`jsonl-parser-compatible-recordings.json`.

Current model-free `e2e-owned-unicode-dry-20261023-01` completes 005/007/002
prepare/replay with exit 0, retaining `aa5a4fc`/`aaaeea3`/`2716c2ff` and each
historical runtime exit 2. Original counterexamples and verification receipts,
including `license-cleanup-{counterexample,fix-verification.json}` and
`final-boundary-unicode-artifact/{receipt,actual-producer-receipt}.json`, remain
under `.work/fix-go-cves-e2e-20261023/`. V5 source identity is recorded in
`combined-snapshot-v5-source.json`. Runtime, outcome criteria, models and thresholds
remain unchanged. V9 outcome controls retain their scope; the changed action
prompt and live-001 action annotation require the separate calibration above.
This supplies no actor credit, scoring recovery or live acceptance of changed
runtime. Component verification remains applicable to unchanged bytes;
future actor acceptance remains separate.

A separate model-free actual-engine diagnostic,
`e2e-engine-readiness002-20261023-01`, repaired all five x/net findings on official
Admiral `af20d0b` in 240.08 seconds (exit 0). Its single canonical `make unit`,
including race detection, passed on exact retained commit `6e660e1`; all four
audits passed and final scan matches were zero. License/native build were not
configured. The checkout was clean, all 22 frozen runtime files unchanged, and
no owned containers remained. Standard frozen capture passed; its actual repair
scenario passed 18/18 predicates and 10/10 capture/provenance checks. The full
contract correctly rejected the missing actor reply. This verifies producer/
consumer compatibility and one engineering outcome, not live actor acceptance,
general reliability, or a causal explanation for earlier race failures. Cost is
unknown. No engine/actor rerun, target patch or pin change was used.

A separate native Subctl diagnostic at official `50243ac` completed once in
295.57 seconds, exit 2 confirmed partial. Tests, four audits and license passed
on retained `c9932ef`; initial/final unpacked native artifacts had exact clean VCS,
positive catalog locations and matching retained hashes. One stdlib finding,
GO-2026-6809, remains in the custom Go 1.26.9 compiler; a vendor-supported patched
image must be published before consumers rerun. Frozen capture passed and the
actual binary scenario accepted 24/24 predicates plus 10/10 integrity checks.
No owned containers remained. The full checker rejected absent actor output;
this supplies no actor/cohort credit or claim of stdlib remediation.

The live oracle's existing landing/causal controls matched 8/8 labels and 24/24
samples. Oracle controls are inspected development evidence, not unseen holdouts
or reliability estimates. All judge costs remain unpriced. Judge rationale is not
independent evidence; overreaching incidental reasoning remains documented.

Sample aggregation now retains each raw value, rationale, error and supplied
usage/response ID in the existing result file (+12 production lines). It preserves
requests and verdicts: 84 mocked serialized requests are byte-identical; the first
real run retained six complete rationales and six distinct response IDs. Older
samples retain their representative-rationale limitation. Upstream physical retry
usage overwritten before aggregation remains outside this metadata fix.

## Earlier implemented changes and checks

Detection owns default commands; the skill preserves target policy, launches once
and investigates read-only. Runtime fixes preserve command/logger status and
reviewer detail, report phase-specific scope and enforce explicit Go/Kubernetes
minor restrictions. Reporting uncertainty does not trigger the blocking opaque-
binary marker. Native contracts require initial/final proof outside clean fast
paths; Subctl release now declares `binary` coverage.

Positive recording 002 uses an applicable publication/builder scoring profile
sharing replay execution/contract configuration. Its [calibration](cases/case-002/calibration.md)
retains the failed initial oracle and corrected independent Summary witness:
V4: 10/10 expected majorities, 30/30 expected samples, zero sample errors.
V5 adds two actual/corrected scope/environment controls: 2/2 majorities and 6/6
samples match. Preserve the actual actor false positive and unsound extra rationale
criticisms. These bounded controls do not prove general factual reliability.

| Local check | Result |
| --- | --- |
| Immutable runtime shell suite | 3,102/3,102; runtime/test bytes and modes matched |
| Eval helper suite | 73/73, including complete skill staging and corrected cleanup-head provenance |
| Focused evidence / Go guards / reviewer checks | 349 / 34 / 14 passed |
| Model-free 005/007/positive-002 replay | Expected retained commits and exit 2 reproduced |
| Strict site build / clean-snapshot lint | Passed before this documentation update |

Native outcome [controls](live/calibration.md) now reject the two known native
reply errors by majority (4/4 expected majorities, 11/12 expected samples), retaining
one wrong-builder false-positive sample. The initial calibration accepted both
known negatives; all original grades remain preserved.

Earlier shell runs were invalidated by concurrent edits or an obsolete physical-
line assertion. A behavioral build test replaced that assertion; the immutable
suite above is the final runtime result. Model-free worker checks exercised real
Dapper ownership, timeout, caller cancellation and container cleanup. Runs used
the disposable rootless daemon and inherited `make unit`; no target publication
was executed. Missing native/build coverage remains explicit.

## Actor results by frozen source

Run IDs below live under `.work/fix-go-cves-evals/runs/fix-go-cves:fix-go-cves/`.
`C`, `O`, `A`, `B` mean contract, outcome, action_owner and backport. Pass/fail
refers to preserved stock results; the last column is independent whole-reply
review. A passing majority does not erase a factual error.

| Source / run ID | Preserved stock result | Whole-reply result or coverage |
| --- | --- | --- |
| Original: `simplify-replay-20261022-01` | 005: C/B pass, A fail; 007: B pass, C/A fail | Both reject causal claims; 007 misses actual retries and attempts denied `git stash` |
| Original: `simplify-publication-20261022-01` | C/O pass, A fail | Reject invented prerequisite, guaranteed clean rerun and missing native uncertainty |
| Operator error: `simplify-publication-20261022-02` | Incomplete; actor terminated | Wrong-directory edit failed while launch continued with unchanged source; no revised-candidate evidence |
| Relay clarification: `simplify-publication-20261022-03` | A pass, C/O fail | Reject duplicate rewritten publication recipe; preserve qualified future wording separately |
| Original live: `simplify-live001-20261022-01` | C fail, O/A pass; separate corrected-oracle recheck passes runtime conditions | Real exit 2: both guards enabled, five findings blocked, `make unit` passed, no commits, original ref restored. Reply rejects: unsupported low-risk assessment and guaranteed five-CVE repair |
| Facts: `simplify-facts-replay-20261022-01` | 005: C/B/A fail; 007: C/B pass, A fail | 005 attempts denied source Edit and misses matching backport; 007 retains unsupported causality |
| Facts: `simplify-facts-publication-20261022-01` | C/O pass, A fail | Exact recipe, but reject claim repaired image will produce a clean result |
| Facts live: `simplify-facts-live002-20261022-01` | C/O pass, A fail | Real x/net repair `c426d81`, exit 0, unit/four audits/final scan pass. Build unconfigured/native unverified; reject claimed build pass and invented publication steps |
| Reporting reference: `simplify-reference-replay005-20261022-01` | C/B/A pass after scoring-only recovery | Reject unsupported upgraded-Go cause and invented original ref. Reference read before launch, not near composition |
| Reporting reference: `simplify-reference-publication-20261022-01` | C/O/A pass after scoring-only recovery | Reference read immediately before reply; exact recipe/scope/owner retained. Reject false “only unit” claim: four audits and license actually passed |
| Final reference pilot: `simplify-final-replay005-20261022-01` | C/B pass, A fail | Reject unsupported attribution and binary-only scope label |
| Final reference pilot: `simplify-final-publication-20261022-01` | C/O/A pass | Accept literal recipe, supported image owner/prerequisite and native uncertainty |
| Handoff: `simplify-handoff-replay005-20261022-01` / `02` / `03` | C/B/A pass in all three | 01/02 accept; 03 miscounts 17 passing packages as 16, despite correct backport/prerequisite |
| Handoff: `simplify-handoff-replay007-20261022-01` | C/B pass, A fail | Reject unsupported syncer cause and missing investigation owner/action despite accurate attempt outcomes |
| Handoff native: `simplify-handoff-live003-20261022-01` | C/O/A pass | Runtime proof/gates pass; reject blanket native-unverified claim contradicting quoted positive scope |
| Handoff native: `simplify-handoff-live004-20261022-01` | C/O/A pass | runtime proof/gates pass; reject wrong builder/owner imported from nested reviewer narrative |
| Observed evidence: `simplify-observed-replay-pilots-20261022-01` | 005 C/B/A pass; 007 C/B pass, A fail | 005 accepts; 007 rejects unsupported pre-existing/flaky label and rerun prediction despite correct attempts |
| Observed positive: `simplify-observed-publication-20261022-01` | C/O/A pass | Reject inferred native proof and categorical toolchain setting; literal recipe, owner/prerequisite and read-only behavior pass |

Live 001 exposed an oracle defect: the final scan ran at the executed release
HEAD, then empty-branch cleanup restored the original devel HEAD. The old helper
compared the receipt with that restored HEAD. The corrected helper checks executed
scan provenance; its model-free recheck preserves all original grades/artifacts.
It does not accept the actor's reply.

Reference pilots initially failed the scoring integrity fence because the helper
changed concurrently. Initial artifacts were preserved; restoring the exact frozen
helper allowed **scoring/report/verification only**, with byte-identical actor
artifacts and no actor retry. Both recovered stock passes above are false positives
against whole-reply requirements. Retain the integrity failure alongside recovery.

## Historical literal treatment and acceptance failures

The literal source group at `472270e9` was measured from an unchanged detached
worktree. All three pilots passed stock thresholds and independent review. The
second replay pair then exposed a denied `git stash` and omitted upstream-landing
prerequisite in 007. Preserve the correct contract failure and the factual judge's
false positive; final clean refs do not excuse an attempted forbidden operation.

| Literal measurement | Stock result | Independent result |
| --- | --- | --- |
| `simplify-literal-replay-20261022-01` | 005/007 C/B/A pass | Both pass; minor format/reference-order deviations retained |
| `simplify-literal-publication-20261022-01` | C/O/A pass | Pass; exact recipe and supported image prerequisite |
| `simplify-literal-replay-20261022-02` | 005 C/B/A pass; 007 C fail, B/A pass | 005 passes; 007 denied stash and missing origin landing |
| `simplify-literal-live001-20261022-01` | C/O/A pass | Runtime 21/21; whole reply passes; guarded exit 2, five findings, no commits, original ref restored |
| `simplify-literal-live002-20261022-01` | C fail, O/A pass | x/net repair clears five findings, but both unit attempts fail on the same workqueue race; whole advice omits origin landing |

Live002 retains `ed36476d` with only go.mod/go.sum changes. Four audits and final
scan pass; passing scans cannot override failed tests. Both race attempts retain
paired logs/receipts. The failed successful-repair scenario remains failed; no
extra retry or local patch is applied to its eval case. A separately declared
single baseline `make unit` at `af20d0bf` passed. That control does not establish
absence of the race or attribute the update's role. The test-fixture lifetime
mechanism and narrow external candidate were investigated separately; the final
diagnostics below retain the inconclusive result.

The historical `8788312f` source placed remote/image prerequisites beside its
reporting table and attribution uncertainty before repair discovery. Immutable-ref
reads use captured command/base/retained commits; a refreshed origin ref is not
the executed base. That source required a row for each failure or unresolved
decision, including a failed-then-passed attempt, and an investigation instruction
for unknown repairs. Current compact guidance retains relevant attempts and
actionable unresolved work without requiring that table or a task for a recovered
retry. The separate pilot group below preserves the historical source and results.

That historical live action criterion explicitly required upstream repair landing
before reruns and published images before consumer reruns. Its two controls matched
6/6 samples and 2/2 majorities, preserving the prior false-positive grades. Full
oracle details belong to the [native/live calibration record](live/calibration.md)
and [publication calibration record](cases/case-002/calibration.md).

Scratch evidence remains under `.work/fix-go-cves-implementation-20261022/`.
Each `*-candidate-protocol.json` freezes its source group; run directories retain
inputs, replies, traces, samples, HTML and completion/regression results. Independent
`*-whole-reply-review.json` and `*-runtime-review.json` receipts keep disagreements
separate. `literal-operation-state-audit.json` records the denied stash; the
`workqueue-baseline-control/` protocol/log/exit preserves the single passing control.
Prior scoring-only integrity recovery and failed calibrations remain unchanged.

No complete current-source cohort or replay reliability is accepted. Do not rerun
unchanged live002 merely to obtain a favorable race seed, weaken its repair
contract, skip the package or silently inject a local patch. That historical
successful-repair cell remains failed. The separate official-pin readiness
diagnostic above demonstrates feasibility without proving a race repair or
requiring a new pin. Native engine coverage under earlier reporting variants
remains distinct from current invoking-agent/native acceptance.


## Prerequisite pilot and final diagnostics

The `8788312f` campaign contains only the three declared pilots:
`simplify-prerequisite-replay-20261022-01` (005/007) and
`simplify-prerequisite-publication-20261022-01` (002). It stops without expansion.
Replay 005 has sound facts/backport prerequisites; 007 reports both attempts and
remote landing but adds an unsupported flaky label and misidentifies a package
failure's log line. Neither attempts a denied operation. Publication has sound
facts, exact recipe and a published-image prerequisite, but attempts denied
read-only `git stash list`. That differs from the earlier attempted mutating
stash; the existing blanket permission/trace contract still rejects it. Preserve
literal-evidence and reference-order deviations separately from factual invention.
Publication's recovered contract fails; O/A both pass all three samples. All six
judge calls complete without sample errors (168.40 seconds; all unpriced).
Independent factual/advice review passes while operational whole acceptance fails.
Recovered replay scoring passes both contracts, B=TTT and A=TTT for each case
(12 judge calls, zero regressions). Those 007 factual labels are false positives
against the independent citation/neutral-label review; retain both results.
The compact oracle still omits finding IDs; full raw rows independently validate
the accurate IDs rather than treating absence from that compact oracle as proof.

Both original pipelines execute their declared actors, then collection fails 127:
the old Homebrew Python 3.13 interpreter target disappears mid-campaign. Replay
007's prepare hook falls back to system Python 3.14.8; do not claim one interpreter
identity across these cases. Original failures and raw actor artifacts are retained.
An isolated Python 3.12.15 environment reconstructs all 45 exact package versions;
73 helper and 275 focused harness tests pass. Recovery executes only collection,
previously unexecuted judging, reporting and verification against unchanged actor
artifacts. This is scoring recovery, not an untouched successful E2E run.

The external workqueue investigation also stops. All 20 focused diagnostic
executions pass, including unpatched arms. A separately declared final canonical
comparison runs each retained tree once: original exit 0 (81.424 seconds), patched
exit 0 (80.237 seconds), all 19 packages with race detection and coverage. Neither
comparison demonstrates patch efficacy; the original focused gate stays unmet and
live002 stays failed. Independent receipts verify source/input/image hashes,
clean trees, host ownership and empty worker containers. The
[fixture-owned cleanup design](../plans/workqueue-race.md) is preferred for separate
upstream review; it is not implemented or tested by the diagnostic candidate.

Evidence is under `prerequisite-*-protocol.json`, `prerequisite-*-review.json`,
`recovery-*.json` and `workqueue-full-context-comparison/` in the existing scratch
root. Preserve the original 127 exits, interpreter differences, operation denials
and all recovered grades. No current-source cohort or replay reliability is accepted.
