---
name: JIRA Activity Type Categorizer
description: Detailed categorization logic for assigning JIRA tickets to activity type categories
command: /jira:categorize-activity-type
---

# JIRA Activity Type Categorizer - Implementation Guide

You are an expert JIRA ticket categorization specialist with deep knowledge of software development workflows, operational patterns, and engineering activities. This skill provides detailed categorization logic for the `/jira:categorize-activity-type` command.

## When to Use This Skill

This skill is invoked automatically by the `/jira:categorize-activity-type` command to analyze JIRA tickets and assign activity type categories.

## Prerequisites

- MCP Jira server must be configured (see [plugin README](../../README.md))
- MCP tools available: `mcp__atlassian__jira_get_issue`, `mcp__atlassian__jira_update_issue`
- Access to JIRA instance with Activity Type custom field (`customfield_12320040`)

## Activity Type Categories

1. **Associate Wellness & Development**
   - Professional growth, training, learning, team building, and employee development activities
   - Examples: Conference attendance, training sessions, mentoring, onboarding, knowledge sharing

2. **Incidents & Support**
   - Production incidents, customer support, troubleshooting, emergency fixes, and reactive operational work
   - Examples: Outages, customer escalations, hotfixes, emergency deployments, support tickets

3. **Security & Compliance**
   - Security vulnerabilities, compliance requirements, security patches, audits, and regulatory work
   - Examples: CVE remediation, security audits, penetration testing, compliance reports

4. **Quality / Stability / Reliability**
   - Bug fixes, test improvements, reliability enhancements, technical debt reduction, and quality initiatives
   - Examples: Bug fixes, flaky test resolution, crash fixes, error handling improvements, test coverage

5. **Future Sustainability**
   - Infrastructure improvements, developer experience enhancements, automation, tooling, and proactive technical investments
   - Examples: Refactoring, CI/CD improvements, developer tooling, observability, technical debt cleanup

6. **Product / Portfolio Work**
   - Feature development, product enhancements, new capabilities, and planned product roadmap items
   - Examples: New features, user-facing enhancements, MVPs, product requirements, roadmap items

## Categorization Methodology

### 1. Primary Analysis Sources (Priority Order)

Analyze these data sources in order of importance:

1. **Ticket Summary (title)** - Often contains key indicator words and intent
2. **Ticket Description** - Provides detailed context, acceptance criteria, and technical details
3. **Issue Type** - Bug, Story, Task, Vulnerability, Weakness, Epic, Sub-task
4. **Parent Epic/Story details** - Inherit context from parent when ticket is a child
5. **Labels and metadata** - Additional classification hints (e.g., "technical-debt", "security")

### 2. Issue Type Heuristics

Apply these default mappings based on issue type, then validate/override with keyword analysis:

| Issue Type | Default Category | Initial Confidence | Override Conditions |
|------------|------------------|-------------------|---------------------|
| Vulnerability | Security & Compliance | High | Rarely override |
| Weakness | Security & Compliance | Medium-High | Override if clearly not security |
| Bug (with security keywords) | Security & Compliance | High | Never override |
| Bug (standard) | Quality / Stability / Reliability | High | Override if infrastructure/sustainability focus |
| Story (product-focused) | Product / Portfolio Work | Medium | Override if operational/infrastructure |
| Story (operational) | Future Sustainability | Medium | Override if customer-facing |
| Task (Epic child) | Inherit from Epic | Medium | Override with strong keywords |
| Task (standalone) | Analyze keywords | Low | Always analyze |
| Epic | Analyze keywords + children | Low | Always analyze |

**Critical rule:** Security-related content ALWAYS takes precedence over other categorizations.

### 3. Keyword Indicators

Scan the combined text (summary + description) for these keyword patterns:

#### Incidents & Support
**Primary keywords:** `incident`, `outage`, `customer issue`, `support ticket`, `emergency`, `hotfix`, `production down`, `urgent fix`

**Contextual phrases:**
- "customer reported"
- "production failure"
- "emergency deployment"
- "service degradation"
- "immediate attention required"

**Scoring:** 3+ matches = High confidence

#### Security & Compliance
**Primary keywords:** `CVE`, `vulnerability`, `security patch`, `compliance`, `audit`, `penetration test`, `authentication`, `authorization`, `privilege escalation`, `XSS`, `SQL injection`

**Patterns:**
- CVE identifiers (CVE-YYYY-NNNNN)
- Security advisory references
- OWASP mentions
- Compliance framework names (SOC2, HIPAA, PCI-DSS)

**Scoring:** 1+ match = High confidence (security is critical)

#### Quality / Stability / Reliability
**Primary keywords:** `bug`, `flaky test`, `memory leak`, `crash`, `error handling`, `test coverage`, `intermittent failure`, `race condition`, `deadlock`, `timeout`, `retry logic`

**Contextual phrases:**
- "fix crashes"
- "improve stability"
- "reduce flakiness"
- "handle errors"
- "prevent failures"

**Scoring:** 2+ matches = High confidence

#### Future Sustainability
**Primary keywords:** `refactor`, `technical debt`, `developer experience`, `CI/CD`, `automation`, `tooling`, `infrastructure`, `observability`, `monitoring`, `alerting`, `logging`, `performance optimization`, `build time`

**Contextual phrases:**
- "improve development workflow"
- "reduce build time"
- "enhance developer productivity"
- "automate manual process"
- "infrastructure as code"
- "observability improvements"

**Scoring:** 3+ matches = High confidence

#### Product / Portfolio Work
**Primary keywords:** `feature`, `enhancement`, `capability`, `user story`, `requirement`, `MVP`, `roadmap`, `customer request`, `new functionality`, `user-facing`

**Contextual phrases:**
- "new functionality"
- "user-facing change"
- "product requirement"
- "customer-requested feature"
- "roadmap item"

**Scoring:** 2+ matches = Medium-High confidence

#### Associate Wellness & Development
**Primary keywords:** `training`, `learning`, `conference`, `onboarding`, `mentoring`, `knowledge sharing`, `team building`, `career development`, `workshop`, `certification`

**Contextual phrases:**
- "attend conference"
- "training session"
- "professional development"
- "team offsite"
- "knowledge transfer"

**Scoring:** 1+ match = High confidence (usually clear and unambiguous)

### 4. Parent Context Inheritance

When a ticket is a subtask or linked to an Epic, apply inheritance logic:

#### Inheritance Process

1. **Fetch Parent Epic/Story:**
   ```python
   if parent_key:
       parent_issue = mcp__atlassian__jira_get_issue(
           issue_key=parent_key,
           fields="summary,customfield_12320040"
       )
       parent_summary = parent_issue["fields"].get("summary", "")
       parent_activity_type = parent_issue["fields"].get("customfield_12320040", {}).get("value", None)
   ```

2. **Evaluate Parent Category:**
   - **If parent has Activity Type already set:**
     - Inherit parent category if ticket has no strong contradicting keywords
     - Set confidence to Medium
     - Note in reasoning: "Inherited from parent Epic {parent_key}"

   - **If parent Activity Type not set, analyze parent summary:**
     - Apply keyword scanning to parent summary (e.g., "Security Remediation Q4" → Security & Compliance)
     - Use inferred category with Low-Medium confidence
     - Note in reasoning: "Inferred from parent Epic title"

3. **Override Parent When Appropriate:**
   - If ticket has 3+ strong keywords contradicting parent → override with High confidence
   - If ticket is clearly different nature than parent → override with Medium confidence
   - Example: Parent Epic = "Product Feature X" (Product Work), but child task = "Set up CI pipeline" (Future Sustainability)

#### Parent Context Examples

**Strong inheritance:**
- Parent Epic: "Security Remediation Q4" → Child tasks likely "Security & Compliance"
- Parent Epic: "Developer Experience Improvements" → Child tasks likely "Future Sustainability"

**Override parent:**
- Parent Epic: "User Dashboard Feature" (Product Work)
- Child Task: "Fix crash in dashboard rendering" → Override to "Quality / Stability / Reliability"

### 5. Ambiguity Resolution

When multiple categories seem applicable, use this priority order:

#### Priority Hierarchy (Highest to Lowest)

1. **Security & Compliance** - ALWAYS wins if security-related
2. **Incidents & Support** - Takes precedence for production emergencies
3. **Explicit Keyword Evidence** - Strong keyword matches override issue type
4. **Issue Type Heuristic** - Default to type-based categorization
5. **Parent Inheritance** - Use parent Epic category when keywords weak
6. **Low Confidence + User Clarification** - When completely unclear, report Low confidence

#### Common Ambiguity Cases

**Case 1: Bug that improves infrastructure**
- Example: "Fix slow build times in CI pipeline"
- Resolution: **Future Sustainability** (primary intent is infrastructure improvement, not fixing user-facing bug)
- Confidence: Medium-High

**Case 2: Feature that addresses security**
- Example: "Add two-factor authentication support"
- Resolution: **Security & Compliance** (security always wins)
- Confidence: High

**Case 3: Task with no Epic and minimal description**
- Example: "Update documentation"
- Resolution: Analyze what documentation (user-facing → Product, developer → Sustainability)
- Confidence: Low or Medium (depends on available context)

**Case 4: Operational story vs. product story**
- Example: "Improve database query performance"
- Resolution: If user-facing performance → **Product Work**, if backend optimization → **Future Sustainability**
- Confidence: Medium (requires careful reading)

## Implementation Steps

### Step 1: Extract and Normalize Ticket Data

```python
# Extract core fields
summary = issue_data["fields"]["summary"]
description = issue_data["fields"].get("description", "") or ""
issue_type = issue_data["fields"]["issuetype"]["name"]
labels = issue_data["fields"].get("labels", [])
parent_key = issue_data["fields"].get("parent", {}).get("key", None)
components = [c["name"] for c in issue_data["fields"].get("components", [])]
current_activity_type = issue_data["fields"].get("customfield_12320040", {}).get("value", None)

# Normalize text for keyword matching
combined_text = (summary + " " + description).lower()
```

### Step 2: Apply Issue Type Heuristic

```python
initial_category = None
initial_confidence = "Low"

if issue_type in ["Vulnerability", "Weakness"]:
    initial_category = "Security & Compliance"
    initial_confidence = "High" if issue_type == "Vulnerability" else "Medium-High"

elif issue_type == "Bug":
    # Check for security keywords first
    security_keywords = ["cve", "security", "vulnerability", "exploit", "xss", "injection", "privilege"]
    if any(kw in combined_text for kw in security_keywords):
        initial_category = "Security & Compliance"
        initial_confidence = "High"
    else:
        initial_category = "Quality / Stability / Reliability"
        initial_confidence = "High"

elif issue_type == "Story":
    # Default to Product Work, but will be validated by keywords
    initial_category = "Product / Portfolio Work"
    initial_confidence = "Medium"

elif issue_type == "Task":
    # Tasks need more analysis - check parent or keywords
    initial_category = None  # Will be determined by parent or keywords
    initial_confidence = "Low"

elif issue_type == "Epic":
    # Epics need keyword analysis
    initial_category = None
    initial_confidence = "Low"
```

### Step 3: Keyword Scanning and Scoring

```python
# Define keyword sets
keyword_categories = {
    "Incidents & Support": [
        "incident", "outage", "customer issue", "support ticket", "emergency",
        "hotfix", "production down", "urgent fix", "customer reported",
        "service degradation"
    ],
    "Security & Compliance": [
        "cve", "vulnerability", "security patch", "compliance", "audit",
        "penetration test", "authentication", "authorization", "privilege",
        "xss", "injection", "exploit"
    ],
    "Quality / Stability / Reliability": [
        "bug", "flaky test", "memory leak", "crash", "error handling",
        "test coverage", "intermittent", "race condition", "deadlock",
        "timeout", "retry logic", "stability"
    ],
    "Future Sustainability": [
        "refactor", "technical debt", "developer experience", "ci/cd",
        "automation", "tooling", "infrastructure", "observability",
        "monitoring", "alerting", "performance optimization", "build time"
    ],
    "Product / Portfolio Work": [
        "feature", "enhancement", "capability", "user story", "requirement",
        "mvp", "roadmap", "customer request", "new functionality", "user-facing"
    ],
    "Associate Wellness & Development": [
        "training", "learning", "conference", "onboarding", "mentoring",
        "knowledge sharing", "team building", "career development",
        "workshop", "certification"
    ]
}

# Count keyword matches for each category
keyword_scores = {}
for category, keywords in keyword_categories.items():
    score = sum(1 for kw in keywords if kw in combined_text)
    keyword_scores[category] = score

# Find dominant category based on keywords
dominant_category = max(keyword_scores, key=keyword_scores.get)
dominant_score = keyword_scores[dominant_category]
```

### Step 4: Determine Final Category

```python
final_category = initial_category
final_confidence = initial_confidence
reasoning_notes = []

# Security ALWAYS wins if keywords present
if keyword_scores["Security & Compliance"] >= 1:
    final_category = "Security & Compliance"
    final_confidence = "High"
    reasoning_notes.append("Security-related content takes precedence")

# Strong keyword evidence (3+ matches)
elif dominant_score >= 3:
    final_category = dominant_category
    final_confidence = "High"
    reasoning_notes.append(f"Strong keyword evidence ({dominant_score} matches)")

# Moderate keyword evidence (1-2 matches)
elif dominant_score >= 1 and dominant_category != initial_category:
    final_category = dominant_category
    final_confidence = "Medium"
    reasoning_notes.append(f"Keyword evidence ({dominant_score} matches) overrides issue type")

# No strong keywords, use issue type heuristic
elif initial_category:
    final_category = initial_category
    final_confidence = initial_confidence
    reasoning_notes.append("Based on issue type heuristic")

# No clear category, check parent
elif parent_key:
    # Attempt parent inheritance (see Step 5)
    pass

# Still no category
else:
    final_category = "Product / Portfolio Work"  # Safe default
    final_confidence = "Low"
    reasoning_notes.append("Insufficient evidence, using default")
```

### Step 5: Parent Inheritance (If Needed)

```python
if not final_category and parent_key:
    try:
        parent_issue = mcp__atlassian__jira_get_issue(
            issue_key=parent_key,
            fields="summary,customfield_12320040"
        )
        parent_summary = parent_issue["fields"].get("summary", "")
        parent_activity_type = parent_issue["fields"].get("customfield_12320040", {}).get("value", None)

        if parent_activity_type:
            # Parent has Activity Type already set
            final_category = parent_activity_type
            final_confidence = "Medium"
            reasoning_notes.append(f"Inherited from parent Epic {parent_key}")
        elif parent_summary:
            # Parent has no Activity Type, analyze summary for keywords
            parent_text = parent_summary.lower()
            for category, keywords in keyword_categories.items():
                score = sum(1 for kw in keywords if kw in parent_text)
                if score >= 1:
                    final_category = category
                    final_confidence = "Low" if score == 1 else "Medium"
                    reasoning_notes.append(f"Inferred from parent Epic title: {parent_summary}")
                    break
    except Exception as e:
        # Parent fetch failed, log and continue without inheritance
        reasoning_notes.append(f"Could not fetch parent Epic {parent_key}: {str(e)}")
```

### Step 6: Confidence Adjustment

```python
# Increase confidence
if keyword_scores.get(final_category, 0) >= 3:
    final_confidence = "High"
elif issue_type in ["Vulnerability"] and final_category == "Security & Compliance":
    final_confidence = "High"

# Decrease confidence
if not description or len(description) < 50:
    if final_confidence == "High":
        final_confidence = "Medium"
    reasoning_notes.append("Limited context due to short/missing description")

if keyword_scores.get(final_category, 0) == 0 and not parent_key:
    final_confidence = "Low"
    reasoning_notes.append("No supporting keyword evidence")
```

### Step 7: Generate Structured Output

```python
# Collect evidence
evidence_points = []
evidence_points.append(f"Issue Type: {issue_type}")

if keyword_scores.get(final_category, 0) > 0:
    # Find which keywords matched
    matched_keywords = [kw for kw in keyword_categories[final_category] if kw in combined_text]
    evidence_points.append(f"Summary/Description contains: {', '.join(matched_keywords[:3])}")

if parent_key:
    evidence_points.append(f"Parent Epic: {parent_key}")

if labels:
    evidence_points.append(f"Labels: {', '.join(labels[:3])}")

# Build reasoning
reasoning = f"{' '.join(reasoning_notes)}. "

if issue_type == "Bug" and final_category == "Quality / Stability / Reliability":
    reasoning += "This is a standard bug fix addressing system stability and reliability. "
elif issue_type == "Vulnerability":
    reasoning += "This is a security vulnerability that must be addressed through security remediation processes. "
elif final_category == "Future Sustainability":
    reasoning += "This work focuses on improving infrastructure, tooling, or developer experience for long-term sustainability. "
elif final_category == "Product / Portfolio Work":
    reasoning += "This work delivers user-facing features or product enhancements aligned with the roadmap. "

# Format output
output = f"""
Activity Type: {final_category}
Confidence: {final_confidence}

Reasoning: {reasoning}

Key Evidence:
{chr(10).join('- ' + point for point in evidence_points)}
"""

return {
    "category": final_category,
    "confidence": final_confidence,
    "reasoning": reasoning,
    "evidence": evidence_points,
    "output": output
}
```

## Quality Standards

- **Be decisive but honest** - Choose a category, but clearly state confidence level
- **Always cite evidence** - Reference specific ticket data in reasoning
- **Consider multiple sources** - Don't rely on a single indicator
- **Prioritize security** - Security-related content always takes precedence
- **Never invent data** - Only use information present in the ticket
- **Explain uncertainty** - If confidence is Low, explain why and what's missing

## Error Handling

### Missing or Incomplete Data

**Missing description:**
```python
if not description or len(description) < 20:
    # Lower confidence
    if final_confidence == "High":
        final_confidence = "Medium"
    # Note in reasoning
    reasoning_notes.append("Limited context due to missing/short description")
```

**No parent Epic (for Tasks):**
```python
if issue_type == "Task" and not parent_key:
    # Rely heavily on keywords
    if keyword_scores.get(final_category, 0) == 0:
        final_confidence = "Low"
        reasoning_notes.append("No parent Epic context available")
```

**Unknown issue type:**
```python
if issue_type not in ["Bug", "Story", "Task", "Epic", "Vulnerability", "Weakness"]:
    # Treat as generic task
    initial_category = None
    initial_confidence = "Low"
    reasoning_notes.append(f"Uncommon issue type: {issue_type}")
```

### MCP Errors

**Parent fetch failure:**
```python
try:
    parent_issue = mcp__atlassian__jira_get_issue(
        issue_key=parent_key,
        fields="summary,customfield_12320040"
    )
except Exception as e:
    # Continue without parent context
    reasoning_notes.append("Could not fetch parent Epic details")
```

## Output Examples

### Example 1: High Confidence Bug Fix

```text
Activity Type: Quality / Stability / Reliability
Confidence: High

Reasoning: Based on issue type heuristic. This is a Bug issue type focused on fixing a
memory leak in the scanner component. Memory leaks directly impact system stability and
reliability. The description mentions "intermittent crashes" and "resource exhaustion,"
which are classic reliability concerns. No security implications mentioned, and this is
a proactive fix rather than a customer-facing incident.

Key Evidence:
- Issue Type: Bug
- Summary/Description contains: memory leak, crash, intermittent
- No security keywords present
```

### Example 2: Medium Confidence with Parent Inheritance

```text
Activity Type: Future Sustainability
Confidence: Medium

Reasoning: Inherited from parent Epic ROX-25641. Keyword evidence (2 matches) supports
categorization. This task is part of a larger developer experience improvement initiative
focused on enhancing CI/CD pipeline performance.

Key Evidence:
- Issue Type: Task
- Summary/Description contains: automation, build time
- Parent Epic: ROX-25641
- Labels: technical-debt
```

### Example 3: Security Vulnerability (Always High)

```text
Activity Type: Security & Compliance
Confidence: High

Reasoning: Security-related content takes precedence. This is a Vulnerability issue type
requiring immediate security remediation. The ticket references CVE-2024-12345 and
describes a privilege escalation vulnerability in the authentication module.

Key Evidence:
- Issue Type: Vulnerability
- Summary/Description contains: CVE-2024-12345, privilege escalation, authentication
- Labels: security
```

### Example 4: Low Confidence (Needs Clarification)

```text
Activity Type: Product / Portfolio Work
Confidence: Low

Reasoning: Insufficient evidence, using default. The ticket has minimal description and
no clear keyword indicators. Issue type is Task with no parent Epic context available.

Key Evidence:
- Issue Type: Task
- Summary: "Update configuration"
- No parent Epic context available
- No supporting keyword evidence
```

Note: For Low confidence, the command should always prompt the user for confirmation
before applying, even with `--auto-apply` flag.
