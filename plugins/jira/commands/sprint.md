---
description: Generate a sprint report
argument-hint: <board-id-or-name> [sprint-name] [--text]
---

## Name
jira:sprint

## Synopsis
```
/jira:sprint <board-id-or-name> [sprint-name] [--text]
```

## Description

Display a list of Jira issues for a specific sprint, given a scrum-type Jira board ID or board name.  The results can be displayed either on a web page or as plain text.  When displayed on a web page, you can sort on any column and view additional details about each issue.  When displayed as plain text, it is recommended to increase the width of your terminal.

## Implementation

Important: Always use the Jira API to get Jira information.

1. Determine which board ID the user wants from the <board-id-or-name> argument.
- If it's all digits, treat it as a board ID.  Get the Rapid Board based on the board ID and not the board name.
- If it's not all digits, treat it as a board name.  Get the Rapid Board based on this name, and filter to get only boards of type "scrum" (not "kanban").  If there are multiple matches, present the list and ask the user which one to select.

2. Display a table of Jira issues
- If a sprint name is given, get the information in the Sprint Report.
    - Create a table with the columns: Key, Summary, Assignee

- If no sprint name is given, get the information in Active sprints.  If there are more than one active sprint, it should get all of them.
    - Create a table with the columns: Key, Summary, Assignee, Status

3. If --text option, display a text-based table.  See the Output Format section for the example format.

4. If --text option is not given, it will be shown on a web page.
    - Create an aesthetic but simple HTML page from this data.  IMPORTANT: Don't show the HTML code that is generated; just save the file.
    - Use the data to create a JavaScript object.  Make sure all double quotes are escaped in this object, so there are no syntax errors.
    - Every column is sortable by clicking the column name.  On the first click, it sorts by ascending order.  On the second click, it sorts by descending order.  On the third click, it behaves like the first click and so on.  All the columns are sorted lexicographically except Key where it's sorted numerically after the dash character (e.g. NETOBSERV-2545 comes after NETOBSERV-300 in ascending order).
    - The keys (e.g. NETOBSERV-2545) should be links to the Jira issue (e.g. https://issues.redhat.com/browse/NETOBSERV-2545).
    - The table data for the key should not wrap (`<td nowrap>`).
    - Create a directory "www" if it doesn't exist.
    - Save the file as sprint-<board-id>-<sprint-name>.html (e.g. sprint-15335-282.html) in this directory.  If the file already exists, ask the user if they want to overwrite it. If overwrite, just replace the file in one shot.
    - Launch a browser and display the web page using a file URL.  Specify the file path as the argument (e.g. file:///home/guest/www/sprint-15335-282.html).

## Return Value

- Return 0 if the table was displayed
- Return 1 otherwise

## Examples

1. **Display Jira issues for the latest sprint in the "Network Observability" board on a web page**
   ```bash
   /jira:sprint "Network Observability"
   ```

2. **Display Jira issues for the latest sprint in board 15335 on a web page**
   ```bash
   /jira:sprint 15335
   ```

3. **Display Jira issues for sprint 281 in board 15335 as plain text**
   ```bash
   /jira:sprint 15335 281 --text
   ```

## Output format

Example table output: No sprint given

```text
**NetObserv - Sprint 282 (Active)**
Sprint Period: Dec 29, 2025 - Jan 16, 2026
Board ID: 15335

Total Issues: **2**

Key             Summary                                Assignee       Status
NETOBSERV-2516  Add runbooks                           Unassigned     To Do
NETOBSERV-2545  External traffic quick filter          Dev Rev        Review
```

Example table output: Sprint given

```text
**NetObserv - Sprint 281**
Sprint Period: Dec 8, 2025 - Dec 26, 2025
Board ID: 15335

Total Issues: **3**

Key             Summary                                      Assignee
NETOBSERV-2146  FLP: show Gateway objects as owners          A Hacker
NETOBSERV-2147  Console plugin: integration with Gateways    Break Fast
NETOBSERV-2182  Issues with One way / Back and forth option  C Kubed
```

## Prerequisites

1. **MCP Jira Server**: Must be configured and connected
    - See [Jira Plugin README](../README.md) for setup instructions

2. **Web browser**: Able to launch a web browser if displaying on a web page

## Arguments

- **board-id-or-name** (required): Jira Rapid Board name or board ID (e.g. "Network Observability", 15335).  This must be a scrum board and not a Kanban board.
    - If all digits, treat it as a board ID else it's a Rapid Board name.
    - If it's a Rapid Board name, attempt to match all or part of existing Rapid Board names of type "scrum" only.
    - If multiple matches to a Rapid Board name, list the matches and ask to select which one.
    - If the Rapid Board name contains spaces, it must be quoted.

- **sprint-name** (optional): Sprint name
    - If argument not provided, use the latest sprint.
    - The sprint name is typically a number. It is not the internal Jira ID.
    - If it contains spaces, it must be quoted.

- **--text** (optional): Display table in a text-based format
    - Without this option, it displays the table on a web page.
