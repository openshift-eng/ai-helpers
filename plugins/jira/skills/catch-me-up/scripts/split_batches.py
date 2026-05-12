#!/usr/bin/env python3
"""Split gathered events into batch files for parallel classification.

Groups events by issue key so all events for an issue stay in the same batch.
Oversized issues (>3x target) are split chronologically.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main():
    """Split events into batches grouped by issue key for parallel classification."""
    if len(sys.argv) < 2:
        print("Usage: split_batches.py <events.json> [batch_size]", file=sys.stderr)
        sys.exit(1)

    events_file = Path(sys.argv[1])
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    with open(events_file) as f:
        data = json.load(f)

    events = data["events"]

    authors = Counter(e["author"] for e in events)
    fields = Counter(e["field"] for e in events if e["type"] == "field_change")

    context = {
        "total_events": len(events),
        "jira_username": data.get("config", {}).get("jira_username"),
        "top_authors": dict(authors.most_common(20)),
        "top_fields": dict(fields.most_common(15)),
    }

    groups = defaultdict(list)
    for event in events:
        groups[event["issue"]["key"]].append(event)

    max_batch_size = batch_size * 3

    batches: list[list[dict]] = []
    current_batch: list[dict] = []

    for issue_key, issue_events in groups.items():
        if len(issue_events) > max_batch_size:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
            for i in range(0, len(issue_events), max_batch_size):
                batches.append(issue_events[i : i + max_batch_size])
            continue

        if current_batch and len(current_batch) + len(issue_events) > batch_size:
            batches.append(current_batch)
            current_batch = []
        current_batch.extend(issue_events)

    if current_batch:
        batches.append(current_batch)

    batch_dir = events_file.parent / "batches"
    if batch_dir.exists():
        for old_file in batch_dir.glob("batch_*.json"):
            old_file.unlink()
    batch_dir.mkdir(parents=True, exist_ok=True)

    batch_files = []
    for i, batch in enumerate(batches):
        batch_num = i + 1
        batch_data = {
            "batch_number": batch_num,
            "total_batches": len(batches),
            "context": context,
            "events": batch,
        }
        batch_file = batch_dir / f"batch_{batch_num}.json"
        with open(batch_file, "w") as f:
            json.dump(batch_data, f, indent=2)
        batch_files.append(str(batch_file.resolve()))

    output = {
        "batch_files": batch_files,
        "batch_count": len(batch_files),
        "total_events": len(events),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
