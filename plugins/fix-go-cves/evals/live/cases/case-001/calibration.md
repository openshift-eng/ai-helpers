`reply.md` and the two causal negatives describe the captured blocked run
`fix-go-cves-20261019T204904Z-1274266`, using its `output/evidence.txt` plus
the retained base/result `go.mod` diff and `golang.org/x/tools` versions.
They are judge calibration examples, not expected findings for future live runs.

For `action_owner`, the reference should pass and each negative should fail.
Each negative replaces only the reference's causality paragraph. The reference
uses the evidence available in that run, without importing the later operator
baseline experiment. The pinned default-branch source facts in annotations
establish the available backport, not the cause of a particular test failure.
