# GCP-HCP Skill Maintenance Guide

Sections of SKILL.md are sourced from upstream files in
openshift-online/gcp-hcp. When updating this skill, fetch the latest
content from the upstream sources and reconcile any changes.

## Upstream Sources

| SKILL.md Section                          | Upstream File                              |
|-------------------------------------------|--------------------------------------------|
| Story Template structure                  | docs/jira-story-template.md               |
| Story Sizing Guide (within story section) | docs/jira-story-template.md               |
| Epic Template structure                   | docs/jira-epic-template.md                |
| Feature Template structure                | docs/jira-feature-template.md             |
| Definition of Done                        | docs/definition-of-done.md                |

## Sync Instructions

When this skill needs updating (upstream templates changed, new sections added):

1. Fetch the latest content from each upstream file:
   - https://raw.githubusercontent.com/openshift-online/gcp-hcp/main/docs/jira-story-template.md
   - https://raw.githubusercontent.com/openshift-online/gcp-hcp/main/docs/jira-epic-template.md
   - https://raw.githubusercontent.com/openshift-online/gcp-hcp/main/docs/jira-feature-template.md
   - https://raw.githubusercontent.com/openshift-online/gcp-hcp/main/docs/definition-of-done.md
2. Compare against the embedded content in SKILL.md
3. Update SKILL.md with any new or changed content
4. Run `make lint` from the `ai-helpers` repo root to validate

## Notes on Intentional Omissions

The following upstream content was intentionally excluded from SKILL.md and should not be re-introduced during sync:

- **Feature Template worked example** (`jira-feature-template.md` "Example Feature" section): Omitted to keep SKILL.md focused on template structure rather than filled-in examples.
- **Epic Template worked example** (`jira-epic-template.md` "Example Epic" section): Omitted to keep SKILL.md focused on template structure rather than filled-in examples.

All upstream URLs reference the `main` branch. If the canonical branch changes, update the URLs above accordingly.
