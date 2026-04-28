## Review Panel Verdict

**Disposition**: <APPROVE | REQUEST_CHANGES | NEEDS_DISCUSSION> <optional one-line qualifier>

---

### Specialist Findings

**Architecture Reviewer**: <findings on structural patterns, SOLID, cross-file impact, module boundaries>

**Security & Supply Chain Reviewer**: <findings on vulnerability surfaces, credential handling, dependency trust, supply chain integrity, lockfile changes, build pipeline risk>

**UX & API Reviewer**: <findings on naming, error messages, API ergonomics, backwards compatibility>

**Codebase Consistency Reviewer**: <findings on duplicate helpers, convention adherence, style match, shared utility usage>

**QA Engineer**: <findings on test coverage gaps, untested error paths, missing edge-case tests, concrete test suggestions>

**Devil's Advocate**: <findings on broken assumptions, failure scenarios, race conditions, resource leaks, off-by-one errors. If no issues found, state what was tried and why the code holds up.>

**Technical Writer**: <findings on stale docs, missing docs for new features, inconsistencies between docs and code. If the repo has little to no documentation, note this.>

---

### External Reviewers

**CodeRabbit**: <full output from `coderabbit review --agent`, or error message if the tool failed>

---

### Panel Synthesis

<Synthesize all findings — internal specialists and external reviewers (if any). Resolve any disagreements between reviewers. Where an external reviewer corroborates an internal specialist, note the convergence. Where they conflict, explain the resolution. If Devil's Advocate flags a concrete failure scenario, it is blocking unless another specialist provides a specific technical refutation. Ratify the disposition. State the strategic call. If reviewers agreed and the change is straightforward, say so plainly in one or two sentences.>

---

### Required Actions Before Merge

1. <required action with file:line pointer. If disposition is APPROVE with no required actions, write "None.">

---

### Optional Follow-ups

- <follow-up suggestion out of scope for this change but worth tracking>
