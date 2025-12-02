#!/usr/bin/env python3
"""
check_permissions.py - Check user permissions and warn if write access detected

Usage: ./check_permissions.py KUBECONFIG
Returns: 0 if user confirms to proceed, 1 if user cancels or error, 2 if write perms detected

Note: This script must be run from the scripts/ directory or have the scripts/
      directory in PYTHONPATH for the ovn_utils import to work.

Requirements: Python 3.6+, kubectl in PATH
"""

import subprocess
import sys
import os
from typing import List, Optional

# Import shared utilities (must be in same directory or in PYTHONPATH)
from ovn_utils import detect_ovn_namespace

# Dangerous write permissions to check
_DANGEROUS_PERMS = (
    ("delete", "pods", "Delete pods"),
    ("create", "pods", "Create pods"),
    ("patch", "pods", "Modify pods"),
    ("update", "pods", "Update pods"),
    ("deletecollection", "pods", "Bulk delete pods"),
    ("delete", "deployments", "Delete deployments"),
    ("create", "deployments", "Create deployments"),
    ("patch", "deployments", "Modify deployments"),
    ("delete", "services", "Delete services"),
    ("create", "services", "Create services"),
)


class PermissionChecker:
    """Check Kubernetes RBAC permissions for the OVN topology skill."""

    # Configuration constants
    _PERMISSION_CHECK_TIMEOUT = 5  # seconds

    def __init__(self, kubeconfig: str):
        self.kubeconfig = kubeconfig
        self.write_perms_found = False
        self.write_perms_list: List[str] = []
        self.ovn_namespace: Optional[str] = None


    def check_kubectl_available(self) -> bool:
        """Check if kubectl is available in PATH."""
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = self.kubeconfig
            subprocess.run(
                [
                    "kubectl",
                    "--kubeconfig",
                    self.kubeconfig,
                    "version",
                    "--client=true",
                    "--output=json",
                ],
                capture_output=True,
                check=True,
                env=env,
            )
            return True
        except FileNotFoundError:
            print("❌ Error: kubectl not found in PATH", file=sys.stderr)
            return False
        except subprocess.CalledProcessError:
            # kubectl exists but may have other issues - still return True
            return True

    def check_permission(
        self, resource: str, verb: str, namespace: Optional[str] = None
    ) -> bool:
        """
        Check if user has a specific permission.

        Args:
            resource: Kubernetes resource type (e.g., "pods", "*" for all resources).
            verb: Action verb (e.g., "get", "create", "*" for all verbs).
            namespace: Namespace to check permissions in. Pass None to check
                cluster-wide permissions. Defaults to None.

        Returns:
            True if permission exists, False otherwise. Handles transient failures
            gracefully by treating them as "no permission".

        Note:
            All exceptions are caught and handled internally. Timeouts and errors
            are logged to stderr and return False.
        """
        cmd = [
            "kubectl",
            "--kubeconfig", self.kubeconfig,
            "auth", "can-i",
            verb, resource,
            "--quiet"
        ]

        if namespace is not None:
            cmd.extend(["-n", namespace])

        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = self.kubeconfig
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self._PERMISSION_CHECK_TIMEOUT,
                env=env
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(
                f"⚠️  Warning: Error checking permission '{verb} {resource}': {e}. "
                "Assuming no permission.",
                file=sys.stderr,
            )
            return False

    def check_all_permissions(self) -> None:
        """Check all dangerous write permissions."""
        print("🔐 Checking your Kubernetes permissions...\n", file=sys.stderr)
        print(f"Checking permissions in '{self.ovn_namespace}' namespace...\n", file=sys.stderr)

        # Check dangerous write permissions
        for verb, resource, description in _DANGEROUS_PERMS:
            if self.check_permission(resource, verb, self.ovn_namespace):
                self.write_perms_found = True
                self.write_perms_list.append(f"  ⚠️  {description} ({verb} {resource})")

        # Check cluster-wide admin permissions
        if self.check_permission("*", "*", None):
            self.write_perms_found = True
            self.write_perms_list.append(
                "  ⚠️  CLUSTER ADMIN - Full cluster access "
                "(all verbs on all resources)"
            )

        # Check namespace admin (only add if not already cluster admin)
        if not any("CLUSTER ADMIN" in perm for perm in self.write_perms_list):
            if self.check_permission("*", "*", self.ovn_namespace):
                self.write_perms_found = True
                self.write_perms_list.append(
                    f"  ⚠️  NAMESPACE ADMIN - Full access to "
                    f"{self.ovn_namespace} namespace"
                )

    def display_warning(self) -> None:
        """Display warning message about write permissions."""
        print("⚠️  WARNING: Write permissions detected!\n", file=sys.stderr)
        print(
            "Your kubeconfig has the following write/admin permissions:\n",
            file=sys.stderr,
        )

        for perm in self.write_perms_list:
            print(perm, file=sys.stderr)

    def handle_confirmation(self) -> int:
        """
        Handle user confirmation based on mode.

        Returns:
            0: User confirmed to proceed (or no write perms found).
            1: User cancelled.
            2: Non-interactive mode with write perms (needs AI agent
               confirmation).
        """
        if not self.write_perms_found:
            print("✅ Permission check passed\n", file=sys.stderr)
            print("Your access level:", file=sys.stderr)
            print("  • Read-only permissions detected", file=sys.stderr)
            print("  • No write/admin access found", file=sys.stderr)
            print("  • Safe to proceed with topology generation\n", file=sys.stderr)
            return 0

        self.display_warning()

        print("WRITE_PERMISSIONS_DETECTED")
        print("PERMISSIONS_LIST_START")
        for perm in self.write_perms_list:
            print(perm)
        print("PERMISSIONS_LIST_END")
        return 2

    def run(self) -> int:
        """Run the permission check."""
        if not self.check_kubectl_available():
            return 1

        # Detect OVN namespace after kubectl availability check
        try:
            self.ovn_namespace = detect_ovn_namespace(self.kubeconfig)
        except Exception as exc:
            print(f"❌ Error detecting OVN namespace: {exc}", file=sys.stderr)
            return 1

        self.check_all_permissions()
        return self.handle_confirmation()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} KUBECONFIG", file=sys.stderr)
        return 1

    kubeconfig = sys.argv[1]

    if not os.path.exists(kubeconfig):
        print(f"❌ Error: Kubeconfig file not found: {kubeconfig}", file=sys.stderr)
        return 1

    checker = PermissionChecker(kubeconfig)
    return checker.run()


if __name__ == "__main__":
    sys.exit(main())
