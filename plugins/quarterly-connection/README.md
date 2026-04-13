# Quarterly Connection Plugin

Build quarterly accomplishment summaries with dense formatting and Red Hat competency mapping for performance reviews. Organizes your work by competencies relevant to your CURRENT role.

**⚠️ CRITICAL: This tool ORGANIZES and MAPS accomplishments. It does NOT evaluate what role you deserve or assess promotion readiness. It is a mapping tool, NOT an evaluation tool.**

## Commands

### `/quarterly-connection:build`

Build a comprehensive quarterly accomplishment summary by gathering data from multiple sources, then formatting into dense bullets with full URLs organized by Red Hat competency categories relevant to your current role.

**Usage:**
```bash
/quarterly-connection:build [role] [start-date] [end-date]
```

**Example:**
```bash
/quarterly-connection:build PSE 2026-01-01 2026-03-31
```

**Roles (Red Hat v10.6 framework - exactly 6):**
- `SE` - Software Engineer
- `SSE` - Senior Software Engineer
- `PSE` - Principal Software Engineer
- `SPSE` - Senior Principal Software Engineer
- `DE` - Distinguished Engineer
- `SDE` - Senior Distinguished Engineer

**Features:**
- **Sequential prompting:** Guides you through data sources ONE AT A TIME (Workday Goals → Jira → GitHub → Google Drive → Email → Slack → Other)
- **Smart link collection:** After data gathering, reads each document and prompts for public links
- **Opinionated directory structure:** `.work/quarterly-connection/inputs/` with organized subdirectories
- **Automatic queries:** GitHub PRs and Jira API (if configured)
- **Deduplication:** Combines Jira+PR for same work
- **Dense formatting:** No fluff, facts only
- **Full URLs:** Readable link text for all references
- **Competency mapping:** Red Hat v10.6 framework
- **Role organization:** Groups by competencies relevant to your CURRENT role
- **No evaluation:** NEVER makes judgements about level, promotion readiness, or deserved role
- **Copy-ready output:** HTML and markdown for performance reviews

**Format Requirements:**
- Dense bullets: action + deliverable + readable links + **explicit Red Hat v10.6 competency keywords (1 Responsibility + 1 Skill)** + impact + details
- No adjectives unless quantitative (5 bugs, 30% faster, 15+ work streams)
- No adverbs (successfully, carefully, thoroughly, effectively, clearly, etc.)
- Readable link text: `[PR#123](URL)`, `[JIRA-456](URL)`, `[Doc Name](URL)`
- One sentence per bullet
- **REQUIRED:** Use exact v10.6 framework terms (e.g., "Internal and External Collaboration and Collaboration" not just "collaboration")

**Output:**
- **Primary (HTML):** `q[N]-[year]-accomplishments-workday.html` ✨ **COPY/PASTE DIRECTLY INTO WORKDAY**
  - Clean format: **Top Accomplishments** (3 bullets) + **Other Accomplishments** (by competency)
  - No summary statistics, no extra commentary
  - Clickable links ready for Workday
- **Secondary (Markdown):** `q[N]-[year]-accomplishments-workday.md` ✨ **COPY/PASTE DIRECTLY**
  - Same clean structure as HTML
  - For systems that accept markdown
- **Detailed Analysis:** `q[N]-[year]-complete-accomplishments.md` 📊 **BACKGROUND REFERENCE**
  - Extended context on top 3 accomplishments
  - Complete breakdown by competency
  - Source analysis (Jira/GitHub/Email/Slack/Docs)
  - Summary statistics (counts, quantified impact)
  - **NOT for Workday - use for self-reflection and planning**
- Saved to `.work/quarterly-connection/outputs/` directory
- **Primary/Secondary files do NOT include: Summary statistics, analysis, level assessments, promotion evaluations**

## How Data Gathering Works

**The command guides you through data collection SEQUENTIALLY:**

1. **Command creates directory structure** - No manual setup required
2. **Prompts ONE source at a time** - Workday Goals → Jira → GitHub → Google Drive → Email → Slack → Other
3. **You save documents as .txt, .md, or .eml files** - No PDFs, CSVs, etc.
4. **Command reads each file** - Understands content automatically
5. **Prompts for public links** - "I found `doc.md` about X. Public link? (URL or 'none')"
6. **Prompts for importance hierarchy** - "Default: Jira/GitHub highest → Docs/Email medium → Slack lower. Adjust?"
7. **Prompts for TOP 3 accomplishments** - "What were your 3 most impactful accomplishments this quarter?"
8. **Stores mappings** - `source-links.txt` (URLs) and `importance-hierarchy.txt` (priorities + top 3)

**Why Workday Goals First?**
- Provides critical context for professional development
- Shows what you were supposed to accomplish this quarter
- Helps map accomplishments to goals and development items
- Demonstrates progress on agreed-upon objectives

**Example Interaction:**

```text
Tool: "First, let's gather your Workday goals and development items. This provides critical context for your professional development. Go to Workday and copy your goals and development items for this quarter, then save as inputs/additional/workday-goals.txt. Type 'done' when ready."
You: [copy goals from Workday, save to workday-goals.txt] "done"

Tool: "Let's gather Jira data. Export closed issues and save to inputs/jira-exports/ as .txt or .md. Type 'done' when ready."
You: [save q1-2026-jira.txt] "done"

Tool: "Now let's gather GitHub data. I'll automatically query your PRs. Type 'done' to continue."
You: "done"

Tool: "Let's gather Google Drive docs. In Google Drive, search for 'Owned by me' and filter by 'Last modified' from 2026-01-01 to today (not quarter end - you may have updated docs after). Save design docs as .txt or .md to inputs/google-docs/. Type 'done' when ready."
You: [search Drive: owner:me modified:2026-01-01 to 2026-04-15]
You: [save tnf-strategy.md, api-design.md, roadmap.md] "done"

Tool: "Let's gather email threads. In Gmail, search for 'in:sent -\"From Google Calendar\"' and filter by date range 2026-01-01 to 2026-03-31. Save important threads as .eml, .txt, or .md to inputs/emails/. Type 'done' when ready."
You: [search Gmail: in:sent -"From Google Calendar" after:2026-01-01 before:2026-03-31]
You: [save customer-escalation.eml, cross-team-alignment.eml] "done"

Tool: "Let's gather Slack threads. In Slack, search for 'from:@your-username after:2025-12-31 before:2026-04-01' (replace @your-username with your Slack handle, dates are one day before/after for inclusive range) to see all your messages. Then refine with optional filters like 'has:thread' or 'has::emoji:'. Look for announcements, decisions, coordination. Save as .txt or .md to inputs/slack/. Type 'done' when ready."
You: [search Slack: from:@jpoulin after:2025-12-31 before:2026-04-01]
You: [refine with: from:@jpoulin has:thread after:2025-12-31 before:2026-04-01]
You: [save release-announcement.txt, incident-coordination.md] "done"

[link collection phase begins...]

Tool: [scans directory] "I found tnf-strategy.md about two-node fencing GA strategy. Do you have a public link? (URL or 'none')"
You: "https://docs.google.com/document/d/ABC123/edit"

Tool: "I found api-design.md about PacemakerCluster CRD design. Do you have a public link?"
You: "https://docs.google.com/document/d/XYZ789/edit"

Tool: "I found roadmap.md about Q1 2026 roadmap. Do you have a public link?"
You: "none"

Tool: "I found customer-escalation.txt about etcd performance issue. Do you have a public link?"
You: "none"

[continues with slack, additional...]
```

**File Format:**
- **Supported:** `.txt`, `.md`, `.eml` (email native format)
- **Not supported:** PDF, CSV, DOCX (convert to text first)
- **Email tip:** Save as `.eml` to preserve headers and threading
- Use descriptive names: `tnf-strategy.md`, `customer-thread.eml`
- One document per file

**Examples:**

Build Q1 2026 accomplishments for Principal Software Engineer:
```bash
/quarterly-connection:build PSE 2026-01-01 2026-03-31
```

Build Q4 2025 for Senior Software Engineer:
```bash
/quarterly-connection:build SSE 2025-10-01 2025-12-31
```

## Red Hat Competency Framework

**Framework Version:** v10.6

**⚠️ CRITICAL: Competencies are used to ORGANIZE accomplishments, NOT to evaluate level or promotion readiness.**

The plugin maps accomplishments to Red Hat's Software Engineering Competencies using **1 Responsibility + 1 Skill per bullet**.

### Responsibilities (What You DO) - 8 Total
1. Technical Impact
2. Ensure Software Quality and Reliability
3. Internal and External Collaboration
4. Mentor and Develop Engineering Talent
5. Own and Deliver Business Impact
6. Apply and Advance Technical Practices
7. Leverage and Utilize AI Tools *(NEW in v10.6)*
8. SDLC

### Job Skills (Capabilities You HAVE) - 10 Total
1. Technical Acumen
2. Quality Management
3. System Design
4. Communication
5. Collaboration
6. Leadership
7. Business impact
8. Continuous Learning
9. Influence
10. Knowledge Sharing

## Output Format

**Primary/Secondary Files Structure (Workday Copy/Paste):**

```text
## Top Accomplishments
- Major achievement 1 [links] via [Responsibility + Skill] to [impact], [details]
- Major achievement 2 [links] via [Responsibility + Skill] to [impact], [details]
- Major achievement 3 [links] via [Responsibility + Skill] to [impact], [details]

## Other Accomplishments

### Own and Deliver Business Impact + Business impact
- Accomplishment [links] via [Responsibility + Skill] to [impact], [details]
- Accomplishment [links] via [Responsibility + Skill] to [impact], [details]

### Technical Impact + Technical Acumen
- Accomplishment [links] via [Responsibility + Skill] to [impact], [details]

... [continues by competency]
```

**Example Bullet (with explicit Red Hat v10.6 competency keywords):**
```text
Fixed job controller startup [PR#1500](https://github.com/openshift/cluster-etcd-operator/pull/1500) via Apply and Advance Technical Practices and Technical Acumen to prevent false degraded states, implementing exponential backoff to retry TNF setup for 10 minutes before degrading.
```

**Key Elements:**
- **Action:** Fixed
- **Deliverable:** job controller startup
- **Link:** [PR#1500](URL) - clickable in HTML
- **Explicit Competencies (v10.6):** "Apply and Advance Technical Practices and Technical Acumen" (1 Responsibility + 1 Skill)
- **Impact:** prevent false degraded states
- **Details:** implementing exponential backoff, 10 minutes retry

**Detailed Analysis File Includes (Background Reference Only):**
- Extended context on top 3 accomplishments
- Competency mappings (which competencies demonstrated)
- Distribution across competency categories for your current role
- Summary statistics (count by source, quantified impact)
- Source breakdown (Jira/GitHub/Email/Slack/Docs)
- **Does NOT include level indicators or promotion assessments**

## Data Sources

**Automatic:**
- GitHub: PRs authored and merged in date range (PRIORITIZE PRs, NOT COMMITS)
  - Extracts Jira references from PR titles/bodies
  - Validates extracted Jira issues (assignee, resolution date)
  - Adds qualified Jira issues to sources automatically
- Jira API: Closed issues (if MCP configured)

**Manual (via inputs directory):**
- Jira exports
- Google Docs links
- Email threads
- Slack threads
- Additional freeform accomplishments

## Configuration

Requires:
- GitHub authentication (via `gh` CLI or `GH_TOKEN`)
- Jira authentication (via Atlassian MCP server, optional)

**Jira MCP Setup:** See [plugins/jira/docs/MCP_SETUP.md](../jira/docs/MCP_SETUP.md)

**GitHub Token:** Place in `~/.claude/.gh-token` or configure `gh auth login`

## Tips

**For Performance Reviews:**
1. Run at end of quarter with date range
2. Review competency mappings - align with your current role's expectations
3. Use bullets grouped by competency category
4. Highlight quantified impacts (3 developers, 4.16+, 10 minutes)

**For Self-Assessments:**
1. Use competency distribution to see coverage across categories
2. Map to your current role's expectations
3. Identify gaps or areas for growth
4. Track quarter-over-quarter progression

**What This Tool Does NOT Do:**
- ❌ Evaluate whether you're ready for promotion
- ❌ Assess whether accomplishments are "good enough"
- ❌ Suggest what role you deserve
- ❌ Compare your work to other levels
- ❌ Make judgements about role fit

## Migration from v9.0 to v10.6

**What Changed:**
Red Hat updated the Engineering Competencies framework from v9.0 (March 2022) to v10.6. The plugin now uses the current framework.

**Old (v9.0):** 4 categories (Technical Contribution, Leadership, Mentorship, End-to-End Delivery) with 16 subcategories

**New (v10.6):** 8 Responsibilities + 10 Job Skills

**Your Existing Documents:**
Bullets from previous quarters using v9.0 keywords remain valid for historical context. Only the terminology changed - the pattern and content quality requirements are identical.

**Quick Translation Table:**

| v9.0 Keyword | v10.6 Replacement |
|--------------|------------------|
| "technical innovation and business impact" | "Apply and Advance Technical Practices and Technical Acumen" |
| "cross-functional collaboration" | "Internal and External Collaboration and Collaboration" |
| "functional area leadership" | "Own and Deliver Business Impact and Leadership" |
| "continuous improvement" | "Apply and Advance Technical Practices and Continuous Learning" |
| "product delivery lifecycle management" | "SDLC and Quality Management" |
| "team enablement" | "Mentor and Develop Engineering Talent and Leadership" |

See `reference/red-hat-competencies.md` for complete mapping guide.

## Reference

- **Red Hat Competencies:** `./reference/red-hat-competencies.md`
- **Example Bullets:** `./reference/example-bullets.md`
- **Command Documentation:** `./commands/build.md`
