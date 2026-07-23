---
name: "deep-review"
description: "Use when a deeper level of code review is requested. Multi-agent panel code review with specialist reviewers and forced runtime reproducers for all BLOCKING bug findings. Optionally posts to GitHub/GitLab as a PENDING review."
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

```text
/code-review:deep-review [flags] [pr-url-or-number]
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

- `/code-review:deep-review` — all reviewers, review current branch
- `/code-review:deep-review --serial` — cheaper serial mode
- `/code-review:deep-review -qa,-writer` — skip QA and Technical Writer
- `/code-review:deep-review --comment 42` — review PR #42, post verdict as comment
- `/code-review:deep-review --coderabbit https://github.com/org/repo/pull/42`
- `/code-review:deep-review https://gitlab.com/org/repo/-/merge_requests/7`

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

```text
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

Split the argument string on whitespace. Flags (`--serial`,
`--comment`, `--coderabbit`, `--codex`) set modes. Tokens like
`-writer,-qa` exclude those specialists (validate against the
roster; unknown names warned and ignored). A PR URL or bare
integer is the PR identifier (for bare integers, detect platform
from git remote). Error if: all specialists excluded, `--comment`
without PR identifier, or multiple PR identifiers.

#### Step 1.2: Check out the PR and determine base ref

If a PR/MR URL or number was provided, parse it before checkout.
Do not pass a raw URL as an ID:

1. **GitHub URL** (`github.com/.../pull/N`): set
   `PLATFORM=github`, `OWNER`, `REPO`, `PR_NUMBER=N`
2. **GitLab URL** (`gitlab.com/.../-/merge_requests/N`): set
   `PLATFORM=gitlab`, `PROJECT` (group/subgroup/repo path),
   `MR_IID=N`. Prefer `OWNER`/`REPO` only when the project path
   has exactly two segments
3. **Bare integer**: detect platform from `git remote -v`
   (GitHub → `gh`, GitLab → `glab`), then set `PR_NUMBER` or
   `MR_IID`. Derive `OWNER`/`REPO` or `PROJECT` from the matching
   remote URL

Check out locally (always quote shell arguments):

**GitHub:**
```bash
gh pr checkout "$PR_NUMBER"
```

**GitLab:**
```bash
glab mr checkout "$MR_IID" --repo "$PROJECT"
```

If `glab` accepts the full MR URL as a single argument, that is
also fine — but never treat the URL string as `$MR_IID` for flags
that expect a numeric IID alone.

Determine the base branch and remote:

1. If a PR/MR is known, use its base ref
   (`gh pr view --json baseRefName` or `glab mr view --output json`)
2. Discover remotes with `git remote -v` (do **not** hardcode
   `origin`/`upstream`). Prefer the remote whose fetch URL matches
   the PR/MR host and project; otherwise use the remote tracked by
   the current branch (`git branch -vv`), then any remaining remote
3. For each candidate remote, probe `main` then `master`
   (`git ls-remote --heads "$REMOTE" main master`). Record the
   first match as `$BASE_REMOTE` and `$BASE_BRANCH`

Fetch and compute the merge base:

```bash
git fetch "$BASE_REMOTE" "$BASE_BRANCH"
MERGE_BASE=$(git merge-base "$BASE_REMOTE/$BASE_BRANCH" HEAD)
```

If no base ref can be determined, error and exit.

#### Step 1.3: Verify there are changes

Check that the branch has commits ahead of the base. If there are
no changes, stop: "No changes found between HEAD and the base
branch."

If a PR/MR exists, also fetch its description for context.

#### Step 1.4: Detect prior reviews (PR only)

When reviewing a PR/MR, check for previous panel review comments:

**GitHub:**
```bash
gh pr view "$PR_NUMBER" --json comments --jq \
  '.comments[] | select(.body | contains("Generated by /deep-review") or contains("Generated by /code-review:deep-review")) | {createdAt, body}'
```

**GitLab:**
```bash
glab mr note list "$MR_IID" --repo "$PROJECT" 2>/dev/null \
  | rg -n "Generated by /(code-review:)?deep-review" || true
```

If prior panel reviews exist, extract their findings and pass them
to all specialists and the arbiter as context. Specialists should:

- Note which prior findings have been addressed by subsequent commits
- Flag prior findings that remain unresolved
- Avoid re-raising issues that were already noted and resolved
- Call out any regressions — issues that were fixed but reappeared

### Phase 2 — Dispatch Specialists

Each specialist has its own prompt in
[references/specialists/](references/specialists/):

| Specialist | Prompt |
|------------|--------|
| bugs | [references/specialists/bugs.md](references/specialists/bugs.md) |
| adversarial | [references/specialists/adversarial.md](references/specialists/adversarial.md) |
| security | [references/specialists/security.md](references/specialists/security.md) |
| architecture | [references/specialists/architecture.md](references/specialists/architecture.md) |
| consistency | [references/specialists/consistency.md](references/specialists/consistency.md) |
| qa | [references/specialists/qa.md](references/specialists/qa.md) |
| writer | [references/specialists/writer.md](references/specialists/writer.md) |

Append the findings JSON schema to each specialist prompt:

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

#### Parallel Mode (default)

Launch **all enabled specialist sub-agents in a single message** so
they run concurrently, using the Agent tool with
`run_in_background: true`.

Each sub-agent gets:
- The prompt: "You are a {specialist}. Read
  references/specialists/{specialist}.md for your review
  instructions."
- The merge base ref
- The PR number or branch name being reviewed
- Any prior review findings (if detected in Step 1.4)
- The findings JSON schema above

Sub-agents have full read access to the locally checked-out
codebase. They explore the code on their own — read files, grep,
run git commands, etc.

**Sub-agents MUST NOT modify any files, and MUST NOT run any
remote-write git commands** (`git push`, force-push variants,
push to protected branches, or pushes to any remote). They are
read-only reviewers.

Use `subagent_type: "general-purpose"`. Do NOT set the `model`
parameter.

#### Serial Mode (`--serial`)

Run all enabled specialists **inline in the main agent**, one after
another. Do **not** launch sub-agents for specialist dispatch.
(Phase 4 reproducer sub-agents are still launched even in serial
mode — the no-sub-agent constraint applies only to specialists.)

Then for each specialist in roster order, state the specialist name
as a heading, read `references/specialists/{specialist}.md` for
review instructions, review through that lens, and produce findings
in the same JSON format. Context from earlier specialists' file
reads and findings carries over automatically.

**Do NOT modify any files, and do NOT push to any remote.** Serial
mode is read-only, same as parallel.

#### External Reviewers

If external reviewers were requested, launch them in parallel with
(or before, in serial mode) the specialist dispatch.

**CodeRabbit** (`--coderabbit`):
```bash
timeout 300 coderabbit review --agent --base "$MERGE_BASE" 2>&1
```

**Codex** (`--codex`):
```bash
timeout 300 codex review 2>&1
```

External reviewer output is captured as-is and included in the
arbiter's synthesis input as a peer specialist. If a command fails
(non-zero exit, tool not found, timeout), record the error and
continue — never block the panel on an external tool failure.

### Phase 3 — Completeness Gate

After all sub-agents and external reviewers return, verify all
enabled specialists produced findings (or an explicit "no issues"
with what was checked). A valid empty JSON array `[]` with an
explanation of what was checked is success — do **not** retry it.
If any specialist returned an error or a missing/malformed result,
re-dispatch it **once**. If the retry also fails, record the
failure and proceed.

External reviewer failures are non-blocking — note the error and
continue.

### Phase 4 — Reproduce

For every BLOCKING finding with `reproducer_needed: true`, launch
a reproducer subagent (up to 5 in parallel). See
[references/reproducer-prompt.md](references/reproducer-prompt.md)
for the prompt template and result processing rules.

### Phase 5 — Panel Arbiter

Perform synthesis directly in the main agent (not a sub-agent).

1. **Deduplicate** — merge duplicates, keep strongest reproducer
2. **Filter noise** — remove false positives, style nitpicks,
   speculative findings, and issues already addressed in the branch
3. **Resolve conflicts** — corroboration strengthens; adversarial
   concerns are blocking unless concretely refuted
4. **Assign disposition** — APPROVE (no BLOCKING), REQUEST_CHANGES
   (BLOCKING findings), or NEEDS_DISCUSSION (needs author input).
   Biases: security over ergonomics, consistency over elegance,
   reproduced bugs are always BLOCKING, do not manufacture findings
5. **Prioritize** — reproduced security bugs > reproduced functional
   bugs > unreproduced > architecture > style/docs
6. **Emit verdict** — use collapsible `<details>` blocks for
   specialist findings (each specialist collapsed with severity
   counts). Sections: Disposition, Specialist Findings, Panel
   Synthesis, Required Actions, Optional Follow-ups, Stats.
   Footer: `<sub>Generated by [/code-review:deep-review](https://github.com/openshift-eng/ai-helpers/tree/main/plugins/code-review/skills/deep-review)</sub>`.
   Include collapsible reproducer details for confirmed BLOCKING bugs.

### Phase 6 — Post to PR (Optional)

When `--comment` was passed, follow
[references/pr-posting.md](references/pr-posting.md) to post the
verdict to the PR and optionally create inline review comments.
`$OWNER`, `$REPO`, `$PR_NUMBER` / `$PROJECT`, `$MR_IID` must already
be set from Step 1.2.

## Quality Gates

A change passes when: no unresolved functional bugs, no unrefuted
adversarial scenarios, no unmitigated vulnerabilities or supply
chain risks, sound architecture, no duplicate helpers, adequate
test coverage, documentation consistent with changes, and the
panel arbiter has ratified the disposition.

## Error Handling

- **`gh`/`glab` not authenticated**: Review can still run on a
  locally checked-out branch.
- **No PR exists**: Skip Phase 6; the verdict is the deliverable.
- **External tool not installed/timeout**: Skip, warn, continue.
- **Subagent timeout**: Report which specialist timed out, continue.
- **No changes**: Stop — "No changes found."
- **Review creation fails (422)**: Remove bad comments, retry.

## Guardrails

- Never submit a PR review without explicit user confirmation.
- Never use `"event"` in the initial review creation payload.
- **Review agents MUST NOT modify any files in the working tree.**
- **Never `git push`, force-push, or push to protected branches
  (`main`/`master`) or any other remote.** Do not assume remote
  names — discover them with `git remote -v` when needed for reads.
- Reproducers run in /tmp. Do not push reproducer files.
- Do not run destructive operations in reproducers.
- Cap at 30 inline PR comments. Overflow goes to the review body.
