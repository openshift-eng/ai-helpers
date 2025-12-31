#!/usr/bin/env python3
"""
check_permissions.py - Check user permissions and warn if write access detected

Usage: ./check_permissions.py KUBECONFIG
Returns: 0 if user confirms to proceed, 1 if user cancels or error, 2 if write perms detected

Note: This script must be run from the scripts/ directory or have the scripts/
      directory in PYTHONPATH for the gateway_utils import to work.

Requirements: Python 3.6+, kubectl in PATH
"""

import os
import subprocess
import sys
from typing import List, Optional

# Import shared utilities (must be in same directory or in PYTHONPATH)
from gateway_utils import check_gateway_api_installed

# Dangerous write permissions to check for Gateway API resources
_DANGEROUS_PERMS = (
    # Gateway API resources
    ("delete", "gateways.gateway.networking.k8s.io", "Delete Gateways"),
    ("create", "gateways.gateway.networking.k8s.io", "Create Gateways"),
    ("patch", "gateways.gateway.networking.k8s.io", "Modify Gateways"),
    ("delete", "httproutes.gateway.networking.k8s.io", "Delete HTTPRoutes"),
    ("create", "httproutes.gateway.networking.k8s.io", "Create HTTPRoutes"),
    ("patch", "httproutes.gateway.networking.k8s.io", "Modify HTTPRoutes"),
    ("delete", "gatewayclasses.gateway.networking.k8s.io", "Delete GatewayClasses"),
    ("create", "gatewayclasses.gateway.networking.k8s.io", "Create GatewayClasses"),
    # Standard Kubernetes resources
    ("delete", "services", "Delete Services"),
    ("create", "services", "Create Services"),
    ("delete", "pods", "Delete Pods"),
    ("create", "pods", "Create Pods"),
)


class PermissionChecker:
    """Check Kubernetes RBAC permissions for the Gateway topology skill."""

    _PERMISSION_CHECK_TIMEOUT = 5  # seconds

    def __init__(self, kubeconfig: str):
        self.kubeconfig = kubeconfig
        self.write_perms_found = False
        self.write_perms_list: List[str] = []

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
            return True

    def check_permission(
        self, resource: str, verb: str, namespace: Optional[str] = None
    ) -> bool:
        """
        Check if user has a specific permission.

        Args:
            resource: Kubernetes resource type
            verb: Action verb (e.g., "get", "create")
            namespace: Namespace to check permissions in

        Returns:
            True if permission exists, False otherwise
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

        # Check dangerous write permissions (cluster-wide for Gateway API)
        for verb, resource, description in _DANGEROUS_PERMS:
            if self.check_permission(resource, verb, None):
                self.write_perms_found = True
                self.write_perms_list.append(f"  ⚠️  {description} ({verb})")

        # Check cluster-wide admin permissions
        if self.check_permission("*", "*", None):
            self.write_perms_found = True
            self.write_perms_list.append(
                "  ⚠️  CLUSTER ADMIN - Full cluster access "
                "(all verbs on all resources)"
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
            0: User confirmed to proceed (or no write perms found)
            1: User cancelled
            2: Non-interactive mode with write perms (needs AI agent confirmation)
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

        # Verify Gateway API is installed
        is_installed, installed_crds = check_gateway_api_installed(self.kubeconfig)
        if not is_installed:
            print("❌ Error: Gateway API CRDs not found in cluster", file=sys.stderr)
            print("\nTo install Gateway API:", file=sys.stderr)
            print("  kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/"
                  "releases/download/v1.0.0/standard-install.yaml", file=sys.stderr)
            return 1

        print(f"✓ Gateway API installed: {len(installed_crds)} CRDs found", file=sys.stderr)

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
