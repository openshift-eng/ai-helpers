---
description: Ask questions about your research project's indexed content
argument-hint: <project-name> <question>
---

## Name
research:query

## Synopsis
```
/research:query <project-name> <question>
```

## Description

The `research:query` command searches your research project's vector database for content relevant to your question, retrieves the most similar chunks, and provides an accurate answer based solely on the indexed content.

**Key Features:**
- Semantic search (understands meaning, not just keywords)
- Returns source citations for verification
- Refuses to answer if content doesn't exist in the knowledge base
- Cross-references multiple sources for comprehensive answers

## Implementation

The command delegates to the research-engine skill:

### 1. Validate Project Exists
```bash
# Check project exists
ls .work/research/{project-name}/vectordb/
```

If project doesn't exist, inform user and suggest `/research:add`.

### 2. Perform Semantic Search
```bash
python3 plugins/research/skills/research-engine/scripts/query.py \
  --project "{project-name}" \
  --question "{user-question}" \
  --top-k 10
```

The script:
1. Loads the ChromaDB collection for the project
2. Embeds the question using sentence-transformers
3. Performs similarity search to find top-k relevant chunks
4. Returns chunks with metadata (source, title, relevance score)

### 3. Present Results to Claude
The query script outputs JSON with relevant chunks:
```json
{
  "query": "How do pods communicate?",
  "results": [
    {
      "content": "Pods can communicate with each other using...",
      "source": "https://kubernetes.io/docs/concepts/services-networking/",
      "title": "Kubernetes Networking",
      "relevance": 0.89,
      "chunk_id": "web-abc123-chunk-5"
    }
  ]
}
```

### 4. Generate Answer
Based on the retrieved chunks:
1. Read all relevant content
2. Synthesize an answer that ONLY uses information from the chunks
3. Include citations to sources
4. If no relevant content found, explicitly state that

### 5. Answer Format
Present the answer with:
- Clear, direct response to the question
- Source citations (clickable links when available)
- Confidence indicator based on relevance scores
- Suggestion for follow-up queries if relevant

## Arguments
- `$1`: Project name (required) - The research project to query
- `$2+`: Question (required) - Natural language question (all remaining arguments joined)

## Return Value

**Format**: Markdown response with:
- Answer synthesized from indexed content
- Source citations with links
- Relevance/confidence indicator

**Example output**:
```markdown
## Answer

Based on the indexed documentation, pods communicate with each other through...

### Sources
1. [Kubernetes Networking](https://kubernetes.io/docs/...) (relevance: 89%)
2. [Pod-to-Pod Communication](https://example.com/...) (relevance: 76%)

---
*Answer generated from 3 sources in project "k8s-study"*
```

## Examples

1. **Basic question**:
   ```
   /research:query k8s-study How do pods communicate with each other?
   ```

2. **Code-related question**:
   ```
   /research:query etcd-deep-dive How does etcd handle leader election?
   ```

3. **Specific topic**:
   ```
   /research:query openshift-networking What is the role of OVN in OpenShift?
   ```

4. **Comparison question**:
   ```
   /research:query cloud-platforms What are the differences between EKS and GKE?
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Project not found` | Project doesn't exist | Create with `/research:add {project} {source}` |
| `No relevant content` | Question not covered by sources | Add more relevant sources |
| `Empty database` | No content indexed yet | Add sources with `/research:add` |

## Tips

- **Be specific**: "How does X work in Y context?" is better than "Tell me about X"
- **Use domain terms**: Use terminology from your sources for better matching
- **Follow up**: If the answer is incomplete, ask a more specific follow-up
- **Check sources**: Click source links to verify and explore further


