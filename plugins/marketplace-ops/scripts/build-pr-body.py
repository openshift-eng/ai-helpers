#!/usr/bin/env python3
"""
Generate the PR body for a marketplace pruning PR.

Reads plugin-level and item-level removal data and builds the full
markdown body with removal manifest, cross-reference warnings,
save/drop instructions, and protected items list.

Usage: build-pr-body.py --plugin-report FILE --item-removals FILE [--cross-refs FILE]
"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-report", required=True,
                        help="JSON from score-plugins.py")
    parser.add_argument("--item-removals", required=True,
                        help="JSON array of {path, reason} from LLM or direct removals")
    parser.add_argument("--cross-refs", default=None,
                        help="JSON from cross-reference-scan.py")
    args = parser.parse_args()

    with open(args.plugin_report) as f:
        plugin_data = json.load(f)
    with open(args.item_removals) as f:
        item_data = json.load(f)
    cross_refs = {"warnings": []}
    if args.cross_refs:
        with open(args.cross_refs) as f:
            cross_refs = json.load(f)

    rows = []
    for plugin in plugin_data.get("candidates", []):
        reasons = "; ".join(plugin.get("reasons", []))
        rows.append(f"| plugin | `{plugin['path']}` | {reasons} |")

    for item in item_data:
        item_type = item.get("type", "item")
        rows.append(f"| {item_type} | `{item['path']}` | {item.get('reason', '')} |")

    manifest = "| Type | Path | Reason |\n|------|------|--------|\n"
    manifest += "\n".join(rows) if rows else "| — | — | No items flagged for removal |"

    xref_section = "None"
    if cross_refs.get("warnings"):
        xref_lines = []
        for w in cross_refs["warnings"]:
            xref_lines.append(f"- `{w['removed']}`: referenced by `{w['referenced_by']}`")
        xref_section = "\n".join(xref_lines)

    protected_section = "None"
    protected = plugin_data.get("protected", [])
    if protected:
        plines = [f"- `{p['path']}` — listed in .pruneprotect" for p in protected]
        protected_section = "\n".join(plines)

    body = f"""## Summary
Automated pruning of stale/inactive plugins, commands, and skills.

## Removal Manifest

{manifest}

## Cross-Reference Warnings
{xref_section}

## How to Save or Drop Items
To keep something that's being removed, comment on this PR:

```text
/save plugins/foo/
/save plugins/bar/commands/baz.md
```

Saved items will be restored from git history and added to `.pruneprotect` so they won't be flagged in future pruning cycles.

To manually add a removal, comment:

```text
/drop plugins/baz/commands/old-cmd.md
```

Commands are processed automatically on a weekly schedule.

## Protected Items
Items listed in `.pruneprotect` were excluded from analysis.

{protected_section}"""

    print(body)


if __name__ == "__main__":
    main()
