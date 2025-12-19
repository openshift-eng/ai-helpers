---
description: List all sources in a research project
argument-hint: [project-name]
---

## Name
research:list

## Synopsis
```
/research:list [project-name]
```

## Description

The `research:list` command displays all sources indexed in a research project, including metadata like source type, title, number of chunks, and indexing status.

If no project name is provided, lists all available research projects.

## Implementation

### 1. If no project specified, list all projects
```bash
ls -la .work/research/
```

Display each project with summary stats from their manifest files.

### 2. If project specified, show detailed source list
```bash
python3 plugins/research/skills/research-engine/scripts/list_sources.py \
  --project "{project-name}"
```

The script reads `manifest.json` and queries ChromaDB for stats.

### 3. Output Format

**All projects view**:
```
📚 Research Projects
═══════════════════════════════════════════════════════════════

Project              Sources    Chunks    Last Updated
────────────────────────────────────────────────────────────────
k8s-study            12         847       2024-12-12 10:30
openshift-networking 8          523       2024-12-11 15:45
etcd-deep-dive       5          312       2024-12-10 09:00

Use `/research:list <project>` for details.
```

**Single project view**:
```
📚 Project: k8s-study
═══════════════════════════════════════════════════════════════
Created: 2024-12-12 08:00:00
Total Sources: 12
Total Chunks: 847

Sources:
────────────────────────────────────────────────────────────────
Type     Title                                    Chunks  Status
────────────────────────────────────────────────────────────────
🌐 web   Kubernetes Concepts Overview             45      ✅ indexed
🌐 web   Pod Networking Deep Dive                 78      ✅ indexed
📺 yt    Kubernetes Tutorial for Beginners        156     ✅ indexed
📺 yt    Advanced K8s Networking                  89      ✅ indexed
🐙 gh    kubernetes/kubernetes (README + docs)    312     ✅ indexed
📄 local study-notes.md                           23      ✅ indexed
...

Legend: 🌐 web | 📺 youtube | 🐙 github | 📄 local | 📝 gdocs
```

## Arguments
- `$1`: Project name (optional) - Show details for specific project. If omitted, shows all projects.

## Return Value
- **Format**: Formatted table of projects or sources
- **Data**: Source metadata including type, title, chunks, status

## Examples

1. **List all projects**:
   ```
   /research:list
   ```

2. **List sources in a specific project**:
   ```
   /research:list k8s-study
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `No projects found` | No research projects exist | Create one with `/research:add` |
| `Project not found` | Specified project doesn't exist | Check spelling or run `/research:list` to see available projects |


