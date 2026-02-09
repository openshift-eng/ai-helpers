"""
Create or update a Component Readiness triage record via the Sippy API.
Links one or more regressions to a JIRA bug with a triage type and description.
"""

import sys
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional


class TriageManager:
    """Creates or updates triage records via the Sippy API."""

    BASE_URL = "https://sippy-auth.dptools.openshift.org/api/component_readiness/triages"

    VALID_TYPES = ("product", "test", "ci-infra", "product-infra")

    def __init__(self, regression_ids: List[int], token: str,
                 url: Optional[str] = None, triage_type: Optional[str] = None,
                 description: Optional[str] = None,
                 triage_id: Optional[int] = None):
        """
        Initialize triage manager.

        Args:
            regression_ids: List of regression IDs to link to this triage
            token: OAuth Bearer token for authenticating to sippy-auth
            url: JIRA bug URL (required for create, optional for update - uses existing value)
            triage_type: Triage type (required for create, optional for update - uses existing value)
            description: Optional description for the triage
            triage_id: Optional existing triage ID to update (omit to create new)
        """
        self.regression_ids = regression_ids
        self.token = token
        self.url = url
        self.triage_type = triage_type
        self.description = description
        self.triage_id = triage_id
        # These are populated from the existing triage during update()
        self._resolved = None
        self._resolution_reason = None

    def _build_payload(self) -> Dict[str, Any]:
        """Build the JSON payload for create or update."""
        payload = {
            "url": self.url,
            "type": self.triage_type,
            "regressions": [{"id": rid} for rid in self.regression_ids],
        }

        if self.description is not None:
            payload["description"] = self.description

        if self.triage_id is not None:
            payload["id"] = self.triage_id

        # Preserve resolved status and resolution reason from existing triage
        if self._resolved is not None:
            payload["resolved"] = self._resolved
        if self._resolution_reason is not None:
            payload["resolution_reason"] = self._resolution_reason

        return payload

    def _auth_headers(self) -> Dict[str, str]:
        """Build request headers with auth token."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _fetch_existing_triage(self) -> Optional[Dict[str, Any]]:
        """
        Fetch an existing triage record by ID.

        Returns:
            dict: The existing triage data, or None on error
        """
        url = f"{self.BASE_URL}/{self.triage_id}"
        req = urllib.request.Request(
            url,
            headers=self._auth_headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception:
            return None

    def create(self) -> Dict[str, Any]:
        """
        Create a new triage record.

        Returns:
            dict: Response with success status and created triage or error
        """
        payload = self._build_payload()
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            self.BASE_URL,
            data=data,
            headers=self._auth_headers(),
            method="POST",
        )
        return self._send(req, "create")

    def update(self) -> Dict[str, Any]:
        """
        Update an existing triage record.

        Fetches the existing triage first to preserve its current regressions,
        then merges the new regression IDs with the existing ones. The PUT
        endpoint uses full replacement semantics, so we must always send the
        complete list.

        Returns:
            dict: Response with success status and updated triage or error
        """
        if self.triage_id is None:
            return {
                'success': False,
                'error': "triage_id is required for update",
                'operation': 'update',
                'regression_ids': self.regression_ids,
            }

        # Fetch existing triage to get current regressions and fill in defaults
        existing = self._fetch_existing_triage()
        if existing is None:
            return {
                'success': False,
                'error': f"Failed to fetch existing triage {self.triage_id}. Cannot update safely without knowing current state.",
                'operation': 'update',
                'regression_ids': self.regression_ids,
            }

        # Use existing values for fields not provided on command line.
        # The PUT endpoint uses full replacement semantics, so any field
        # not included in the payload will be wiped.
        if self.url is None:
            self.url = existing.get('url', '')
        if self.triage_type is None:
            self.triage_type = existing.get('type', '')
        if self.description is None:
            self.description = existing.get('description', '')

        # Preserve resolved status and resolution reason from existing triage
        self._resolved = existing.get('resolved')
        self._resolution_reason = existing.get('resolution_reason', '')

        # Merge existing regression IDs with new ones (deduplicate)
        existing_ids = set()
        for reg in existing.get('regressions', []):
            reg_id = reg.get('id')
            if reg_id is not None:
                existing_ids.add(reg_id)

        merged_ids = existing_ids | set(self.regression_ids)
        self.regression_ids = sorted(merged_ids)

        payload = self._build_payload()
        data = json.dumps(payload).encode('utf-8')
        url = f"{self.BASE_URL}/{self.triage_id}"
        req = urllib.request.Request(
            url,
            data=data,
            headers=self._auth_headers(),
            method="PUT",
        )
        return self._send(req, "update")

    def _send(self, req: urllib.request.Request, operation: str) -> Dict[str, Any]:
        """Send a request and return structured response."""
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))

                if isinstance(response_data, dict) and 'error' in response_data:
                    return {
                        'success': False,
                        'error': f"API error: {response_data['error']}",
                        'operation': operation,
                        'regression_ids': self.regression_ids,
                    }

                return {
                    'success': True,
                    'operation': operation,
                    'regression_ids': self.regression_ids,
                    'triage': response_data,
                }

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode('utf-8')
            except Exception:
                pass
            return {
                'success': False,
                'error': f"HTTP error {e.code}: {e.reason}",
                'detail': body,
                'operation': operation,
                'regression_ids': self.regression_ids,
            }
        except urllib.error.URLError as e:
            return {
                'success': False,
                'error': f"Failed to connect to Sippy API: {e.reason}.",
                'operation': operation,
                'regression_ids': self.regression_ids,
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'operation': operation,
                'regression_ids': self.regression_ids,
            }


def format_summary(results: Dict[str, Any]) -> str:
    """
    Format results as a human-readable summary.

    Args:
        results: Results from create() or update()

    Returns:
        str: Formatted summary text
    """
    lines = []
    operation = results.get('operation', 'unknown').capitalize()

    if not results.get('success'):
        lines.append(f"Triage {operation} - FAILED")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Error: {results.get('error', 'Unknown error')}")
        if results.get('detail'):
            lines.append(f"Detail: {results.get('detail')}")
        return "\n".join(lines)

    lines.append(f"Triage {operation} - SUCCESS")
    lines.append("=" * 60)
    lines.append("")

    triage = results.get('triage', {})
    lines.append(f"Triage ID: {triage.get('id', 'N/A')}")
    lines.append(f"URL: {triage.get('url', 'N/A')}")
    lines.append(f"Type: {triage.get('type', 'N/A')}")
    if triage.get('description'):
        lines.append(f"Description: {triage.get('description')}")

    regressions = triage.get('regressions', [])
    lines.append(f"Linked Regressions: {len(regressions)}")
    for reg in regressions:
        lines.append(f"  - Regression {reg.get('id', 'N/A')}")

    return "\n".join(lines)


def main():
    """Create or update a triage record from command line."""
    if len(sys.argv) < 2:
        print("Usage: triage_regression.py <regression_ids> [options]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Arguments:", file=sys.stderr)
        print("  regression_ids   Comma-separated list of regression IDs", file=sys.stderr)
        print("", file=sys.stderr)
        print("Required Options:", file=sys.stderr)
        print("  --token <token>        OAuth Bearer token for sippy-auth (use oc-auth skill to obtain)", file=sys.stderr)
        print("  --url <jira_url>       JIRA bug URL (e.g., https://issues.redhat.com/browse/OCPBUGS-12345)", file=sys.stderr)
        print("  --type <triage_type>   Triage type: product, test, ci-infra, product-infra", file=sys.stderr)
        print("", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  --triage-id <id>       Existing triage ID to update (omit to create new)", file=sys.stderr)
        print("  --description <text>   Description for the triage", file=sys.stderr)
        print("  --format json|summary  Output format (default: json)", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  # Create a new triage for one regression", file=sys.stderr)
        print("  triage_regression.py 33639 --token $TOKEN --url https://issues.redhat.com/browse/OCPBUGS-12345 --type product", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Create a new triage for multiple regressions", file=sys.stderr)
        print("  triage_regression.py 33639,33640,33641 --token $TOKEN --url https://issues.redhat.com/browse/OCPBUGS-12345 --type product", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Update an existing triage to add more regressions", file=sys.stderr)
        print("  triage_regression.py 33639,33640 --token $TOKEN --triage-id 456 --url https://issues.redhat.com/browse/OCPBUGS-12345 --type product", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Create with a description", file=sys.stderr)
        print("  triage_regression.py 33639 --token $TOKEN --url https://issues.redhat.com/browse/OCPBUGS-12345 --type test --description 'Flaky test in discovery suite'", file=sys.stderr)
        sys.exit(1)

    # Parse regression IDs (first positional argument)
    try:
        regression_ids = [int(x.strip()) for x in sys.argv[1].split(',')]
    except ValueError:
        print("Error: regression_ids must be comma-separated integers", file=sys.stderr)
        sys.exit(1)

    # Parse options
    token = None
    url = None
    triage_type = None
    description = None
    triage_id = None
    output_format = 'json'

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--token' and i + 1 < len(sys.argv):
            token = sys.argv[i + 1]
            i += 2
        elif arg == '--url' and i + 1 < len(sys.argv):
            url = sys.argv[i + 1]
            i += 2
        elif arg == '--type' and i + 1 < len(sys.argv):
            triage_type = sys.argv[i + 1]
            i += 2
        elif arg == '--triage-id' and i + 1 < len(sys.argv):
            try:
                triage_id = int(sys.argv[i + 1])
            except ValueError:
                print("Error: --triage-id requires an integer value", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == '--description' and i + 1 < len(sys.argv):
            description = sys.argv[i + 1]
            i += 2
        elif arg == '--format' and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
            if output_format not in ('json', 'summary'):
                print(f"Error: Invalid format '{output_format}'. Use 'json' or 'summary'", file=sys.stderr)
                sys.exit(1)
            i += 2
        else:
            print(f"Error: Unknown argument '{arg}'", file=sys.stderr)
            sys.exit(1)

    # Validate required options
    if not token:
        print("Error: --token is required (use oc-auth skill to obtain token from DPCR cluster)", file=sys.stderr)
        sys.exit(1)
    if triage_id is None:
        # Creating: url and type are required
        if not url:
            print("Error: --url is required when creating a new triage", file=sys.stderr)
            sys.exit(1)
        if not triage_type:
            print("Error: --type is required when creating a new triage", file=sys.stderr)
            sys.exit(1)
    if triage_type is not None and triage_type not in TriageManager.VALID_TYPES:
        print(f"Error: Invalid type '{triage_type}'. Must be one of: {', '.join(TriageManager.VALID_TYPES)}", file=sys.stderr)
        sys.exit(1)

    # Create or update
    try:
        manager = TriageManager(regression_ids, token, url, triage_type, description, triage_id)

        if triage_id is not None:
            results = manager.update()
        else:
            results = manager.create()

        if output_format == 'json':
            print(json.dumps(results, indent=2))
        else:
            print(format_summary(results))

        return 0 if results.get('success') else 1

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
