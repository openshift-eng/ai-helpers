---
description: Query LDAP directory with natural language questions
argument-hint: <question>
---

## Name
ldap:ask

## Synopsis
```
/ldap:ask <question>
```

## Description
Ask natural language questions about the LDAP directory. The command parses your question and returns the relevant information.

**Example questions:**
- "find user jsmith"
- "who is manager of jdoe"
- "what groups does jsmith have"
- "who is in group engineering-team"

## Implementation

1. **Check ldapsearch is available**: Verify `ldapsearch` is installed
   - macOS: `brew install openldap`
   - RHEL/Fedora: `dnf install openldap-clients`
   - Ubuntu/Debian: `apt-get install ldap-utils`

2. **Configure LDAP**: Use environment variables `LDAP_HOST` and `LDAP_BASE_DN`, or defaults:
   - Host: `ldap://ldap.corp.redhat.com`
   - Base DN: `dc=redhat,dc=com`

3. **Parse question**: Determine query type and extract search terms from the natural language question

5. **Format output**: Return results in simple, readable format

**Query types:**
- User info: Search by uid, email, or name → return user details
- Manager: Look up user's manager DN → resolve manager details
- User's groups: Find all groups where user is a member (check `member`, `memberUid`, `uniqueMember`)
- Group members: List all members of a group

## Examples

```
/ldap:ask find user jsmith
/ldap:ask who is manager of jdoe
/ldap:ask what groups does jsmith have
/ldap:ask who is in group engineering-team
```

## Arguments
- Natural language question about users, managers, or groups
