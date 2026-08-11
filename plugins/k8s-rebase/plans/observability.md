# Observability — k8s-rebase Skill

## Goal

The skill currently runs as a background session. We can see commits and
gate reports, but not *why* decisions were made, what issues the agent hit,
or how well it reasoned. Adding observability makes debugging faster, reveals
skill quality gaps, and enables automated improvement discovery.

---

## 1. Step narrative log — HIGH VALUE

**What**: After each orchestrator step completes, the agent appends a
narrative summary to `.rebase-tmp/narrative.md`:

```markdown
## Step 2: Compile

Found 3 compilation errors:
- pkg/foo/bar.go:42 — reflect.Ptr removed in k8s 1.35, replaced with reflect.Pointer
- pkg/ovn/controller.go:91 — API change in admission webhook signature
- test/e2e/suite.go:17 — klog v1 import, migrated to v2

Fixed in 2 commits. All step2 gates passed first attempt.
```

**Why**: Currently this context is lost. `make results` shows hunk counts
but not what kind of work the rebase required. The narrative becomes the
human-readable artifact to review when a rebase looks off.

**Implementation**: Add to each step .md: "After all gates pass, append a
brief narrative to `.rebase-tmp/narrative.md` summarizing what issues were
found and how they were resolved." Read existing narrative first to append.

---

## 2. Court reporter — MEDIUM VALUE

**What**: Add a Phase D to court after the jury vote. A reporter agent reads
prosecution, defense, judge, and all juror transcripts and produces a
1-paragraph human-readable summary:

```
COURT SUMMARY: The rebase correctly targets k8s 1.35.3. The main
contested point was the removal of SetFromMap({WatchListClient: false})
from 4 Ginkgo suites — prosecution argued this risks test hangs; defense
and 2 jurors found the env-var wiring sufficient. The PASS (2-1) reflects
genuine judgment, not consensus.
```

**Why**: Raw court transcripts are 3-5 pages each. The summary tells you
in 5 seconds what was contested and why the verdict was what it was.
Currently a human has to read all transcripts to understand a 2-1 split.

**Implementation**: In `cmd_court` after the jury phase, launch one more
`claude -p` call with pros/def/judge/juror content → summarize in 1
paragraph → write to `cdir/summary.txt` and print to stdout.

---

## 3. Artifact review agents — MEDIUM VALUE

**What**: A new `make review` target (or part of `make court`) that
launches analysis agents over completed rebase artifacts:

- **Pattern agent**: reads commits, identifies what autofix patterns fired
  and whether they look right
- **Gate agent**: reads all gate reports, flags any suspicious PASSes
  (e.g., a gate that always passes in 0ms, might mean it's not running)
- **Diff agent**: reads the VS KNOWN-GOOD diff and flags unusual patterns
  (very large diffs, specific files that always differ)

These run asynchronously after the test completes and write findings to
`.matrix-state/review/<repo>-<version>.md`.

**Why**: Currently we do this manually. The agents that ran the test session
don't have fresh eyes — they satisfice on "PASS." Separate review agents
with no memory of the run catch what the skill misses.

---

## 4. Human-readable results reporter — LOW-MEDIUM VALUE

**What**: `make report repo=X version=Y` produces a narrative of the full
run:

```
ovn-org/ovn-kubernetes 1.36.2 — PASS (2026-08-19)

Rebase: 15 commits above from_commit. k8s.io/* bumped to v0.36.2.
Autofix: klog v1→v2 migration (7 files), reflect.Ptr→Pointer (3 files).
Gates: 32/32 pass (4 SKIP). Step 4 lint took 26m.
VS known-good: 287 code hunks differ. Court: PASS (2-1, contested on
WatchListClient SetFromMap removal — see court summary).
```

**Implementation**: A script that reads results.tsv + gate reports +
narrative.md + court summary.txt and formats them into a concise report.

---

## 5. `make lint` as skill improvement surface — LOW VALUE

**What**: Add a `make skill-review` target that launches a workflow to
review recent gate reports and narrative logs looking for:
- Gates that always PASS without substance
- Agent decisions that look wrong in retrospect
- Patterns in what types of fixes are needed per repo/version

This is the "automated improvement discovery" piece.

---

## Implementation order

1. **Court reporter** (Phase D) — smallest change, highest immediate value
   for understanding court verdicts
2. **Step narrative log** — enables everything else; without narrative context
   the artifact review agents have less to work with
3. **Artifact review agents** — builds on narrative + gate reports
4. **Human-readable reporter** — assembles the above into a command
5. **Skill review target** — longer-horizon, depends on accumulated data
