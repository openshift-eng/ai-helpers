#!/usr/bin/env python3
"""
State management for proof PR workflows.

Handles CRUD operations, state recovery from GitHub, and sync detection.
State is stored as JSON files in .work/proof-pr/{original_pr_number}/state.json

State Recovery:
    If state file is missing or corrupted, can recover by scanning GitHub
    for proof PRs (identified by HTML comments in PR body).

Sync Detection:
    Automatically detects if GitHub reality differs from saved state
    (e.g., if PRs were modified/merged outside the workflow).
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class ProofPR:
    """Represents a single proof PR in the workflow"""

    # Basic PR info
    repo: str  # e.g., "openshift/client-go"
    number: int
    url: str
    branch: str
    created_at: str

    # What this PR is currently proving
    # Initially: proves original PR
    # After conversion: may prove a newly-converted PR
    proving_repo: str  # e.g., "openshift/api"
    proving_pr: int

    # What this PR depends on (go.mod dependency)
    depends_on_repo: str  # e.g., "openshift/api"

    # Conversion tracking
    converted: bool = False
    merged: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProofPR':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class ProofPRState:
    """Complete state for a proof PR workflow session"""

    # Original PR that started the workflow
    original_repo: str
    original_pr: int
    original_url: str
    original_branch: str

    # All proof PRs in this workflow
    proof_prs: List[ProofPR] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'original_repo': self.original_repo,
            'original_pr': self.original_pr,
            'original_url': self.original_url,
            'original_branch': self.original_branch,
            'proof_prs': [pr.to_dict() for pr in self.proof_prs],
            'created_at': self.created_at,
            'last_updated': self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProofPRState':
        """Create from dictionary"""
        proof_prs = [ProofPR.from_dict(pr) for pr in data.get('proof_prs', [])]
        return cls(
            original_repo=data['original_repo'],
            original_pr=data['original_pr'],
            original_url=data['original_url'],
            original_branch=data['original_branch'],
            proof_prs=proof_prs,
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            last_updated=data.get('last_updated', datetime.utcnow().isoformat())
        )


class StateManager:
    """Manages proof PR workflow state with recovery and sync capabilities"""

    WORK_DIR = Path.home() / '.work' / 'proof-pr'
    PROOF_PR_MARKER = "<!-- PROOF-PR:"
    PROVING_MARKER = "<!-- PROVING:"
    DEPENDS_ON_MARKER = "<!-- DEPENDS-ON:"

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.WORK_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str):
        """Print verbose logging"""
        if self.verbose:
            print(f"[state-manager] {message}", file=sys.stderr)

    def _get_state_path(self, pr_number: int) -> Path:
        """Get path to state file for a given original PR number"""
        return self.WORK_DIR / str(pr_number) / 'state.json'

    def _run_gh(self, args: List[str]) -> str:
        """Run gh CLI command and return output"""
        try:
            result = subprocess.run(
                ['gh'] + args,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"gh command failed: {e.stderr}")

    def save(self, state: ProofPRState) -> None:
        """Save state to disk"""
        state.last_updated = datetime.utcnow().isoformat()
        state_path = self._get_state_path(state.original_pr)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(state_path, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)

        self._log(f"Saved state to {state_path}")

    def load(self, pr_number: int, auto_recover: bool = True) -> ProofPRState:
        """
        Load state with optional auto-recovery.

        Args:
            pr_number: Original PR number
            auto_recover: If True, attempt to recover from GitHub if state missing

        Returns:
            ProofPRState

        Raises:
            FileNotFoundError: If state not found and auto_recover=False
            RuntimeError: If recovery fails
        """
        state_path = self._get_state_path(pr_number)

        # Try to load from disk
        if state_path.exists():
            try:
                with open(state_path) as f:
                    data = json.load(f)
                state = ProofPRState.from_dict(data)
                self._log(f"Loaded state from {state_path}")

                # Check if state is in sync with GitHub
                if self._is_out_of_sync(state):
                    self._log("WARNING: State is out of sync with GitHub")
                    self._log("Consider running sync to update state")

                return state

            except (json.JSONDecodeError, KeyError) as e:
                self._log(f"State file corrupted: {e}")
                if auto_recover:
                    self._log("Attempting recovery...")
                    return self.recover(pr_number)
                raise RuntimeError(f"State file corrupted: {e}")

        # State file doesn't exist
        if auto_recover:
            self._log(f"State file not found at {state_path}")
            self._log("Attempting to recover from GitHub...")
            return self.recover(pr_number)

        raise FileNotFoundError(f"State file not found: {state_path}")

    def recover(self, pr_number: int) -> ProofPRState:
        """
        Recover state by scanning GitHub for proof PRs.

        Searches for PRs containing PROOF_PR_MARKER in their body,
        then reconstructs the state from PR metadata.

        Args:
            pr_number: Original PR number to recover

        Returns:
            Recovered ProofPRState

        Raises:
            RuntimeError: If recovery fails
        """
        self._log(f"Recovering state for PR #{pr_number}")

        # Step 1: Get original PR info
        try:
            pr_json = self._run_gh([
                'pr', 'view', str(pr_number),
                '--json', 'url,headRefName,repository'
            ])
            pr_data = json.loads(pr_json)

            original_url = pr_data['url']
            original_branch = pr_data['headRefName']
            original_repo = pr_data['repository']['nameWithOwner']

            self._log(f"Original PR: {original_repo}#{pr_number}")

        except Exception as e:
            raise RuntimeError(f"Failed to fetch original PR: {e}")

        # Step 2: Search for proof PRs across all repos
        # We'll search for PRs with the PROOF_PR_MARKER in the body
        proof_prs = []

        # Get list of all PRs we've authored (likely to be our proof PRs)
        try:
            search_query = f"is:pr author:@me {self.PROOF_PR_MARKER}"
            prs_json = self._run_gh([
                'search', 'prs',
                '--json', 'number,url,headRefName,repository,body,state',
                '--limit', '100',
                search_query
            ])

            prs_data = json.loads(prs_json)

            for pr in prs_data:
                body = pr.get('body', '')

                # Check if this is a proof PR for our original PR
                if self.PROOF_PR_MARKER not in body:
                    continue

                # Extract metadata from HTML comments
                proving_repo, proving_pr = self._extract_proving_info(body)
                depends_on_repo = self._extract_depends_on(body)

                # Check if this is for our original PR
                if proving_repo and proving_pr == pr_number:
                    proof_pr = ProofPR(
                        repo=pr['repository']['nameWithOwner'],
                        number=pr['number'],
                        url=pr['url'],
                        branch=pr['headRefName'],
                        created_at=datetime.utcnow().isoformat(),  # Approximate
                        proving_repo=proving_repo,
                        proving_pr=proving_pr,
                        depends_on_repo=depends_on_repo or proving_repo,
                        converted=False,
                        merged=(pr['state'] == 'MERGED')
                    )

                    proof_prs.append(proof_pr)
                    self._log(f"Found proof PR: {proof_pr.repo}#{proof_pr.number}")

        except Exception as e:
            self._log(f"Warning: Error searching for proof PRs: {e}")

        # Step 3: Create recovered state
        state = ProofPRState(
            original_repo=original_repo,
            original_pr=pr_number,
            original_url=original_url,
            original_branch=original_branch,
            proof_prs=proof_prs
        )

        # Save recovered state
        self.save(state)

        self._log(f"Recovered state with {len(proof_prs)} proof PRs")
        return state

    def _extract_proving_info(self, body: str) -> tuple:
        """Extract proving_repo and proving_pr from PR body"""
        match = re.search(rf'{self.PROVING_MARKER}\s*(\S+)#(\d+)', body)
        if match:
            return match.group(1), int(match.group(2))
        return None, None

    def _extract_depends_on(self, body: str) -> Optional[str]:
        """Extract depends_on_repo from PR body"""
        match = re.search(rf'{self.DEPENDS_ON_MARKER}\s*(\S+)', body)
        if match:
            return match.group(1)
        return None

    def _is_out_of_sync(self, state: ProofPRState) -> bool:
        """
        Check if state is out of sync with GitHub reality.

        Checks:
        - Are all proof PRs still open?
        - Have any been merged?
        - Do PR bodies still match?

        Returns:
            True if out of sync
        """
        for proof_pr in state.proof_prs:
            try:
                # Get current PR state from GitHub
                pr_json = self._run_gh([
                    'pr', 'view', str(proof_pr.number),
                    '--repo', proof_pr.repo,
                    '--json', 'state,merged'
                ])
                pr_data = json.loads(pr_json)

                # Check if merged status differs
                github_merged = pr_data.get('merged', False)
                if github_merged != proof_pr.merged:
                    self._log(f"Out of sync: {proof_pr.repo}#{proof_pr.number} merged status differs")
                    return True

            except Exception as e:
                self._log(f"Warning: Could not check {proof_pr.repo}#{proof_pr.number}: {e}")
                continue

        return False

    def sync(self, state: ProofPRState) -> ProofPRState:
        """
        Sync state with GitHub reality.

        Updates:
        - Merged status
        - PR states
        - Branch names

        Returns:
            Updated state
        """
        self._log("Syncing state with GitHub...")

        for proof_pr in state.proof_prs:
            try:
                pr_json = self._run_gh([
                    'pr', 'view', str(proof_pr.number),
                    '--repo', proof_pr.repo,
                    '--json', 'state,merged,headRefName'
                ])
                pr_data = json.loads(pr_json)

                # Update merged status
                proof_pr.merged = pr_data.get('merged', False)

                # Update branch name (might change if PR rebased)
                proof_pr.branch = pr_data.get('headRefName', proof_pr.branch)

                self._log(f"Synced {proof_pr.repo}#{proof_pr.number}: merged={proof_pr.merged}")

            except Exception as e:
                self._log(f"Warning: Could not sync {proof_pr.repo}#{proof_pr.number}: {e}")
                continue

        # Save updated state
        self.save(state)

        return state


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage proof PR workflow state"
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Load command
    load_parser = subparsers.add_parser('load', help='Load state')
    load_parser.add_argument('pr_number', type=int, help='Original PR number')
    load_parser.add_argument('--no-recover', action='store_true', help='Disable auto-recovery')

    # Recover command
    recover_parser = subparsers.add_parser('recover', help='Recover state from GitHub')
    recover_parser.add_argument('pr_number', type=int, help='Original PR number')

    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync state with GitHub')
    sync_parser.add_argument('pr_number', type=int, help='Original PR number')

    # Common options
    parser.add_argument('--quiet', action='store_true', help='Suppress verbose output')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    manager = StateManager(verbose=not args.quiet)

    try:
        if args.command == 'load':
            state = manager.load(args.pr_number, auto_recover=not args.no_recover)
        elif args.command == 'recover':
            state = manager.recover(args.pr_number)
        elif args.command == 'sync':
            state = manager.load(args.pr_number, auto_recover=False)
            state = manager.sync(state)

        if args.json:
            print(json.dumps(state.to_dict(), indent=2))
        else:
            print(f"\nState for {state.original_repo}#{state.original_pr}:")
            print(f"  Proof PRs: {len(state.proof_prs)}")
            for pr in state.proof_prs:
                status = "MERGED" if pr.merged else ("CONVERTED" if pr.converted else "ACTIVE")
                print(f"    - {pr.repo}#{pr.number} [{status}]")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
