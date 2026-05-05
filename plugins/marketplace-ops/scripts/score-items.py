#!/usr/bin/env python3
"""
Score individual commands and skills within plugins for staleness.

Complements score-plugins.py: this script analyzes items inside plugins
that were NOT flagged for full removal. It gathers per-file git metadata
and structural signals, outputting JSON for LLM-assisted review.

Usage: score-items.py [--plugins PLUGIN1,PLUGIN2,...] [repo-root]
  --plugins   Comma-separated plugin names to analyze (default: all non-protected)
  repo-root   Path to the repository root (default: cwd)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    plugin_filter = None
    repo_root = os.getcwd()
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--plugins" and i + 1 < len(args):
            plugin_filter = [p.strip() for p in args[i + 1].split(",")]
            i += 2
        else:
            repo_root = args[i]
            i += 1
    return plugin_filter, Path(repo_root)


def load_pruneprotect(repo_root):
    protect_file = repo_root / ".pruneprotect"
    protected = []
    if protect_file.exists():
        for line in protect_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            protected.append(line)
    return protected


def is_protected(path, protected):
    for prefix in protected:
        if path.startswith(prefix) or path.rstrip("/") == prefix.rstrip("/"):
            return True
    return False


def git(repo_root, *args):
    result = subprocess.run(
        ["git", "-C", str(repo_root)] + list(args),
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def get_last_commit_date(repo_root, path):
    out = git(repo_root, "log", "-1", "--format=%aI", "--", path)
    if not out:
        return None
    return datetime.fromisoformat(out)


def get_commit_count(repo_root, path):
    out = git(repo_root, "rev-list", "--count", "HEAD", "--", path)
    try:
        return int(out)
    except (ValueError, TypeError):
        return 0


def get_contributor_count(repo_root, path):
    out = git(repo_root, "shortlog", "-sn", "--all", "--", path)
    return len([l for l in out.splitlines() if l.strip()])


def get_contributors(repo_root, path):
    out = git(repo_root, "shortlog", "-sn", "--all", "--", path)
    contributors = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                contributors.append({"commits": int(parts[0].strip()), "name": parts[1].strip()})
    return contributors


def get_file_size(path):
    try:
        return path.stat().st_size
    except OSError:
        return 0


def read_frontmatter(filepath):
    """Extract YAML frontmatter from a markdown file."""
    try:
        text = filepath.read_text()
    except (OSError, UnicodeDecodeError):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def score_item(item_info, now):
    score = 0
    reasons = []

    last_date = item_info["last_commit_date"]
    if last_date:
        days_inactive = (now - last_date).days
        item_info["days_since_last_commit"] = days_inactive
        if days_inactive > 180:
            score += 4
            reasons.append(f"Last commit {days_inactive} days ago (>180)")
        elif days_inactive > 150:
            score += 3
            reasons.append(f"Last commit {days_inactive} days ago (>150)")
        elif days_inactive > 120:
            score += 2
            reasons.append(f"Last commit {days_inactive} days ago (>120)")
        elif days_inactive > 90:
            score += 1
            reasons.append(f"Last commit {days_inactive} days ago (>90)")
    else:
        item_info["days_since_last_commit"] = None

    if item_info["commit_count"] <= 2:
        score += 1
        reasons.append(f"Only {item_info['commit_count']} commits")

    if item_info["contributor_count"] == 1:
        score += 1
        reasons.append("Single contributor")

    if item_info["size_bytes"] < 500:
        score += 1
        reasons.append(f"Very small ({item_info['size_bytes']} bytes)")

    item_info["score"] = score
    item_info["reasons"] = reasons
    return score


def analyze_plugin(repo_root, plugin_dir, protected, now):
    plugin_name = plugin_dir.name
    commands = []
    skills = []

    cmd_dir = plugin_dir / "commands"
    if cmd_dir.is_dir():
        for cmd_file in sorted(cmd_dir.glob("*.md")):
            rel_path = str(cmd_file.relative_to(repo_root))
            if is_protected(rel_path, protected):
                continue

            fm = read_frontmatter(cmd_file)
            last_date = get_last_commit_date(repo_root, rel_path)

            info = {
                "type": "command",
                "name": cmd_file.stem,
                "path": rel_path,
                "plugin": plugin_name,
                "description": fm.get("description", ""),
                "size_bytes": get_file_size(cmd_file),
                "last_commit_date": last_date,
                "commit_count": get_commit_count(repo_root, rel_path),
                "contributor_count": get_contributor_count(repo_root, rel_path),
                "contributors": get_contributors(repo_root, rel_path),
            }
            score_item(info, now)
            commands.append(info)

    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            rel_path = f"plugins/{plugin_name}/skills/{skill_dir.name}/"
            if is_protected(rel_path, protected):
                continue

            fm = read_frontmatter(skill_md)
            last_date = get_last_commit_date(repo_root, rel_path)

            # Skill size = total size of all files in the skill directory
            total_size = sum(f.stat().st_size for f in skill_dir.rglob("*") if f.is_file())

            info = {
                "type": "skill",
                "name": skill_dir.name,
                "path": rel_path,
                "plugin": plugin_name,
                "description": fm.get("description", fm.get("name", "")),
                "size_bytes": total_size,
                "last_commit_date": last_date,
                "commit_count": get_commit_count(repo_root, rel_path),
                "contributor_count": get_contributor_count(repo_root, rel_path),
                "contributors": get_contributors(repo_root, rel_path),
            }
            score_item(info, now)
            skills.append(info)

    return commands, skills


def main():
    plugin_filter, repo_root = parse_args()
    now = datetime.now(timezone.utc)
    protected = load_pruneprotect(repo_root)
    plugins_dir = repo_root / "plugins"

    if not plugins_dir.is_dir():
        print(json.dumps({"error": "No plugins/ directory found"}, indent=2))
        sys.exit(1)

    all_items = []

    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue

        plugin_name = plugin_dir.name
        rel_path = f"plugins/{plugin_name}/"

        # Skip protected plugins entirely
        if is_protected(rel_path, protected):
            continue

        # If --plugins filter specified, only analyze those
        if plugin_filter and plugin_name not in plugin_filter:
            continue

        commands, skills = analyze_plugin(repo_root, plugin_dir, protected, now)
        all_items.extend(commands)
        all_items.extend(skills)

    # Serialize datetimes
    for item in all_items:
        if isinstance(item.get("last_commit_date"), datetime):
            item["last_commit_date"] = item["last_commit_date"].isoformat()

    flagged = [i for i in all_items if i["score"] >= 3]
    clean = [i for i in all_items if i["score"] < 3]

    output = {
        "generated_at": now.isoformat(),
        "summary": {
            "total_items": len(all_items),
            "total_commands": sum(1 for i in all_items if i["type"] == "command"),
            "total_skills": sum(1 for i in all_items if i["type"] == "skill"),
            "flagged": len(flagged),
            "clean": len(clean),
        },
        "flagged": sorted(flagged, key=lambda x: -x["score"]),
        "clean": sorted(clean, key=lambda x: (-x["score"], x["path"])),
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
