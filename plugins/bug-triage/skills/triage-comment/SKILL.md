---
name: Bug Triage Comment
description: General-purpose analysis logic and comment template for posting AI triage comments on OCPBUGS issues before bug scrub meetings
---

# Bug Triage Comment

This skill defines the complete analysis logic, decision trees, and comment templates used to generate AI triage comments on OCPBUGS issues for any OpenShift team. Each comment is posted directly on the Jira issue so the team can review it during bug scrub meetings.

The skill is designed to be team-agnostic. Team-specific knowledge (sub-area taxonomy, routing rules, FAQs) is loaded at runtime from documentation files provided via the `--team-docs` argument.

## When to Use This Skill

- **Referenced by**: The `/bug-triage:scrub` command at `plugins/bug-triage/commands/scrub.md`. That command handles the query, grouping, and posting lifecycle; this skill defines what goes *inside* the comment.
- **Trigger**: When analyzing an individual OCPBUGS issue owned by the team specified via `--team`.
- **Not used for**: CVE cluster summaries or ART reconciliation summaries, which have their own lightweight templates at the end of this document.

## Prerequisites

- **jira CLI** (`jira`) must be installed and authenticated. The CLI is the `jira-cli` tool available via `brew install jira-cli` or from [github.com/ankitpokhrel/jira-cli](https://github.com/ankitpokhrel/jira-cli).
- **OCPBUGS project access**: The authenticated user must have permission to view, comment on, and edit labels for issues in the `OCPBUGS` Jira project.
- **Network access**: The machine must be able to reach the Red Hat Jira instance.
- **Team component map**: The `plugins/teams/team_component_map.json` file must be available in the ai-helpers repo for team lookup.

## Analysis Steps

Each step below is performed sequentially for a single issue. The outputs feed into the final comment template.

---

### Step 0: Load Team Context

Before analyzing any issue, load the team's identity and domain knowledge from two sources:

#### A. Team Component Map (required)

Read the team entry from `plugins/teams/team_component_map.json` using the `--team` argument as the key. Extract:

| Field | Source | Used In |
|---|---|---|
| Team name | Map key (e.g., "Network Ingress and DNS") | Comment header, display |
| Components | `components` array (e.g., ["Networking / DNS", "Networking / router"]) | JQL queries (Steps 1, 6), routing check (Step 3) |
| Repos | `repos` array (each has `repo_name` URL and optional `description`) | PR discovery (Steps 1, 5d) |
| Description | `description` field | Context for sub-area classification |
| Slack channels | `slack_channels` array | Informational only |
| Team size | `team_size` integer | Context |

If the team name is not found in the map, report an error and exit: "Team '{name}' not found in team_component_map.json. Run /teams:list-teams to see available teams."

#### B. Team Documentation (optional, from `--team-docs`)

If `--team-docs` is provided, read all markdown files from that directory:

| File | Purpose | If Missing |
|---|---|---|
| `sub-areas.md` | Sub-area taxonomy with descriptions and keywords | Report sub-area as the Jira component name (e.g., "Networking / router") |
| `routing-guide.md` | Non-team keyword groups for misrouting detection | Skip routing check; assume correctly assigned |
| `context/*.md` | Additional docs (FAQs, AGENTS.md, dev guides) | No extra context; proceed with core analysis |

Read each file using the Read tool. Store the contents for use in subsequent steps. If `--team-docs` is not provided, all team-doc-dependent steps degrade gracefully (see each step for fallback behavior).

---

### Step 1: Fetch Issue Details

Retrieve the full issue context using both the plain and raw (JSON) outputs:

```bash
jira issue view {KEY} --plain --comments 10
jira issue view {KEY} --raw 2>/dev/null
```

The `--plain` output is for human-readable analysis. The `--raw` JSON output provides structured access to fields not visible in plain text.

Extract and store the following fields for use in subsequent steps:

| Field | Source | Notes |
|---|---|---|
| Summary | Issue title | |
| Description | Full description body | |
| Component(s) | Jira component field | |
| Priority | Current priority value | |
| Reporter | Reporter display name and username | |
| Labels | All labels on the issue | |
| Linked Issues | All issue links (type and target key) | |
| Assignee | Current assignee (may be empty) | |
| Created Date | Issue creation timestamp | Used for bug age calculation |
| Status | Current workflow status | |
| Comments | Last 10 comments | Increased from 5 for better SFDC/PR detection |
| Affected Versions | `versions` field from raw JSON | Used for regression detection |
| Fix Versions | `fixVersions` field from raw JSON | Shows if fix is targeted |
| Sprint | `customfield_10020` from raw JSON | Active sprint detection |
| Votes | `votes.votes` from raw JSON | Community impact signal |
| Watchers | `watches.watchCount` from raw JSON | Team interest signal |
| Attachments | `attachment` array from raw JSON | Log/stack trace availability |

#### Enrichment: Extract GitHub PRs from Comments

Scan all fetched comments for GitHub PR URLs matching the team's repos (from Step 0).

Build a regex pattern from the team's repo list. For example, if the team owns `openshift/router` and `openshift/cluster-ingress-operator`, match:
```text
Pattern: https://github.com/openshift/(router|cluster-ingress-operator)/pull/(\d+)
```

For each extracted PR URL, fetch metadata:
```bash
gh pr view {url} --json number,title,state,isDraft,url,mergedAt 2>/dev/null
```

Store extracted PRs for use in the comment template.

#### Enrichment: Extract SFDC Cases from Comments

Scan all fetched comments for SFDC Integration bot patterns:
```text
Pattern: created new external case link for case: (\d+)
```

If SFDC case IDs are found, store them. This is a strong signal for Customer-Impacting importance tier (Step 4).

#### Enrichment: Detect Workarounds in Comments

Scan all fetched comments for workaround language:
```text
Keywords: workaround, work around, work-around, alternative, bypass, temporary fix, mitigation, you can use, as a workaround
```

If found, store the commenter name and a brief excerpt. This context helps the team decide urgency during scrub.

If the jira CLI returns an error (e.g., issue not found, auth failure), log the error and skip this issue entirely. Do not attempt to construct a partial comment. If the `--raw` command fails, continue with `--plain` output only -- the enrichment fields will be empty but core analysis can proceed.

---

### Step 2: Sub-area Classification

Map the bug to one of the team's sub-areas based on **what the issue is about** (the problem being described), not merely which repo or component name appears in the text.

**Important**: Repo names and component names appearing in the summary or description are context clues, not deterministic classifiers. Read the description to understand what functional area the bug/story affects. If the issue is about infrastructure, CI, documentation, or tooling that happens to touch a team repo, classify it as the relevant non-functional category rather than forcing it into a component sub-area.

#### Loading sub-areas

If `--team-docs` was provided and `sub-areas.md` exists, read the sub-area taxonomy from that file. The file contains sections with sub-area names as headings and prose descriptions with keywords. Use the descriptions to semantically classify the issue -- the LLM should understand what each sub-area covers and match based on meaning, not just keyword hits.

If `sub-areas.md` is not available, skip detailed sub-area classification and report the sub-area as the Jira component name (e.g., "Networking / router").

#### Non-functional Categories

These categories are universal across all teams. If the issue is not about a functional problem in any team-specific sub-area, classify into one of:

- **Documentation** -- AGENTS.md, README, docs, enhancement proposals, conventions
- **CI / Infrastructure** -- test infrastructure, prow jobs, CI config, Dockerfiles, build scripts
- **Tooling** -- developer tooling, scripts, automation, MCP server, plugins
- **Dependency Management** -- go.mod bumps, image updates, ART reconciliation

#### Decision

- If the issue describes a functional bug or feature in a specific sub-area, assign that sub-area.
- If one sub-area has clear keyword/semantic matches, assign it.
- If multiple sub-areas match with similar strength, assign the one with the most hits and note the secondary match.
- If the issue is about non-functional work (docs, CI, tooling, deps), use the non-functional category instead.
- If no keywords match any sub-area or non-functional category, classify as **"Uncategorized -- needs manual review"**.

---

### Step 3: Routing Check (Is This the Right Team's Bug?)

Scan the summary and description for keywords that indicate the bug may have been misrouted to this team when it actually belongs to a different team.

#### Loading routing rules

If `--team-docs` was provided and `routing-guide.md` exists, read the non-team keyword groups from that file. Each group should have: a name, keywords, and a suggested reroute target.

If `routing-guide.md` is not available, skip the routing check and assume the bug is correctly assigned. Report: "(/) Assumed correctly assigned (no routing guide provided)".

#### Team keywords (for comparison)

Use the combined keyword set from Step 2 (all sub-area keywords from `sub-areas.md`) as the team keyword set. If no sub-areas are loaded, use the team's component names as a minimal keyword set.

#### Decision Logic

1. Count non-team keyword hits in the summary + description (from routing guide).
2. Count team keyword hits in the summary + description (from sub-areas).
3. Apply the following rules:

| Non-Team Hits | Team Hits | Verdict |
|---|---|---|
| >= 1 | 0 | **Likely misrouted** |
| >= 1 | >= 1 | **Needs review -- may span multiple areas** |
| 0 | >= 1 | **Correctly assigned** |
| 0 | 0 | **Correctly assigned** (generic description, keep with filed component) |

When flagging as "Likely misrouted", suggest the correct component based on the routing guide's suggested targets.

---

### Step 4: Importance Assessment

Check multiple signals and assign exactly one importance tier. Evaluate tiers in the order listed below; the first match wins.

#### Reporter Analysis

To distinguish internal bugs from externally reported ones, check whether the reporter is a member of the team. You can infer this from:
- The team size from `team_component_map.json`
- If `--team-docs` provides a team roster or member list
- The reporter's association with the team's Jira components

If the reporter cannot be identified as a team member, treat them as external for importance assessment purposes.

#### Tier: Customer-Impacting

Matches when ANY of the following are true:
- **SFDC case detected** (from Step 1 enrichment): If an SFDC case ID was extracted from comments, this is definitively customer-impacting. Include the case ID in the importance explanation.
- The reporter appears to be external to the team AND at least one of:
  - Reporter appears to be CEE/support (display name or username contains "CEE", or user is in a known support org)
  - Description contains any of: `customer`, `case`, `production`, `outage`, `escalation`, `P1`, `sev1`, `sev2`, `incident`, `critical environment`, `revenue impact`
  - Labels include `needs_manual_sfdc`, `ocp-sustaining`, or `ServiceDeliveryBlocker`
  - Linked to a Salesforce case (link type or label referencing SFDC)
- **High community signal**: `votes` count >= 5 (many users affected)

#### Tier: Regression

Matches when any of the following are true:
- Labels include `component-regression` or `backport-requested`
- Description or summary contains any of: `regression`, `used to work`, `broke after upgrade`, `worked in 4.`, `no longer works after`, `bisected to`, `started failing in`

#### Tier: Security/CVE

Matches when any of the following are true:
- Labels include `SecurityTracking`, `Security`, or any label matching pattern `CVE-*`
- Summary contains `CVE-` followed by a year and sequence number

#### Tier: CI/Test

Matches when any of the following are true:
- Labels include `ci`, `e2e`, `ci-fix`, `test`, `CI`, `ci-fail`, `ci-only`, `test-flake`
- Summary or description primarily discusses test failures, CI flakes, or test infrastructure
- Summary contains: `e2e`, `CI failure`, `flake`, `test failure`, `periodic`, `periodic-ci-`, `rehearsal`, `prow job`
- Comments contain: "Won't affect the product", "only affects CI", "CI-only", "test infrastructure"

When classified as CI/Test, note whether this is a **product-affecting test failure** vs. **CI infrastructure noise**:
- If description mentions a real product symptom that surfaces in a test, classify as the functional sub-area with a CI/Test note
- If purely CI infrastructure (prow config, test image, rehearsal failure), keep as CI/Test

#### Tier: Internal

Default tier when:
- Reporter is a known team member
- No customer, regression, security, or CI signals are present

#### Priority Suggestion

If the current priority is `Undefined` or blank, suggest a priority based on the importance tier:

| Importance Tier | Suggested Priority |
|---|---|
| Customer-Impacting | `Major` or `Critical` (use `Critical` if description mentions outage, P1, or sev1) |
| Regression | `Major` |
| Security/CVE | Per CVE severity: Critical/High -> `Critical`, Medium -> `Major`, Low -> `Minor` |
| CI/Test | `Minor` |
| Internal | `Normal` |

If the priority is already set, do not suggest a change -- simply report the current value.

---

### Step 5: Bug vs RFE Classification

Analyze the description and summary language to determine whether this issue is a genuine bug report or a feature request (RFE).

#### Bug Indicators
Keywords and phrases that signal a bug: `fails`, `broken`, `error`, `crash`, `regression`, `used to work`, `no longer works`, `unexpected behavior`, `panic`, `nil pointer`, `segfault`, `data loss`, `does not work`, `should not`, `wrong`, `incorrect`, `missing`, `timeout unexpectedly`, `connection reset`, `SIGSEGV`, `stack trace`, `degraded`, `CrashLoopBackOff`

#### RFE Indicators
Keywords and phrases that signal a feature request: `would be nice`, `feature request`, `please add`, `support for`, `enhance`, `new capability`, `proposal`, `wish`, `ability to`, `it would be great`, `consider adding`, `we need`, `use case`, `can we`, `could you add`, `improvement`, `nice to have`, `should support`

#### Decision Logic

1. Count bug indicator hits in the summary + description.
2. Count RFE indicator hits in the summary + description.
3. Apply:

| Bug Hits | RFE Hits | Verdict |
|---|---|---|
| >= 1 | 0 | **Bug** |
| 0 | >= 1 | **Possible RFE -- consider converting** |
| >= 1 | >= 1 | **Unclear -- needs discussion** (include both signal counts in the comment) |
| 0 | 0 | **Bug** (default -- absence of RFE language implies a bug report) |

When flagging as "Possible RFE", add a note: "This issue reads more like a feature request than a bug report. Consider converting to an RFE."

---

### Step 5a: Bug Age Classification

Calculate the age of the bug from its Created Date to today and assign an age category:

| Age | Category | Display |
|---|---|---|
| < 7 days | Very Fresh | `(/) Very Fresh ({N}d)` |
| 7-30 days | Fresh | `(/) Fresh ({N}d)` |
| 30-60 days | Getting Stale | `(i) Getting Stale ({N}d)` |
| 60-90 days | Stale | `(!) Stale ({N}d)` |
| > 90 days | Old | `(!) Old ({N}d) -- has been sitting untriaged` |

Bugs older than 60 days that are still in `New` status should be flagged for attention -- they may need to be closed, reassigned, or escalated.

---

### Step 5b: Description Completeness Check

Check whether the bug has sufficient information for the team to triage effectively. Look for:

| Section | How to detect | Status if missing |
|---|---|---|
| Steps to Reproduce | Text block under "Steps to Reproduce" or "How reproducible" or numbered steps (1. 2. 3.) | `(!) Missing reproduction steps` |
| Expected Results | Text under "Expected results" or "Expected behavior" | `(i) Missing expected results` |
| Actual Results | Text under "Actual results" or "Actual behavior" | `(i) Missing actual results` |
| Version Info | Text under "Version" or presence of OCP version like "4.XX" | `(i) No version specified` |
| Description present | Any description at all | `(x) No description provided` |

#### Output

- If all key fields are present: `*Completeness:* (/) Complete`
- If some are missing: `*Completeness:* (i) Partial -- missing: {list}`
- If description is empty: `*Completeness:* (x) Empty -- no description provided. Needs more info from reporter.`

This directly informs the Suggested Action -- bugs with empty descriptions should get "Needs more info from reporter".

---

### Step 5c: Version & Regression Analysis

Use the `versions` (Affected Versions) and `fixVersions` (Fix Versions) fields from the raw JSON output to detect regressions and version scope:

1. **Multi-version detection**: If `versions` contains 3+ versions, this is likely a regression affecting multiple releases. Auto-upgrade importance to `Regression` tier if not already Customer-Impacting.

2. **Fix already targeted**: If `fixVersions` is populated, note which versions have the fix targeted. This is useful context: "Fix targeted for 4.22" tells the team the bug is being tracked.

3. **Backport signals**: If `versions` includes older releases (e.g., 4.14, 4.15) alongside current ones, flag as needing backport attention.

#### Output

Include version context in the comment when relevant:
- `*Versions:* Affects 4.18, 4.19, 4.20. Fix targeted for 4.21.`
- Or omit if no version data is available.

---

### Step 5d: GitHub PR Discovery

If GitHub PRs were extracted from comments in Step 1 (Enrichment), store their metadata for use in the Related Context section (Step 7).

Additionally, if no PRs were found in comments, perform a fallback search across the team's repos (from Step 0):
```bash
gh pr list --repo {repo-url} --search "{ISSUE-KEY} in:title,body" --state all --limit 5 --json number,title,state,url 2>/dev/null
```

Search across all repos listed in the team's `repos` array from `team_component_map.json`. Extract the repo org/name from the `repo_name` URL field.

For each discovered PR, note: repo, PR number, title, state (MERGED/OPEN/DRAFT/CLOSED), and URL.

**Output**: Do NOT create a standalone "Fix status" section. Instead, include relevant PRs inline in the *Related context* section (Step 7) where they add useful context.

---

### Step 6: Duplicate Detection

Attempt to find existing open issues that may be duplicates of the current bug.

#### Procedure

1. **Check existing links**: Look at the issue's linked issues for `DUPLICATES` or `IS DUPLICATED BY` relationships. If such links already exist, report them and skip the search.

2. **Extract search terms**: Take 2-3 key terms from the summary after removing noise words (articles, prepositions, "OpenShift", "OCP", version numbers). Focus on the technical noun phrases.

3. **Search for candidates**: Run a JQL query against open OCPBUGS with the team's components (from Step 0):

   ```bash
   jira issue list --jql "project = OCPBUGS AND component in ({quoted-components}) AND status not in (Closed) AND key != {KEY} AND summary ~ \"{terms}\"" --plain --no-truncate
   ```

   Build the `{quoted-components}` from the team's components array, e.g., `"Networking / router", "Networking / DNS"`.

4. **Evaluate candidates**:
   - If the search returns results, compare the top 3 candidates against the current issue.
   - For each candidate, note: issue key, summary, and a brief reason why it might be a duplicate.
   - Only include candidates that have genuine similarity, not just shared generic terms.

5. **Report findings**:
   - If candidates found: list the top 3 with key, summary, and similarity reason.
   - If no candidates found: state "No obvious duplicates found".
   - If the duplicate search query times out or fails: state "Duplicate check skipped (search timed out)".

---

### Step 7: Related Context

Identify issues that are **related but not duplicates** -- sibling tasks, parallel efforts, or useful background context that would help the team during scrub.

#### What to look for

1. **Clone relationships**: If the issue has a `CLONES` or `IS CLONED BY` link, the linked issue is the same task applied to a different scope. Note the relationship explicitly.

2. **Blocks / Blocked-by**: If the issue blocks or is blocked by other issues, note them with context on why the dependency exists.

3. **Related issues in the same epic**: If the issue has a parent epic, briefly note sibling stories that provide context.

4. **GitHub PRs** (from Step 5d): Include discovered PRs inline with the related issue they belong to. For example, if the clone source has an open PR, mention it alongside the clone link.

5. **Sprint context**: If the issue is in an active sprint (from Step 1 enrichment), note the sprint name and goal as a separate bullet.

6. **Prior art**: If the duplicate search (Step 6) turned up issues that aren't duplicates but are thematically related, note them here instead of in the duplicate section.

#### Output format

- If related context is found, list each item with its key (hyperlinked), a one-line description, and the nature of the relationship.
- Include PR links inline with the related issue they belong to, not as a separate section.
- If no related context is found, omit this section from the comment entirely (do not print "No related context").

---

### Step 8: Confidence Assessment

Before posting the comment, evaluate the overall confidence of the triage analysis. This serves as a quality gate to prevent incorrect or misleading triage comments.

#### Per-field confidence scoring

Assign a confidence level to each analysis field:

| Field | High Confidence | Medium Confidence | Low Confidence |
|---|---|---|---|
| Sub-area | Clear keyword matches in description; obvious functional area | Repo name matches but description is vague | No keyword matches; ambiguous description |
| Routing | Strong team or non-team keyword signals | Mixed signals from both team and non-team keywords | No keywords found; generic description |
| Importance | Clear reporter + label + description signals align | Some signals present but not definitive | Reporter unknown, no labels, generic description |
| Classification | Clear bug or RFE language in description | Mixed language or short description | No description provided |
| Duplicate check | Exact or near-exact match found | Partial keyword match with plausible similarity | Search returned no results or timed out |

#### Overall confidence

- **High**: All fields are High or Medium confidence. Proceed with posting.
- **Medium**: At least one field is Low confidence, but the others are High/Medium. Post the comment but include a confidence note in the comment footer.
- **Low**: Multiple fields are Low confidence, or the description is missing/empty. Handle per mode:
  - In `--dry-run` mode: display the analysis with low-confidence fields highlighted and ask for confirmation before proceeding.
  - In live mode: post the comment but prepend a warning: `(?) *Confidence: Low* -- some fields could not be reliably assessed. Please verify during bug scrub.`

#### How confidence appears in the comment

Add a confidence line to the comment, after the suggested action:

- High: `*Confidence:* (/) High`
- Medium: `*Confidence:* (i) Medium -- {list fields with low confidence}`
- Low: `*Confidence:* (?) Low -- {list fields with low confidence}. Manual verification recommended.`

---

## Comment Template

The triage comment uses mixed Jira wiki markup (for headings and horizontal rules) and CommonMark markdown (for links). The `jira-cli` processes the content through `ToJiraMD()` which converts CommonMark to Jira wiki markup before posting via REST API v2.

The `{team-name}` and `{command-name}` placeholders below should be replaced with the actual team name and the invoking command (e.g., `/nid:bug-scrub` for a team wrapper, or `/bug-triage:scrub` for direct usage).

```text
h2. {team-name} Bug Scrub -- AI Pre-Triage

*Sub-area:* {sub-area classification}
*Routing:* {routing check result with (/) or (!)}
*Classification:* {Bug | Possible RFE | Unclear}
*Importance:* {importance tier with emoji -- one-line explanation}
*Priority suggestion:* {suggested priority} (currently: {current priority})
*Age:* {age category with emoji and day count}
*Completeness:* {completeness check result}

*Duplicate check:*
{duplicate findings with hyperlinked issue keys, or "No obvious duplicates found"}

*Workaround:* {excerpt from comments if workaround detected, or omit section if none}

*Versions:* {affected versions and fix versions, or omit if no version data}

*Related context:*
{related issues with hyperlinked keys, PR links, and relationship description, or omit if none}

*Summary:* {2-3 sentence AI summary of the bug: what is broken, what component is affected, what is the user impact}

*Suggested action:* {one-line recommendation}
*Confidence:* {confidence level with explanation}

----
_Generated by_ {{{command-name}}} _via_ [ai-helpers bug-triage](https://github.com/openshift-eng/ai-helpers)
```

**Linking format**: `jira-cli` processes template content through `ToJiraMD()`, which converts CommonMark markdown to Jira wiki markup before posting via the REST API v2. This means:

- **Use CommonMark markdown links** for ALL clickable references: `[OCPBUGS-12345](https://redhat.atlassian.net/browse/OCPBUGS-12345)`. jira-cli converts this to proper Jira wiki `[OCPBUGS-12345|url]` internally, which renders as a clickable link.
- **Jira issue keys**: Always use `[KEY](https://redhat.atlassian.net/browse/KEY)` format. The Jira base URL is `https://redhat.atlassian.net/browse/`. Bare issue keys (e.g., `OCPBUGS-12345`) do NOT auto-link when posted via API -- they render as plain text with escaped dashes.
- **GitHub URLs**: Use `[PR #1341](https://github.com/openshift/repo/pull/1341)` for a clean display, or write the full URL as plain text (Jira auto-links raw URLs).
- **Do NOT use** `[text|url]` Jira wiki markup directly in the template -- `ToJiraMD()` escapes the brackets, breaking the link.
- **Do NOT rely on bare issue keys auto-linking** -- this only works in the Jira web editor, not via API.

**Conditional sections**: The following sections should be OMITTED entirely (not printed as empty) if they have no data:
- Workaround (no workaround language detected)
- Versions (no version data in Jira)
- Related context (no related issues found)

**Note on GitHub PRs**: Do NOT include a standalone "Fix status" section. Instead, include relevant PR links inline within the *Related context* section where they provide useful context.

**Comment posting method**: ALWAYS use a template file to post comments to avoid shell escaping issues that break URLs:
```bash
# Write comment to temp file
cat > /tmp/bug-triage-{KEY}.txt << 'EOF'
{comment content}
EOF

# Post using --template flag
jira issue comment add {KEY} --template /tmp/bug-triage-{KEY}.txt --no-input

# Clean up
rm /tmp/bug-triage-{KEY}.txt
```

Do NOT use inline `$'...'` strings or heredocs passed directly to the comment body argument -- they break URLs at period characters.

### Template Field Reference

| Field | Example Value |
|---|---|
| Sub-area | Router / HAProxy |
| Sub-area (non-functional) | Documentation (cluster-dns-operator) |
| Sub-area (no team docs) | Networking / router |
| Routing | (/) Correctly assigned |
| Routing (misrouted) | (!) Likely misrouted -- consider Networking / ovn-kubernetes |
| Routing (no guide) | (/) Assumed correctly assigned (no routing guide provided) |
| Classification | Bug |
| Importance | Customer-Impacting (!) -- SFDC case 04395474, reporter is CEE |
| Priority suggestion | Major (currently: Undefined) |
| Age | (!) Stale (74d) |
| Completeness | (i) Partial -- missing: Steps to Reproduce, Expected Results |
| Duplicate check | Possible duplicate of [OCPBUGS-12345](https://redhat.atlassian.net/browse/OCPBUGS-12345) (same symptom: route not admitted after upgrade) |
| Workaround | Jane D. (Apr 13): "As a workaround, manually set the trustBundleName field..." |
| Versions | Affects 4.20, 4.21. Fix targeted for 4.22. |
| Related context | [OCPBUGS-11111](https://redhat.atlassian.net/browse/OCPBUGS-11111) -- same issue in 4.15 (clone source, Fixed). [PR #1341](https://github.com/openshift/cluster-ingress-operator/pull/1341) merged. |
| Summary | HAProxy router pods enter CrashLoopBackOff after cluster upgrade to 4.16. The router template fails to render when custom annotations exceed the buffer size. |
| Suggested action | Assign to engineer -- likely router template bug |
| Confidence | (/) High |
| Confidence (low) | (?) Low -- sub-area and classification could not be reliably assessed. Manual verification recommended. |

### Suggested Action Options

Use one of these standardized action phrases:

- `Assign to engineer` -- standard bug that needs investigation
- `Assign to engineer -- {sub-area context}` -- standard bug with sub-area hint
- `Reroute to {component}` -- misrouted bug, specify target component
- `Close as duplicate of {ISSUE-KEY}` -- clear duplicate found
- `Convert to RFE` -- issue is a feature request, not a bug
- `Needs more info from reporter` -- insufficient detail to triage
- `Discuss in bug scrub` -- ambiguous situation requiring team discussion
- `Verify fix is backported` -- for regression/backport scenarios
- `Workaround exists -- prioritize accordingly` -- workaround detected in comments
- `Fix in review -- monitor {PR link}` -- PR is open, awaiting merge

### Jira Wiki Markup Emoji Reference

Use these Jira wiki markup notations for visual signals:

- `(/)` -- green checkmark (correct routing, resolved items)
- `(!)` -- warning/attention (misrouted, customer-impacting, regression)
- `(x)` -- red X (blocked, critical)
- `(i)` -- info (neutral observation)
- `(?)` -- question mark (unclear, needs discussion)

---

## Special Templates

### CVE Cluster Template

Used when CVE/Security tracker issues are grouped together (see Phase 2 of the scrub command). Post this comment on the newest tracker in each CVE group.

```text
h2. {team-name} Bug Scrub -- AI Pre-Triage (CVE Cluster)

*CVE:* {CVE-ID} -- {brief description extracted from summary}
*Component:* {affected image/component}
*Tracker count:* {N} version-specific trackers
*Versions:* {comma-separated version list}
*Unresolved:* {count} trackers still open ({version list of open trackers})
*Suggested action:* Verify fix is backported to remaining versions.

----
_Generated by_ {{{command-name}}} _via_ [ai-helpers bug-triage](https://github.com/openshift-eng/ai-helpers)
```

### ART Reconciliation Template

Used when ART Bot reconciliation issues are grouped together (see Phase 2 of the scrub command). Post this comment on the newest ART issue in the group.

```text
h2. {team-name} Bug Scrub -- AI Pre-Triage (ART Reconciliation)

*Count:* {N} image update requests this period
*Packages:* {package name (count), e.g., haproxy (3), golang (2), coredns (1)}
*Issues:* {OCPBUGS-XXXXX, OCPBUGS-YYYYY, OCPBUGS-ZZZZZ}
*Suggested action:* Standard ART reconciliation flow -- review and approve.

----
_Generated by_ {{{command-name}}} _via_ [ai-helpers bug-triage](https://github.com/openshift-eng/ai-helpers)
```

---

## Idempotency

This skill MUST be idempotent. Running the triage analysis on the same issue multiple times must not produce duplicate comments.

### Gate: Team-specific Label

Use a label formatted as `{team-short-name}-ai-triaged` (e.g., `nid-ai-triaged`, `apiserver-ai-triaged`).

**Label derivation priority:**
1. **Explicit**: If `sub-areas.md` contains a `Label:` line (e.g., `Label: nid-ai-triaged`), use that value exactly.
2. **Derived**: Otherwise, derive from the team name: lowercase, drop filler words (`and`, `the`, `of`, `for`), join remaining words with hyphens, append `-ai-triaged`. For example, "Network Ingress and DNS" becomes `network-ingress-dns-ai-triaged`; "API Server" becomes `api-server-ai-triaged`.

Teams are strongly encouraged to specify an explicit `Label:` line in `sub-areas.md` to avoid collisions between teams whose names share a first word. The same derivation logic is used by the `scrub.md` command (Phase 0, step 3).

1. **Before commenting**: ALWAYS check if the label already exists on the issue. If it does, skip the issue entirely.

2. **After posting the comment**: Immediately add the label to the issue:

   ```bash
   jira issue edit {KEY} -l "{label}" --no-input
   ```

3. **For CVE/ART groups**: Add the label to ALL issues in the group, not just the one that received the comment.

4. **On failure**: If the comment posting fails, do NOT add the label. This ensures the issue will be retried on the next run.

### Re-triage

If re-triage is needed (e.g., the issue description changed significantly), the user must manually remove the label from the issue before running the scrub command again.

---

## Error Handling

| Failure Mode | Behavior |
|---|---|
| Team not found in component map | Report error with team name and exit. Suggest running `/teams:list-teams`. |
| `--team-docs` path doesn't exist | Report warning. Proceed without team docs (graceful degradation). |
| `jira issue view` fails (auth, network, 404) | Log error message with issue key. Skip the issue. Continue to next issue. |
| Comment posting fails | Log error message with issue key. Do NOT add the triaged label. Continue to next issue. |
| Label editing fails | Log warning. The comment is already posted, so the issue may be double-commented on next run. Log the key for manual label addition. |
| Duplicate search query times out | Skip the duplicate section in the comment. Include "Duplicate check skipped (search timed out)" in the comment body. |
| Issue has no description | Proceed with analysis using only the summary. Note in the comment: "No description provided -- analysis based on summary only." |
| JQL query returns no results (Phase 1) | Report "No untriaged bugs found for the given period" and exit cleanly. |

All errors should be logged to stderr so they appear in terminal output but do not interfere with the structured comment output.
