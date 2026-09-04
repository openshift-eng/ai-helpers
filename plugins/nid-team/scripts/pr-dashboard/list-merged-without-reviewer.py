#!/usr/bin/env python3
"""Lists PRs on the NI&D dashboard that merged in the last week without ever
being assigned a primary reviewer.

Output: first line is the count, then one line per PR:
  short_repo#number|full_repo|title|merged_date

Usage: list-merged-without-reviewer.py [days]  (default: 7)
"""

import json
import subprocess
import datetime
import sys

days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

raw = subprocess.run(
    ["gh", "project", "item-list", "28", "--owner", "openshift",
     "--format", "json", "--limit", "500"],
    capture_output=True, text=True, check=True
)
data = json.loads(raw.stdout)

results = []
for item in data["items"]:
    c = item.get("content", {})
    if c.get("type") != "PullRequest":
        continue
    if item.get("primary Reviewer", "") or item.get("secondary Reviewer", ""):
        continue
    repo = c.get("repository", "")
    number = str(c.get("number", ""))
    title = c.get("title", "")
    r = subprocess.run(
        ["gh", "pr", "view", number, "-R", repo,
         "--json", "state,mergedAt", "-q", '.state + " " + .mergedAt'],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"WARNING: gh pr view failed for {repo}#{number}: {r.stderr.strip()}", file=sys.stderr)
        continue
    parts = r.stdout.strip().split(" ", 1)
    if len(parts) == 2 and parts[0] == "MERGED":
        try:
            merged_at = datetime.datetime.fromisoformat(parts[1].replace("Z", "+00:00"))
            if merged_at >= cutoff:
                results.append((repo, number, title, merged_at.strftime("%Y-%m-%d")))
        except Exception as e:
            print(f"WARNING: could not parse mergedAt for {repo}#{number}: {e}", file=sys.stderr)

print(len(results))
for repo, number, title, date in results:
    short_repo = repo.split("/")[-1]
    print(f"{short_repo}#{number}|{repo}|{title}|{date}")
