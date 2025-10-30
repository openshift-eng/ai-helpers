---
description: Test and verify JIRA MCP server authentication setup
---

## Name
jira:test-auth

## Synopsis
```
/jira:test-auth
```

## Description
The `jira:test-auth` command helps users verify their JIRA MCP server configuration and authentication setup. It performs a series of diagnostic tests to ensure the MCP server is properly configured, credentials are valid, and permissions are correctly set up.

This command is particularly useful for:
- Initial MCP server setup verification
- Troubleshooting authentication issues
- Confirming access to private projects
- Diagnosing permission problems

Key capabilities:
- Tests MCP server connectivity
- Verifies authentication credentials
- Checks read permissions
- Displays accessible project count
- Provides actionable setup guidance
- Shows current authentication status

## Implementation

The command executes the following diagnostic workflow:

1. **Check MCP Server Availability**
   - Attempt to call a lightweight MCP tool to test connectivity
   - Use `mcp__atlassian__jira_search_issues` with minimal JQL query
   - Example test query: `project is not EMPTY ORDER BY created DESC`
   - Record result: Available or Not Available
   - If not available, skip remaining tests and show setup instructions

2. **Test Authentication Credentials**
   - If MCP server is available, attempt authenticated operation
   - Try to search for a single issue to verify credentials
   - Verify response is valid JSON and contains expected fields
   - Record result: Valid, Invalid, or Cannot Verify
   - Extract user information if available from response

3. **Test Read Permissions**
   - Attempt a broader JQL search to test permissions
   - Query: `project is not EMPTY ORDER BY created DESC`
   - Limit to 50 results to avoid performance issues
   - Count number of accessible projects from results
   - Record result: OK (with count) or Failed

4. **Display Diagnostic Results**
   - Format output with clear visual indicators:
     - ✅ for successful tests
     - ❌ for failed tests
     - ⚠️ for warnings or partial success
   - Show each test result:
     - MCP Server status
     - Authentication status
     - User information (if available)
     - Read permissions status
     - Accessible project count
   - Display overall status with appropriate icon

5. **Provide Actionable Guidance**
   - If all tests pass:
     - Display: "Status: 🔐 Ready for authenticated mode"
     - Message: "All systems ready! JIRA commands will use authenticated mode."
   - If MCP server not available:
     - Display: "Status: 🌐 Public API mode only"
     - Provide setup instructions with links
     - Show command to configure MCP server
     - Remind to re-test after setup
   - If authentication fails:
     - Display error details
     - Provide token refresh instructions
     - Link to credential management pages
   - If permissions limited:
     - Show accessible project count
     - Explain potential limitations
     - Suggest checking project permissions

6. **Output Formatting**
   - Use clear section headers
   - Align status indicators consistently
   - Include relevant URLs for documentation
   - Keep output concise and actionable

**Error Handling:**
- Network errors: Display connectivity troubleshooting steps
- Invalid credentials: Provide token regeneration guidance
- Permission errors: Explain project access requirements
- MCP server errors: Show MCP server logs/debugging steps

**Performance Considerations:**
- Use minimal test queries to reduce load
- Limit result sets to 50 items
- Fail fast on unavailable MCP server
- Cache results not needed (diagnostic command)

## Return Value

**Success Case (All Tests Pass):**
```
JIRA Authentication Test
========================

✅ MCP Server: Connected
✅ Authentication: Valid
✅ User: john.doe@redhat.com
✅ Read Permissions: OK
✅ Accessible Projects: 15 found

Status: 🔐 Ready for authenticated mode

All systems ready! JIRA commands will use authenticated mode.
```

**Failure Case (MCP Not Available):**
```
JIRA Authentication Test
========================

❌ MCP Server: Not available
⚠️  Authentication: Cannot verify

Status: 🌐 Public API mode only

To enable authenticated mode:
1. Configure MCP server: plugins/jira/README.md#setting-up-jira-mcp-server
2. Required: JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
3. Run: claude mcp add atlassian npx @modelcontextprotocol/server-atlassian
4. Re-test with: /jira:test-auth
```

**Partial Success (Authentication Issues):**
```
JIRA Authentication Test
========================

✅ MCP Server: Connected
❌ Authentication: Invalid credentials
⚠️  Read Permissions: Cannot test (auth required)

Status: ⚠️ Authentication needs attention

To fix authentication:
1. Verify JIRA credentials are correct
2. Generate new API token: https://id.atlassian.com/manage-profile/security/api-tokens
3. For Red Hat JIRA, also set JIRA_PERSONAL_TOKEN: https://issues.redhat.com/secure/ViewProfile.jspa
4. Update MCP server configuration with new tokens
5. Re-test with: /jira:test-auth
```

## Examples

1. **Test authentication setup**:
   ```
   /jira:test-auth
   ```

   Performs complete diagnostic and displays results.

2. **After MCP server setup**:
   ```
   /jira:test-auth
   ```

   Verifies the new configuration is working correctly.

3. **Troubleshooting authentication errors**:
   ```
   /jira:test-auth
   ```

   Identifies which component (MCP, auth, permissions) is causing issues.

## Arguments

None - this command takes no arguments.
