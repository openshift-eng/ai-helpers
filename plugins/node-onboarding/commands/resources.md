---
description: Print categorized bookmarks and links for Node team day-to-day work
---

## Name

node-onboarding:resources

## Synopsis

```text
/node-onboarding:resources
```

## Description

Prints a categorized list of useful links and bookmarks for Node team
members: Jira boards and filters, Slack channels, documentation, upstream
meetings, and support portals. Useful during onboarding and as an ongoing
quick-reference.

## Implementation

1. Read
   [references/resources.md](../references/resources.md).
2. Read the team-wide links from the node-team plugin's
   [shared/team-info.md](../../node-team/skills/node/references/shared/team-info.md):
   Key Links, Slack Channels, Mailing List and Groups, and Upstream
   Communities (meeting times). That link is relative to a repo checkout.
   When the plugin is installed, read the file from
   `"${CLAUDE_PLUGIN_ROOT}"/../../node-team/*/skills/node/references/shared/team-info.md`
   (glob the version directory), or invoke the `node-team:node` skill and
   read from its base directory. If it cannot be found, print the local
   bookmarks and say that the team-wide links are unavailable.
3. Merge both sources by category (Jira, Slack, Documentation, Google
   Groups, Upstream, Upstream Meetings, Support) and present each category
   as a section with a table of links. Do not list a link twice.

## Return Value

A formatted list of categorized resources with clickable URLs.
