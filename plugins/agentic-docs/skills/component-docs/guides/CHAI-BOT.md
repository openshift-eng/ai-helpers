# Chai-Bot Tribal Knowledge Enrichment

When hosted or external Chai Bot access is available, you MUST run both prompts below. Do not skip.

**Exhaust local sources first**: Read `docs/`, `docs/enhancements/`, and any local design/proposal docs before querying chai-bot. Only ask for things genuinely absent from the repo (operational incidents, Slack context, cross-component friction).

## Prompt 1 — Operational Knowledge

Run using the Chai Bot access path selected in `SKILL.md`. Substitute `{component}` with the repo name.

```
"I'm generating agentic documentation for {component}
(github.com/openshift/{component}).

I already have complete architecture, code structure, controller
design, Makefile targets, and API types from reading the source
code. DO NOT describe any of these — your answers about repo
internals will be wrong.

Instead, tell me ONLY things that cannot be learned from the
source code:

1. OPERATIONAL ISSUES: Production failures, support escalations,
   upgrade gotchas, or common misconfigurations discussed in
   Slack or filed in Jira. Include Jira keys if you know them.

2. CROSS-COMPONENT FRICTION: Misunderstood boundaries or
   surprising interactions between {component} and other
   OpenShift components (OLM, service-ca, console, CCO,
   monitoring, etc.).

Format each item as:
- Title (short)
- Source (Slack channel, Jira key, or 'team knowledge')
- Description (2-3 sentences max)

If you don't have tribal knowledge for a category, say so —
don't fill it with code observations."
```

## Prompt 2 — Design Rationale

Review your Phase 4 (Architecture) findings. Identify 3-5 patterns that are surprising, inconsistent, or divergent — where the code shows *what* but not *why*. Then run:

```
"I'm documenting design decisions for {component}
(github.com/openshift/{component}). I already know WHAT the
code does — I need to know WHY from Slack, Jira, or team
discussions.

For each question below, only answer if you have actual context
from Slack threads, Jira issues, PR discussions, or team
conversations. If you're guessing from code structure, say
'no tribal knowledge found' — that's more useful than inference.

1. [Specific divergence found in Phase 4]
2. [Another divergence]
3. [...]

For each answer, include the source (Slack channel/thread date,
Jira key, PR number) so I can trace it."
```

## Filtering

DISCARD any claims about repo internals (namespaces, file paths, Makefile targets, function names, controller structure) — chai-bot fabricates these. KEEP only Slack/Jira/docs knowledge that cannot be learned from code.

## Placement

No separate file — findings go where developers already look:
- Operational issues → `DEVELOPMENT.md` "Known Operational Issues" section
- Cross-component friction → `ARCHITECTURE.md` under "OpenShift Integration Points"
- Design rationale → `ARCHITECTURE.md` "Design References" section
