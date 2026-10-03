# Agentic Rebase Manager: Workflow Blueprint

The `rebase-manager` is a state-aware agentic tool designed for the Network Ingress & DNS (NI&D) team to automate and track upstream rebases for repositories such as `openshift/coredns`.

Unlike generic, one-shot rebase scripts, this tool maintains context across runs and responds to human feedback during the review process. It is designed to be executed periodically (e.g., weekly via CI/CD) or manually, determining its next actions dynamically by inspecting local state, git history, and active GitHub Pull Request metadata.

---

## Architecture

At the start of each execution, the tool queries the local repository (specifically the `.rebase/` subdirectory) and the GitHub API to infer the current workflow phase.

```text
                   [Check Local .rebase/ & Open PRs]
                                  |
         +------------------------+------------------------+
         | No Active PR/Branch    | PR is Draft            | PR is Ready (Non-Draft)
         v                        v                        v
+------------------+     +------------------+     +------------------+
|    Phase 1:      |     |    Phase 2:      |     |    Phase 3:      |
|   DISCOVERY &    |     |   ACTIVE DRAFT   |     |    FINAL PROW    |
|    REPORTING     |     |  FEEDBACK LOOP   |     |  REVIEW & MERGE  |
+------------------+     +------------------+     +------------------+
```

---

## Detailed Workflow Phases

### Phase 1: DISCOVERY & REPORTING (No active rebase PR or branch)

*   **Detection Conditions:**
    *   No local or remote `rebase-<tag>` branch exists.
    *   No open Pull Request with the title prefix `"Rebase to <tag>"` exists on the target repository.
*   **Workflow Steps:**
    1.  **State Directory Setup:** Create a local `.rebase/` directory if it does not exist, and append `.rebase/` to `.gitignore` to prevent committing transient rebase states.
    2.  **Fetch & Sync:** Discover tracked remotes via `git remote -v` and run `git fetch --all --tags`.
    3.  **Version Comparison:** Compare the latest tag in `openshift/master` (or main) against the latest stable upstream release tag (excluding `-alpha`, `-beta`, or `-rc`).
    4.  **No-Op Handshake:** If the repository is fully up-to-date, log the status, output a summary, and terminate.
    5.  **Release Report & Carry Commit Listing:** If behind, compile and write two files to the local `.rebase/` directory:
        *   `.rebase/release-report.md`: Highlighting comparison tags, upstream changelogs, major features, and breaking changes.
        *   `.rebase/commits.tsv`: Listing all downstream carry commits (`UPSTREAM:` commits on `openshift/master` since the previous tag's merge-base) with automated decisions (`cherry-pick`, `squash`, `drop`).
    6.  **Human Feedback Input (Optional):** The team can review the generated report and manually edit the `.rebase/commits.tsv` file to override decisions (e.g., changing a decision from `cherry-pick` to `drop` or vice versa) before proceeding.

---

### Phase 2: ACTIVE DRAFT & FEEDBACK LOOP (Draft PR is open on GitHub)

*   **Detection Conditions:**
    *   A local/remote branch `rebase-<tag>` exists, AND/OR an open Pull Request exists on GitHub in **Draft** mode.
*   **Workflow Steps:**
    1.  **Initial Rebase & Draft PR Generation (if not yet open):**
        *   Checkout a branch named `rebase-<tag>` off the upstream tag.
        *   Merge `openshift/master` with `-s ours` strategy.
        *   Execute the cherry-pick and squash decisions. If a custom `.rebase/commits.tsv` is found, incorporate any manual overrides made by the team during Phase 1.
        *   Run Go dependency management (`go mod tidy && go mod vendor`) and compile checks (`make`, `go build`, `go test`).
        *   On success, explicitly prompt the user for approval, then push the branch (without forcing) to the discovered remote and open a **Draft Pull Request** on GitHub against the target repository.
        *   **Agenda Integration:** The Draft PR description is written to *be* the official agenda for the Rebase Approval meeting (detailing changelogs, carries, and build status).
    2.  **Interactive Feedback Iteration (if Draft PR is already open):**
        *   During meetings or async reviews, the team provides feedback by leaving comments/discussion threads directly on the draft PR.
        *   When the skill is executed, it fetches all open comments on the PR:
            *   Analyze feedback (e.g., requests to change commit decisions, resolve test failures, or adjust configurations).
            *   Check out the `rebase-<tag>` branch, apply requested code/rebase alterations, and re-run build and verification tests.
            *   Reply directly to the comment threads on GitHub to document the changes and optionally resolve the threads.
            *   Prompt the user for approval, then push updated commits to the draft PR without force-pushing.
*   **Exit Condition:** A human gatekeeper moves the PR out of draft mode (marking it "Ready for Review"). This acts as the signal that the rebase is approved by the team.

---

### Phase 3: FINAL PROW REVIEW & MERGE (PR is open, Draft mode is OFF)

*   **Detection Conditions:**
    *   An open PR exists on GitHub and is **not** in draft mode.
*   **Workflow Steps:**
    1.  **CI Monitoring:** Monitor GitHub check runs and Prow job statuses on the PR.
    2.  **Failure Reporting:** If final CI/Prow jobs fail, extract failure logs and report them. (Human review continues to gate final merges via `/lgtm` and `/approve` commands).
    3.  **Completion & Cleanup:** Once the PR has been successfully merged:
        *   Clean up the local `.rebase/` directory and delete local `rebase-<tag>` branches.
        *   Declare the rebase cycle complete and log success.
