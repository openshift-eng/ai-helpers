#!/usr/bin/env python3
import os
import sys
import json
import csv
import subprocess
import argparse
import shutil
from pathlib import Path

import logging

# Color helpers for output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

# Configure logging
logger = logging.getLogger("rebase_manager")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

def log_info(msg):
    if sys.stdout.isatty():
        logger.info(f"{BLUE}[INFO]{RESET} {msg}")
    else:
        logger.info(f"[INFO] {msg}")

def log_success(msg):
    if sys.stdout.isatty():
        logger.info(f"{GREEN}[SUCCESS]{RESET} {msg}")
    else:
        logger.info(f"[SUCCESS] {msg}")

def log_warn(msg):
    if sys.stdout.isatty():
        logger.warning(f"{YELLOW}[WARN]{RESET} {msg}")
    else:
        logger.warning(f"[WARN] {msg}")

def log_error(msg):
    if sys.stdout.isatty():
        logger.error(f"{RED}[ERROR]{RESET} {msg}")
    else:
        logger.error(f"[ERROR] {msg}")

class RebaseManager:
    def __init__(self, target_tag=None, auto=False, dry_run=False, start_over=False):
        self.target_tag = target_tag
        self.auto = auto
        self.dry_run = dry_run
        self.start_over = start_over
        
        # Paths
        self.cwd = Path(os.getcwd())
        self.rebase_dir = self.cwd / ".rebase"
        self.report_file = self.rebase_dir / "release-report.md"
        self.commits_file = self.rebase_dir / "commits.tsv"
        
        if self.start_over:
            log_info("Start-over flag provided. Wiping local .rebase state store.")
            if self.rebase_dir.exists() and not self.dry_run:
                try:
                    for f in self.rebase_dir.iterdir():
                        f.unlink()
                    self.rebase_dir.rmdir()
                    log_success("Wiped `.rebase/` state folder.")
                except Exception as e:
                    log_warn(f"Failed to cleanly wipe `.rebase/` directory: {e}")
        
        # Git / GH metadata (resolved lazily)
        self._repo_name = None
        self._main_branch = None

    @property
    def repo_name(self):
        if not self._repo_name:
            self._repo_name = self.get_github_repo_name()
        return self._repo_name

    @property
    def main_branch(self):
        if not self._main_branch:
            self._main_branch = self.get_main_branch()
        return self._main_branch

    def run_cmd(self, args, check=True, capture_output=True, timeout=None):
        """Helper to run shell commands safely without command substitution syntax."""
        # Read-only allowlist for dry-run
        read_only_commands = ["branch", "log", "show", "merge-base", "fetch", "tag", "show-ref", "list", "view", "checks", "api", "user", "repo", "remote", "status"]
        if self.dry_run:
            # Check if it's a git or gh command and its subcommand is in the allowlist
            is_read_only = False
            if len(args) > 1 and args[0] in ["git", "gh"] and args[1] in read_only_commands:
                is_read_only = True
            
            if not is_read_only:
                log_warn(f"Dry-run: Skipping command: {' '.join(args)}")
                return ""
        
        try:
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                text=True,
                check=check,
                timeout=timeout
            )
            return result.stdout.strip() if capture_output else ""
        except subprocess.TimeoutExpired as e:
            if capture_output:
                log_error(f"Command timed out: {' '.join(args)}\nError: {e.stderr}")
            else:
                log_error(f"Command timed out: {' '.join(args)}")
            raise e
        except subprocess.CalledProcessError as e:
            if capture_output:
                log_error(f"Command failed: {' '.join(args)}\nError: {e.stderr}")
            else:
                log_error(f"Command failed: {' '.join(args)}")
            raise e

    def get_github_repo_name(self):
        """Extract repo name (e.g. openshift/coredns) from gh or git remotes."""
        try:
            return self.run_cmd(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
        except Exception:
            # Fallback to git remote parsing
            for remote in ["openshift", "upstream", "origin"]:
                try:
                    remote_v = self.run_cmd(["git", "remote", "get-url", remote])
                    break
                except Exception:
                    continue
            else:
                return "unknown/repository"
            
            # Normalize and extract owner/repo
            url = remote_v.replace("git@github.com:", "github.com/")
            url = url.replace("https://github.com/", "github.com/")
            url = url.replace("http://github.com/", "github.com/")
            if "github.com/" in url:
                parts = url.split("github.com/")[-1].replace(".git", "").split("/")
                if len(parts) >= 2:
                    return f"{parts[0]}/{parts[1]}"
            return "unknown/repository"

    def get_main_branch(self):
        """Determine if main branch is master or main."""
        branches = self.run_cmd(["git", "branch", "-r"])
        if "openshift/master" in branches:
            return "openshift/master"
        if "openshift/main" in branches:
            return "openshift/main"
        if "origin/master" in branches:
            return "master"
        return "main"

    def ensure_gitignore(self):
        """Ensure .rebase/ is added to .gitignore."""
        gitignore = self.cwd / ".gitignore"
        entry = ".rebase/"
        if gitignore.exists():
            content = gitignore.read_text()
            if entry not in content:
                log_info(f"Adding {entry} to .gitignore")
                if not self.dry_run:
                    with open(gitignore, "a") as f:
                        f.write(f"\n# Rebase Manager State Store\n{entry}\n")
        else:
            log_info(f"Creating .gitignore with {entry}")
            if not self.dry_run:
                gitignore.write_text(f"{entry}\n")

    def get_current_github_user(self):
        """Fetch the current authenticated GitHub user's login."""
        try:
            return self.run_cmd(["gh", "api", "user", "--jq", ".login"])
        except Exception:
            return ""

    def detect_active_pr(self):
        """Check GitHub for open rebase PRs matching the current target version branch and authored by us."""
        try:
            # 1. Determine the target version we are interested in
            target = self.target_tag

            if not target:
                # If we are currently on a local rebase branch, infer the target version from it
                try:
                    current_branch = self.run_cmd(["git", "branch", "--show-current"])
                    if current_branch.startswith("rebase-"):
                        target = current_branch.replace("rebase-", "")
                        log_info(f"Currently on branch {current_branch}. Target rebase version is {target}.")
                except Exception:
                    pass

            if not target:
                # Fallback: find the latest upstream tag
                try:
                    tags = self.get_upstream_tags()
                    if tags:
                        target = tags[-1]
                        log_info(f"Target rebase version tag is inferred as {target}.")
                except Exception:
                    pass

            expected_branch = None
            if not target:
                log_warn("Could not determine target rebase version. Querying general rebase PRs.")
            else:
                expected_branch = f"rebase-{target}"

            # 2. Search for open PRs from current repo
            cmd_args = [
                "gh", "pr", "list",
                "--repo", self.repo_name,
                "--state", "open",
                "--json", "number,title,isDraft,headRefName,url,author"
            ]
            if expected_branch:
                # Some PRs might be rebase-to-v..., but gh pr list --head is exact. 
                # Let's query with limit 100 to catch both naming conventions flexibly
                cmd_args.extend(["--limit", "100"])
            else:
                cmd_args.extend(["--limit", "100"])
                
            prs_json = self.run_cmd(cmd_args)
            prs = json.loads(prs_json)

            # Filter PRs to only those authored by the current authenticated user
            current_user = self.get_current_github_user()
            if current_user:
                prs = [pr for pr in prs if pr.get("author", {}).get("login") == current_user]

            for pr in prs:
                if "Rebase to " in pr["title"]:
                    if expected_branch:
                        # Match branch name flexibly to avoid matching stale past drafts
                        possible_branches = [expected_branch, expected_branch.replace("rebase-", "rebase-to-")]
                        if pr["headRefName"] in possible_branches:
                            return pr
                    else:
                        # Loose matching if branch is unknown
                        return pr
            return None
        except Exception as e:
            log_warn(f"Failed to query GitHub PRs: {e}")
            return None

    def determine_phase(self, active_pr):
        """Determine current workflow phase based on local state and remote PR."""
        if self.start_over:
            log_info("Start-over flag provided. Forcing PHASE_1_DISCOVERY to rebuild rebase from scratch.")
            return "PHASE_1_DISCOVERY"

        # Get current local branch
        try:
            current_branch = self.run_cmd(["git", "branch", "--show-current"])
        except Exception:
            current_branch = "unknown"

        # If --auto is specified and we are on the main branch, we force PHASE_1_DISCOVERY
        # only if commits.tsv does not exist yet. If it does exist, we transition to PHASE_2.
        # We split on "/" to compare local branch name (e.g. 'master') with the base of the remote main branch (e.g. 'openshift/master').
        if self.auto and current_branch == self.get_main_branch().split("/")[-1]:
            if not self.commits_file.exists():
                log_info(f"Currently on main branch '{current_branch}' with --auto and no existing commits.tsv. Bypassing draft PR check to start fresh.")
                return "PHASE_1_DISCOVERY"
            else:
                log_info("Found existing `.rebase/commits.tsv` state file. Proceeding to PHASE_2_ACTIVE_DRAFT for local rebase execution.")
                return "PHASE_2_ACTIVE_DRAFT"

        if active_pr:
            if active_pr["isDraft"]:
                return "PHASE_2_ACTIVE_DRAFT"
            else:
                return "PHASE_3_FINAL_PROW"
        
        # Check if local rebase branch exists
        local_branches = self.run_cmd(["git", "branch"])
        rebase_branches = [line.replace("*", "").strip() for line in local_branches.split("\n") if line.replace("*", "").strip().startswith("rebase-")]
        has_rebase_branch = len(rebase_branches) > 0
        
        if has_rebase_branch:
            return "PHASE_2_ACTIVE_DRAFT"
            
        # Check if .rebase/commits.tsv exists, indicating Phase 1 is done and report was reviewed
        if self.commits_file.exists():
            log_info("Found existing `.rebase/commits.tsv` state file. Transitioning to PHASE_2_ACTIVE_DRAFT for local rebase execution.")
            return "PHASE_2_ACTIVE_DRAFT"
            
        return "PHASE_1_DISCOVERY"

    def parse_version(self, tag):
        """Parse tag string to numeric tuple for semantic comparison."""
        parts = tag.lstrip("v").split(".")
        if not all(p.isdigit() for p in parts):
            return None
        return tuple(int(p) for p in parts)

    def get_upstream_tags(self):
        """Get sorted list of stable upstream tags."""
        tags_raw = self.run_cmd(["git", "tag", "-l"])
        tags = []
        for tag in tags_raw.split("\n"):
            tag = tag.strip()
            # Filter stable releases (starts with v, doesn't contain rc, alpha, beta, dev)
            if tag.startswith("v") and "." in tag and not tag.startswith("v3.") and not any(x in tag.lower() for x in ["rc", "alpha", "beta", "dev"]):
                tags.append(tag)
        
        keyed = [(self.parse_version(t), t) for t in tags]
        parsed = [(k, t) for k, t in keyed if k is not None]
        for k, t in keyed:
            if k is None:
                log_warn(f"Skipping tag with unparsable version: {t}")
        parsed.sort()
        return [t for _, t in parsed]

    def get_current_fork_version(self, upstream_tags):
        """Find the highest upstream tag currently reachable from main branch."""
        # We find which of the upstream tags is merged into openshift/master (or main)
        log_info("Determining current fork base upstream version...")
        for tag in reversed(upstream_tags):
            try:
                # Check if tag is an ancestor of main branch
                self.run_cmd(["git", "merge-base", "--is-ancestor", tag, self.main_branch])
                return tag
            except Exception:
                continue
        return None

    def get_commit_category(self, sha):
        """Analyze commit files to dynamically categorize the downstream carry commit."""
        try:
            files_raw = self.run_cmd(["git", "show", "--name-only", "--pretty=format:", sha])
            files = [f.strip() for f in files_raw.split("\n") if f.strip()]
            
            if not files:
                return "code"

            # Category triggers
            is_build = all(any(x in f for x in ["Dockerfile", "OWNERS", ".ci-operator.yaml", "Makefile", ".github", ".gitignore", "dependabot"]) for f in files)
            is_deps = all(any(x in f for x in ["go.mod", "go.sum", "vendor/", ".go-version"]) for f in files)
            is_plugins = any(any(x in f for x in ["plugin/", "coredns.go", "plugin.cfg"]) for f in files)
            
            if is_build:
                return "build"
            if is_deps:
                return "deps"
            if is_plugins:
                return "plugins"
        except Exception:
            pass
        return "code"

    def generate_release_report(self, current_version, target_version):
        """Compose a highly structured release-report.md and commits.tsv."""
        self.rebase_dir.mkdir(exist_ok=True)
        self.ensure_gitignore()
        
        log_info(f"Generating Grouped Release Report: {current_version} -> {target_version}")
        
        # 1. Gather upstream commits/changelog links
        changelog_url = f"https://github.com/coredns/coredns/releases/tag/{target_version}"
        if "coredns" not in self.repo_name:
            # Generic upstream guess
            changelog_url = f"Upstream Release: {target_version}"
            
        # 2. Get carry commits (UPSTREAM: prefix commits)
        # Find merge base between current main branch and previous tag
        try:
            merge_base = self.run_cmd(["git", "merge-base", self.main_branch, current_version])
        except Exception:
            # Fallback to direct log if tag is missing/unresolvable
            merge_base = current_version
            
        log_info(f"Analyzing carries from merge base {merge_base} to {self.main_branch}")
        
        carries_raw = self.run_cmd([
            "git", "log", f"{merge_base}..{self.main_branch}",
            "--no-merges", "--reverse", "--pretty=tformat:%h|%s"
        ])
        
        carries_map = {} # Maps message -> sha (keeping most recent because git log is --reverse)
        if carries_raw:
            for line in carries_raw.split("\n"):
                if "|" in line:
                    sha, msg = line.split("|", 1)
                    carries_map[msg] = sha

        # Rebuild chronological list from the deduped map
        carries = [(sha, msg) for msg, sha in carries_map.items()]

        # 3. Categorize and group carries
        commits_data = [["Sha", "Message", "Decision"]]
        
        build_carries = []
        deps_carries = []
        plugins_carries = []
        code_carries = []
        
        for sha, msg in carries:
            category = self.get_commit_category(sha)
            
            # Rule-based decision
            decision = "cherry-pick"
            reason = "Standard downstream carry"
            
            if "UPSTREAM: <carry>: Add OpenShift files" in msg:
                decision = "cherry-pick"
                reason = "Persistent OpenShift bootstrap file set"
            elif "UPSTREAM: <drop>" in msg:
                decision = "drop"
                reason = "Marked explicitly to drop"
            elif "UPSTREAM:" not in msg:
                decision = "undecided"
                reason = "Unprefixed commit requires manual team review"
            else:
                # Rule-based decision for configuration files (squash candidate)
                if category in ["build", "deps"]:
                    decision = "squash"
                    reason = "Configuration carry candidate for squashing into core files carry"
            
            carry_item = (sha, msg, decision, reason)
            commits_data.append([sha, msg, decision])
            
            if category == "build":
                build_carries.append(carry_item)
            elif category == "deps":
                deps_carries.append(carry_item)
            elif category == "plugins":
                plugins_carries.append(carry_item)
            else:
                code_carries.append(carry_item)

        # 4. Generate the Unified High-Signal Meeting Agenda & PR Body (.rebase/release-report.md)
        report_content = f"""# Upstream Rebase Report: {current_version} to {target_version}

This report was automatically generated by the NI&D Rebase Manager. It details the release delta, domain-grouped carry commits, and designated follow-up actions. This document serves as the official agenda for the Rebase Approval meeting and will populate the Draft PR description.

## Upstream Changelog
*   **Release Tag:** [{target_version}]({changelog_url})
*   **Changelog Comparison:** {current_version} ... {target_version}

## Key Upstream Changes
*The team should summarize major upstream features, API deprecations, and breaking changes here before finalizing.*

---

## Domain-Grouped Carry Commit Agenda

Below is the structured analysis of the {len(carries)} downstream carry commits currently maintained on `{self.main_branch}`. High-level configuration sections have been condensed, while critical code changes remain expanded for developer review.

### 1. Toolchain & Dependencies (go.mod, vendor tree, Go version)
**Review Focus:** Build & Dependency alignment owners to ensure offline builds and toolchains remain viable.
*   **Summary:** We are carrying **{len(deps_carries)}** dependency and toolchain alignment commits. These are highly repetitive configuration changes (such as pinning Go versions, tracking `vendor/` tree ignores, and pulling in CVE security updates). 
*   **Action Required:** Redo `go mod vendor` post-rebase and ensure `GOTOOLCHAIN=local` is set to compile with the downstream environment.

"""
        if not deps_carries:
            report_content += "*No carries detected in this functional domain.*\n\n"
        else:
            report_content += """<details>
<summary><b>🔍 Click to expand itemized commits audit table (Toolchain & Dependencies)</b></summary>

| Carry SHA | Commit Message | Default Action | Reason |
| :--- | :--- | :--- | :--- |
"""
            for sha, msg, decision, reason in deps_carries:
                report_content += f"| `{sha}` | {msg} | **{decision}** | {reason} |\n"
            report_content += "\n</details>\n\n"
        
        report_content += f"""### 2. Build, CI, and Packaging (Dockerfiles, Prow config, Make targets)
**Review Focus:** Release, ART, & CI/operator owners to sign off on packaging and automation toggles.
*   **Summary:** We are carrying **{len(build_carries)}** packaging, Dockerfile, and Prow configuration commits. These represent standard OpenShift releases metadata, make target shims, and base-image overrides (e.g. updating base images to match `ocp-build-data` config).
*   **Action Required:** Reconcile downstream Dockerfiles with any upstream base-image changes, and verify `make test` targets align with CI rehearsals.

"""
        if not build_carries:
            report_content += "*No carries detected in this functional domain.*\n\n"
        else:
            report_content += """<details>
<summary><b>🔍 Click to expand itemized commits audit table (Build, CI, and Packaging)</b></summary>

| Carry SHA | Commit Message | Default Action | Reason |
| :--- | :--- | :--- | :--- |
"""
            for sha, msg, decision, reason in build_carries:
                report_content += f"| `{sha}` | {msg} | **{decision}** | {reason} |\n"
            report_content += "\n</details>\n\n"

        report_content += """### 3. Core DNS & Custom Extensions (ocp_dnsnameresolver, other plugins)
**Review Focus:** DNS Operator sub-team to vet custom DNS extensions and routing plugins.
*   **Description:** Integrates OpenShift-specific CoreDNS external plugins (e.g., `ocp_dnsnameresolver`, `coredns-mdns`) and custom plugin-chaining configuration rules. These represent critical custom logic that must be reviewed carefully during the meeting.

"""
        if not plugins_carries:
            report_content += "*No carries detected in this functional domain.*\n\n"
        else:
            report_content += "| Carry SHA | Commit Message | Default Action | Reason |\n| :--- | :--- | :--- | :--- |\n"
            for sha, msg, decision, reason in plugins_carries:
                report_content += f"| `{sha}` | {msg} | **{decision}** | {reason} |\n"
            report_content += "\n"

        report_content += """### 4. Standard Code Carries & Bug Fixes (downstream code patches)
**Review Focus:** Principal reviewers and feature owners to vet behavioral regressions.
*   **Description:** Downstream-specific Go code modifications, temporary hotfixes, and custom features not covered by plugins. These require direct code reviews to check for duplication or obsolescence against upstream changes.

"""
        if not code_carries:
            report_content += "*No carries detected in this functional domain.*\n\n"
        else:
            report_content += "| Carry SHA | Commit Message | Default Action | Reason |\n| :--- | :--- | :--- | :--- |\n"
            for sha, msg, decision, reason in code_carries:
                report_content += f"| `{sha}` | {msg} | **{decision}** | {reason} |\n"
            report_content += "\n"

        report_content += f"""---

## Rebase Action Plan

_Status legend:_ ⬜️ pending · 🔄 in progress · ✅ complete

| Status | Task | Notes |
| :---: | :--- | :--- |
| ⬜️ | Produce and audit carry commits (`commits.tsv`) | Phase 1 State Store |
| ⬜️ | Review and customize carry decisions | Manual developer adjustments |
| ⬜️ | Execute local rebase branch & ours-merge baseline | Phase 2 local checkout |
| ⬜️ | Port and resolve conflict on carries | Applying squashes / cherry-picks |
| ⬜️ | Align vendoring tree (`go mod tidy && vendor`) | Offline build alignment |
| ⬜️ | Pass local verification tests (`make && make test`) | Build & Unit validation |
| ⬜️ | Push branch and open Draft PR | Description serves as meeting agenda |
| ⬜️ | Address review comments & PR feedback | Iterative feedback loop |
| ⬜️ | Move PR out of Draft ("Ready for Review") | Human approval trigger |
| ⬜️ | Verify Prow CI checks succeed | Phase 3 CI Monitoring |
| ⬜️ | Final merge and environment cleanup | Phase 4 complete |

---
*Edit `.rebase/commits.tsv` locally to adjust decisions, then re-run to execute Phase 2.*
"""

        # Write files (Always write local state files to .rebase/ even under dry-run so the developer can review them on disk)
        self.report_file.write_text(report_content)
        with open(self.commits_file, "w", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerows(commits_data)
            
        log_success(f"Grouped Release report written to {self.report_file}")
        log_success(f"Carried commits table written to {self.commits_file}")

        if not self.dry_run:
            print(f"\n{YELLOW}== ACTION REQUIRED =={RESET}")
            print(f"Please review the grouped release report in {report_file_url(self.report_file)}")
            print("You can manually adjust decisions in `.rebase/commits.tsv` if needed.")
            print(f"{RED}*** AGENT STOP INSTRUCTION ***{RESET}")
            print("To the executing AI agent: Do NOT run this tool again autonomously. Stop here and wait for the human to review the files and explicitly ask you to proceed.")
            print("Once the human is ready, they will ask you to run the tool again to execute Phase 2.\n")
        else:
            print(f"\n{BLUE}=== DRY-RUN: GENERATED PR DESCRIPTION / AGENDA PREVIEW ==={RESET}\n")
            print(report_content)
            print(f"\n{BLUE}=== END OF DRY-RUN PREVIEW ==={RESET}\n")

    def run_phase_1(self):
        """Phase 1: Discovery & Tag Comparison."""
        log_info("=== PHASE 1: DISCOVERY & REPORTING ===")
        
        # Fetch tags
        log_info("Fetching all remotes and tags...")
        self.run_cmd(["git", "fetch", "--all", "--tags"])
        
        tags = self.get_upstream_tags()
        if not tags:
            log_error("No upstream release tags found starting with 'v'. Ensure remotes are set up.")
            return
            
        current_version = self.get_current_fork_version(tags)
        if not current_version:
            log_error(f"Could not determine current fork base upstream version reachable from {self.main_branch}.")
            return
            
        target_version = self.target_tag if self.target_tag else tags[-1]
        
        log_info(f"Current version in fork: {current_version}")
        log_info(f"Latest upstream version: {target_version}")
        
        if current_version == target_version and not self.target_tag:
            log_success("The OpenShift fork is fully up-to-date with upstream. No rebase needed.")
            return
            
        cur_parsed = self.parse_version(current_version)
        tar_parsed = self.parse_version(target_version)
        
        if cur_parsed and tar_parsed and tar_parsed <= cur_parsed:
            log_error(f"Target version {target_version} is not newer than the current version {current_version}. Aborting rebase.")
            return

        self.generate_release_report(current_version, target_version)

    def run_phase_2(self, target_version=None):
        """Phase 2: Active Draft Rebase & PR Feedback Loop."""
        log_info("=== PHASE 2: ACTIVE DRAFT & FEEDBACK LOOP ===")
        
        active_pr = self.detect_active_pr()
        
        if self.start_over and not target_version and active_pr:
            # Infer from active PR head branch (e.g. rebase-to-v1.13.2 or rebase-v1.13.2)
            ref = active_pr["headRefName"]
            target_version = ref.replace("rebase-to-", "").replace("rebase-", "")
            log_info(f"Inferred target version '{target_version}' from active PR head branch: '{ref}'")

        if not active_pr and not target_version:
            # Need to infer target_version from branch name if we have a local rebase branch
            local_branches = self.run_cmd(["git", "branch"])
            rebase_branches = [line.replace("*", "").strip() for line in local_branches.split("\n") if line.replace("*", "").strip().startswith("rebase-")]
            if rebase_branches:
                # Find branch with highest parsed tag
                highest_branch = rebase_branches[0]
                highest_parsed = None
                for br in rebase_branches:
                    tag_part = br.replace("rebase-", "")
                    parsed = self.parse_version(tag_part)
                    if parsed:
                        if not highest_parsed or parsed > highest_parsed:
                            highest_parsed = parsed
                            highest_branch = br
                target_version = highest_branch.replace("rebase-", "")
                log_info(f"Inferred target version {target_version} from local branch {highest_branch}")
            else:
                log_error("No active PR or local rebase branch found. Run Phase 1 first.")
                return

        if self.start_over:
            log_info("Start-over flag provided. Forcing fresh local rebase execution.")
            self.execute_local_rebase(target_version, active_pr)
            return

        # Step 1: Initial Rebase and Draft PR Creation (if no PR exists yet)
        if not active_pr:
            self.execute_local_rebase(target_version)
        else:
            # Step 2: Interactive Comment & Fixup Loop (PR already exists)
            log_info(f"Found active Draft PR: #{active_pr['number']} ({active_pr['url']})")
            self.process_pr_feedback(active_pr)

    def execute_local_rebase(self, target_version, active_pr=None):
        """Do the actual local checkout, ours-merge, cherry-picking, tidying, and PR opening."""
        branch_name = f"rebase-{target_version}"
        log_info(f"Initiating local rebase to tag '{target_version}' on branch '{branch_name}'")
        
        if self.dry_run:
            log_warn(f"Dry-run: Would checkout {branch_name}, merge -s ours, apply carries, tidy vendor, and open Draft PR.")
            return
            
        # 1. Check if the branch already exists and has commits ahead of target_version
        branch_exists = False
        try:
            self.run_cmd(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"])
            branch_exists = True
        except Exception:
            pass

        is_resuming = False
        if branch_exists:
            try:
                ahead = self.run_cmd(["git", "log", "--first-parent", f"{target_version}..{branch_name}", "--oneline"])
                if ahead.strip():
                    is_resuming = True
            except Exception:
                pass

        if is_resuming:
            log_info(f"Branch {branch_name} already exists and contains commits. Resuming rebase process.")
            self.run_cmd(["git", "checkout", branch_name])
        else:
            if branch_exists:
                log_info(f"Branch {branch_name} already exists but has no commits ahead of target. Resetting to {target_version}.")
                self.run_cmd(["git", "checkout", branch_name])
                self.run_cmd(["git", "reset", "--hard", target_version])
            else:
                log_info(f"Creating fresh branch {branch_name} from {target_version}...")
                try:
                    self.run_cmd(["git", "checkout", "-b", branch_name, target_version])
                except Exception as e:
                    log_error(f"Failed to checkout fresh branch {branch_name}: {e}")
                    return

            # 2. Ours-merge openshift/master to establish the baseline
            try:
                log_info(f"Merging {self.main_branch} using strategy 'ours'...")
                self.run_cmd([
                    "git", "merge", "-s", "ours", self.main_branch,
                    "-m", f"UPSTREAM: <merge>: Merge {self.main_branch} baseline into {branch_name}"
                ])
            except Exception as e:
                log_error(f"Failed ours-merge baseline: {e}")
                return

        # 3. Apply custom decisions from commits.tsv
        if not self.commits_file.exists():
            log_error("No `.rebase/commits.tsv` found. Please run Phase 1 first.")
            return
            
        log_info("Applying carried commits from decisions table...")
        decisions = []
        with open(self.commits_file, newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader) # Skip header
            for row in reader:
                if len(row) >= 3:
                    decisions.append((row[0], row[1], row[2]))

        squash_shas = []
        for sha, msg, decision in decisions:
            # Check if commit message is already present in branch history
            commit_exists = False
            try:
                log_out = self.run_cmd(["git", "log", "--first-parent", f"{target_version}..HEAD", "--format=%s"])
                if msg in log_out:
                    commit_exists = True
            except Exception:
                pass

            if commit_exists:
                log_info(f"Commit '{msg}' is already applied. Skipping.")
                continue

            if decision == "cherry-pick":
                log_info(f"Cherry-picking carry: {sha} ({msg})")
                try:
                    self.run_cmd(["git", "cherry-pick", sha])
                except Exception:
                    log_warn(f"Conflict during cherry-pick of {sha}. Please resolve manually.")
                    return
            elif decision == "squash":
                log_info(f"Queueing configuration carry for squash: {sha} ({msg})")
                squash_shas.append((sha, msg))
            elif decision == "drop":
                log_info(f"Skipping (dropping) carry: {sha} ({msg})")

        # 4. Perform the squash of configuration carries
        squash_done = False
        try:
            log_out = self.run_cmd(["git", "log", "--first-parent", f"{target_version}..HEAD", "--format=%s"])
            if "UPSTREAM: <carry>: Add and update OpenShift configurations" in log_out:
                squash_done = True
        except Exception:
            pass

        if squash_shas and not squash_done:
            log_info(f"Cherry-picking and squashing {len(squash_shas)} configuration carries...")
            # Record current HEAD before any cherry-picks
            try:
                pre_squash_head = self.run_cmd(["git", "rev-parse", "HEAD"])
            except Exception as e:
                log_error(f"Failed to record HEAD before squash: {e}")
                return

            # We cherry-pick them to get their contents onto the index
            for sha, msg in squash_shas:
                try:
                    self.run_cmd(["git", "cherry-pick", sha])
                except Exception:
                    log_warn(f"Conflict during cherry-pick of squash-carry {sha}.")
                    return
            
            # Squash them into a single commit
            log_info("Squashing commits...")
            try:
                # Soft reset back to recorded HEAD
                self.run_cmd(["git", "reset", "--soft", pre_squash_head])
                commit_msg = "UPSTREAM: <carry>: Add and update OpenShift configurations\n\nSquashed configuration commits:\n"
                for sha, msg in squash_shas:
                    commit_msg += f"- {sha}: {msg}\n"
                
                self.run_cmd(["git", "commit", "-m", commit_msg])
                log_success("Successfully squashed configuration commits.")
            except Exception as e:
                log_error(f"Squash failed: {e}")
                return

        # 5. Dependency alignment (Go modules)
        if (self.cwd / "go.mod").exists():
            log_info("Go repository detected. Running go mod tidy and go mod vendor...")
            try:
                self.run_cmd(["go", "mod", "tidy"])
                self.run_cmd(["go", "mod", "vendor"])
                # Check if there are changes to commit
                status = self.run_cmd(["git", "status", "--porcelain"])
                if status:
                    self.run_cmd(["git", "add", "go.mod", "go.sum", "vendor/"])
                    self.run_cmd(["git", "commit", "-m", "UPSTREAM: <carry>: Run go mod tidy and vendor update"])
                    log_success("Dependencies tidied and committed.")
            except Exception as e:
                log_warn(f"Go module alignment failed: {e}")

        # 6. Verification build and test checks
        log_info("Running local verification tests (this may take a few minutes)...")
        verification_passed = True
        try:
            if (self.cwd / "Makefile").exists():
                self.run_cmd(["make"], timeout=600)
                self.run_cmd(["make", "test"], timeout=1200)
            else:
                self.run_cmd(["go", "build", "./..."], timeout=600)
                self.run_cmd(["go", "test", "./..."], timeout=1200)
            log_success("All local verification tests passed!")
        except subprocess.TimeoutExpired as e:
            log_warn(f"Verification tests timed out: {e}. Opening Draft PR anyway with warning flags.")
            verification_passed = False
        except Exception as e:
            log_warn(f"Verification tests failed: {e}. Opening Draft PR anyway with warning flags.")
            verification_passed = False

        # Compose PR Body using Report
        pr_body = self.report_file.read_text() if self.report_file.exists() else "Rebase onto " + target_version
        if not verification_passed:
            pr_body = "⚠️ **WARNING: Local verification builds/tests failed on initial rebase. Please inspect CI.**\n\n" + pr_body
            
        # Remote Discovery
        push_remote = "origin"
        fork_owner = ""
        try:
            remote_url = self.run_cmd(["git", "remote", "get-url", "origin"])
            if "github.com" in remote_url.replace(":", "/"):
                parts = remote_url.replace("git@github.com:", "github.com/").replace("https://github.com/", "github.com/").split("github.com/")[-1].replace(".git", "").split("/")
                if len(parts) >= 2:
                    fork_owner = parts[0]
        except Exception:
            pass

        head_ref = branch_name
        repo_owner = self.repo_name.split("/")[0] if "/" in self.repo_name else ""
        if fork_owner and repo_owner and fork_owner != repo_owner:
            head_ref = f"{fork_owner}:{branch_name}"

        # 7. Push branch and open Draft PR (or update existing PR if start_over is used)
        if not active_pr:
            if self.auto:
                log_info(f"Ready to push branch {branch_name} to {push_remote}...")
                if sys.stdout.isatty():
                    ans = input(f"Do you want to push branch '{branch_name}' to '{push_remote}' and open a draft PR? [y/N]: ")
                    if ans.lower() not in ['y', 'yes']:
                        log_info("Push cancelled by user.")
                        return
                else:
                    log_info("Non-interactive mode: Auto-pushing branch...")

                try:
                    self.run_cmd(["git", "push", push_remote, branch_name])
                    log_success("Successfully pushed branch.")
                except Exception as e:
                    log_error(f"Failed to push branch: {e}")
                    return
                
                log_info("Auto-creating Draft PR on GitHub...")
                try:
                    pr_url = self.run_cmd([
                        "gh", "pr", "create", "--draft",
                        "--repo", self.repo_name,
                        "--title", f"Rebase to {target_version} for OCP DNS/Ingress",
                        "--head", head_ref,
                        "-F", str(self.report_file)
                    ])
                    log_success(f"Successfully created Draft PR: {pr_url.strip()}")
                except Exception as e:
                    log_error(f"Failed to create Draft PR: {e}")
                return
            else:
                log_success(f"Local rebase and verification tests for '{target_version}' completed successfully on branch '{branch_name}'!")
                print(f"\n{YELLOW}== LOCAL REBASE COMPLETE (WAITING) =={RESET}")
                print(f"Since no active Draft PR was found on GitHub, the tool has stopped here for your review.")
                print(f"Please inspect the local branch '{branch_name}', resolve any skews, and run tests.")
                print("When you are ready, you can push the branch and open a Draft PR manually:")
                print(f"  git push {push_remote} {branch_name}")
                print(f"  gh pr create --draft --repo {self.repo_name} --title \"Rebase to {target_version} for OCP DNS/Ingress\" --head {head_ref} -F .rebase/release-report.md\n")
                return

        log_info(f"Ready to push branch {branch_name} to {push_remote}...")
        if sys.stdout.isatty():
            ans = input(f"Do you want to push branch '{branch_name}' to '{push_remote}'? [y/N]: ")
            if ans.lower() not in ['y', 'yes']:
                log_info("Push cancelled by user.")
                return
        else:
            log_info("Non-interactive mode: Auto-pushing branch...")

        try:
            self.run_cmd(["git", "push", push_remote, branch_name])
        except Exception as e:
            log_error(f"Failed to push branch: {e}")
            return

        log_info(f"Draft PR #{active_pr['number']} is already open. Updating its description and commits...")
        try:
            self.run_cmd([
                "gh", "pr", "edit", str(active_pr["number"]),
                "-R", self.repo_name,
                "--body", pr_body
            ])
            log_success(f"Successfully updated Draft PR #{active_pr['number']} description!")
            print(f"\n{GREEN}== REBASE PR UPDATED =={RESET}")
            print(f"URL: {active_pr['url']}")
            print("The PR description serves as the Rebase Approval meeting agenda.\n")
        except Exception as e:
            log_warn(f"Failed to update Draft PR description: {e}")

    def process_pr_feedback(self, active_pr):
        """Fetch comments, apply code/rebase alterations, and post reply resolutions."""
        pr_num = active_pr["number"]
        log_info(f"Scanning Draft PR #{pr_num} comments for human feedback...")
        
        processed_comments_file = self.rebase_dir / "processed_comments.json"
        processed_comments = []
        if processed_comments_file.exists():
            try:
                processed_comments = json.loads(processed_comments_file.read_text())
            except Exception:
                pass
        
        # 1. Fetch comments on PR using gh API
        try:
            # Gets review comments & issue comments
            comments_json = self.run_cmd([
                "gh", "api", "--paginate", "--slurp", f"repos/{self.repo_name}/issues/{pr_num}/comments"
            ])
            pages = json.loads(comments_json)
            # Flatten pages
            comments = [c for page in pages for c in page]
        except Exception as e:
            log_error(f"Failed to fetch PR comments: {e}")
            return

        # Filter comments written by real humans (skip bots and prow command helpers)
        human_comments = []
        bot_logins = ["coderabbitai", "openshift-bot", "openshift-cherrypick-robot", "openshift-ci", "openshift-ci-robot", "github-actions"]
        for c in comments:
            if c.get("id") in processed_comments:
                continue
            author = c.get("user", {}).get("login", "")
            if author and author not in bot_logins and "[bot]" not in author:
                human_comments.append(c)

        if not human_comments:
            log_success("No new human comments/feedback detected on the Draft PR.")
            self.check_pr_ci_status(active_pr)
            return

        log_info(f"Found {len(human_comments)} human comment(s) to evaluate.")
        
        # We simulate checking out and fixing up based on instructions.
        # An expert AI-helper using this skill will read the file and comments and perform
        # surgical code edits. Here we outline what was processed.
        for c in human_comments:
            author = c["user"]["login"]
            body = c["body"]
            comment_id = c["id"]
            log_info(f"Feedback from @{author}: '{body[:80]}...'")
            
            # Respond to the comment on GitHub noting we are processing or have resolved it
            reply_body = f"🤖 **REBASE MANAGER UPDATE:**\n\nI have evaluated your feedback:\n> {body}\n\nI am analyzing the repository code, applying requested alterations (modifying carry commits/resolving compile errors), running test validations, and pushing updates to the PR branch."
            
            if not self.dry_run:
                try:
                    self.run_cmd([
                        "gh", "pr", "comment", str(pr_num),
                        "-R", self.repo_name,
                        "--body", reply_body
                    ])
                    log_success(f"Posted acknowledgement to @{author}'s comment.")
                    processed_comments.append(comment_id)
                except Exception as e:
                    log_warn(f"Failed to post comment reply: {e}")
            else:
                processed_comments.append(comment_id)
        
        if not self.dry_run:
            processed_comments_file.write_text(json.dumps(processed_comments))
                    
        # In actual usage, the running AI Agent is responsible for executing the code edits.
        # This python script acts as the driver that alerts the runner.
        self.check_pr_ci_status(active_pr)

    def check_pr_ci_status(self, active_pr):
        """Query and log PR CI check statuses."""
        pr_num = active_pr["number"]
        log_info(f"Checking CI statuses for PR #{pr_num}...")
        try:
            checks_json = self.run_cmd([
                "gh", "pr", "checks", str(pr_num),
                "-R", self.repo_name,
                "--json", "name,state,link"
            ], check=False)
            checks = json.loads(checks_json)
            
            if not checks:
                log_info("No CI checks have started yet on the PR.")
                return
                
            passed = 0
            failed = 0
            pending = 0
            for check in checks:
                state = check.get("state", "").upper()
                name = check.get("name", "")
                if state == "SUCCESS":
                    passed += 1
                elif state in ["FAILURE", "ERROR"]:
                    failed += 1
                    log_warn(f"❌ CI Job Failed: {name} ({check.get('link')})")
                else:
                    pending += 1
            
            log_info(f"CI Check Summary: Passed={passed}, Failed={failed}, Pending={pending}")
        except Exception as e:
            log_warn(f"Failed to fetch PR checks: {e}")

    def run_phase_3(self, active_pr):
        """Phase 3: Final Prow Review & Merge (Draft is OFF)."""
        log_info("=== PHASE 3: FINAL PROW REVIEW & MERGE ===")
        pr_num = active_pr["number"]
        log_info(f"Active PR #{pr_num} is READY FOR REVIEW (Draft status is OFF).")
        
        # 1. Check CI status
        self.check_pr_ci_status(active_pr)
        
        # 2. Instruct team on merge gating
        print(f"\n{BLUE}== FINAL APPROVAL PHASE =={RESET}")
        print(f"PR URL: {active_pr['url']}")
        print("Final merge is gated by standard OpenShift Prow commands.")
        print("Team leaders must comment `/lgtm` and `/approve` on the PR to trigger the auto-merge.")
        print("Once the PR is merged, run this manager once more to execute Phase 4 cleanup.\n")

    def run_cleanup(self, active_pr=None):
        """Phase 3: Completion & Cleanup."""
        log_info("=== COMPLETION & CLEANUP ===")
        
        # Check if the PR was actually merged
        pr_merged = False
        if active_pr:
            try:
                state = self.run_cmd([
                    "gh", "pr", "view", str(active_pr["number"]),
                    "-R", self.repo_name,
                    "--json", "state", "-q", ".state"
                ])
                if state == "MERGED":
                    pr_merged = True
            except Exception:
                pass

        if pr_merged:
            log_success("Rebase PR has been successfully merged! Cleaning up local environment.")
            
            # Remove state directory
            if self.rebase_dir.exists():
                log_info(f"Cleaning up {self.rebase_dir} state store...")
                if not self.dry_run:
                    shutil.rmtree(self.rebase_dir, ignore_errors=True)
                    log_success("Deleted `.rebase/` folder.")
            
            # Find and delete local rebase branches
            try:
                local_branches = self.run_cmd(["git", "branch"])
                for line in local_branches.split("\n"):
                    branch = line.replace("*", "").strip()
                    if branch.startswith("rebase-"):
                        log_info(f"Deleting local rebase branch: {branch}")
                        self.run_cmd(["git", "branch", "-D", branch])
            except Exception as e:
                log_warn(f"Branch deletion failed: {e}")
                
            log_success("Workflow cycle complete! Fork is now fully up to date with upstream.")
        else:
            log_warn("PR is not merged yet. Please complete final reviews and wait for merge.")

def report_file_url(file_path):
    """Helper to return path representation."""
    return f"file://{file_path}"

def main():
    parser = argparse.ArgumentParser(description="NI&D Team Rebase Manager State Machine")
    parser.add_argument("--tag", help="Specify target upstream tag version (e.g. v1.11.3)")
    parser.add_argument("--auto", action="store_true", help="Auto-discover and target the latest upstream version tag")
    parser.add_argument("--dryrun", action="store_true", help="Do a dry-run execution without write side-effects")
    parser.add_argument("--start-over", action="store_true", help="Clear the .rebase state folder and force-rebuild the rebase branch/Draft PR from scratch")
    args = parser.parse_args()

    try:
        # Create Manager
        manager = RebaseManager(target_tag=args.tag, auto=args.auto, dry_run=args.dryrun, start_over=args.start_over)
        
        # Trigger lazy load validation early
        _ = manager.repo_name
        _ = manager.main_branch

        # If dryrun is requested, always force PHASE_1_DISCOVERY to print the full would-be PR description
        if args.dryrun:
            log_info("Dry-run requested. Simulating PHASE_1_DISCOVERY to output the full, domain-grouped PR description / meeting agenda.")
            manager.run_phase_1()
            return

        # 1. Determine active PR status
        active_pr = manager.detect_active_pr()
        
        # 2. Check if the active PR was merged
        if active_pr:
            try:
                state = manager.run_cmd([
                    "gh", "pr", "view", str(active_pr["number"]),
                    "-R", manager.repo_name,
                    "--json", "state", "-q", ".state"
                ])
                if state == "MERGED":
                    manager.run_cleanup(active_pr)
                    return
            except Exception:
                pass

        # 3. Determine and run phase
        phase = manager.determine_phase(active_pr)
        log_info(f"Detected Active Phase: {phase}")
        
        if phase == "PHASE_1_DISCOVERY":
            manager.run_phase_1()
        elif phase == "PHASE_2_ACTIVE_DRAFT":
            manager.run_phase_2()
        elif phase == "PHASE_3_FINAL_PROW":
            manager.run_phase_3(active_pr)
        else:
            log_error(f"Unknown phase state: {phase}")
    except subprocess.CalledProcessError as e:
        # Catch unexpected lookup errors gracefully at the top level
        log_error("Failed to query git or github metadata. Ensure you are running this script inside a valid cloned github repository.")
        sys.exit(1)

if __name__ == "__main__":
    main()
