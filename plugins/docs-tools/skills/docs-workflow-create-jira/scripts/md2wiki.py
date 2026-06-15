#!/usr/bin/env python3
"""Convert markdown to JIRA wiki markup.

Usage: python3 md2wiki.py <input_file> <output_file>
"""

import re
import sys


def convert(content: str) -> str:
    lines = content.split("\n")
    result = []
    in_table = False

    for line in lines:
        if line.startswith("## "):
            result.append("h2. " + line[3:])
            continue
        if line.startswith("### "):
            result.append("h3. " + line[4:])
            continue
        if line.strip() == "---":
            result.append("----")
            continue
        line = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", line)
        line = re.sub(r"`([^`]+)`", r"{{\1}}", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\1|\2]", line)
        numbered = re.match(r"^(\d+)\.\s+(.*)", line)
        if numbered:
            result.append("# " + numbered.group(2))
            continue
        if "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().split("|")]
            cells = [c for c in cells if c]
            if all(re.match(r"^[-:]+$", c) for c in cells):
                continue
            if not in_table:
                result.append("||" + "||".join(cells) + "||")
                in_table = True
            else:
                result.append("|" + "|".join(cells) + "|")
            continue
        else:
            in_table = False
        result.append(line)

    return "\n".join(result)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_file> <output_file>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        content = f.read()

    with open(sys.argv[2], "w") as f:
        f.write(convert(content))
