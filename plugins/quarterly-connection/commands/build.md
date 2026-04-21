---
description: Build quarterly accomplishment summaries with dense formatting and competency mapping
argument-hint: "[role] [start-date] [end-date]"
---

## Name
quarterly-connection:build

## Synopsis
```bash
/quarterly-connection:build [role] [start-date] [end-date]
```

## Description
The `quarterly-connection:build` command gathers accomplishments from multiple sources for a specified time period, then transforms them into dense, direct bullet points with explicit Red Hat competency keywords mapped to your CURRENT role's expectations.

**CRITICAL: This tool ORGANIZES and MAPS accomplishments to competencies. It does NOT make judgements about what role you deserve or should be promoted to. It maps your work against your CURRENT role's competency expectations only.**

Outputs Workday-ready HTML (primary) with clickable links, plus markdown and detailed analysis versions organized by the competencies relevant to your current role.

Use for performance reviews, quarterly summaries, and competency self-assessment against your current role.

## Implementation

The command processes accomplishments using this pattern:
1. **GATHER** - Prompt user to collect data, then read from standardized inputs directory
2. **ANALYZE** - Identify action, deliverable, competency, impact
3. **FORMAT** - Transform to dense bullets with full URLs
4. **MAP** - Organize by competencies relevant to user's CURRENT role (NOT evaluate level)

**NEVER DO:**
- ❌ Make judgements about what role the user deserves
- ❌ Suggest the user "demonstrates X-level work"
- ❌ Evaluate whether accomplishments are "good enough" for promotion
- ❌ Compare accomplishments across roles or levels

**ALWAYS DO:**
- ✅ Map accomplishments to competencies demonstrated
- ✅ Organize by the user's CURRENT role's competency expectations
- ✅ Provide neutral, factual competency categorization
- ✅ Focus on what was done and which competencies were applied

**Directory Structure (Opinionated):**
```text
.work/quarterly-connection/
├── inputs/                          # User places raw data here
│   ├── README.md                   # Instructions (auto-created if not exists)
│   ├── source-links.txt            # URL mappings for documents (auto-generated)
│   ├── importance-hierarchy.txt    # User's importance guidance (auto-generated)
│   ├── jira-exports/               # Jira exports as .txt or .md files
│   ├── google-docs/                # Google docs saved as .txt or .md files
│   ├── emails/                     # Email threads as .txt or .md files
│   ├── slack/                      # Slack threads as .txt or .md files
│   └── additional/                 # Other accomplishments as .txt or .md files
└── outputs/                         # Generated files
    ├── README.md                   # Explanation (auto-created if not exists)
    ├── q[N]-[year]-accomplishments-workday.html
    ├── q[N]-[year]-accomplishments-workday.md
    └── q[N]-[year]-complete-accomplishments.md
```

**Note:**
- Directory structure and helper files are automatically created on first run
- Users save documents as .txt, .md, or .eml files in appropriate directories
- After data collection, tool prompts for public links to each document
- Links are stored in `source-links.txt` for use in formatted output bullets

**Process:**
1. **Validate role parameter** - Must be one of: SE, SSE, PSE, SPSE, DE, SDE
2. **Prompt for manual data gathering:**
   - Jira: Export closed issues from date range to `inputs/jira-exports/`
   - Google Drive: Save doc links or exports to `inputs/google-docs/`
   - Email: Save relevant threads to `inputs/emails/`
   - Slack: Export important threads to `inputs/slack/`
   - Additional: Write freeform items to `inputs/additional/`
3. **Automatically query:**
   - GitHub for merged PRs in date range
   - Jira API for closed issues (if MCP configured)
4. **Read from inputs directory:**
   - Parse all files in `inputs/` subdirectories
   - Combine with automatic queries
5. **Deduplicate** - Merge Jira+PR for same work
6. **Format** - Transform to dense bullets with explicit competency keywords
7. **Map to CURRENT role** - Organize bullets by competencies expected for the provided role
8. **Refine and validate:**
   - Collect PR numbers from merge commits (not just hashes)
   - Thematic review - ensure all major work themes represented
   - Association validation - verify PR/Jira links match accomplishments
   - Unlisted work review - surface NO-JIRA commits and tooling work
   - Document link review - confirm which docs should be publicly linked
9. **Output** - Save to `outputs/` directory

## Dense Bullet Format Structure

**Pattern:**
```text
[Action verb] [deliverable] [readable links] via [Red Hat competency keywords] to [impact], [how/details].
```

**Writing Rules:**
- Use past tense action verbs (Fixed, Created, Updated, Implemented)
- No adjectives unless quantitative (e.g., "5 bugs", "30% faster", "3 teams")
- No adverbs (e.g., avoid "significantly", "greatly", "successfully", "carefully", "thoroughly")
- One sentence per bullet
- Focus on facts, not emphasis
- **REQUIRED: Include readable link text for all references**
- **REQUIRED: Use explicit Red Hat competency keywords (not generic descriptions)**

**Components:**

1. **Action** - What you did
   - Good: Fixed, Created, Updated, Implemented, Debugged, Refactored, Led, Designed
   - Avoid: "Successfully fixed", "Carefully created", "Effectively implemented"

2. **Deliverable** - Concrete output
   - Examples: PR, test, API, library, fix, document, proposal, tracker, demo

3. **Reference** - Readable link text (Workday/HTML format)
   - **GitHub PRs:** `[PR#NUMBER](URL)`
   - **Jira Issues:** `[ISSUE-KEY](URL)`
   - **Google Docs:** `[Descriptive Name](URL)`
   - Multiple references comma-separated in sentence
   - Examples:
     - `[PR#123](https://github.com/org/repo-name/pull/123)`
     - `[PR#456](https://github.com/org/another-repo/pull/456), [PROJ-789](https://jira.company.com/browse/PROJ-789)`
     - `[Strategy Doc](https://docs.example.com/document/DOCUMENT_ID/edit)`

4. **Competency** - **EXPLICIT Red Hat competency keywords (v10.6)**
   - **NOT:** "via collaboration" (too generic)
   - **YES:** "via Internal and External Collaboration and Collaboration" (1 Responsibility + 1 Skill)
   - Use 1 RESPONSIBILITY + 1 SKILL from v10.6 framework:
     - Responsibilities: Technical Impact, Ensure Software Quality and Reliability, Internal and External Collaboration, Mentor and Develop Engineering Talent, Own and Deliver Business Impact, Apply and Advance Technical Practices, Leverage and Utilize AI Tools, SDLC
     - Skills: Technical Acumen, Quality Management, System Design, Communication, Collaboration, Leadership, Business impact, Continuous Learning, Influence, Knowledge Sharing

5. **Impact** - Business value (what capability resulted)
   - Focus on: time saved, bugs prevented, capability enabled, team unblocked, alignment achieved
   - Quantify when possible (3 developers, 4.16+, 10 minutes, 30% faster, 15+ work streams)

6. **How/Details** - Brief technical or process details
   - Explains the approach taken
   - Provides context for the competency demonstrated
   - Examples: "analyzing timeline risks", "implementing exponential backoff", "testing LINSTOR/DRBD failover"

## Process Flow

1. **Role Validation**
   - Parse role argument (or prompt if missing)
   - Validate against v10.6 framework roles (exactly 6): SE, SSE, PSE, SPSE, DE, SDE
   - Load competency expectations for that role
   - **CRITICAL: Role is used ONLY for organizing accomplishments by relevant competencies, NOT for evaluation**

2. **Date Range Parsing**
   - Parse start-date and end-date arguments
   - Validate format (YYYY-MM-DD)
   - Calculate quarter (Q1-Q4)

3. **Directory Structure Setup**
   - Create `.work/quarterly-connection/inputs/` and `outputs/` directory structure if not exists
   - Create subdirectories: `jira-exports/`, `google-docs/`, `emails/`, `slack/`, `additional/`
   - Create helper files if they don't already exist (preserves user modifications):
     - `inputs/README.md` - Instructions for gathering data
     - `outputs/README.md` - Explanation of generated files

4. **Sequential Data Gathering (ONE SOURCE AT A TIME)**

   **Step 4a: Workday Goals and Development Items**
   - Prompt: "First, let's gather your Workday goals and development items. This provides critical context for your professional development. Go to Workday and copy your goals and development items for this quarter, then save as a .txt or .md file to `inputs/additional/workday-goals.txt`. Type 'done' when ready."
   - Wait for user confirmation
   - **Why first:** Goals set context for what you were supposed to accomplish this quarter

   **Step 4b: Jira Data**
   - Prompt: "Let's gather Jira data. Export closed issues assigned to you from [start-date] to [end-date] (CSV or JSON) and save .txt or .md files to `inputs/jira-exports/`. Type 'done' when ready."
   - Wait for user confirmation
   - Attempt automatic Jira API query if MCP configured

   **Step 4c: GitHub Data and Jira Cross-Reference**
   - Prompt: "Now let's gather GitHub data. I'll automatically query your merged PRs and extract any Jira references. Type 'done' to continue."
   - **GitHub query (PRIORITIZE PRs, NOT COMMITS):**
     - Search PRs merged in date range: `author:[username] merged:[start-date]..[end-date]`
     - Fetch: PR number, title, body, repository, merge date, author
     - **DO NOT query individual commits** - PRs are the unit of accomplishment
   - **Jira extraction from GitHub PRs:**
     - Parse PR titles and bodies for Jira issue keys (e.g., PROJ-123, TEAM-456)
     - Extract all Jira references found in your PRs
     - For each extracted Jira issue:
       - Query Jira API to get issue details (assignee, resolution date, status, summary)
       - **Validate qualification:** Check if issue falls within qualified window:
         - Assignee = current user (or you were a contributor)
         - Resolution date within quarter OR significant work done during quarter
         - Status = Done/Closed (or moved to review/QE during quarter)
       - If qualified, add to Jira sources (even if not in manual export)
     - Store in `inputs/jira-exports/github-extracted-jiras.txt`:
       ```
       Extracted from GitHub PRs:
       PROJ-123 (from PR#100) - Qualified: Resolved 2026-03-15
       TEAM-456 (from PR#200) - Qualified: Assignee match, resolved 2026-02-10
       PROJ-789 (from PR#300) - Not qualified: Resolved 2025-12-01 (outside quarter)
       ```
   - **Benefits:**
     - Captures Jira issues you may have forgotten to export manually
     - Ensures PR→Jira linkage is complete
     - Validates Jira issues are actually your work and in the time window
   - Wait for user confirmation

   **Step 4d: Google Drive Data**
   - Prompt: "Let's gather Google Drive docs. In Google Drive, search for 'Owned by me' and filter by 'Last modified' from [start-date] to today (not [end-date] - you may have updated docs after the quarter ended). Save design docs, proposals, strategy docs, and meeting notes as .txt or .md files to `inputs/google-docs/`. Type 'done' when ready."
   - Wait for user confirmation
   - **Search tips:**
     - Use Drive search: `owner:me modified:[start-date] to [current-date]`
     - Ensures you don't miss docs updated after the quarter ended
     - Look for docs you created or significantly contributed to

   **Step 4e: Email Data**
   - Prompt: "Let's gather email threads. In Gmail, search for 'in:sent -\"From Google Calendar\"' and filter by date range [start-date] to [end-date]. This shows emails you sent (excluding calendar invites). Save important threads (cross-team coordination, customer engagement, technical decisions) as .eml, .txt, or .md files to `inputs/emails/`. Type 'done' when ready."
   - Wait for user confirmation
   - **Search tips:**
     - Gmail search: `in:sent -"From Google Calendar" after:[start-date] before:[end-date]`
     - Focuses on emails you actively sent
     - Excludes calendar noise
     - Look for cross-team coordination, escalations, technical discussions
   - **Export formats:**
     - `.eml` - Native email format (preserves headers, threading)
     - `.txt` - Plain text copy/paste
     - `.md` - Markdown formatted

   **Step 4f: Slack Data**
   - Prompt: "Let's gather Slack threads. In Slack, search for `from:@your-username after:[day-before-start] before:[day-after-end]` (replace @your-username with your Slack handle, e.g., from:@username). For quarter [start-date] to [end-date], use after:[day-before-start] before:[day-after-end] to ensure inclusive date range. Then refine with these optional filters:
     - Add `has:thread` to find threads you started (leadership)
     - Add `has::emoji:` to find messages with reactions (high impact)
     - Add `in:#channel-name` to focus on specific channels
     Look for: announcements, technical decisions, cross-team coordination, problem solving. Copy important threads to .txt or .md files in `inputs/slack/`. Type 'done' when ready."
   - Wait for user confirmation
   - **Search tips:**
     - Replace `@your-username` with your actual Slack username (e.g., @username)
     - Use one day before/after for inclusive date range (handles timezones)
     - Start with basic date range search, then add filters to refine
     - Thread starters often indicate you drove discussion
     - Reactions indicate community value/impact
     - Look in team channels, cross-functional channels, incident channels
   - **Future enhancement:** Slack API integration for automatic retrieval

   **Step 4g: Additional Data**
   - Prompt: "Finally, add any other accomplishments not captured above. Save freeform accomplishments as .txt or .md files to `inputs/additional/`. Type 'done' when ready."
   - Wait for user confirmation

5. **Link Collection for All Documents**
   - Scan all input directories for .txt and .md files
   - For each file found:
     - Read the file to understand its content
     - Prompt user: "I found `[filename]` about [brief summary from content]. Do you have a public link for this? (URL or 'none')"
     - If URL provided, store mapping in `inputs/source-links.txt`:
       ```
       [filename]|[URL]|[brief description]
       ```
   - This enables readable link text in output bullets: `[Doc Name](URL)` instead of just file references

6. **Accomplishment Importance Hierarchy and Top 3 Highlights**

   **Step 6a: General Hierarchy**
   - Prompt user for prioritization guidance on accomplishment sources
   - **Default hierarchy:**
     1. **Highest importance:** Jira issues and GitHub PRs (concrete deliverables)
     2. **Medium importance:** Email threads and Google Docs (strategic work, coordination)
     3. **Lower importance:** Slack threads (communication, collaboration)
     4. **Context:** Workday goals (provides alignment context)
   - **Prompt:** "I've collected accomplishments from multiple sources. The default importance hierarchy is: Jira/GitHub (highest) → Email/Google Docs (medium) → Slack (lower). Do you want to adjust this hierarchy? (Type 'default' to use standard hierarchy, or provide guidance)"
   - **User guidance options:**
     - Accept default hierarchy
     - Specify which specific documents/sources were most impactful
     - Note any work that should be emphasized or de-emphasized

   **Step 6b: Top 3 Accomplishments**
   - After hierarchy established, prompt for top 3 highlights
   - **Prompt:** "Now let's identify your TOP 3 accomplishments from this quarter - the ones you want featured most prominently in your performance review. These will be highlighted at the beginning of your output. What were your 3 most impactful accomplishments?"
   - **Guidance for user:**
     - Think about work that had the biggest business impact
     - Consider work that demonstrates growth or new capabilities
     - Look for accomplishments that align with your Workday goals
     - Consider work that involved leadership, innovation, or cross-team collaboration
   - **User can specify by:**
     - Jira ticket ID (e.g., "PROJ-123")
     - GitHub PR number (e.g., "PR#1500")
     - Document name (e.g., "project strategy doc")
     - Brief description (e.g., "atomic promotion investigation")
   - Store in `inputs/importance-hierarchy.txt`:
     ```
     Hierarchy: [default|custom]
     High priority sources: [list]
     Medium priority sources: [list]
     Low priority sources: [list]

     Top 3 Accomplishments:
     1. [user-specified accomplishment 1]
     2. [user-specified accomplishment 2]
     3. [user-specified accomplishment 3]

     User notes: [specific guidance]
     ```
   - **Output formatting:**
     - Top 3 accomplishments featured prominently at the beginning
     - Potentially bolded or marked as "Key Accomplishment" in detailed output
     - Ensures most impactful work is immediately visible to reviewers

7. **Input Directory Parsing**
   - Read all .txt, .md, and .eml files from `inputs/jira-exports/`
     - **Includes:** Manual exports + `github-extracted-jiras.txt` (auto-generated)
   - Read all .txt, .md, and .eml files from `inputs/google-docs/`
   - Read all .txt, .md, and .eml files from `inputs/emails/` (native .eml support)
   - Read all .txt, .md, and .eml files from `inputs/slack/`
   - Read all .txt, .md, and .eml files from `inputs/additional/`
   - Cross-reference with `inputs/source-links.txt` for URLs
   - Parse and extract accomplishments from each source
   - **Note:** .eml files preserve email headers (From, To, Subject, Date) for better context
   - **Note:** GitHub-extracted Jira issues are merged with manual Jira exports

8. **Combining & Deduplication**
   - Match Jira issues to PRs by:
     - JIRA-ID in PR title or body (already extracted in Step 4c)
     - Similar work descriptions
   - Combine matched items into single accomplishment
   - Preserve all URLs (both PR and Jira links)
   - **GitHub-extracted Jiras automatically linked to their source PRs**
   - Result: Single bullet with `[PR#123](URL), [PROJ-456](URL)` for same work

9. **Format Application** - Transform to dense format:
   - Use past tense action verb (no adverbs)
   - State deliverable (no adjectives unless quantitative)
   - **Include readable link text: [PR#123](URL), [JIRA-456](URL), [Doc Name](URL)**
   - Add competency with "via" or "by"
   - State impact with "to" or "enabling"
   - Remove: "successfully", "effectively", "comprehensive", "thorough", "carefully"

10. **Quality Checks**
   - Remove all unnecessary adjectives/adverbs
   - Verify one sentence per bullet
   - Confirm facts over emphasis
   - Quantify when possible (numbers, percentages, team size)
   - **Verify all references use readable link text**
   - Map to Red Hat competencies demonstrated

11. **Competency Mapping (ORGANIZATION ONLY, NOT EVALUATION)**
   - Identify which competencies each accomplishment demonstrates
   - Group accomplishments by competencies relevant to user's CURRENT role
   - **DO NOT** assess whether accomplishments are "sufficient" for the role
   - **DO NOT** suggest what level the accomplishments represent
   - **ONLY** organize by competency categories expected for the role

12. **Link Validation (CRITICAL QUALITY CONTROL)**
   - **Purpose:** Verify every link in every bullet is accurate, authored by user, within time range, and directly tied to the accomplishment
   - **Process:**
     1. Extract all formatted accomplishment bullets (from both Top 3 and Other Accomplishments)
     2. For each bullet, identify all links (GitHub PRs, Jira tickets, Google Docs, etc.)
     3. For each link found:
        - **Verify against source data:** Check the link exists in the collected inputs
        - **Verify authorship:** Confirm the link is authored/owned by the user (not someone else's work)
        - **Verify time range:** Confirm the link is within the specified quarter date range
        - **Verify association:** Confirm the link is directly related to the accomplishment described
        - **Verify format:** Ensure readable link text is correct (e.g., `[PR#1500]` not `[PR#1234]`)
        - **Verify URL:** Confirm the URL is complete and correct
     4. Cross-reference with:
        - `inputs/source-links.txt` (document URLs)
        - GitHub API data (PR numbers, repositories, **author**, **merge date**)
        - Jira API data (issue keys, **assignee**, **resolution date**)
        - Input files (for any manually provided links)
   - **Validation criteria:**
     - ✅ Link exists in source data
     - ✅ **Link is authored/owned by the user (GitHub: PR author, Jira: assignee, Docs: owner)**
     - ✅ **Link is within the quarter date range (or reasonable buffer)**
     - ✅ Link is directly tied to the accomplishment (not a different PR/issue)
     - ✅ Link text is readable and accurate (PR#123, PROJ-456, etc.)
     - ✅ URL is complete (no truncation)
     - ❌ **NEVER include links authored by other people**
     - ❌ **NEVER include links from outside the time range**
     - ❌ **NEVER include links that aren't directly verifiable from sources**
     - ❌ **NEVER guess or infer link numbers**
   - **Authorship validation:**
     - **GitHub PRs:** Check PR author matches user (from GitHub API data)
     - **Jira issues:** Check assignee matches user (from Jira API data)
     - **Google Docs:** Check owner matches user (from Drive metadata or user confirmation)
     - **If authorship unclear:** REMOVE link or ask user for confirmation
   - **Time range validation:**
     - **GitHub PRs:** Check merge date is within quarter (allow small buffer for edge cases)
     - **Jira issues:** Check resolution date is within quarter
     - **Google Docs:** Check last modified date is within quarter (already filtered during collection)
     - **If outside range:** REMOVE link or note as context-only (not an accomplishment)
   - **One-by-one review:**
     - Review each bullet individually
     - For each link in the bullet, trace back to the original source
     - Verify authorship AND time range AND association
     - If a link cannot be verified on ANY criteria, REMOVE it or replace with description only
     - Log any removed/corrected links for transparency with reason (wrong author, wrong date, etc.)
   - **Output:** Clean, verified bullets with 100% accurate, user-authored, time-appropriate links

12.5 **PR Number Collection Enhancement**
   - **Purpose:** Ensure PR numbers are collected, not just commit hashes
   - **Process:**
     1. For each repository with commits in the quarter:
        - Run: `git log --merges --author="[user]" --since="[start-date]" --until="[end-date]" --format="%H %ai %s"`
        - Parse merge commit messages for "Merge pull request #XXXX from ..."
        - Extract PR numbers and associate with commit hashes
     2. For each PR number found:
        - Verify PR author matches user
        - Verify merge date is within quarter (allow small buffer)
        - Store in `inputs/github-prs-q[N]-[year].txt`:
          ```
          Repository: org/backend-service
          PR#123 - Merged 2026-02-04 - PROJ-456: feature implementation
          PR#200 - Merged 2025-10-17 - NO-JIRA: reliability improvement (OUTSIDE QUARTER - context only)

          Repository: org/frontend-app
          PR#789 - Merged 2026-02-05 - TEAM-101: UI enhancement
          ```
     3. Update GitHub data with PR numbers for linking in bullets
   - **Why this matters:**
     - PR numbers are more recognizable than commit hashes
     - PRs have better context (description, reviews, discussions)
     - Easier to verify in GitHub UI
   - **Fallback:** If git history unavailable, use commit hashes with note

13. **Thematic Review**
   - **Purpose:** Ensure all major themes of work are represented in the report
   - **Process:**
     1. Generate initial competency distribution analysis:
        - Count bullets by competency category
        - Show user: "Here's your competency distribution:
          - Own and Deliver Business Impact: 5 bullets
          - Technical Impact: 4 bullets
          - Ensure Software Quality and Reliability: 6 bullets
          - Leverage and Utilize AI Tools: 1 bullet
          - Mentor and Develop Engineering Talent: 1 bullet
          - etc."
     2. **Prompt user for missing themes:**
        - "Are there any competency areas that feel underrepresented?"
        - "Any major themes of work that didn't make it into the report?"
     3. **Specifically prompt for v10.6 competencies:**
        - "Did you do significant work in:
          - Leverage and Utilize AI Tools? (AI tool development, AI-assisted workflows)
          - Mentor and Develop Engineering Talent? (mentorship, onboarding, training)
          - Internal and External Collaboration? (partner work, customer engagement)
          - SDLC? (CI/CD improvements, release management)"
     4. **If user identifies missing theme:**
        - Search ALL input files for related keywords
        - Example: User says "AI work is underrepresented"
          - Search: `grep -ri "AI\|claude\|copilot\|coderabbit\|automation" inputs/`
          - Review results for buried accomplishments
          - Ask user: "I found these AI-related items. Should any be added?"
     5. **Document in review notes:**
        - Record which themes user flagged as important
        - Note any additional accomplishments surfaced
   - **Why this matters:**
     - Different work streams have different visibility in inputs
     - Strategic work (AI tools, mentorship) often lives in Slack/email, not Jira
     - User knows which competencies matter for their role/goals

14. **Association Validation**
   - **Purpose:** Ensure PR/Jira tickets are correctly associated with accomplishment descriptions
   - **Process:**
     1. Generate association report showing all PR/Jira links per bullet:
        ```
        Bullet: "Designed feature X API and monitoring system..."
        Links: repo-a#123, repo-b#456, PROJ-789, PROJ-101

        Bullet: "Improved test suite stability..."
        Links: repo-c#222, TEAM-333
        ```
     2. **Present to user:** "Here are the PRs/tickets linked to each bullet. Please review these associations. Type 'ok' if correct, or flag any that seem wrong."
     3. **Common misassociations to catch:**
        - PR addresses different aspect than described (e.g., PR is about test infrastructure, bullet says user experience)
        - Work was reverted in later PR (should be removed)
        - Multiple PRs for same Jira, but only some are relevant
        - Jira epic contains work, but user didn't do the specific task described
     4. **For flagged associations:**
        - Ask user: "What's the correct PR/Jira for this accomplishment?" or "Should this bullet be removed/reworded?"
        - Update bullet with correct association
        - Document correction in review notes
   - **Why this matters:**
     - Prevents incorrect attribution
     - Catches work that was reverted or superseded
     - Ensures accomplishment descriptions match actual PR/Jira content

15. **Unlisted Work Review**
   - **Purpose:** Surface work from inputs that didn't make it into bullets
   - **Process:**
     1. Compare collected inputs against generated bullets:
        - List all Jira tickets from inputs
        - List all GitHub commits/PRs from inputs
        - List all Google Docs from inputs
        - Mark which ones appear in bullets
     2. **Generate unlisted work report:**
        ```
        Work NOT in current bullets:

        GitHub commits (NO-JIRA):
        - repo-a@abc123def: Refactor timeout handling logic
        - repo-a@456789abc: Improve retry mechanism
        - repo-b@xyz987fed: Fix flaky integration test

        Jira tickets:
        - PROJ-444: Feature X delivery (closed 2026-02-15)

        Google Docs:
        - quarterly-planning-q1.md (strategic planning document)
        ```
     3. **Present to user:** "The following work from your inputs didn't make it into bullets. Should any be added?"
     4. **Highlight categories often missed:**
        - NO-JIRA commits (test infrastructure, tooling improvements)
        - Test infrastructure improvements
        - Tooling/automation work
        - Strategic planning documents
        - Process improvements
     5. **User decides what to add:**
        - User can say "Add X" or "Ignore Y"
        - For added items, generate bullet following dense format
   - **Why this matters:**
     - Test infrastructure work often lacks Jira tickets
     - Tooling improvements (like quarterly-connection plugin!) are easy to miss
     - NO-JIRA commits can represent significant technical work

16. **Document Link Review**
   - **Purpose:** Ensure all important documents have public links in bullets
   - **Process:**
     1. List all Google Docs from inputs with their public links:
        ```
        Documents with public links:
        - Project Readiness Tracker: https://docs.example.com/.../edit
        - Coverage Planning Doc: https://docs.example.com/.../edit
        - Team Member Feedback: https://docs.example.com/.../edit

        Documents without public links:
        - quarterly-planning-q1.md (no link provided during collection)
        - project-strategy-notes.md (no link provided during collection)
        ```
     2. **Review bullets for document references:**
        - Check which documents are mentioned in bullets
        - Check which have clickable links vs. just descriptions
     3. **Present to user:** "The following documents appear in your inputs. Which should have public links in your bullets?"
        - Show documents currently linked in bullets
        - Show documents available but not linked
        - Show documents used as background context only
     4. **User decides document visibility:**
        - "Link it" - Add public link to bullet
        - "Background only" - Keep document as context, don't link publicly
        - "Remove" - Don't reference document
     5. **Update bullets with confirmed links:**
        - Replace generic descriptions with clickable links where appropriate
        - Example: "tracked in project readiness document" → "tracked in [Project Readiness Tracker](URL)"
   - **Why this matters:**
     - Important strategic work documented in Google Docs deserves links
     - GA Readiness tracking, planning documents show project management
     - Links make work verifiable and add credibility
     - But not all documents should be public (sensitive info, drafts)

17. **Output**
   - Files saved to `.work/quarterly-connection/outputs/` directory (gitignored)
   - **Primary:** `q[N]-[year]-accomplishments-workday.html`
   - **Secondary:** `q[N]-[year]-accomplishments-workday.md`
   - **Detailed:** `q[N]-[year]-complete-accomplishments.md`
   - **Workday HTML Format (Primary):**
     - **TOP 3 ACCOMPLISHMENTS section at the beginning** (if specified by user)
     - Bulleted list organized by competency categories
     - Clickable hyperlinks: `<a href="URL">readable text</a>`
     - Explicit Red Hat competency keywords
     - One sentence per bullet
     - Dense format (no unnecessary adjectives/adverbs)
     - Top 3 accomplishments potentially marked or visually distinguished
     - Copy/paste directly into Workday
   - **Markdown Format (Secondary):**
     - Same content as HTML
     - Markdown links: `[text](URL)`
     - Top 3 accomplishments at the beginning
     - For systems that accept markdown
   - **Detailed Analysis:**
     - Top 3 accomplishments highlighted
     - Competency mappings (which competencies demonstrated, NOT level assessment)
     - Distribution across competency categories for current role
     - Importance hierarchy applied to organization
     - **NO level indicators or promotion readiness assessments**

18. **Review**
   - Display file paths
   - Show accomplishment count by source (Jira, GitHub, Google Docs, Email, Slack, Additional)
   - Note transformations applied
   - List competencies demonstrated
   - **Report link validation results:**
     - Total links validated
     - Any links removed/corrected with reasons:
       - Wrong author (included someone else's work)
       - Wrong date (outside quarter time range)
       - Unverifiable (couldn't confirm in source data)
       - Wrong association (not related to accomplishment)
     - Confirmation that all remaining links are verified, user-authored, and time-appropriate
   - **Report refinement results:**
     - PR numbers collected: X PRs found from merge commits
     - Thematic review: Competencies flagged as underrepresented, items added
     - Association validation: X associations corrected
     - Unlisted work: X items added from NO-JIRA/test infrastructure/tooling
     - Document links: X documents linked publicly
   - **Remind user: This is an organization tool, not an evaluation of role fit**

## Examples - Dense Format with Red Hat Competency Keywords (Workday/HTML Format)

**Before (verbose, generic competencies, unnecessary adverbs):**
```text
Successfully developed a comprehensive API specification [api#123] using extensive technical collaboration with platform team to clearly define how we effectively monitor service health.
```

**After (direct, explicit Red Hat competency keywords, quantified impact):**
```text
Developed service health API specification [[PR#123](https://github.com/org/api-repo/pull/123)] via Internal and External Collaboration and System Design to enable automated health monitoring in production, working with platform team.
```

**Before (verbose, generic descriptions, unnecessary adverbs):**
```text
Carefully fixed the service startup reliability issue [service#456, TEAM-789] using thorough debugging in conjunction with the infrastructure team to ensure a high-quality, reliable service.
```

**After (direct, explicit competencies, clear impact):**
```text
Fixed service startup [[PR#456](https://github.com/org/backend-service/pull/456)] via Apply and Advance Technical Practices and Technical Acumen to prevent false degraded states, implementing exponential backoff to retry initialization for 10 minutes before degrading.
```

**Additional Examples with Explicit Red Hat Competency Keywords:**
```text
Fixed cluster consensus detection [[PR#789](https://github.com/org/backend-service/pull/789), [PROJ-101](https://jira.company.com/browse/PROJ-101)] via Technical Impact and Technical Acumen to eliminate false consensus-lost alerts during node failover operations.

Created testing framework [[PR#222](https://github.com/org/test-library/pull/222), [TEAM-333](https://jira.company.com/browse/TEAM-333)] via Apply and Advance Technical Practices and Leadership to enable 3 test authors to develop integration tests in parallel without code duplication.

Fixed CI pipeline reliability [[PR#444](https://github.com/org/ci-config/pull/444)] via SDLC and Quality Management to reduce timeout failures, adding parallelism to integration test suite for v2.0+.

Led strategic planning [[Strategy Doc](https://docs.example.com/document/DOCUMENT_ID/edit)] via Own and Deliver Business Impact and Leadership to achieve cross-company alignment on delivery timeline, analyzing risks, alternatives, and mitigation plan.
```

**Key Improvements:**
- **Explicit competency keywords:** Use v10.6 Responsibility + Skill combinations (not just generic terms like "collaboration" or "innovation")
- **No unnecessary adverbs:** Removed "successfully", "carefully", "thoroughly", "effectively", "clearly"
- **Quantified details:** "3 test authors", "10 minutes", "4.16+", "15+ work streams"
- **Clear impact first, details second:** Impact stated with "to [outcome]", then technical details in second clause

## Red Hat Engineering Competencies (v10.6)

**Full Reference:** See `../reference/red-hat-competencies.md`

**Example Bullets:** See `../reference/example-bullets.md`

**⚠️ CRITICAL USAGE NOTE:**
Competencies are used to ORGANIZE accomplishments by the categories expected for your current role. This tool does NOT evaluate whether you demonstrate competencies at the right level, whether you're ready for promotion, or what role you deserve. It ONLY maps what you did to which competency categories were demonstrated.

**NEVER make statements about:**
- Level of work demonstrated (e.g., "This shows PSE-level work")
- Promotion readiness (e.g., "Ready for promotion to X")
- Role fit or deserved role (e.g., "Demonstrates Principal Engineer capabilities")
- Comparison to other levels

**ONLY provide:**
- Which competencies were demonstrated
- Organization by competency categories relevant to current role
- Factual categorization without evaluation

Map accomplishments using v10.6 framework: **1 Responsibility + 1 Skill per bullet**

### Responsibilities (What You DO)
1. **Technical Impact** - Design and develop software solutions
2. **Ensure Software Quality and Reliability** - Testing, debugging, quality practices
3. **Internal and External Collaboration** - Community engagement, cross-functional teamwork
4. **Mentor and Develop Engineering Talent** - Coaching and mentorship
5. **Own and Deliver Business Impact** - Business value delivery and ownership
6. **Apply and Advance Technical Practices** - Adoption of new tools and technologies
7. **Leverage and Utilize AI Tools** - AI assistants and agentic workflows *(NEW)*
8. **SDLC** - Software Development Life Cycle adherence and improvement

### Job Skills (Capabilities You HAVE)
1. **Technical Acumen** - Proficiency with codebase, tools, tech stack
2. **Quality Management** - Accountability for quality and testing
3. **System Design** - Design and architecture capabilities
4. **Communication** - Technical communication to diverse audiences
5. **Collaboration** - Cross-functional and cross-team collaboration
6. **Leadership** - Technical leadership and influence
7. **Business impact** - How technical work creates business value
8. **Continuous Learning** - Staying current with technologies
9. **Influence** - Ability to persuade and drive technical direction
10. **Knowledge Sharing** - Documentation, presentations, teaching

**Mapping Guide (Responsibility + Skill) - CATEGORIZATION ONLY:**
- Bug fixes → Own and Deliver Business Impact + Business impact
- New features → Technical Impact + Technical Acumen
- Quality/testing → Ensure Software Quality and Reliability + Quality Management
- Cross-team work → Internal and External Collaboration + Collaboration
- Process improvements → Apply and Advance Technical Practices + Continuous Learning
- Mentoring → Mentor and Develop Engineering Talent + Leadership
- Strategic planning → Own and Deliver Business Impact + Leadership
- CI/CD work → SDLC + Quality Management
- Customer engagement → Own and Deliver Business Impact + Communication
- Upstream contributions → Internal and External Collaboration + Knowledge Sharing
- AI/automation → Leverage and Utilize AI Tools + Technical Acumen

**This mapping identifies WHICH competencies apply, NOT whether they're demonstrated at the appropriate level for your role.**

## Return Value

Files are saved to `.work/quarterly-connection/outputs/` directory (gitignored).

- **Primary Output (HTML)**: `q[N]-[year]-accomplishments-workday.html`
  - **Workday-ready HTML format - COPY/PASTE DIRECTLY:**
    - **Top Accomplishments** section (3 bullets highlighting most significant work)
    - **Other Accomplishments** section organized by competency categories (h3 headers)
    - Clickable hyperlinks: `<a href="URL">PR#123</a>`, `<a href="URL">JIRA-456</a>`
    - Dense format with explicit Red Hat v10.6 competency keywords
    - Quantified impact where possible
    - **Clean format - no summary statistics, no extra commentary**
    - Opens in browser for easy copying
    - Example structure:
      ```html
      <h2>Top Accomplishments</h2>
      <ul>
        <li>Major achievement 1...</li>
        <li>Major achievement 2...</li>
        <li>Major achievement 3...</li>
      </ul>

      <h2>Other Accomplishments</h2>

      <h3>Own and Deliver Business Impact + Business impact</h3>
      <ul>
        <li>Accomplishment...</li>
        <li>Accomplishment...</li>
      </ul>

      <h3>Technical Impact + Technical Acumen</h3>
      <ul>
        <li>Accomplishment...</li>
      </ul>
      ```

- **Secondary Output (Markdown)**: `q[N]-[year]-accomplishments-workday.md`
  - **Markdown version - COPY/PASTE DIRECTLY:**
    - Same structure as HTML (Top Accomplishments + Other Accomplishments)
    - Markdown link format: `[PR#123](URL)`
    - **Clean format - no summary statistics, no extra commentary**
    - For systems that accept markdown

- **Detailed Analysis**: `q[N]-[year]-complete-accomplishments.md`
  - **Background reference - NOT for Workday:**
    - Top 3 accomplishments with extended context
    - Complete accomplishment list by competency
    - Source breakdown (Jira/GitHub/Email/Slack/Google Docs)
    - Detailed competency mappings (which competencies demonstrated)
    - Summary statistics (count by source, count by competency, quantified impact)
    - All URLs organized by source
    - **DOES NOT INCLUDE: Level assessments, promotion readiness, role fit evaluations**

## Manual Data Gathering Guide

**The command will guide you through data gathering ONE SOURCE AT A TIME:**

**Workflow:**
1. Command creates directory structure automatically
2. Prompts you sequentially for each data source
3. You save documents as .txt, .md, or .eml files
4. After all sources collected, command reads each file and prompts for public links
5. Links are stored in `source-links.txt` for use in formatted bullets

**Data Source Order:**

**1. Workday Goals and Development Items (prompted FIRST)**
   - **WHY FIRST:** Provides critical context for professional development and what you were supposed to accomplish
   - Go to Workday → Goals and Development
   - Copy your goals and development items for the quarter
   - Save as `inputs/additional/workday-goals.txt` or `.md`
   - Example content:
     ```
     Goal 1: Complete Two-Node Fencing GA delivery
     Goal 2: Mentor 2 junior engineers on etcd debugging
     Development: Improve cross-functional collaboration skills
     ```

**2. Jira (prompted second)**
   - Go to Jira → Filters → Advanced search
   - Query: `assignee = currentUser() AND status in (Done, Closed) AND resolved >= [start-date] AND resolved <= [end-date]`
   - Export → Save as .txt or .md to `inputs/jira-exports/`
   - Example: `inputs/jira-exports/q1-2026-jira-export.txt`

**3. GitHub (automatic)**
   - Command automatically queries merged PRs in date range
   - No manual action required

**4. Google Drive (prompted fourth)**
   - **Search strategy:** In Google Drive, search "Owned by me" and filter by "Last modified" from [start-date] to TODAY (not end-date)
   - **Why to today:** You may have updated docs after the quarter ended
   - **Advanced search:** `owner:me modified:[start-date] to [current-date]`
   - Find design docs, proposals, strategy docs, meeting notes
   - Save each as .txt or .md to `inputs/google-docs/`
   - Example: `inputs/google-docs/tnf-strategy-doc.md`
   - You'll be prompted for the public link after saving

**5. Email (prompted fifth)**
   - **Search strategy:** In Gmail, search `in:sent -"From Google Calendar"` and filter by date range
   - **Advanced search:** `in:sent -"From Google Calendar" after:[start-date] before:[end-date]`
   - **Why this works:** Shows emails you sent (active communication), excludes calendar noise
   - Find important threads: cross-team coordination, customer engagement, technical decisions, escalations
   - **Export formats:** Save as .eml (native), .txt, or .md to `inputs/emails/`
   - Example: `inputs/emails/customer-escalation-thread.eml`
   - **Tip:** Most email clients support "Save as .eml" or "Download message"

**6. Slack (prompted sixth)**
   - **Primary search:** Start with `from:@your-username after:YYYY-MM-DD before:YYYY-MM-DD` to see all your messages
   - **Important:** Replace `@your-username` with your actual Slack username (e.g., @username)
   - **Date range tip:** Use one day before/after for inclusive range (handles timezones)
     - For Q1 2026 (Jan 1 - Mar 31), search: `after:2025-12-31 before:2026-04-01`
     - Ensures you don't miss boundary messages
   - **Refinement filters (optional):**
     - Add `has:thread` - Threads you started (leadership/driving discussion)
     - Add `has::emoji:` - Messages with reactions (community impact)
     - Add `in:#channel-name` - Messages in specific channel
   - **Example searches:**
     - `from:@username after:2025-12-31 before:2026-04-01` (Q1 2026, inclusive - use YOUR username)
     - `from:@username has:thread after:2025-12-31 before:2026-04-01` (threads only)
     - `from:@username has::raised_hands: after:2025-12-31` (with reactions)
   - **What to look for:**
     - Announcements you made to the team
     - Technical decisions or proposals you drove
     - Cross-team coordination (working across channels)
     - Problem solving (incident response, debugging help)
     - Mentoring (helping others, answering questions)
   - **Tips for finding substantive content:**
     - Thread starters indicate you initiated important discussions
     - Reactions (👍 ✅ 🎉) suggest high-value contributions
     - Long threads where you participated indicate collaboration
     - Messages in cross-functional channels show broader impact
   - Save as .txt or .md to `inputs/slack/`
   - Example: `inputs/slack/release-planning-discussion.md`, `inputs/slack/incident-response-thread.txt`
   - **Note:** Slack doesn't have character-count filters, use context clues (threads, reactions, channels) to identify important messages

**7. Additional (prompted last)**
   - Add freeform accomplishments not captured elsewhere
   - Save as .txt or .md to `inputs/additional/`
   - Example: `inputs/additional/conference-presentation.txt`

**Link Collection Phase:**
After you finish saving all files, the command will:
1. Scan all directories for .txt and .md files
2. Read each file to understand its content
3. Prompt you: "I found `tnf-strategy-doc.md` about [summary]. Do you have a public link? (URL or 'none')"
4. Store links in `inputs/source-links.txt` for use in formatted bullets

## Examples

1. **Build Q4 2025 accomplishments for Senior Software Engineer**:
   ```
   /quarterly-connection:build SSE 2025-10-01 2025-12-31
   ```

2. **Build Q1 2026 for Principal Software Engineer**:
   ```
   /quarterly-connection:build PSE 2026-01-01 2026-03-31
   ```

3. **If role is omitted, user will be prompted:**
   ```
   /quarterly-connection:build 2026-01-01 2026-03-31

   Output: "What is your CURRENT role? (SE/SSE/PSE/SPSE/DE/SDE): "
   ```

## Arguments

- **$1**: Role (required or prompted) - Your CURRENT role from Red Hat v10.6 framework (exactly 6 roles):
  - `SE` - Software Engineer
  - `SSE` - Senior Software Engineer
  - `PSE` - Principal Software Engineer
  - `SPSE` - Senior Principal Software Engineer
  - `DE` - Distinguished Engineer
  - `SDE` - Senior Distinguished Engineer
  - **Used ONLY to organize accomplishments by relevant competencies for that role**
  - **NOT used to evaluate whether you deserve the role or assess promotion readiness**
- **$2**: Start date in YYYY-MM-DD format (required)
- **$3**: End date in YYYY-MM-DD format (required)

## Notes

**⚠️ CRITICAL - This Tool's Purpose:**
- ✅ **DOES:** Organize accomplishments by competency categories
- ✅ **DOES:** Map work to competencies demonstrated
- ✅ **DOES:** Format in dense, factual style
- ✅ **DOES:** Group by competencies relevant to your CURRENT role
- ✅ **DOES:** Validate every link against source data
- ✅ **DOES:** Verify all links are user-authored (not other people's work)
- ✅ **DOES:** Verify all links are within the quarter time range
- ❌ **NEVER:** Evaluate level or promotion readiness
- ❌ **NEVER:** Assess whether you "deserve" a role
- ❌ **NEVER:** Judge quality or sufficiency of accomplishments
- ❌ **NEVER:** Make statements like "demonstrates PSE-level work" or "ready for promotion"
- ❌ **NEVER:** Compare accomplishments to level expectations
- ❌ **NEVER:** Suggest what role you should have
- ❌ **NEVER:** Include unverified or guessed links
- ❌ **NEVER:** Include links authored by other people
- ❌ **NEVER:** Include links from outside the quarter date range

**This is a MAPPING and ORGANIZATION tool, NOT an EVALUATION tool.**

**Dense Format Requirements:**
- **REQUIRED: Use readable link text (Workday/HTML format)**
- **REQUIRED: Use explicit Red Hat competency keywords from framework**
- Remove adjectives unless quantitative (5 bugs, 30% faster, 3 teams, 15+ work streams)
- Remove adverbs (successfully, carefully, thoroughly, effectively, significantly, clearly, extensively)
- Use facts, not emphasis
- One sentence per bullet
- State impact first, then technical/process details

**Link Format Requirements (Workday/HTML Style):**
- **GitHub PRs:** `[PR#NUMBER](https://github.com/org/repo/pull/NUMBER)`
- **Jira Issues:** `[ISSUE-KEY](https://issues.redhat.com/browse/ISSUE-KEY)`
- **Google Docs:** `[Descriptive Name](URL)` - e.g., `[Strategy Doc]`, `[Spike Proposal]`, `[Technical Brief]`
- **Multiple refs:** Comma-separated within sentence
- **Example:** `[[PR#123](URL), [PROJ-456](URL)]`

**Competency Keyword Requirements (v10.6):**
- **Use 1 RESPONSIBILITY + 1 SKILL** from Red Hat framework v10.6
- **NOT generic:** "via collaboration" or "via innovation"
- **YES explicit:** "via Internal and External Collaboration and Collaboration" or "via Apply and Advance Technical Practices and Technical Acumen"
- **Common explicit keyword combinations:**
  - Technical work: Technical Impact + Technical Acumen
  - Quality work: Ensure Software Quality and Reliability + Quality Management
  - Collaboration: Internal and External Collaboration + Collaboration
  - Mentoring: Mentor and Develop Engineering Talent + Leadership
  - Business delivery: Own and Deliver Business Impact + Business impact
  - Innovation: Apply and Advance Technical Practices + Continuous Learning
  - Process/CI: SDLC + Quality Management
  - Strategic: Own and Deliver Business Impact + Leadership
  - Community: Internal and External Collaboration + Knowledge Sharing
  - AI/Automation: Leverage and Utilize AI Tools + Technical Acumen
- Infer from work type which Responsibility + Skill combination applies
- Use exactly 2 keywords per bullet: 1 Responsibility + 1 Skill
- Map each accomplishment using the work-type mapping guide

**Impact Focus:**
- State business value directly
- Quantify when possible
- Focus on: capabilities enabled, bugs fixed, time saved, teams unblocked, versions affected

**Data Sources (Sequential Collection):**
1. **Workday Goals/Development** - Manual copy as .txt/.md in `inputs/additional/` (critical for professional development context)
2. **Jira** - Manual exports as .txt/.md in `inputs/jira-exports/` (automatic API query if MCP configured)
3. **GitHub** - Automatic query for merged PRs (PRIORITIZE PRs, NOT COMMITS)
   - **Plus:** Automatic extraction of Jira references from PR titles/bodies
   - **Plus:** Validation and addition of extracted Jira issues if qualified
4. **Google Drive** - Manual saves as .txt/.md in `inputs/google-docs/` (prompted for public links)
5. **Email** - Manual saves as .eml/.txt/.md in `inputs/emails/`
6. **Slack** - Manual saves as .txt/.md in `inputs/slack/` (search with `from:@your-username has:thread has::emoji:`)
7. **Additional** - Manual saves as .txt/.md in `inputs/additional/`

**GitHub → Jira Cross-Reference:**
- Automatically extract Jira issue keys from PR titles and bodies
- Validate extracted Jira issues against quarter window and assignee
- Add qualified Jira issues to sources (stored in `inputs/jira-exports/github-extracted-jiras.txt`)
- Ensures complete PR↔Jira linkage

**Future Enhancements:**
- Slack API integration for automatic message retrieval
- Minimum character count filtering for Slack messages
- Automated thread extraction

**Input File Standards:**
- **Supported formats:** .txt, .md, .eml (email native format)
- **Not supported:** PDF, CSV, DOCX (convert to text first)
- **Email tip:** Save as .eml to preserve headers (From, To, Subject, Date)
- Use descriptive file names: `tnf-strategy-doc.md`, `customer-escalation-thread.eml`
- One document per file
- After saving, you'll be prompted for public links to each document
- Links stored in `inputs/source-links.txt` enable readable link text: `[Strategy Doc](URL)`

**Sequential Prompting:**
- Tool prompts ONE data source at a time
- Starts with Workday goals (context setting)
- Wait for "done" confirmation before moving to next source
- Prevents overwhelming you with all sources at once
- Ensures complete data collection
- Goals inform how accomplishments map to professional development
