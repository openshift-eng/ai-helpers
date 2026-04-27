---
name: Create Jira Initiative
description: Implementation guide for creating Jira initiatives representing strategic architectural or improvement-focused work
---

# Create Jira Initiative

This skill provides implementation guidance for creating Jira initiatives, which represent strategic architectural improvements or operational excellence work spanning ~6 months.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create initiative` command to guide the initiative creation process.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to create issues in the target project
- Understanding of the strategic goal or improvement area
- Technical/operational context for the initiative

**Reference Documentation:**
- [Markdown for Jira Reference](../../reference/markdown-for-jira.md) - Markdown formatting for Jira descriptions
- [MCP Tools Reference](../../reference/mcp-tools.md) - MCP tool signatures and custom fields
- [CLI Fallback Reference](../../reference/cli-fallback.md) - jira-cli commands (only if MCP unavailable)

## What is an Initiative?

An initiative is:
- A **strategic architectural or improvement-focused effort** that spans ~6 months or single release
- **Scoped to a single product/engineering area**
- Focused on **technical debt reduction**, **architectural improvements**, **operational excellence**, or **scalability**
- Has **clear completion criteria** and measurable success metrics
- Contains **multiple features or epics** to deliver the goal

### Initiative vs Feature vs Epic

| Level | Scope | Duration | Focus | Example |
|-------|-------|----------|-------|---------|
| **Initiative** | Strategic architectural/improvement work | ~6 months / 1 release | Technical excellence, infrastructure | "Modernize CI/CD Pipeline Infrastructure" |
| Feature | Strategic product capability | 1-3 releases (3-9 months) | Customer-facing value | "Advanced hosted control plane observability" |
| Epic | Specific capability within initiative/feature | 1 quarter/release | Deliverable component | "Multi-cluster metrics aggregation" |

### Initiative Characteristics

Initiatives should:
- Address a **strategic technical or operational goal**
- Focus on **architectural improvements**, **technical debt**, **operational excellence**, or **scalability**
- Span **~6 months or single release**
- Have **SMART success criteria** (Specific, Measurable, Achievable, Relevant, Time-bound)
- Contain **multiple features or epics** (typically 2-5)
- Deliver **foundation for future capabilities** or **risk mitigation**

## Initiative Description Best Practices

### Goal

Every initiative should clearly state:
- **What is our purpose?** What are we enabling?
- **What strategic goals** does this support? (technical debt reduction, architectural improvements, operational excellence, scalability)
- **Why now?** What makes this a priority?

**Good example:**
```
## Goal

Modernize our CI/CD pipeline infrastructure to support faster release cycles and improved developer productivity.

This initiative supports our strategic goals of:
- Operational excellence: Reduce pipeline failures from 15% to <5%
- Developer productivity: Cut build times from 45min to 15min
- Scalability: Support 3x increase in concurrent builds
- Technical debt reduction: Migrate from legacy Jenkins to modern GitOps-based pipelines

We're prioritizing this now because our current pipeline infrastructure is blocking quarterly release cadence and causing developer frustration (NPS: 4/10).
```

**Bad example:**
```
Fix CI/CD issues.
```

### Benefit Hypothesis

Explain the expected benefits:
- **Benefits to Red Hat:** Cost reduction, efficiency, capability enablement
- **Benefits to customers:** Improved reliability, faster features, better support
- **Benefits to community:** Better tooling, faster contributions
- **Impact on security, performance, supportability**
- **Why is this a priority?**

**Example:**
```
## Benefit Hypothesis

### Expected Outcomes
- **Reduced operational overhead:** 60% reduction in pipeline maintenance time (from 20hrs/week to 8hrs/week)
- **Improved reliability:** Pipeline success rate increases from 85% to 95%
- **Foundation for future capabilities:** Enables automated security scanning, performance testing integration
- **Risk mitigation:** Reduces dependency on single Jenkins instance (currently SPOF)
- **Developer productivity:** Developers spend 40% less time waiting for builds

### Why This is a Priority
Current pipeline infrastructure is:
- Blocking quarterly release goals (can't meet 3-month cadence)
- Causing developer frustration (survey NPS: 4/10, builds are #1 complaint)
- Creating operational burden (team spends 50% of time on pipeline maintenance)
- Becoming a competitive disadvantage (competitors ship 2x faster)
```

### Success Criteria

Define how you'll measure success (SMART criteria):
- **Specific:** Clear, unambiguous metrics
- **Measurable:** Can be quantified or observed
- **Achievable:** Realistic given constraints
- **Relevant:** Aligned with strategic goals
- **Time-bound:** Target dates or milestones

**Example:**
```
## Success Criteria

### Performance Metrics
- Build time reduced from 45min to <15min (measured via pipeline analytics)
- Pipeline success rate >95% (currently 85%)
- Support for 150 concurrent builds (currently 50)

### Operational Metrics
- Pipeline maintenance time reduced from 20hrs/week to <8hrs/week
- Mean time to recovery (MTTR) for pipeline issues <30min (currently 4hrs)
- Zero downtime deployments (currently 2-3 outages/month)

### Developer Experience
- Developer NPS for build system improves from 4/10 to 8/10
- 90% of developers report "builds are fast enough" (currently 30%)

### Timeline
- Q1 2026: MVP pipeline operational for 2 pilot teams
- Q2 2026: Full migration of all 15 teams complete
- Q3 2026: Advanced capabilities (security scanning, perf testing) deployed
```

## Interactive Initiative Collection Workflow

When creating an initiative, guide the user through strategic thinking:

### 1. Goal and Purpose

**Prompt:** "What is the goal of this initiative? What are you enabling or improving?"

**Probing questions:**
- What strategic goals does this support? (technical debt, architecture, operational excellence, scalability)
- What are we enabling with this work?
- Why is this a priority now?
- What happens if we don't do this?

**Example response:**
```
Modernize CI/CD pipeline infrastructure to support faster release cycles. We need to reduce build times from 45min to <15min and improve reliability to >95% to meet quarterly release commitments. Current infrastructure is blocking releases and causing developer frustration.
```

### 2. Benefit Hypothesis

**Prompt:** "What are the expected benefits and outcomes? Who benefits and how?"

**Categories to consider:**
- Operational efficiency (time, cost savings)
- Technical capability (foundation, scalability)
- Risk mitigation (security, reliability)
- Developer/customer experience

**Example response:**
```
Operational: 60% reduction in pipeline maintenance time
Technical: Foundation for automated security scanning
Risk: Eliminates single point of failure (Jenkins instance)
Experience: Developers spend 40% less time waiting for builds
```

### 3. Success Criteria

**Prompt:** "How will you measure success? What metrics will tell you this initiative achieved its goals?"

**SMART framework:**
- Specific: What exactly improves?
- Measurable: How will you quantify it?
- Achievable: Is this realistic?
- Relevant: Does this align with goals?
- Time-bound: When will this be achieved?

**Example response:**
```
Performance: Build time <15min (from 45min), >95% success rate
Operational: Maintenance time <8hrs/week (from 20hrs/week)
Experience: Developer NPS 8/10 (from 4/10)
Timeline: Full migration complete by end of Q2 2026
```

### 4. Scope Definition

**Prompt:** "What's included in this initiative? What are the major deliverables?"

**Ask for:**
- 2-5 major features/epics that comprise the initiative
- Explicitly define what's OUT of scope to avoid confusion

**Example response:**
```
Included:
- Migrate from Jenkins to GitHub Actions
- Implement automated build caching
- Deploy parallel build infrastructure
- Integrate security scanning in pipeline
- Create developer documentation and training

NOT Included:
- Log aggregation platform (separate initiative)
- Production deployment automation (follow-on work)
- Desktop development environment improvements
```

### 5. Dependencies and Responsibilities

**Prompt:** "What dependencies or blockers exist? Which teams need to be involved?"

**Identify:**
- Blocking work or external dependencies
- Required approvals or decisions
- Team responsibilities

**Example response:**
```
Dependencies:
- GitHub Enterprise license procurement (HCMPE-500)
- Infrastructure team to provision build agents
- Security team approval for pipeline changes

Responsibilities:
- Platform Engineering: Pipeline migration, infrastructure
- Developer Experience: Developer docs, training
- Security: Pipeline security review, scanning integration
```

### 6. Timeline and Milestones

**Prompt:** "What's the timeline? What are key milestones?"

**Example response:**
```
Timeline: 6 months (2 quarters)
Milestones:
- Q1 2026: MVP pipeline for 2 pilot teams
- Q2 2026: Full migration of all 15 teams
- Q2 2026: Advanced capabilities deployed (security, perf testing)
```

## Field Validation

Before submitting the initiative, validate:

### Required Fields
- ✅ Summary clearly states the strategic goal or improvement area
- ✅ Description includes goal and purpose
- ✅ Benefit hypothesis articulated
- ✅ SMART success criteria defined (measurable)
- ✅ Scope clearly defined (included + NOT included)
- ✅ Component is specified (if required by project)
- ✅ Target version/release is set (if required)

### Initiative Quality
- ✅ Addresses a strategic technical or operational goal
- ✅ Timeframe is realistic (~6 months / single release)
- ✅ Success criteria are SMART
- ✅ Scope includes multiple features/epics (not a single epic)
- ✅ Benefits are clearly articulated
- ✅ Dependencies identified

### Security
- ✅ No credentials, API keys, or secrets in any field
- ✅ No confidential business information (if public project)

## MCP Tool Parameters

### Basic Initiative Creation

```python
mcp__atlassian__jira_create_issue(
    project_key="<PROJECT_KEY>",
    summary="<initiative summary>",
    issue_type="Initiative",
    description="""
## Goal

<What is our purpose? What are we enabling? Strategic goals supported?>

## Benefit Hypothesis

### Expected Outcomes
- <Outcome 1>
- <Outcome 2>
- <Outcome 3>

### Why This is a Priority
<Explanation of why now>

## Success Criteria

### <Metric Category 1>
- <SMART metric 1>
- <SMART metric 2>

### <Metric Category 2>
- <SMART metric 1>

### Timeline
- <Quarter/Date>: <Milestone 1>
- <Quarter/Date>: <Milestone 2>

## Scope

### Included
- <Major deliverable 1>
- <Major deliverable 2>
- <Major deliverable 3>

### NOT Included
- <Out of scope item 1>
- <Out of scope item 2>

## Responsibilities

- **<Team/Role>:** <What they'll do>
- **<Team/Role>:** <What they'll do>

## Dependencies

- <Dependency 1>
- <Dependency 2>

## Additional Context

<Background, technical notes, links to related docs>

## Resources

- <Link to design doc>
- <Link to related work>
    """,
    components="<component name>",  # if required
    additional_fields={
        # Add project-specific fields
    }
)
```

### Example: Platform Engineering Initiative

```python
mcp__atlassian__jira_create_issue(
    project_key="HCMPE",
    summary="Modernize CI/CD Pipeline Infrastructure",
    issue_type="Initiative",
    description="""
## Goal

Modernize our CI/CD pipeline infrastructure to support faster release cycles and improved developer productivity.

This initiative supports our strategic goals of:
- **Operational excellence:** Reduce pipeline failures from 15% to <5%
- **Developer productivity:** Cut build times from 45min to 15min
- **Scalability:** Support 3x increase in concurrent builds
- **Technical debt reduction:** Migrate from legacy Jenkins to modern GitOps-based pipelines

We're prioritizing this now because our current pipeline infrastructure is blocking quarterly release cadence and causing developer frustration (survey NPS: 4/10).

## Benefit Hypothesis

### Expected Outcomes
- **Reduced operational overhead:** 60% reduction in pipeline maintenance time (from 20hrs/week to 8hrs/week)
- **Improved reliability:** Pipeline success rate increases from 85% to 95%
- **Foundation for future capabilities:** Enables automated security scanning, performance testing integration
- **Risk mitigation:** Reduces dependency on single Jenkins instance (currently SPOF)
- **Developer productivity:** Developers spend 40% less time waiting for builds
- **Cost savings:** $100K annual savings on Jenkins infrastructure and maintenance

### Why This is a Priority

Current pipeline infrastructure is:
- **Blocking quarterly release goals** - can't meet 3-month release cadence due to slow builds
- **Causing developer frustration** - build system is #1 complaint (NPS: 4/10)
- **Creating operational burden** - team spends 50% of time on pipeline maintenance vs feature work
- **Becoming a competitive disadvantage** - competitors ship 2x faster
- **Technical risk** - Jenkins instance is a single point of failure (2-3 outages/month)

## Success Criteria

### Performance Metrics (Measured via pipeline analytics)
- Build time reduced from 45min to <15min
- Pipeline success rate >95% (currently 85%)
- Support for 150 concurrent builds (currently 50)
- P95 build time <20min (currently 60min)

### Operational Metrics
- Pipeline maintenance time reduced from 20hrs/week to <8hrs/week
- Mean time to recovery (MTTR) for pipeline issues <30min (currently 4hrs)
- Zero unplanned pipeline downtime (currently 2-3 outages/month)
- Automated rollback success rate 100%

### Developer Experience (Measured via quarterly survey)
- Developer NPS for build system improves from 4/10 to 8/10
- 90% of developers report "builds are fast enough" (currently 30%)
- 80% of developers report "pipeline is reliable" (currently 45%)

### Business Impact
- Quarterly release cadence achieved (currently missing 40% of release dates)
- $100K annual cost savings on infrastructure
- 20% increase in developer productivity (via time tracking analysis)

### Timeline
- **Q1 2026:** MVP pipeline operational for 2 pilot teams (Platform Eng, Developer Experience)
- **Q2 2026:** Full migration of all 15 teams complete
- **Q2 2026:** Advanced capabilities deployed (security scanning, performance testing)

## Scope

### Included
1. **Migrate from Jenkins to GitHub Actions** - Replace legacy Jenkins with modern GitHub Actions workflows
2. **Implement automated build caching** - Reduce build times via intelligent caching strategy
3. **Deploy parallel build infrastructure** - Scale to 150 concurrent builds
4. **Integrate security scanning in pipeline** - Automated SAST/DAST scanning on every build
5. **Create developer documentation and training** - Comprehensive docs and training sessions for all teams

### NOT Included
- **Log aggregation platform** - Separate initiative planned for H2 2026
- **Production deployment automation** - Follow-on work, separate from CI/CD modernization
- **Desktop development environment improvements** - Out of scope for pipeline work
- **Non-OpenShift projects** - Scoped to OpenShift platform engineering only

## Responsibilities

- **Platform Engineering:** Pipeline migration, infrastructure provisioning, ongoing maintenance
- **Developer Experience Team:** Developer documentation, training sessions, developer onboarding
- **Security Team:** Pipeline security review, scanning tool integration, security approval
- **Infrastructure Team:** Build agent provisioning, network configuration
- **Individual Engineering Teams:** Pilot participation, migration testing, feedback

## Dependencies

### Blocking Dependencies
- **GitHub Enterprise license procurement** (HCMPE-500) - Required before migration start
- **Build agent infrastructure** - Infrastructure team to provision 150 build agents by Q1 2026
- **Security approval** - Security team approval for new pipeline architecture (in progress)

### Required Approvals
- Architecture review board approval (scheduled for Jan 15, 2026)
- Budget approval for GitHub Actions usage ($50K annual)

### External Dependencies
- GitHub Actions SLA guarantee from GitHub
- Integration with existing monitoring tools (Datadog, PagerDuty)

## Additional Context

### Background
Our current Jenkins-based CI/CD pipeline was implemented in 2019 and has not kept pace with our growth. We've scaled from 5 teams to 15 teams, and from 50 builds/day to 300 builds/day. The infrastructure is showing strain:
- Frequent outages (2-3/month)
- Slow build times (45min average, 2hr P95)
- High maintenance burden (20hrs/week)
- Developer frustration (builds are #1 complaint)

### Technical Approach
- **Phase 1 (Q1):** Pilot migration of 2 teams to GitHub Actions, prove out architecture
- **Phase 2 (Q2):** Full migration of remaining 13 teams
- **Phase 3 (Q2):** Deploy advanced capabilities (security scanning, perf testing)

### Risk Mitigation
- **Risk:** Migration disrupts release cycles
  - **Mitigation:** Phased rollout with pilot teams, maintain Jenkins during migration
- **Risk:** GitHub Actions costs exceed budget
  - **Mitigation:** Cost analysis completed, usage caps configured, monitoring in place
- **Risk:** Teams struggle with new pipeline format
  - **Mitigation:** Comprehensive training, office hours, migration support from Platform Eng team

## Resources

- [CI/CD Modernization Design Doc](https://docs.example.com/cicd-modernization)
- [GitHub Actions Migration Runbook](https://docs.example.com/migration-runbook)
- [Cost Analysis Spreadsheet](https://sheets.example.com/cost-analysis)
- [Architecture Diagrams](https://diagrams.example.com/cicd-architecture)

## Results

_To be updated quarterly with outcomes and progress_
    """,
    components="Platform Engineering",
    additional_fields={
        "labels": ["ai-generated-jira", "cicd", "infrastructure", "technical-debt"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

## Jira Description Formatting

Use Markdown formatting (the MCP tool converts it to Jira wiki markup automatically):

### Initiative Template Format

```markdown
## Goal

<What is our purpose? What are we enabling? Strategic goals supported?>

## Benefit Hypothesis

### Expected Outcomes
- <Outcome 1>
- <Outcome 2>

### Why This is a Priority
<Explanation>

## Success Criteria

### <Metric Category>
- <SMART metric 1>
- <SMART metric 2>

### Timeline
- <Quarter/Date>: <Milestone>

## Scope

### Included
- <Deliverable 1>
- <Deliverable 2>

### NOT Included
- <Out of scope item 1>

## Responsibilities

- **<Team/Role>:** <Responsibility>

## Dependencies

- <Dependency 1>

## Additional Context

<Background, technical notes>

## Resources

- <Link 1>

## Results

_To be updated quarterly_
```

## Error Handling

### Initiative Too Small

**Scenario:** Initiative could be accomplished as a single feature or epic.

**Action:**
1. Suggest creating as Feature or Epic instead
2. Explain initiative should contain multiple features/epics

**Example:**
```
This initiative seems small enough to be a single Feature or Epic (1-2 months, single capability).

Initiatives should typically:
- Contain 2-5 features or epics
- Span ~6 months or single release
- Address strategic technical or operational goal

Would you like to create this as a Feature or Epic instead? (yes/no)
```

### Missing Strategic Context

**Scenario:** User doesn't provide goal or benefit hypothesis.

**Action:**
1. Explain importance of strategic framing
2. Ask probing questions
3. Help articulate strategic value

**Example:**
```
For an initiative, we need to understand the strategic context:

1. What strategic goal does this support? (technical debt, architecture, operational excellence, scalability)
2. What are the expected benefits and outcomes?
3. Why is this a priority now?

These help stakeholders understand why we're investing in this work.

Let's start with: What strategic goal does this initiative support?
```

### Vague Success Criteria

**Scenario:** Success criteria are not SMART (Specific, Measurable, Achievable, Relevant, Time-bound).

**Action:**
1. Identify vague criteria
2. Ask for SMART metrics
3. Suggest measurable alternatives

**Example:**
```
Success criteria should be SMART (Specific, Measurable, Achievable, Relevant, Time-bound).

"Pipeline is better" is too vague.

Instead, use SMART criteria like:
- Specific: "Build time reduced from 45min to 15min"
- Measurable: "Pipeline success rate >95%"
- Achievable: "Support 150 concurrent builds"
- Relevant: "Developer NPS improves from 4/10 to 8/10"
- Time-bound: "Full migration complete by Q2 2026"

What specific, measurable metrics would indicate success for this initiative?
```

### No Scope Definition

**Scenario:** User doesn't define what's included/excluded.

**Action:**
1. Explain importance of scope boundaries
2. Help identify major deliverables
3. Identify what's explicitly out of scope

**Example:**
```
Clear scope definition prevents confusion and scope creep.

What's INCLUDED in this initiative? (2-5 major deliverables)

What's NOT INCLUDED? (Related work that's explicitly out of scope)

For CI/CD modernization, scope might be:
INCLUDED: Jenkins→GitHub Actions migration, build caching, security scanning
NOT INCLUDED: Log aggregation, desktop dev env, production deployment automation
```

### Security Validation Failure

**Scenario:** Sensitive data detected in initiative content.

**Action:**
1. STOP submission
2. Inform user what type of data was detected
3. Ask for redaction

**Example:**
```
I detected confidential information (credentials, API keys).

Please remove sensitive data before proceeding:
- Use placeholders instead of actual credentials
- Reference confidential docs by link (don't paste contents)
```

### MCP Tool Error

**Scenario:** MCP tool returns an error when creating the initiative.

**Action:**
1. Parse error message
2. Provide user-friendly explanation
3. Suggest corrective action

**Common errors:**
- **"Issue type 'Initiative' not available"** → Check if project supports Initiatives
- **"Field 'customfield_xyz' does not exist"** → Remove unsupported custom field

## Examples

### Example 1: Complete Initiative

**Input:**
```bash
/jira:create initiative HCMPE "Modernize CI/CD Pipeline Infrastructure"
```

**Interactive prompts collect:**
- Goal (operational excellence, developer productivity, technical debt reduction)
- Benefit hypothesis (cost savings, reduced operational overhead, improved reliability)
- SMART success criteria (build time, success rate, developer NPS)
- Scope (included: migration, caching, security; NOT included: log aggregation, prod deployment)
- Timeline (6 months, Q1-Q2 2026 milestones)

**Result:**
- Complete initiative with strategic framing
- All conventions applied
- Ready for feature/epic planning

### Example 2: Initiative with Component Detection

**Input:**
```bash
/jira:create initiative HCMPE "Improve System Observability and Monitoring Capabilities"
```

**Auto-detected:**
- Component: Platform Engineering
- Strategic goal: Operational excellence

**Result:**
- Initiative with appropriate component
- Clear observability scope

## Best Practices Summary

1. **Strategic framing:** Always articulate goal and strategic value
2. **SMART success criteria:** Define specific, measurable metrics
3. **Multi-feature/epic scope:** Initiative should contain 2-5 features/epics
4. **Clear scope boundaries:** Explicitly define what's in and what's out
5. **Realistic timeline:** ~6 months or single release typical
6. **Benefit-focused:** Clearly articulate expected outcomes and value
7. **Dependency awareness:** Identify and document blockers

## Anti-Patterns to Avoid

❌ **Initiative is actually a feature or epic**
```
"Add security scanning to pipeline" (single capability, 1-2 months)
```
✅ Too small, create as Feature or Epic

❌ **No strategic context**
```
"Fix CI/CD problems"
```
✅ Must explain strategic goal and expected benefits

❌ **Vague success criteria**
```
"Pipeline works better"
```
✅ Use SMART metrics: "Build time <15min, >95% success rate, Developer NPS 8/10"

❌ **No scope definition**
```
"Modernize everything"
```
✅ Define specific deliverables and explicitly exclude related work

## Workflow Summary

1. ✅ Parse command arguments (project, summary)
2. 🔍 Auto-detect component from summary keywords
3. ⚙️ Apply project-specific defaults
4. 💬 Interactively collect goal and strategic context
5. 💬 Interactively collect benefit hypothesis
6. 💬 Interactively collect SMART success criteria
7. 💬 Collect scope definition (included + NOT included)
8. 💬 Collect responsibilities and dependencies
9. 🔒 Scan for sensitive data
10. ✅ Validate initiative quality and scope
11. 📝 Format description with Markdown
12. ✅ Create initiative via MCP tool
13. 📤 Return issue key and URL

## See Also

- `/jira:create` - Main command that invokes this skill
- `create-feature` skill - For features within initiatives
- `create-epic` skill - For epics within features
- Platform engineering and technical excellence resources
