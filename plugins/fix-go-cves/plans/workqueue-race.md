# Admiral workqueue fixture race

This is a separately reviewable target-repository candidate, not an applied eval
fixture or validated repair. The successful-repair cell stays failed until its
real required tests pass. Do not suppress the package, race detection or assertions.

## Observed failure

`simplify-literal-live002-20261022-01` clears five x/net findings with retained
`ed36476d97237d21229e765cd286c6b428798072`, but both canonical `make unit`
attempts exit 2 with the same race. A previous worker reads the shared `itemCh`
at `pkg/workqueue/queue_test.go:212` while the next fixture replaces it at line 71.
The base is `af20d0bf09dade1c6537d6d38f5175f7b8704042`; workqueue files are
unchanged by the dependency update. That source fact does not establish what role
the update played in these executions.

The priority spec enqueues 50 extra items, checks the first and adjusted items,
then cleanup calls nonwaiting `ShutDown()`. The next fixture can start before the
previous callback completes. The available fetched history contains no repair.

## Candidate and bounded verification

The [patch](patches/admiral-workqueue-drain.patch) gives that priority spec a
`SpecContext` and drains the queue after its existing ordering assertions. Its
52 total sends fit the 100-item channel buffer. Drain waits for callback completion
before the next fixture replaces shared state. This covers the successful spec
path; earlier assertion failures still use the existing cleanup.

One separately declared full baseline suite passed. A four-arm diagnostic then
compared base/retained sources with/without this patch: five independent focused
`go test -v -race -count=1 ./pkg/workqueue` processes per arm, rotating order,
same builder/compiler/cache configuration. All 20 passed. Thus it did not
reproduce the race or establish the patch's effect; its predeclared gate for an
additional canonical run was not met. No automatic extra samples were added.

A separately declared final full-context comparison ran canonical `make unit`
once on each retained tree, original first and patched second. Both passed all
19 packages with race detection and coverage. It adds no discriminating repair
evidence. The focused matrix's gate remains unmet, the live case stays failed,
and unchanged-run diagnostics stop after these two executions.

All executions use the owned rootless worker. Evidence is retained under
`.work/fix-go-cves-implementation-20261022/`: `literal-live002-runtime-review.json`,
`workqueue-baseline-control/`, `workqueue-validation-plan/` and
`workqueue-drain-candidate-analysis.json` and
`workqueue-full-context-comparison/`. No eval cell or original grade is changed.

## Preferred upstream design

Keep the two-line patch as a diagnostic candidate. Prefer fixture-owned awaited
cleanup registered when acquiring each queue, rather than a wait at the end of a
single successful spec. Ginkgo's context/error-aware `DeferCleanup` can use the
bound `wq.ShutDownWithDrain` method without another cleanup abstraction. Capture
per-spec state and finish owned callbacks before the next fixture replaces it.

Review deliberate blockers and failure paths before replacing cleanup: release
owned gates before draining, make releases idempotent, and avoid blocking startup
notifications. Preserve drain-timeout assertions and bounded cleanup. A drain
wait alone cannot release a blocked callback. The existing helper also sends
completion on an unbuffered channel after a possible timeout; review that separate
lifecycle issue without claiming the diagnostic patch fixes it. This preferred
design is read-only analysis, not an implemented or tested replacement.

## Closure prerequisite

A focused pass is not full-suite acceptance. Both bounded diagnostic designs are complete; neither demonstrated the repair
effect. A validated target-repository
repair must land upstream before selecting a new official case pin and declaring
a fresh complete E2E measurement. Keep the current race and missing-origin advice
failures in the [results record](../evals/implementation-results.md).
