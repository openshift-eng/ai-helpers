---
description: Ask questions about your indexed knowledge context
argument-hint: <question>
---

## Name
research:ask

## Synopsis
```
/research:ask <question>
```

## Description

The `research:ask` command searches your unified knowledge context for relevant information and provides accurate answers based solely on the indexed content.

**Key features:**
- Semantic search across all indexed sources
- Combines knowledge from codebase, docs, videos, and repos
- Provides source citations
- Refuses to hallucinate (only answers from indexed content)

## Implementation

**CRITICAL: You MUST use the wrapper script, not Python directly.**

### Step 1: Locate the Plugin Directory

```bash
# Find the research plugin
PLUGIN_DIR=""
for dir in \
    "$HOME/Documents/pillaimanish/ai-helpers/plugins/research" \
    "$HOME/.claude/plugins/cache/ai-helpers/research/*/"; do
    if [[ -f "$dir/skills/research-engine/scripts/research.sh" ]]; then
        PLUGIN_DIR="$dir"
        break
    fi
done
RESEARCH_SH="$PLUGIN_DIR/skills/research-engine/scripts/research.sh"
```

### Step 2: Validate Context Exists
```bash
ls .work/research/context.db/
```

If no context exists, inform user to run `/research:build` first.

### Step 3: Perform Semantic Search

**Use the wrapper script:**
```bash
"$RESEARCH_SH" query --question "{user-question}" --top-k 15
```

The script:
1. Uses Python 3.12 venv (avoids Python 3.14 compatibility issues)
2. Loads the ChromaDB collection
3. Embeds the question using sentence-transformers
4. Finds top-k most relevant chunks across ALL sources
5. Returns chunks with metadata (source type, URL, relevance)

### 3. Generate Answer

Based on the retrieved chunks:
1. Read all relevant content
2. Synthesize an answer using ONLY the indexed content
3. Include citations to sources
4. Group information by source type if helpful

### 4. Format Response

```markdown
## Answer

Based on your indexed context, here's what I found:

[Synthesized answer from chunks]

### Sources

| Source | Type | Relevance |
|--------|------|-----------|
| [kubernetes.io/docs/concepts/pods](url) | 🌐 web | 92% |
| [Your codebase: controllers/pod_controller.go](path) | 📁 code | 87% |
| [YouTube: K8s Tutorial @ 5:23](url) | 📺 video | 78% |

---
*Searched 2,341 chunks across 12 sources*
```

## Arguments

- `$1+`: Question (required) - Natural language question (all arguments joined)

## Return Value

**Success:** Markdown answer with citations
**No results:** Message indicating no relevant content found
**No context:** Instructions to run `/research:build`

## Examples

1. **Basic question:**
   ```
   /research:ask How do pods communicate with each other?
   ```

2. **Code-related question:**
   ```
   /research:ask How should I implement the reconcile loop in my controller?
   ```

3. **Comparison question:**
   ```
   /research:ask What's the difference between Deployments and StatefulSets?
   ```

4. **Project-specific question:**
   ```
   /research:ask What does my controller do when a pod is deleted?
   ```

## Tips

- **Be specific:** "How does X work in Y context?" beats "Tell me about X"
- **Reference your code:** "In my controller..." helps find relevant context
- **Ask follow-ups:** Build on previous answers for deeper understanding
- **Check sources:** Click citations to verify and learn more

