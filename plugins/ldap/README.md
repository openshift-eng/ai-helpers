# LDAP Plugin

Natural language interface for querying LDAP directory information about users, managers, and groups.

## Commands

### `/ldap:ask <question>`

Ask natural language questions about users, managers, and groups in the LDAP directory. The command intelligently parses your question and returns the appropriate information.

**Supported question types:**
- User lookups: "find user jsmith", "who is jdoe", "show me info about John Smith"
- Manager lookups: "who is the manager of jsmith", "jdoe's manager"
- Email lookups: "what is the email of John Smith"
- Group members: "who are the members of engineering-team", "list members of hypershift-team"

**Useful for:**
- Quick lookups without remembering specific command syntax
- Natural interaction with LDAP directory
- Getting user, manager, and group information
- Finding contact details and organizational relationships

See [commands/ask.md](commands/ask.md) for complete details.

## Prerequisites

This plugin requires the LDAP client utilities to be installed on your system:

- **macOS**: `brew install openldap`
- **RHEL/Fedora**: `dnf install openldap-clients`
- **Ubuntu/Debian**: `apt-get install ldap-utils`

## Installation

```bash
/plugin install ldap@ai-helpers
```

## Configuration

Commands will attempt to auto-detect LDAP configuration from:
- `~/.ldaprc` file
- Environment variables: `LDAP_HOST`, `LDAP_BASE_DN`

For Red Hat/OpenShift engineers, the default configuration targets:
- Host: `ldap://ldap.corp.redhat.com`
- Base DN: `dc=redhat,dc=com`

You can customize these values in your `~/.ldaprc` file:

```text
URI ldap://your-ldap-server.com
BASE dc=your,dc=domain,dc=com
```

## Example Usage

```bash
# Find user information
/ldap:ask find user jsmith

# Get user's email
/ldap:ask what is the email of John Smith

# Find someone's manager
/ldap:ask who is the manager of jsmith

# List team members
/ldap:ask who are the members of engineering-team
```

## Security Note

LDAP queries typically use anonymous bind for read-only operations. These commands do not perform authentication or modify directory data.
