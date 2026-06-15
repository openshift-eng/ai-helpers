# Jobs to Be Done (JTBD) framework for documentation planning

Reference material for documentation planning. Covers JTBD methodology, content journey mapping, and JTBD-based module planning.

## Why JTBD matters for documentation planning

Applying JTBD to documentation planning produces measurable improvements:

- **Reduces topic proliferation**: Unless a new feature corresponds to a genuinely new user job, new enhancements are updates to existing job-based topics — not new parent topics.
- **Addresses emotional and social dimensions**: Jobs have functional, emotional, and social aspects. Users want peace of mind, to feel secure, and to look competent to their peers. Documentation that acknowledges these dimensions (e.g., "reliably," "with confidence," "without risking data loss") resonates more strongly than purely functional descriptions.
- **Improves AI and search discoverability**: As documentation is ingested by AI and search engines, outcome-focused content surfaces solutions for users trying to resolve their business problems — not just product names.
- **Reduces support queries**: Intuitive, job-aligned documentation reduces mental effort and frustration, leading to fewer support tickets.
- **Creates timeless structure**: Jobs do not change over time. While the technology used to accomplish them evolves, the fundamental user need remains the same — making JTBD-organized documentation inherently stable.

## Core JTBD principles

1. **Organize by outcomes, not features**: Structure documentation around user goals (main jobs) rather than internal product modules or feature names.

2. **Follow the JTBD hierarchy**: Implement a three-level granularity structure:
   - **Category** (`job_map_stage`) → **Main Job** (`main_job`) → **User Story** (`user_story`)

   This maps to the `granularity` field in JTBD records: `main_job` (stable, high-level goals, ~10-15 per guide), `user_story` (persona-specific implementation paths, 2-7 per main job), and `procedure` (step-by-step instructions).

3. **Frame the user's job**: Before planning any content, identify the job statement:
   - "When [situation], I want to [motivation], so I can [expected outcome]"
   - This job statement informs planning decisions but does NOT appear in final documentation

4. **Distinguish JTBD from User Stories**: JTBD and user stories are complementary but distinct:

   | Dimension | JTBD | User Story |
   |-----------|------|------------|
   | Format | "When [situation], I want to [motivation], so I can [outcome]" | "As a [user], I want [goal] so that [benefit]" |
   | Focus | **What** the user wants to achieve + **Why** it matters | **How** the user will use a specific feature |
   | Scope | High-level, broad — overarching user goals | Detailed, specific — single actionable task |
   | Granularity | `main_job` (Parent Topics) | `user_story` (child modules) |

   A single JTBD (`main_job`) contains multiple user stories. Use JTBD to define navigation and parent topics; use user stories to plan the child modules within each parent topic.

5. **Use natural language**: Avoid product-specific buzzwords or internal vocabulary. Use terms users naturally use when searching for solutions.

6. **Draft outcome-driven titles**:
   - **Bad**: "Ansible Playbook Syntax" (feature-focused)
   - **Good**: "Define automation workflows" (outcome-focused)

7. **Apply active phrasing**: Use imperatives and task-oriented verbs (e.g., "Set up," "Create," "Control") and state the context or benefit when helpful.

8. **Use industry-standard terminology when appropriate**: Industry-standard terms (SSL, HTTP, OAuth, API, RBAC, CI/CD) are acceptable in titles and content. Avoid *product-specific* vocabulary (e.g., internal feature names), but do not avoid universally understood technical terms.

9. **State the benefit or context in titles**: When two titles could sound similar, add context to differentiate:
   - **Bad**: "Managing Roles and Permissions"
   - **Good**: "Control team access with roles and permissions"

   Technique: reverse-engineer titles from job statements. Write the user story ("As a [user], I want to [goal], so that I can [benefit]"), then extract a title from the goal and benefit.
   - User story: "As a project manager, I want to export task reports so I can review team progress."
   - Title: "Review team progress by exporting task reports"

10. **Use only approved JTBD categories**: Structure documentation according to the `job_map_stage` values defined in the jtbd-tools schema. Do not create new categories. Use title case exactly as shown.
   - Get Started
   - Plan
   - Architecture
   - Configure
   - Deploy
   - Upgrade
   - Migrate
   - Develop
   - Administer
   - Operate
   - Observe
   - Monitor
   - Analyze
   - Secure
   - Extend
   - Training
   - Troubleshoot
   - Reference
   - What's New

## Content journey mapping

JTBD provides the **why** — the user's underlying motivation and desired outcome. Content journeys provide the **how** and **where** — the specific steps a user takes and where content can best assist them. Always define the JTBD first, then use content journeys to identify lifecycle gaps — areas where documentation exists for advanced use but is missing for initial discovery, or vice versa.

### The 5-phase content journey

| Phase | User mindset | Documentation purpose | Examples |
|-------|-------------|----------------------|----------|
| **Expand** | Discovery, awareness, first impressions | Help users understand the product exists and what problem it solves | Landing pages, overviews, "what is X" concepts |
| **Discover** | Understanding the technology, evaluating fit | Help users evaluate whether the product fits their needs | Architecture overviews, comparison guides, feature lists |
| **Learn** | Hands-on trial, tutorials, guided experience | Help users get started and build initial competence | Getting started guides, tutorials, quickstarts |
| **Evaluate** | Committing to the solution, early production use | Help users move from trial to production | Installation, configuration, migration procedures |
| **Adopt** | Day-to-day use, optimization, advocacy | Help users operate, optimize, and troubleshoot | Operations guides, troubleshooting, API references |

### How to apply

- After planning modules, tag each with its primary journey phase
- Identify phase gaps: strong Learn content but weak Expand content suggests users can follow tutorials but cannot discover the product
- Use phase distribution to inform prioritization — a product with no Expand content may need high-priority overview modules

## Module planning with JTBD

For each documentation need, follow these steps:

### Step 1: Define the job statement (internal planning only)
- "When [situation], I want to [motivation], so I can [expected outcome]"
- Example: "When I have a new application ready for deployment, I want to configure the runtime environment, so I can run my application reliably in production."

### Step 1b: Check for existing jobs before creating new parent topics
- Before creating a new parent topic, check whether the user's goal is already covered by an existing job in the documentation.
- Unless a new feature corresponds to a genuinely new user job, it should be an update to an existing job-based topic — not a new parent topic.
- Only create a new parent topic when the user's goal is fundamentally distinct from all existing jobs.
- This prevents topic proliferation and keeps the documentation structure stable over time.

### Step 2: Map to the JTBD hierarchy
- **Category** (`job_map_stage`): Broad area, must be selected from the approved list above
- **Main Job** (`main_job`): The user's main goal (e.g., "Deploy applications to production")
- **User Stories** (`user_story`): Specific steps to achieve the goal (e.g., "Configure the runtime," "Set up monitoring")

TOC nesting rules:
- Headings in TOCs must not exceed **3 levels** of nesting.
- **Categories do not count** toward nesting depth because they contain no content — they are organizational groupings only.
- Example: `Configure (category) → Control access to resources (main_job, level 1) → Set up RBAC (user_story, level 2) → RBAC configuration options (reference, level 3)`

### Step 3: Plan Parent Topics

Every `main_job` must have a Parent Topic that serves as the starting point for users looking to achieve the desired outcome. Parent Topic descriptions serve both human readers and AI/search engines — including "the what" and "the why" helps both audiences find the right content.

Parent Topics must include:
- A product-agnostic title using natural language (this becomes the TOC entry for the job)
- A description of "the what" (the desired outcome) and "the why" (the motivation/benefit)
- A high-level overview of how the product helps users achieve this specific goal
- An overview of the high-level steps to achieve the goal, with links to related content

Example Parent Topic outline:
```
Title: Improve application performance
Description: [What] Tune the platform for demanding workloads. [Why] Keep applications responsive and resource usage efficient.
Overview: The product provides tools for resource allocation, pod scheduling, and workload profiling.
High-level steps: 1. Profile workloads → 2. Configure resource limits → 3. Monitor results
```

### Step 4: Recommend module types
- CONCEPT - For explaining what something is and why it matters (supports understanding the job)
- PROCEDURE - For step-by-step task instructions (helps complete the job)
- REFERENCE - For lookup data (tables, parameters, options) (supports job completion)

### Step 5: Assembly organization
- Group related modules into user story assemblies organized by main jobs
- Define logical reading order based on job completion flow
- Identify shared prerequisites
