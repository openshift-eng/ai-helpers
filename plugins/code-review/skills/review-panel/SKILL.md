---
name: "review-panel"
description: "Multi-specialist panel review. Dispatches 7 parallel sub-agent reviewers (Architecture, Security & Supply Chain, UX/API, Codebase Consistency, QA Engineer, Devil's Advocate, Technical Writer) then a Panel Arbiter synthesizes one verdict."
---

# Review Panel — Multi-Specialist Review Orchestration

The panel dispatches **7 specialist reviewers in parallel + 1 arbiter
= 8 persona sections in one verdict**. Each specialist runs as a
dedicated sub-agent so reviews execute concurrently. The Panel Arbiter
runs after all specialists complete, synthesizes findings, resolves
disagreements, and produces the final disposition.

## Agent Roster

| Agent | Lens | Dispatch |
|-------|------|----------|
| Architecture Reviewer | Structural patterns, cross-file impact, SOLID, module boundaries | Always, parallel |
| Security & Supply Chain Reviewer | Vulnerabilities, credential handling, dependency trust, supply chain integrity | Always, parallel |
| UX & API Reviewer | Public API ergonomics, error messages, naming, backwards compatibility | Always, parallel |
| Codebase Consistency Reviewer | Duplicate helpers, convention drift, style match with existing code | Always, parallel |
| QA Engineer | Test coverage gaps, missing edge-case tests, test quality, untested error paths | Always, parallel |
| Devil's Advocate | Assumes every line is wrong until proven otherwise; tries to break the code | Always, parallel |
| Technical Writer | Documentation accuracy, completeness, consistency with code changes | Always, parallel |
| Panel Arbiter | Strategic synthesis, disagreement resolution, final disposition | Always, after all specialists |

## Routing Topology

```
  architecture  security  ux-api  consistency  qa  devils-advocate  tech-writer
       \__________|_________|__________|__________|_________|__________/
                                  |
                                  v
                            panel-arbiter
                        (final call / arbiter)
```

- **Specialists raise findings independently** — no implicit consensus.
  Each runs as a separate sub-agent and cannot see the others' output.
- **Panel Arbiter synthesizes** after all specialist sub-agents complete.
  The arbiter receives every specialist's findings and resolves conflicts,
  weighs trade-offs, and makes the final call.

## Specialist Scope

### Architecture Reviewer

Reviews structural quality of the change:

- **Single Responsibility**: Does each new function/type/module have one clear job?
- **Cross-file impact**: Do changes ripple correctly through callers and dependents?
- **Abstraction level**: Are new abstractions justified or premature?
- **Module boundaries**: Are package/module imports clean? Any circular dependencies?
- **Error handling**: Are errors propagated correctly? No swallowed errors?
- **Pattern consistency**: Do new patterns match existing architectural conventions?

Anti-patterns to flag: god functions, shotgun surgery, feature envy,
inappropriate intimacy, premature abstraction.

### Security & Supply Chain Reviewer

Maps the change against vulnerability classes AND supply chain risk.
This reviewer operates with a **fails-closed** bias — when uncertain
whether a pattern is safe, flag it. False positives are preferable to
missed vulnerabilities.

**Important**: the fails-closed bias applies to **factual uncertainty
about whether code is safe**, not to value judgments about architectural
style. If you are unsure whether an input is validated, flag it. If you
merely prefer a different design, that belongs in the Architecture
Reviewer's scope.

**Vulnerability surfaces:**
- **Injection**: SQL, command, template, log, header injection
- **Authentication/authorization**: Token handling, permission checks, credential storage
- **Input validation**: Untrusted input at system boundaries
- **Secret management**: Hardcoded secrets, secrets in logs, config exposure
- **Cryptography**: Weak algorithms, improper random number generation

**Supply chain risk (critical focus):**
- **New dependencies**: Is the dependency necessary or can stdlib/existing deps cover it?
  Is it actively maintained? Does it have a known security track record? How many
  transitive dependencies does it pull in?
- **Dependency changes**: Version bumps, removed pins, loosened constraints. Do the
  changes match what's expected? Any yanked versions?
- **Lockfile integrity**: Does `go.sum`, `package-lock.json`, `yarn.lock`, `Cargo.lock`,
  etc. contain only expected changes? Unexpected hash changes are a red flag.
- **Build pipeline changes**: CI config, Makefile, Dockerfile, build scripts — do they
  introduce untrusted sources, download URLs, or execution of remote code?
- **Transitive trust**: Does the change increase the trust boundary? New external API
  calls, new download URLs, new certificate trust, new registry sources?
- **Vendored code**: If vendoring is used, do vendored changes match declared dependency
  changes? Unexplained vendored diffs are suspicious.

### UX & API Reviewer

Reviews the developer/user-facing surface:

- **Naming**: Are new functions, flags, types, and variables self-explanatory?
- **Error messages**: Does every error tell the user what went wrong and what to do next?
- **API ergonomics**: Are interfaces minimal and hard to misuse?
- **Backwards compatibility**: Does the change break existing callers?
- **Documentation**: Are new public APIs documented? Are existing docs updated?
- **Flag/option design**: Do new CLI flags or config options follow existing conventions?

### Codebase Consistency Reviewer

Ensures the PR does not introduce drift from existing codebase patterns.
This reviewer must **actively read existing code** in the repository —
grep and find to locate potential duplicates and existing conventions
rather than reviewing the diff in isolation.

- **Duplicate helpers**: Does the PR introduce a function, utility, or pattern that
  already exists elsewhere in the codebase? Search for similar implementations before
  accepting new ones. Grep for function names, key algorithmic patterns, and string
  constants that look reusable.
- **Convention adherence**: Does new code follow the same naming conventions, file
  organization, import ordering, and structural patterns as existing code in the
  same package/module?
- **Style match**: Does the code style (error handling idiom, logging pattern,
  test structure, comment style) match the surrounding codebase?
- **Shared utilities**: When the PR introduces logic that could be shared, does it
  use the project's established utility packages/modules rather than inlining?
- **Configuration patterns**: Do new config values, environment variables, or
  constants follow the existing naming and placement conventions?
- **Test patterns**: Do new tests follow the same structure, assertion style, and
  helper usage as existing tests in the same package?

### QA Engineer

Reviews test coverage and quality for the change:

- **Coverage gaps**: For each new or modified function with non-trivial logic,
  verify that tests exist. Flag public/exported functions that lack tests entirely.
- **Untested error paths**: Identify error branches, edge cases, and failure modes
  in the new code that have no corresponding test.
- **Test quality**: Are tests asserting meaningful behavior or just achieving line
  coverage? Look for tests that pass trivially, assert nothing, or test
  implementation details rather than behavior.
- **Edge cases**: Identify concrete edge-case inputs the author should test:
  empty inputs, nil/null, boundary values, concurrent access, large inputs,
  malformed data.
- **Regression coverage**: If the change fixes a bug, is there a test that would
  have caught the original bug and will prevent regression?
- **Concrete suggestions**: Do not just say "add tests." Suggest specific test
  scenarios with example inputs and expected outputs when possible.

### Devil's Advocate

The adversarial reviewer. Assumes **every line of code is wrong until
proven otherwise**. This reviewer's job is to try to break the code.

- **Logical correctness**: For each conditional, loop, and branch, construct
  an input or state that would cause it to fail. If you cannot construct one,
  say so explicitly — silence is not acquittal.
- **Hidden assumptions**: What does this code assume that is not enforced?
  Nil-safety, ordering guarantees, single-threaded access, input format,
  environment availability, file existence.
- **Off-by-one errors**: Examine loop bounds, slice operations, index arithmetic,
  range boundaries.
- **Race conditions**: If shared state is accessed, is it protected? If goroutines
  or threads are involved, can operations interleave unsafely?
- **Resource leaks**: Are file handles, connections, channels, locks, and
  goroutines properly cleaned up on all paths including error paths?
- **Failure modes**: What happens when the network is down? The file doesn't exist?
  The input is empty? The input is 10GB? The API returns 500? The context is
  cancelled? The disk is full?
- **Implicit coupling**: Does the code depend on ordering, timing, or side effects
  that are not guaranteed by the interface contract?
- **Prove it wrong or admit you can't**: For each finding, describe the specific
  scenario that breaks it. If you cannot find issues, state explicitly what you
  tested and why the code holds up.

### Technical Writer

Reviews documentation accuracy and completeness relative to the change.
This reviewer should first assess whether the repository has meaningful
documentation (READMEs, doc directories, API docs, user guides, man
pages, etc.). **If the repo has little to no documentation, note this
and exit with no findings** — do not flag the absence of docs that
never existed.

When documentation does exist:

- **Stale docs**: Do the changes modify behavior, flags, APIs, or
  configuration that is described in existing documentation? If so,
  is the documentation updated to match?
- **New features**: Does the change add user-facing functionality
  (new commands, flags, endpoints, config options) that should be
  documented but isn't?
- **Inconsistencies**: Does existing documentation contradict the
  new code? Are examples still accurate?
- **README drift**: If the project README describes setup, usage,
  or architecture, does it still reflect reality after this change?
- **Inline doc quality**: For languages with doc conventions (godoc,
  javadoc, docstrings), are new public APIs documented? Are existing
  docs updated if signatures or behavior changed?

## External Reviewers

The panel optionally includes external review tools that run alongside
the internal specialists. External reviewers execute as CLI commands
in parallel with the sub-agents, and their output is included in the
Panel Arbiter's synthesis input.

### Supported External Reviewers

| Name | CLI Tool | Invocation | Activation |
|------|----------|------------|------------|
| CodeRabbit | `coderabbit` | `coderabbit review --agent --base <base-ref>` | User passes `coderabbit` as argument; tool must be on PATH |

### How External Reviewers Integrate

- External reviewers are **not** sub-agents. They are CLI commands
  invoked via Bash, running in parallel with the sub-agent dispatch.
- Their stdout is captured as-is and included in the verdict under
  its own heading in the specialist findings section.
- The Panel Arbiter treats external reviewer output as a **peer
  specialist**. Its findings carry the same weight as internal
  specialists — corroboration strengthens confidence, conflicts
  require the same explicit resolution as any inter-specialist
  disagreement.
- If an external reviewer command fails (non-zero exit, tool not found),
  record the error in the verdict under that reviewer's heading and
  continue — never block the panel on an external tool failure.
- **Timeout**: external reviewer commands should be run with a
  reasonable timeout (5 minutes). If the command exceeds this, kill it
  and record a timeout error in the verdict.

## Execution Procedure

### Step 1 — Determine Base Ref

Figure out what the changes are being compared against:

- **PR identifier provided**: use `gh pr view` to get the base branch.
- **No PR identifier**: find the merge base. Use the first of
  `upstream/main`, `origin/main`, `upstream/master`, `origin/master`
  that exists.

If no base ref can be determined, error and exit.

Also auto-detect language skills (`skills/lang-*/SKILL.md`) and
profile skills (`skills/profile-*/SKILL.md`) relative to the plugin
root — load any that match the repository.

### Step 2 — Dispatch Specialists & External Reviewers

Launch **all seven specialist sub-agents in a single message** so they
run concurrently. Each sub-agent gets:

- Its specialist scope (from the section above)
- The base ref
- Any loaded language/profile skill content

Sub-agents have full repo access. They read files, run git commands,
and grep the codebase themselves. Use `subagent_type: "general-purpose"`.
Do NOT set the `model` parameter.

Each sub-agent returns findings as a list:
- Severity: BLOCKING | SUGGESTION | NOTE
- File:line reference (when applicable)
- Finding description
- Recommended action

If no issues found, say so with what was checked.

If external reviewers were requested, launch them in the **same
message** as the sub-agents. For CodeRabbit:

```bash
timeout 300 coderabbit review --agent --base <base-ref> 2>&1
```

### Step 3 — Completeness Gate

After all sub-agents and external reviewers return, verify all 7
specialists produced findings (or an explicit "no issues" with
what was checked). If any specialist returned an error or empty
result, re-dispatch it **once**. If the retry also fails, record
the failure and proceed.

External reviewer failures are non-blocking — note the error and
continue.

### Step 4 — Panel Arbiter Synthesis

Perform synthesis directly in the main agent (not a sub-agent):

1. Read all specialist and external reviewer findings
2. Resolve any conflicts between specialists
3. Assign disposition: **APPROVE**, **REQUEST_CHANGES**, or
   **NEEDS_DISCUSSION**
4. Compile required actions (blocking) vs optional follow-ups

**Disposition criteria:**

- **APPROVE**: no unresolved BLOCKING findings
- **REQUEST_CHANGES**: BLOCKING findings that require code changes
- **NEEDS_DISCUSSION**: findings that need author input to resolve

**Arbiter biases:**

- Security over ergonomics
- Codebase consistency over local elegance
- Existing patterns over novel ones
- Devil's Advocate concerns are blocking unless specifically refuted
  by another specialist with a concrete technical explanation

Clean changes with no issues are a valid outcome — do not
manufacture findings.

### Step 5 — Emit Verdict

Load `verdict-template.md` (same directory as this skill) and fill
it with findings and synthesis. One verdict, not per-specialist
outputs. Omit the "External Reviewers" section when none were
requested.

## Quality Gates

A change passes when:

- [ ] Architecture Reviewer: structure and patterns are sound
- [ ] Security & Supply Chain Reviewer: no unmitigated vulnerability or supply chain risk
- [ ] UX & API Reviewer: public surfaces are clear and compatible
- [ ] Codebase Consistency Reviewer: no duplicate helpers, conventions match
- [ ] QA Engineer: adequate test coverage, edge cases addressed
- [ ] Devil's Advocate: no unrefuted failure scenarios
- [ ] Technical Writer: documentation consistent with changes
- [ ] Panel Arbiter: trade-offs ratified, disposition set
