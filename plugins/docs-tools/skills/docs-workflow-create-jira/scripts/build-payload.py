#!/usr/bin/env python3
"""Build a JIRA issue creation JSON payload.

Usage: python3 build-payload.py <wiki_file> <output_file> <project_key> <summary>
"""

import json
import sys

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(
            f"Usage: {sys.argv[0]} <wiki_file> <output_file> <project_key> <summary>",
            file=sys.stderr,
        )
        sys.exit(1)

    wiki_file, payload_file, project, summary = (
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
    )

    with open(wiki_file) as f:
        description = f.read()

    payload = {
        "fields": {
            "project": {"key": project},
            "summary": f"[ccs] Docs - {summary}",
            "description": description,
            "issuetype": {"name": "Story"},
            "components": [{"name": "Documentation"}],
        }
    }

    with open(payload_file, "w") as f:
        json.dump(payload, f)
