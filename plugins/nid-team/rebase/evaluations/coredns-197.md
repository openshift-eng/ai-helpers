# CoreDNS #197 local replay

On 2026-10-30, the manager reconstructed the core source changes in
[CoreDNS PR #197](https://github.com/openshift/coredns/pull/197) from historical
inputs. It correctly stopped at `applied`: nine gates passed, the full test suite
failed, and downstream CI was unperformed. This is a local case study, not
qualification for unattended operation or proof of product equivalence.

## Frozen inputs and method

| Role | Revision |
| --- | --- |
| Skills/helper under test, PR #838 | `67d454cba83c5acd33ac3d0da0c266f42568d72c` |
| Downstream input | `ad7aaecd3e975727735ee8245d3917ee870cc50c` |
| Previous upstream, v1.13.1 | `1db4568df6aaacda6ebbce87717156bd855f8103` |
| Target upstream, v1.14.7 | `427fc80ed9ca47f354585eb30a3f1332950856c4` |
| Local replay candidate and tested head | `704bce6eb1b50c8043f26725a3c8f30718cef727` |
| Final reference PR head | `46319ec6c11e3e1fe34cc27e69a4a2cb8536419f` |

A fresh-context manager used the frozen skills with bounded stage workers and
validation separate from implementation. Its isolated checkout received only the three
input histories through a Git bundle; the final reference head was absent from
its object database. A separate assessor inspected the reference and compared the
candidate without feeding reference choices back to the workers. Separation was
procedural, not an operating-system sandbox. The skill's design had already been
informed by this historical case, so this was not a held-out benchmark.

Scope was local execution and reporting. No branch or PR was published, and live
CI, review-feedback handling, and interrupted-run recovery were not exercised.
One coordinator intervention explained how to remove an inherited incompatible
`GOROOT` override when using the cached Go 1.26.6 compiler. No reference-derived
source correction was supplied. Later PR #838 revisions are not retroactively
covered by this replay.

The actual input tree and Git history controlled the comparison. Historical
reports describe an older baseline and a different merge shape from the final
PR. Commit counts, consolidation choices, and SHA equality were not success
criteria. Reference-only reviewer requests were distinguished from missed carries.

## Results

The candidate accounted for 22 source carries: 13 picked, five already upstream,
three dropped, and one regenerated. The plan inventoried 7,822 downstream tree
paths. Application required no additional source-repair commits and returned a
clean checkout.

All tracked nonvendor Go source and plugin registration/order matched the final
reference. Active product packaging and identified security fixes also matched.
The candidate retained the older resolver revision with the target's Kubernetes
0.35.4 dependencies; the reference selected a later resolver and Kubernetes
0.36.2. Vendored resolver Go source was identical. Local build/vendor checks
support a compatible alternative; downstream integration behavior remains untested.

| Gate | Observed result |
| --- | --- |
| Carry accounting, tree accounting, independent review | PASS |
| Generated files and vendor consistency | PASS |
| Plain vendored build and Makefile build | PASS |
| Focused race tests and plugin registration | PASS |
| Full `make test` | FAIL: DNSTap transport EOF and ACL test loopback bind failure |
| Required downstream CI | INCONCLUSIVE: not run |

The helper imported all 11 gates and rejected `advance --to validated` with
`downstream-ci: INCONCLUSIVE; unit-tests: FAIL`. It retained phase `applied` and
the tested head. Passing diagnostics did not replace the failed full-suite gate.

Local validation used Darwin/arm64 and Go 1.26.6. The loopback failure was directly
reproduced on the host. A bounded dependency control reproduced intermittent
transport EOF using the target dependencies and identical test source. The final
reference also built on this host and exhibited both failing test names in its
broad test run. Reference and candidate execution flags differed, so that alone
does not prove an identical cause. A missing `faillint` tool initially skipped a
reference check; after installing it, that focused check passed. Historical
reference CI successes were not transferred to the candidate.

## Lessons incorporated into the skills

- Inspect effects within a mixed-purpose carry separately. Dropping an obsolete
  numeric Go pin also dropped `GOTOOLCHAIN=local`, restoring the upstream compiler
  selector. This was disclosed but still needs downstream policy confirmation;
  it is not a demonstrated product regression. The revised skill requires an
  independent rationale for discarding the persistent policy.
- Review version claims and active build/test configuration after changes. The
  replay README retained Go 1.25 examples despite a Go 1.26.3 module minimum.
  Intentional differences between compiler minimum, selected compiler, and
  server/client versions need explanation, not automatic equality.
- Record effective environment, required tools, skipped checks, and exact commands.
  Preserve initial failures and distinguish diagnostic controls from required
  validation. Neither a flaky baseline nor a narrower passing rerun waives a gate.
- Keep replay comparison separate from readiness. The reference's review-only
  OWNERS addition, dependency modernization, and committed reports are not
  automatically missed carries. Independent review passed but missed documentation
  and policy questions; an agent-authored PASS is evidence to inspect, not proof.

Detailed local evidence was retained under `.work/coredns-197-replay/`: the pinned
manifest and bundle, plan/result/progress records, helper transitions, command
logs, separate reference validation, and comparison reports. Those local artifacts
and the unpublished candidate are not distributed with this repository. Repeating
the case requires a new run with the pinned inputs; newer skills require their own
evaluation rather than reusing this result.
