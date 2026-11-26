#!/usr/bin/env python3
"""Keep open dashboard PRs in newest-added-first project order."""

import argparse
from bisect import bisect_left
from datetime import datetime
import json
import subprocess
import sys


ITEMS_QUERY = """
query DashboardOrder($project: ID!, $after: String) {
  node(id: $project) {
    ... on ProjectV2 {
      items(first: 100, after: $after, query: "is:open is:pr",
            orderBy: {field: POSITION, direction: ASC}) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id createdAt isArchived
          content {
            __typename
            ... on PullRequest { number url state repository { nameWithOwner } }
          }
        }
      }
    }
  }
}
"""

MOVE_MUTATION = """
mutation DashboardMove($project: ID!, $item: ID!, $after: ID) {
  updateProjectV2ItemPosition(input: {
    projectId: $project, itemId: $item, afterId: $after
  }) { clientMutationId }
}
"""


def graphql(query, **variables):
    response = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps({"query": query, "variables": variables}),
        text=True, capture_output=True, check=True,
    )
    result = json.loads(response.stdout)
    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL: " + json.dumps(result["errors"]))
    return result["data"]


def fetch_items(project):
    items = []
    cursor = None
    cursors = set()
    while True:
        page = graphql(ITEMS_QUERY, project=project, after=cursor)["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            if (not item["isArchived"] and content.get("__typename") == "PullRequest"
                    and content.get("state") == "OPEN"):
                items.append(item)
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
        if not cursor or cursor in cursors:
            raise RuntimeError("GitHub returned a non-advancing project cursor")
        cursors.add(cursor)
    if len({item["id"] for item in items}) != len(items):
        raise RuntimeError("GitHub returned duplicate project items; rerun the sync")
    return items


def desired_order(items):
    # Stable sorting preserves manual order for items added at the same instant.
    return sorted(items, key=lambda i: datetime.fromisoformat(
        i["createdAt"].replace("Z", "+00:00")), reverse=True)


def plan_moves(items):
    """Leave a longest ordered subsequence in place to minimize API mutations."""
    desired = desired_order(items)
    ranks = {item["id"]: rank for rank, item in enumerate(desired)}
    tails = []
    tail_ranks = []
    predecessors = [-1] * len(items)
    for index, item in enumerate(items):
        rank = ranks[item["id"]]
        slot = bisect_left(tail_ranks, rank)
        if slot:
            predecessors[index] = tails[slot - 1]
        if slot == len(tails):
            tails.append(index)
            tail_ranks.append(rank)
        else:
            tails[slot] = index
            tail_ranks[slot] = rank
    keep = set()
    index = tails[-1] if tails else -1
    while index != -1:
        keep.add(items[index]["id"])
        index = predecessors[index]
    return [(item, desired[rank - 1]["id"] if rank else None, rank + 1)
            for rank, item in enumerate(desired) if item["id"] not in keep]


def order_project(project, dry_run=False):
    items = fetch_items(project)
    moves = plan_moves(items)
    for item, after, position in moves:
        if not dry_run:
            graphql(MOVE_MUTATION, project=project, item=item["id"], after=after)
        pr = item["content"]
        prefix = "WOULD POSITION" if dry_run else "POSITION"
        print(f"  {prefix}: {pr['repository']['nameWithOwner']}#{pr['number']}"
              f" → {position} (newest dashboard additions first)", flush=True)
    if moves and not dry_run:
        actual = fetch_items(project)
        if [i["id"] for i in actual] != [i["id"] for i in desired_order(actual)]:
            raise RuntimeError("Open PR ordering changed during the update; rerun the sync")
    print(f"  Open PR ordering: {len(items)} PRs, {len(moves)}"
          f" {'moves planned' if dry_run else 'moved'}", flush=True)
    return len(moves)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        order_project(args.project_id, args.dry_run)
    except (subprocess.CalledProcessError, RuntimeError, ValueError, KeyError, TypeError) as error:
        detail = (error.stderr or str(error)).strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(f"ERROR: could not order open dashboard PRs: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
