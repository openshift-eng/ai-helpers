# Risk

Type-specific guidance for creating Jira Risk issues representing uncertain future events that could negatively affect the project.

Risks track events that *might* happen, not work to be done. They require probability and impact assessment and, when known, a mitigation/contingency plan. Use a Story, Task, or Epic instead if the work is already decided and committed.

## Qualifying Criteria

Evaluate the user's description before proceeding. If it does not qualify as a Risk, say why and suggest a more appropriate type.

**Qualifies as a Risk when:**
- There is genuine uncertainty about whether/how it will happen
- It describes something that *might* happen, not something already known or existing
- The trigger is outside the team's full control (external dependencies, vendor decisions, timing)
- There is a credible scenario it materializes before the team can address it

**Does NOT qualify as a Risk:**
- The condition has already been resolved
- Too vague to assess (can't set probability, impact, or a response plan)
- Planned work with no time pressure — just a backlog item
- Open design question with active structured resolution underway
- Work already in progress with a known path

## Summary Format

Write the summary as a one-line risk statement using this pattern:

```
<event> could <consequence> due to <root cause>
```

Examples:
- "Cincinnati API outage could block new cluster creation due to version resolution dependency"
- "Upstream Kubernetes deprecation of node admission webhooks could require emergency rework due to tight release coupling"
- "Vendor contract renewal delay could pause GKE upgrade path due to dependency on partner SLA"

Keep it under 100 characters when possible. If the user provides a free-form description, reformat it into the pattern and confirm.

## Required Fields

Probability and Impact option IDs **must be fetched** via `getJiraIssueTypeMetaWithFields` for the GCP project using the Risk issue type before creation — they cannot be set by value name, only by option ID.

Before creating, also verify the Risk issue type exists in the GCP project via `getJiraProjectIssueTypesMetadata`.

### Risk Probability (`customfield_10642`)

| Level | Criteria |
|---|---|
| **Rare** | Theoretical; no precedent |
| **Unlikely** | Has happened elsewhere but conditions aren't present here |
| **Moderate** | Has happened before or some contributing factors exist today |
| **Likely** | Contributing factors active; expected without changes |
| **Very Likely** | Already showing early signs; matter of when, not if |

### Risk Impact (`customfield_10842`)

| Level | Criteria |
|---|---|
| **Annoyance** | Cosmetic/doc issue; no effect on delivery, service, or customers |
| **Low** | Small delay or workaround; single team/component; no customer-visible effect |
| **Moderate** | Noticeable milestone delay; partial service degradation; multi-team/component; SLO breach possible |
| **Medium** | Significant schedule slip (weeks); outage or data integrity issue; blocks other work; customer-facing; compliance risk |
| **High** | Delivery blocked; complete unavailability or data loss; security/compliance breach; all customers affected; regulatory consequences |

## Auto-Calculated Fields — Do Not Set

ScriptRunner automatically populates these when Probability and Impact are saved. **Never include them in the MCP create or edit call:**

- `customfield_10976` — Risk Score (calculated by ScriptRunner using non-linear impact weights; range 1–250)
- `customfield_10974` — Risk Score Assessment (Low / Low Med / Medium / Med Hi / High — derived from score)

## Optional Fields

Set these when the user provides or chooses to fill them:

| Field | Jira ID | Purpose |
|---|---|---|
| Risk Proximity | `customfield_10645` | How soon the risk could materialize |
| Risk Response | `customfield_10846` | Avoid / Mitigate / Transfer / Accept |
| Risk Category | `customfield_10679` | Technical / Schedule / Resource / External / etc. |

## Interactive Workflow

### 1. Qualifying Check

**Prompt:** "What is the uncertain future event you want to track? Describe what might happen and what trigger would cause it."

Evaluate against qualifying criteria. If it does not qualify as a Risk, explain why and suggest the appropriate type (Story, Task, Epic, or Spike).

### 2. Risk Statement (Summary)

**Prompt:** "How would you summarize this risk in one line?"

Apply the pattern: `<event> could <consequence> due to <root cause>`. If the user gives a free-form statement, reformat it and confirm before proceeding.

### 3. Context (Description)

Collect the three context elements:

- **What could go wrong:** Describe the risk event in detail
- **What triggers it:** Conditions or events that would cause it to materialize
- **What would be affected:** Teams, services, milestones, or customers

### 4. Probability Assessment

Show the probability scale above. **Prompt:** "Based on the criteria above, what probability level fits? (Rare / Unlikely / Moderate / Likely / Very Likely)"

Fetch option IDs via `getJiraIssueTypeMetaWithFields` before creation — do not set by name.

### 5. Impact Assessment

Show the impact scale above. **Prompt:** "If this risk materializes, what is the severity? (Annoyance / Low / Moderate / Medium / High)"

Fetch option IDs via `getJiraIssueTypeMetaWithFields` before creation — do not set by name.

### 6. Component

**Prompt:** "Which GCP component does this risk relate to? (e.g., hypershift-operator-gcp, gcp-hcp-infra)"

Fetch available components for the GCP project and present a list. This field is expected on all real risks.

### 7. Assignee (Risk Owner)

**Prompt:** "Who is the risk owner — responsible for monitoring and responding to this risk?"

The process doc defines the assignee as the person who shepherds the risk through its lifecycle. If the user is unsure, suggest leaving it unset (it can be assigned during triage), but note that unassigned risks are harder to track. Resolve to a Jira account ID via `lookupJiraAccountId` before setting.

### 8. Mitigation and Contingency Plan (Optional)

**Prompt:** "Do you have a mitigation or contingency plan yet? (Press Enter / say 'skip' to leave blank — this can be filled in during the Assess phase.)"

If provided: include the `_Mitigation/contingency plan:_` line in the description.
If skipped: omit that line entirely.

### 9. Optional Fields

**Prompt:** "Do you want to set any optional fields? (Skip to leave unset)"

- Risk Proximity — when could it materialize?
- Risk Response — Avoid / Mitigate / Transfer / Accept
- Risk Category — Technical / Schedule / Resource / External

## Description Template

Use inline italic labels matching the team's existing risk format — **not** markdown headers:

```markdown
_What could go wrong:_ <Describe the risk event in detail>

_What triggers it:_ <Conditions or events that would cause the risk to materialize>

_What would be affected:_ <Teams, services, milestones, or customers impacted>

_Mitigation/contingency plan:_ <Actions to reduce probability or impact; how to respond if it materializes. Omit this line if not yet assessed.>

_Originally raised: YYYY-MM-DD. Raised by: <reporter display name>._
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Anti-Patterns

- Already-in-progress work framed as a risk → create as Story or Task instead
- Vague risk that can't be assessed ("something might go wrong") → refine before creating
- Setting `customfield_10976` (Risk Score) or `customfield_10974` (Risk Score Assessment) manually → ScriptRunner auto-calculates from Probability and Impact
- Using option value names instead of fetched IDs for Probability or Impact → always fetch IDs first
