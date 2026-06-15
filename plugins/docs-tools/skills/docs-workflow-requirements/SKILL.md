---
name: docs-workflow-requirements
description: Analyze documentation requirements for a JIRA ticket using a two-pass fanout. Pass 1 dispatches a discovery agent to enumerate requirements. Pass 2 fans out one deep-analysis agent per requirement for isolated, thorough analysis. Assembles the standard requirements.md output. Invoked by the orchestrator.
argument-hint: <ticket> --base-path <path> [--pr <url>]... [--repo <path>]
allowed-tools: Read, Write, Glob, Grep, Edit, Bash, Skill, Agent, WebSearch, WebFetch
---

# Requirements Analysis Step

Step skill for the docs-orchestrator pipeline. Follows the step skill contract: **parse args → discover → fan out → merge → write output**.

This skill uses a two-pass architecture to analyze documentation requirements:

1. **Discovery pass** — A single `requirements-discoverer` agent enumerates requirements from JIRA, PRs, and specs, producing a JSON skeleton
2. **Deep analysis pass** — One `requirements-analyst` agent per requirement, all running in parallel, each performing thorough analysis with a clean context window
3. **Merge** — The orchestrator assembles per-requirement JSON results into the standard `requirements.md` format

## Arguments

- `$1` — JIRA ticket ID (required)
- `--base-path <path>` — Base output path (e.g., `.agent_workspace/proj-123`)
- `--pr <url>` — PR/MR URL to include in analysis (repeatable)
- `--repo <path>` — Source code repo path (optional, passed to analyst agents for code verification)

## Output

```
<base-path>/requirements/requirements.md
<base-path>/requirements/step-result.json
<base-path>/requirements/discovered_repos.json     (produced by repo extraction, consumed by resolve_source.py)
```

## Execution

### 1. Parse arguments

Extract the ticket ID, `--base-path`, any `--pr` URLs, and optional `--repo` from the args string.

Set the output path:

```bash
OUTPUT_DIR="${BASE_PATH}/requirements"
OUTPUT_FILE="${OUTPUT_DIR}/requirements.md"
DISCOVERY_FILE="${OUTPUT_DIR}/discovery.json"
mkdir -p "$OUTPUT_DIR"
```

### 2. Pass 1 — Discovery

Dispatch one `requirements-discoverer` agent to enumerate requirements from all sources.

```
Agent:
  subagent_type: docs-tools:requirements-discoverer
  description: "Discover requirements for <TICKET>"
  prompt: |
    Discover documentation requirements for JIRA ticket <TICKET>.

    PR/MR URLs to include in analysis (merge with any auto-discovered, dedup):
    - <PR_URL_1>
    - <PR_URL_2>

    Save your JSON output to: <DISCOVERY_FILE>

    Follow your standard discovery procedure: JIRA fetch, ticket graph traversal,
    PR listing, spec identification, requirement enumeration.
```

The PR URL bullet list is conditional — include those bullets only if `--pr` URLs were provided.

After the agent completes, read `<DISCOVERY_FILE>`.

If the discovery JSON has an `error` field set, STOP and report the error (likely an access failure).

### 3. Extract discovered repos

After the discoverer agent completes, extract repo/PR URLs from the JIRA graph data. Skip this step if `$OUTPUT_DIR/discovered_repos.json` already exists (e.g., from a previous run or pre-flight resolution).

```bash
if [ ! -f "$OUTPUT_DIR/discovered_repos.json" ]; then
  JIRA_READER="${CLAUDE_PLUGIN_ROOT}/skills/jira-reader/scripts/jira_reader.py"
  python3 "$JIRA_READER" --graph <TICKET> | \
    python3 ${CLAUDE_SKILL_DIR}/scripts/extract_discovered_repos.py \
      --output-dir "$OUTPUT_DIR" \
      --traverse-links "$JIRA_READER"
fi
```

This produces `discovered_repos.json` in the output directory, which `resolve_source.py` reads at Priority 4 for automatic repo discovery. If the script fails, log a warning and continue — repo discovery is optional.

### 4. Parse discovery output

Extract a lightweight summary from the discovery JSON. Do **not** read the full `discovery.json` into context — use a bash command to extract only what the orchestrator needs for fan-out dispatch:

```bash
python3 -c "
import json
d = json.load(open('<DISCOVERY_FILE>'))
reqs = d.get('requirements', [])
print(json.dumps({
    'count': len(reqs),
    'has_persisted_sources': 'persisted_sources' in d,
    'items': [{'id': r['id'], 'title': r.get('title','')[:60]} for r in reqs]
}))
"
```

This prints a compact JSON with requirement count, IDs, and truncated titles — enough to dispatch agents and build file paths. The full skeleton (sources, one_line_summary, related_tickets, release, persisted_sources) remains in `discovery.json` on disk for agents to read directly.

If `count` is 0, write a minimal `requirements.md` noting that no requirements were found, write `step-result.json`, and exit successfully.

### 5. Pass 2 — Fan out deep analysis

For each requirement in the discovery output, dispatch one `requirements-analyst` agent. Launch ALL agents in a **single message** (parallel execution).

Each agent reads its own requirement skeleton from the discovery file on disk and writes its result to a per-requirement JSON file on disk. This keeps the orchestrator's context lean — agent prompts are compact (~0.3KB each) and agent results are one-line confirmations (~0.1KB each).

For each requirement, use:

```
Agent:
  subagent_type: docs-tools:requirements-analyst
  description: "Analyze REQ-NNN: <title truncated to 40 chars>"
  prompt: |
    Perform deep analysis of a single documentation requirement.

    Read your requirement skeleton from: <DISCOVERY_FILE>
    Extract the entry with id "<REQ_ID>" from the "requirements" array.
    Also read "related_tickets", "release", and "sources_consulted" from the same file.

    [If persisted_sources is present in discovery JSON:]
    The discovery file contains a "persisted_sources" object with file paths
    to pre-fetched source data (comments, specs, diffs). Read from disk
    instead of re-fetching from APIs.

    [If --repo was provided:]
    REPO_PATH: <repo_path>

    Fetch detailed content from each source, perform web search expansion,
    and produce complete documentation requirements with acceptance criteria.

    OUTPUT_FILE: <OUTPUT_DIR>/req-<NNN>.json
    Write your JSON result to the OUTPUT_FILE path above using the Write tool.
    After writing, print ONLY: Written <OUTPUT_DIR>/req-<NNN>.json
```

The `REPO_PATH` line is conditional — include it only if `--repo` was passed to this step.

The `persisted_sources` note is conditional — include it only if the discovery JSON has a `persisted_sources` field (detected in step 4's output).

**Important:** All Agent calls MUST be in a single message so they run in parallel.

### 6. Collect results from disk

After all agents complete, verify which per-requirement JSON files were written:

```bash
ls <OUTPUT_DIR>/req-*.json 2>/dev/null | wc -l
```

For each expected requirement (from step 4's item list):

1. Check if `<OUTPUT_DIR>/req-<NNN>.json` exists
2. If the file exists, it will be read by the merge agent in the next step
3. If the file is missing (agent failed or was skipped), the merge agent will create a fallback entry using skeleton data from `discovery.json`

Log: `"<found_count>/<total_count> requirement analysis files written to disk"`

### 7. Assemble requirements.md via merge agent

Delegate the assembly of `requirements.md` to a merge subagent. This keeps the full markdown content (~30-60KB) out of the orchestrator's context.

```
Agent:
  description: "Merge requirements for <TICKET>"
  prompt: |
    Assemble a requirements.md document from per-requirement analysis files.

    DISCOVERY_FILE: <DISCOVERY_FILE>
    OUTPUT_DIR: <OUTPUT_DIR>
    OUTPUT_FILE: <OUTPUT_FILE>
    EXPECTED_REQUIREMENTS: <comma-separated list of REQ IDs from step 4>

    Instructions:
    1. Read <DISCOVERY_FILE> for metadata: ticket_summary, release, sources_consulted, related_tickets
    2. For each expected requirement ID, read <OUTPUT_DIR>/req-<NNN>.json
       - If a file is missing, create a fallback entry from the skeleton in discovery.json:
         {"id": "<REQ-NNN>", "title": "<from skeleton>", "error": "Agent did not return valid JSON",
          "priority": "<from skeleton>", "category": "<from skeleton>",
          "sources": [{"label": "<source.key or source.url>", "url": "<source.url>", "note": "From discovery (deep analysis failed)"}],
          "summary": "<one_line_summary from skeleton>", "user_impact": null, "scope": null,
          "documentation_actions": [], "acceptance_criteria": [], "references": [],
          "web_findings": [], "is_breaking_change": false, "deprecation_version": null,
          "notes": "Deep analysis failed — using skeleton data only"}
    3. Collect all per-requirement results ordered by ID
    4. Assemble <OUTPUT_FILE> using the format contract below
    5. After writing, print ONLY: Written <OUTPUT_FILE>

    FORMAT CONTRACT — the document structure must match this exactly:

    # Documentation Requirements

    **Source**: <ticket_summary from discovery>
    **Date**: <YYYY-MM-DD>
    **Release/Sprint**: <release from discovery>

    ## Summary

    - Total requirements analyzed: <count>
    - New modules needed: <count documentation_actions with action "Create">
    - Existing modules to update: <count documentation_actions with action "Update">
    - Breaking changes requiring docs: <count where is_breaking_change is true>

    ## Requirements by priority

    ### Critical

    #### REQ-001: [title]
    - **Source**: [label](url) | [label](url)
    - **Summary**: [summary]
    - **User impact**: [user_impact]
    - **Documentation action**:
      - [ ] [action] `[file]` ([type]) [note if present]
    - **Acceptance criteria**:
      - [ ] [criterion]
    - **References**:
      - [label](url): [note]

    ### High
    [Same format, requirements with priority "high"]

    ### Medium
    [Same format, requirements with priority "medium"]

    ### Low
    [Same format, requirements with priority "low"]

    ## Documentation scope

    ### New documentation needed

    | Requirement | Scope | References |
    |-------------|-------|------------|
    | REQ-XXX | [From documentation_actions where action is "Create"] | [source labels] |

    ### Existing documentation to update

    | Requirement | What changed | References |
    |-------------|-------------|------------|
    | REQ-XXX | [From documentation_actions where action is "Update"] | [source labels] |

    ## Breaking changes

    [Table of requirements where is_breaking_change is true. Omit section if none.]

    | Change | Migration steps needed | Deprecation notice | References |
    |--------|------------------------|-------------------|------------|

    ## Notes

    [Aggregate any non-null notes from requirements. Omit section if none.]

    ## Related tickets

    [Format related_tickets from discovery output. Omit section if empty.]

    ## Sources consulted

    ### JIRA tickets
    [From sources_consulted.jira_tickets — deduplicated across all requirements]

    ### Pull requests / Merge requests
    [From sources_consulted.pull_requests — deduplicated]

    ### Code files
    [From references with type "code" across all requirements — deduplicated]

    ### Existing documentation
    [From sources_consulted.existing_docs — deduplicated]

    ### External references
    [From references without type "code" that are not JIRA/PR/web_findings — deduplicated]

    ### Web search findings
    [From web_findings across all requirements — deduplicated by URL]

    RULES:
    - Only include priority sections that have requirements (omit empty ### High if none)
    - Requirements with errors: include under their original priority with: **Note:** Deep analysis failed for this requirement. Skeleton data only.
    - Deduplicate sources consulted and references by URL or file path
    - Convert skeleton sources to analyst format: use key (for JIRA) or URL as label, preserve URL, add note "From discovery (deep analysis failed)"
```

### 8. Write step-result.json

Run the title-extraction script:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/parse_title.py "<OUTPUT_FILE>"
```

The script prints `{"title": "..."}` to stdout. If it exits non-zero, report the stderr message as an error.

Use the `title` value from the script's JSON output to write the sidecar to `<OUTPUT_DIR>/step-result.json`:

```json
{
  "schema_version": 1,
  "step": "requirements",
  "ticket": "<TICKET>",
  "completed_at": "<current ISO 8601 timestamp>",
  "title": "<first heading, max 80 chars>"
}
```

### 9. Verify output

Verify that `<OUTPUT_FILE>` and `<OUTPUT_DIR>/step-result.json` exist.

## Notes

- **Two-pass architecture:** Pass 1 (discovery) is lightweight — JIRA traversal, PR listing, spec identification. Pass 2 (deep analysis) is thorough — each requirement gets a dedicated agent with a clean context window
- **Disk-based data flow:** Agents write their JSON results to per-requirement files (`req-NNN.json`) on disk instead of returning them to the orchestrator context. The merge agent reads from disk to assemble `requirements.md`. This prevents 15+ agent results (~170KB) from accumulating in the orchestrator's context window
- **Compact prompts:** Agent prompts reference `discovery.json` by path instead of embedding the full requirement skeleton. Each agent reads its own skeleton from disk. This reduces per-agent prompt size from ~2.5KB to ~0.3KB
- **Context isolation:** Each deep-analysis agent sees only one requirement's sources. This prevents context degradation when analyzing tickets with 10+ requirements
- **Parallel execution:** All pass-2 agents are dispatched in a single message for parallel execution
- **Error isolation:** A failed deep-analysis agent does not block other requirements — the merge agent uses skeleton data from `discovery.json` as a fallback for missing `req-NNN.json` files
- **Output contract:** The assembled `requirements.md` is identical in format to the previous single-pass output. Downstream consumers (code-analysis, planning, orchestrator) see no change
- **Repo discovery:** After discovery, the repo extraction script produces `discovered_repos.json` from the JIRA graph. This enables `resolve_source.py` Priority 4 to auto-discover and clone repos without user flags
- **Discovery JSON:** The `discovery.json` file is retained in the output directory. It is read by analyst agents (for requirement skeletons and persisted sources) and by the merge agent (for metadata and fallback data)
