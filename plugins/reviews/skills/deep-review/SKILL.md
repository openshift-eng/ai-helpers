---
name: "deep-review"
description: "Multi-agent panel code review with specialist reviewers and forced runtime reproducers for all BLOCKING bug findings. Optionally posts to GitHub/GitLab as a PENDING review."
argument-hint: "[--serial] [--comment] [--coderabbit] [--codex] [-reviewer,...] [pr-url-or-number]"
---

# Deep Review — Multi-Specialist Panel Review with Reproducers

Review a branch's changes with parallel specialist subagent reviewers,
each examining the code through a different lens. Verify every bug
finding with a runtime reproducer. Optionally post to GitHub/GitLab
as a PENDING review.

No PR/MR is required — the review works on any branch with commits
ahead of its base.

**Two execution modes:**

- **Parallel (default)**: Each specialist runs as a dedicated sub-agent
  concurrently. Thorough but expensive — each sub-agent independently
  derives its own view of the codebase.
- **Serial (`--serial`)**: All specialists run inline in the main agent,
  one after another. Significantly cheaper because the codebase context
  is derived once and shared across all specialists. Trade-off: reviews
  run sequentially, and later specialists can see prior specialists'
  findings (which may bias their analysis).

## Arguments

```
/reviews:deep-review [flags] [pr-url-or-number]
```

| Argument | Description |
|----------|-------------|
| `--serial` | Run all specialists inline instead of as parallel sub-agents |
| `--comment` | Post the verdict as a PR comment after review. Requires a PR identifier |
| `--coderabbit` | Include CodeRabbit as an external reviewer |
| `--codex` | Include OpenAI Codex as an external reviewer |
| `-reviewer` | Exclude a specialist (e.g., `-writer,-qa`). All enabled by default |
| pr identifier | GitHub/GitLab PR URL or bare PR number. Optional |

Examples:

- `/reviews:deep-review` — all reviewers, review current branch
- `/reviews:deep-review --serial` — cheaper serial mode
- `/reviews:deep-review -qa,-writer` — skip QA and Technical Writer
- `/reviews:deep-review --comment 42` — review PR #42, post verdict as comment
- `/reviews:deep-review --coderabbit https://github.com/org/repo/pull/42`
- `/reviews:deep-review https://gitlab.com/org/repo/-/merge_requests/7`

## Specialist Panel

All are enabled unless excluded with `-`:

| Specialist | Lens | Reproducer? |
|------------|------|-------------|
| **bugs** | Functional bugs: missing calls, wrong logic, unhandled edge cases | Yes — mandatory |
| **adversarial** | Break the code: bad inputs, race conditions, boundary values | Yes — mandatory |
| **security** | Vulnerabilities, credential handling, dependency trust, supply chain integrity | When claiming a concrete exploit |
| **architecture** | Structural patterns, SOLID, cross-file impact, module boundaries | No |
| **consistency** | Duplicate helpers, convention drift, style match with existing code | No |
| **qa** | Test coverage gaps, missing edge-case tests, concrete test suggestions | No |
| **writer** | Documentation accuracy, staleness, consistency with code changes | No |

### Routing Topology

```
  bugs  adversarial  security  architecture  consistency  qa  writer
    \_______|__________|__________|___________|___________|____|
                                 |
                           [reproduce]  ← bug/security findings only
                                 |
                                 v
                           panel-arbiter
                         (final call)
```

- Specialists raise findings independently — no implicit consensus.
  Each runs as a separate sub-agent and cannot see the others' output.
- Reproducer agents verify bug/security claims before arbitration.
- Panel Arbiter synthesizes after all specialists and reproducers complete.

## Procedure

### Phase 1 — Setup

#### Step 1.1: Parse arguments

Split the argument string on whitespace. Classify each token:

- `--serial` — enable serial execution mode
- `--comment` — post verdict as a PR comment after review
- `--coderabbit` — include CodeRabbit external reviewer
- `--codex` — include Codex external reviewer
- A token starting with `-` followed by specialist name(s) (e.g.,
  `-writer` or `-qa,-writer`) — exclude those specialists. If the
  token contains commas, split on commas and treat each segment as
  a separate exclusion. Validate each name against the known
  specialist roster (bugs, adversarial, security, architecture,
  consistency, qa, writer). Unknown names are warned and ignored.
- A **PR URL** (contains `github.com` and `/pull/`, or `gitlab.com`
  and `/merge_requests/`) or **bare integer** — PR identifier.
  For a bare integer, determine the platform from the git remote
  URL: if it contains `github.com`, use `gh`; if it contains
  `gitlab.com`, use `glab`. If ambiguous, ask the user.
- Anything else — warn and ignore

If all specialists are excluded, error and exit: "At least one
specialist must be enabled."

If `--comment` is passed without a PR identifier, error and exit.
If more than one PR identifier is found, error and exit.

#### Step 1.2: Check out the PR and determine base ref

If a PR/MR URL or number was provided, check out that PR locally
so the code under review is on disk:

**GitHub:** `gh pr checkout $PR_NUMBER`
**GitLab:** `glab mr checkout $MR_IID`

Determine the base branch and remote. In order of preference:
1. If a PR/MR is known, use its base ref (`gh pr view --json baseRefName`)
   and the remote that hosts the PR (typically `origin`)
2. Otherwise, check which of `upstream/main`, `origin/main`,
   `upstream/master`, `origin/master` exists first. Record both the
   remote name (`$BASE_REMOTE`) and branch (`$BASE_BRANCH`).

Fetch and compute the merge base:

```bash
git fetch $BASE_REMOTE $BASE_BRANCH
MERGE_BASE=$(git merge-base $BASE_REMOTE/$BASE_BRANCH HEAD)
```

If no base ref can be determined, error and exit.

#### Step 1.3: Verify there are changes

Check that the branch has commits ahead of the base. If there are
no changes, stop: "No changes found between HEAD and the base
branch."

If a PR/MR exists, also fetch its description for context.

#### Step 1.4: Detect prior reviews (PR only)

When reviewing a PR, check for previous panel review comments:

```bash
gh pr view <pr> --json comments --jq '.comments[] | select(.body | contains("Generated by /deep-review")) | {createdAt, body}'
```

If prior panel reviews exist, extract their findings and pass them
to all specialists and the arbiter as context. Specialists should:

- Note which prior findings have been addressed by subsequent commits
- Flag prior findings that remain unresolved
- Avoid re-raising issues that were already noted and resolved
- Call out any regressions — issues that were fixed but reappeared

### Phase 2 — Dispatch Specialists

#### Parallel Mode (default)

Launch **all enabled specialist sub-agents in a single message** so
they run concurrently, using the Agent tool with
`run_in_background: true`.

Each sub-agent gets:
- The merge base ref
- The PR number or branch name being reviewed
- Any prior review findings (if detected in Step 1.4)

Sub-agents have full read access to the locally checked-out
codebase. They explore the code on their own — read files, grep,
run git commands, etc.

**Sub-agents MUST NOT modify any files.** They are read-only
reviewers. No edits, no writes, no code changes.

Use `subagent_type: "general-purpose"`. Do NOT set the `model`
parameter.

Every specialist sub-agent MUST return its findings as a JSON array
in a fenced `json` code block at the end of its response:

```json
[
  {
    "file": "src/example.py",
    "line": 42,
    "severity": "BLOCKING",
    "title": "Short title",
    "body": "Description of the issue",
    "suggestion": "Recommended action or null",
    "reproducer_needed": true
  }
]
```

**Severity values**: `BLOCKING` | `SUGGESTION` | `NOTE`

If no issues found, return an empty array and state what was checked.

#### Serial Mode (`--serial`)

Run all enabled specialists **inline in the main agent**, one after
another. Do **not** launch sub-agents for specialist dispatch.
(Phase 4 reproducer sub-agents are still launched even in serial
mode — the no-sub-agent constraint applies only to specialists.)

Then for each specialist in roster order, state the specialist name
as a heading, review through that lens using the scope below, and
produce findings in the same JSON format. Context from earlier
specialists' file reads and findings carries over automatically.

**Do NOT modify any files.** Serial mode is read-only, same as
parallel.

#### External Reviewers

If external reviewers were requested, launch them in parallel with
(or before, in serial mode) the specialist dispatch.

**CodeRabbit** (`--coderabbit`):
```bash
timeout 300 coderabbit review --agent --base $MERGE_BASE 2>&1
```

**Codex** (`--codex`):
```bash
timeout 300 codex review 2>&1
```

External reviewer output is captured as-is and included in the
arbiter's synthesis input as a peer specialist. If a command fails
(non-zero exit, tool not found, timeout), record the error and
continue — never block the panel on an external tool failure.

### Specialist Scopes

---

**bugs** specialist:

> You are a meticulous code reviewer focused exclusively on finding
> FUNCTIONAL BUGS in a pull request.
>
> **Your focus**: Missing function calls or initialization. Wrong
> logic (inverted conditions, off-by-one, wrong operator). Unhandled
> edge cases (nil/null, empty collections, zero values). Race
> conditions. Resource leaks. Error handling gaps. Type mismatches.
> Contract violations (caller passes wrong args, callee returns
> unexpected values). Inherited methods that don't work in the
> subclass context.
>
> **Ignore**: Style, formatting, naming. "Could be improved"
> suggestions. Test coverage gaps (unless a test is WRONG).
> Documentation.
>
> **Method**: Identify changed files using the merge base ref.
> For each changed file, read the FULL file to understand context.
> Trace code paths — follow function
> calls, check callers and callees, check base class methods that
> are inherited but not overridden. For each bug found, set
> `reproducer_needed: true`.
>
> **You MUST NOT modify any files.** Read-only review only.

---

**adversarial** specialist:

> You are an adversarial code reviewer. Your job is to BREAK the
> code in this pull request. Assume **every line of code is wrong
> until proven otherwise**. Think like a malicious user, a chaos
> monkey, or a fuzzer.
>
> **Your focus**:
> - **Logical correctness**: For each conditional, loop, and branch,
>   construct an input or state that would cause it to fail. If you
>   cannot construct one, say so explicitly — silence is not acquittal.
> - **Hidden assumptions**: What does this code assume that is not
>   enforced? Nil-safety, ordering guarantees, single-threaded access,
>   input format, environment availability, file existence.
> - **Off-by-one errors**: Examine loop bounds, slice operations,
>   index arithmetic, range boundaries.
> - **Race conditions**: If shared state is accessed, is it protected?
>   Can operations interleave unsafely?
> - **Resource leaks**: Are file handles, connections, channels, locks
>   properly cleaned up on all paths including error paths?
> - **Failure modes**: What happens when the network is down? The file
>   doesn't exist? The input is empty? The input is 10GB? The API
>   returns 500? The context is cancelled? The disk is full?
> - **Implicit coupling**: Does the code depend on ordering, timing,
>   or side effects not guaranteed by the interface contract?
>
> **Prove it wrong or admit you can't**: For each finding, describe
> the specific scenario that breaks it. If you cannot find issues,
> state explicitly what you tested and why the code holds up.
>
> Read full source files for context. Set `reproducer_needed: true`
> for every finding.
>
> **You MUST NOT modify any files.** Read-only review only.

---

**security** specialist:

> You are a security and supply-chain reviewer. You operate with a
> **fails-closed** bias — when uncertain whether a pattern is safe,
> flag it. False positives are preferable to missed vulnerabilities.
>
> **Vulnerability surfaces:**
> - **Injection**: SQL, command, template, log, header injection
> - **Authentication/authorization**: Token handling, permission
>   checks, credential storage
> - **Input validation**: Untrusted input at system boundaries
> - **Secret management**: Hardcoded secrets, secrets in logs,
>   config exposure
> - **Cryptography**: Weak algorithms, improper random number
>   generation
>
> **Supply chain risk:**
> - **New dependencies**: Is the dep necessary? Actively maintained?
>   Known security record? How many transitive deps?
> - **Dependency changes**: Version bumps, removed pins, loosened
>   constraints, yanked versions
> - **Lockfile integrity**: Unexpected hash changes in `go.sum`,
>   `package-lock.json`, `yarn.lock`, `Cargo.lock`, etc.
> - **Build pipeline**: CI config, Makefile, Dockerfile, build
>   scripts — untrusted sources, download URLs, remote code execution
> - **Transitive trust**: New external API calls, download URLs,
>   certificate trust, registry sources
> - **Vendored code**: Do vendored changes match declared dependency
>   changes?
>
> Set `reproducer_needed: true` only for findings where a concrete
> exploit can be demonstrated. Set severity to `BLOCKING` for
> confirmed risks.
>
> **You MUST NOT modify any files.** Read-only review only.

---

**architecture** specialist:

> You are an architecture reviewer evaluating structural and design
> decisions.
>
> **Your focus**:
> - **Single Responsibility**: Does each new function/type/module
>   have one clear job?
> - **Cross-file impact**: Do changes ripple correctly through
>   callers and dependents?
> - **Abstraction level**: Are new abstractions justified or
>   premature?
> - **Module boundaries**: Are package/module imports clean? Any
>   circular dependencies?
> - **Error handling**: Are errors propagated correctly? No swallowed
>   errors?
> - **Pattern consistency**: Do new patterns match existing
>   architectural conventions?
> - **API surface**: Is the public interface minimal and hard to
>   misuse?
> - **Coupling**: Does this create tight coupling that's costly to
>   change later?
>
> Anti-patterns to flag: god functions, shotgun surgery, feature envy,
> inappropriate intimacy, premature abstraction.
>
> Set `reproducer_needed: false`. Focus on decisions costly to
> change.
>
> **You MUST NOT modify any files.** Read-only review only.

---

**consistency** specialist:

> You are a codebase consistency reviewer. You must **actively read
> existing code** in the repository — grep and find to locate
> potential duplicates and existing conventions rather than reviewing
> the changed files in isolation.
>
> **Your focus**:
> - **Duplicate helpers**: Does the PR introduce a function, utility,
>   or pattern that already exists elsewhere? Search for similar
>   implementations before accepting new ones.
> - **Convention adherence**: Does new code follow the same naming
>   conventions, file organization, import ordering, and structural
>   patterns as existing code in the same package/module?
> - **Style match**: Does the code style (error handling idiom,
>   logging pattern, test structure) match the surrounding codebase?
> - **Shared utilities**: Does the PR use the project's established
>   utility packages rather than inlining?
> - **Configuration patterns**: Do new config values, environment
>   variables, or constants follow existing naming and placement?
> - **Test patterns**: Do new tests follow the same structure,
>   assertion style, and helper usage as existing tests?
>
> Set `reproducer_needed: false`.
>
> **You MUST NOT modify any files.** Read-only review only.

---

**qa** specialist:

> You are a QA engineer reviewing test coverage and quality.
>
> **Your focus**:
> - **Coverage gaps**: For each new or modified function with
>   non-trivial logic, verify that tests exist. Flag public/exported
>   functions that lack tests entirely.
> - **Untested error paths**: Identify error branches, edge cases,
>   and failure modes with no corresponding test.
> - **Test quality**: Are tests asserting meaningful behavior or just
>   achieving line coverage? Look for tests that pass trivially,
>   assert nothing, or test implementation details.
> - **Edge cases**: Identify concrete edge-case inputs the author
>   should test: empty inputs, nil/null, boundary values, concurrent
>   access, large inputs, malformed data.
> - **Regression coverage**: If the change fixes a bug, is there a
>   test that would have caught it?
> - **Concrete suggestions**: Do not just say "add tests." Suggest
>   specific test scenarios with example inputs and expected outputs.
>
> Set `reproducer_needed: false`.
>
> **You MUST NOT modify any files.** Read-only review only.

---

**writer** specialist:

> You are a technical writer reviewing documentation accuracy.
>
> First assess whether the repository has meaningful documentation
> (READMEs, doc directories, API docs, user guides). **If the repo
> has little to no documentation, note this and exit with no
> findings** — do not flag the absence of docs that never existed.
>
> When documentation does exist:
> - **Stale docs**: Do changes modify behavior, flags, APIs, or
>   config described in existing docs? Are docs updated to match?
> - **New features**: Does the change add user-facing functionality
>   that should be documented but isn't?
> - **Inconsistencies**: Does existing documentation contradict the
>   new code? Are examples still accurate?
> - **README drift**: If the README describes setup/usage/architecture,
>   does it still reflect reality after this change?
> - **Inline doc quality**: For languages with doc conventions
>   (godoc, javadoc, docstrings), are new public APIs documented?
>
> Set `reproducer_needed: false`.
>
> **You MUST NOT modify any files.** Read-only review only.

### Phase 3 — Completeness Gate

After all sub-agents and external reviewers return, verify all
enabled specialists produced findings (or an explicit "no issues"
with what was checked). If any specialist returned an error or
empty result, re-dispatch it **once**. If the retry also fails,
record the failure and proceed.

External reviewer failures are non-blocking — note the error and
continue.

### Phase 4 — Reproduce

Collect all findings from all specialists.

For every finding where `reproducer_needed` is `true` AND severity
is `BLOCKING`:

Launch a **reproducer subagent** (up to 5 in parallel, 10 minute
timeout each). Each gets this prompt:

> Create and execute a minimal reproducer to verify this bug.
>
> **Finding**: {title} in {file}:{line} — {body}
>
> **Instructions**:
> 1. Read the file and surrounding code for full context
> 2. Design the SMALLEST test case that demonstrates the bug
> 3. Create the reproducer files (scripts, configs, inputs)
> 4. Execute it and capture the output
> 5. Report pass (bug confirmed) or fail (not reproduced)
>
> **Requirements**:
> - Must be runnable, not a thought experiment
> - Must produce a clear pass/fail result
> - Create ALL reproducer files in /tmp — do not write any files
>   to the working tree
> - If the bug requires infrastructure you can't create locally,
>   explain why and report `not_reproducible`
> - Do not run destructive operations
> - Clean up temp files when done
>
> Return a JSON object in a fenced `json` block:
> ```json
> {
>   "reproduced": "confirmed",
>   "explanation": "What happened",
>   "steps": "Exact commands and files",
>   "expected": "Correct behavior",
>   "actual": "What actually happened (real output)",
>   "files": [{"path": "name", "content": "..."}]
> }
> ```
>
> **`reproduced` values**: `"confirmed"` | `"not_confirmed"` |
> `"not_reproducible"`

#### Processing results

- `reproduced: "confirmed"` — keep as BLOCKING, attach reproducer
  details
- `reproduced: "not_confirmed"` — downgrade severity to
  `SUGGESTION`, add note: "Reproducer did not confirm this bug —
  may be a false positive or require conditions not tested."
- `reproduced: "not_reproducible"` — keep severity, add note
  explaining why

### Phase 5 — Panel Arbiter

Perform synthesis directly in the main agent (not a sub-agent).

#### Step 5.1: Deduplicate

Multiple specialists may find the same issue. Merge duplicates,
keeping the most detailed description and the strongest reproducer.

#### Step 5.2: Filter noise

Remove findings that are:
- Clearly false positives (contradicted by code the reviewer missed)
- Style nitpicks that don't match the project's conventions
- Speculative ("this could be a problem if...") without evidence
- Already addressed elsewhere in the branch (e.g., in a later commit)

#### Step 5.3: Resolve conflicts

Where specialists disagree, resolve explicitly:
- Corroboration between specialists (or external reviewers)
  strengthens confidence
- Conflicts require explicit resolution with reasoning
- Devil's Advocate (adversarial) concerns are blocking unless
  specifically refuted by another specialist with a concrete
  technical explanation

#### Step 5.4: Assign disposition

**Disposition criteria:**

- **APPROVE**: No unresolved BLOCKING findings
- **REQUEST_CHANGES**: BLOCKING findings that require code changes
- **NEEDS_DISCUSSION**: Findings that need author input to resolve

**Arbiter biases:**

- Security over ergonomics
- Codebase consistency over local elegance
- Existing patterns over novel ones
- Reproduced bugs are always BLOCKING
- Clean changes with no issues are a valid outcome — do not
  manufacture findings

#### Step 5.5: Prioritize

Rank remaining findings:
1. Reproduced bugs with security implications
2. Reproduced functional bugs
3. Unreproduced but plausible bugs (downgraded to SUGGESTION)
4. Architecture/design concerns
5. Style, consistency, and documentation notes

#### Step 5.6: Emit verdict

Present the verdict using this structure:

```
## Deep Review Verdict

**Disposition**: <APPROVE | REQUEST_CHANGES | NEEDS_DISCUSSION> <qualifier>

---

### Specialist Findings

**Bugs**: <findings>

**Adversarial**: <findings, with "Prove it wrong or admit you can't" results>

**Security & Supply Chain**: <findings>

**Architecture**: <findings>

**Codebase Consistency**: <findings>

**QA Engineer**: <findings>

**Technical Writer**: <findings>

---

### External Reviewers

**CodeRabbit**: <output or "not requested">

**Codex**: <output or "not requested">

---

### Panel Synthesis

<Synthesize all findings. Resolve disagreements. Note corroboration
between reviewers. Ratify disposition. If reviewers agreed and the
change is straightforward, say so plainly in one or two sentences.>

---

### Required Actions Before Merge

1. <required action with file:line pointer, reproducer summary>

(If APPROVE with no required actions, write "None.")

---

### Optional Follow-ups

- <suggestions out of scope for this change>

---

### Stats

Arbiter summary: N findings from M specialists.
Kept: X blocking (Y reproduced), Z suggestions/notes.
Dropped: W duplicates, V false positives.

<sub>Generated by /deep-review</sub>
```

Omit the "External Reviewers" section when none were requested.
For each BLOCKING finding with a reproducer, include a collapsible
reproducer section showing steps, expected, and actual output.

### Phase 6 — Post to PR (Optional)

This phase runs ONLY when `--comment` was passed with a PR identifier.

#### Step 6.1: Post as comment

Post the full verdict as a PR comment:

**GitHub:**
```bash
gh pr comment $PR_NUMBER --body "$(cat <<'EOF'
<verdict content>
EOF
)"
```

**GitLab:** Use `glab mr comment`.

If the comment fails, report the error but still display the verdict
to the user — the review itself is not lost.

#### Step 6.2: Offer inline review (GitHub only)

After posting the comment, offer to also create a PENDING review
with inline comments on specific lines:

**Ask the user**: "Want me to also add inline review comments?
(yes / no)"

If the user says no, stop here.

If yes, compute diff positions and create the review:

**GitHub position rules:**
- The `position` is the 1-based line index in the file's unified
  diff, where position 1 is the first line AFTER the first `@@`
  hunk header. `@@` headers are NOT counted.
- Count every line (context, additions, deletions) sequentially
  across ALL hunks. Each new `@@` header is skipped in the count.
- The count does NOT reset between hunks

If a finding's line falls outside any diff hunk, skip the inline
comment and include it in the review body instead.

**CRITICAL**: Do NOT include an `"event"` field in the JSON payload.
Omitting it creates a PENDING review.

```bash
gh api repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews \
  --method POST \
  --input /tmp/deep-review-payload.json
```

Cap at **30 inline comments**. Overflow goes to the review body.

Format inline comments:

**For BLOCKING findings with a confirmed reproducer:**
```markdown
**Bug: {title}**

{body}

Fix: {suggestion}

<details>
<summary>Reproducer</summary>

**Steps:** {steps}

**Expected:** {expected}

**Actual:** {actual}
</details>
```

**For findings where the reproducer failed:**
```markdown
**Potential: {title}**

{body}

Note: A reproducer was attempted but did not confirm this bug.
Manual verification recommended.
```

**For SUGGESTION/NOTE findings:**
```markdown
**{Severity}: {title}**

{body}

Suggestion: {suggestion}
```

#### Step 6.3: User approval gate

```
PENDING review created with N inline comments on PR #NNN.

Commands:
  "submit"           — post as informational comment
  "request changes"  — post requesting changes
  "drop"             — delete the pending review
```

**Do NOT submit automatically. Wait for the user.**

On "submit":
```bash
gh api repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews/$REVIEW_ID/events \
  --method POST -f event="COMMENT"
```

On "request changes":
```bash
gh api repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews/$REVIEW_ID/events \
  --method POST -f event="REQUEST_CHANGES"
```

On "drop":
```bash
gh api -X DELETE repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews/$REVIEW_ID
```

## Quality Gates

A change passes when:

- [ ] Bugs: no unresolved functional bugs
- [ ] Adversarial: no unrefuted failure scenarios
- [ ] Security & Supply Chain: no unmitigated vulnerability or supply chain risk
- [ ] Architecture: structure and patterns are sound
- [ ] Codebase Consistency: no duplicate helpers, conventions match
- [ ] QA Engineer: adequate test coverage, edge cases addressed
- [ ] Technical Writer: documentation consistent with changes
- [ ] Panel Arbiter: trade-offs ratified, disposition set

## Error Handling

- **`gh`/`glab` not authenticated**: Affects PR checkout (Phase 1)
  for private repos and PR posting (Phase 6). The review can still
  run on a locally checked-out branch without authentication.
- **No PR exists**: Fine — skip Phase 6, the verdict is the
  deliverable.
- **External tool not installed**: Skip that reviewer, warn, continue.
- **External tool timeout**: Record timeout error, continue.
- **Subagent timeout**: Report which specialist timed out, continue
  with available results.
- **No changes**: Stop — "No changes found."
- **Position computation failure**: Move finding to review body.
- **Review creation fails (422)**: Remove bad comments, retry.

## Guardrails

- Never submit a PR review without explicit user confirmation.
- Never use `"event"` in the initial review creation payload.
- **Review agents MUST NOT modify any files in the working tree.**
  All specialists are read-only reviewers.
- Reproducers run locally in /tmp. Do not push reproducer files
  or modify the working tree.
- Do not run destructive operations in reproducers. Mark as
  `not_reproducible` instead.
- Cap at 30 inline PR comments. Overflow goes to the review body.
