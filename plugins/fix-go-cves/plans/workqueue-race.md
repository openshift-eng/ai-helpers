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

All executions use the owned rootless worker. Evidence is retained under
`.work/fix-go-cves-implementation-20261022/`: `literal-live002-runtime-review.json`,
`workqueue-baseline-control/`, `workqueue-validation-plan/` and
`workqueue-drain-candidate-analysis.json`. No eval cell or original grade is changed.

## Closure prerequisite

A focused pass is not full-suite acceptance. Review the bounded canonical-context
comparison separately before any further execution. A validated target-repository
repair must land upstream before selecting a new official case pin and declaring
a fresh complete E2E measurement. Keep the current race and missing-origin advice
failures in the [results record](../evals/implementation-results.md).
