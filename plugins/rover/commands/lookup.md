---
description: Look up a person in Red Hat's Rover directory by name, Kerberos ID, or email
argument-hint: <name, kerberos id, or email>
allowed-tools:
  - mcp__rover__get_person
  - mcp__rover__search_people
  - mcp__rover__get_org_chart
  - mcp__rover__get_team
  - mcp__rover__get_groups
---

## Name

rover:lookup

## Synopsis

```bash
/rover:lookup <name, kerberos id, or email>
```

## Description

Queries the Rover People directory to find a person and return their profile information. Accepts a display name, Kerberos uid, or email address.

Useful for quickly finding someone's role, manager, team, location, or contact details without leaving the terminal.

## Implementation

1. Determine whether the input looks like a Kerberos uid (short, no spaces), an email (contains `@`), or a display name.
2. If the input is a uid or email, call `get_person` directly.
3. If the input is a name or ambiguous, call `search_people` first to find matching entries, then call `get_person` on the best match.
4. Present a concise summary of the person's profile:
   - Name, uid, title, and department
   - Manager
   - Location and timezone
   - Email and IM handles
5. If no match is found, say so clearly and suggest alternative search terms.
