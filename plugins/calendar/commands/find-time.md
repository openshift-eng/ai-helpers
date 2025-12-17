---
description: Find overlapping free time to meet with one or more people.
argument-hint: <email_addresses> [duration_in_minutes] [days_ahead]
---

## Name
calendar:find-time

## Synopsis
```bash
/calendar:find-time <email_addresses> [duration_in_minutes] [days_ahead]
```

## Description
The `calendar:find-time` command helps you find overlapping available time with people by analyzing calendar availability across multiple participants and suggesting optimal meeting times.

## Implementation

### Phase 1: Parse and Validate Arguments
- Parse `$ARGUMENTS` to extract email addresses, duration, and optional date range
- Validate email format for all participants 
- Set default duration to be 30 minutes
- Set default date range if not provided (e.g., next 7 days)
- Convert duration to minutes if provided in other formats

### Phase 2: Gather Free/Busy Information
- Use the `mcp__google-calendar__get-freebusy` function from the google-calendar MCP server to get busy times for all participants
- Query the specified days_ahead for each participant's calendar
- Get current time and primary calendar timezone using `mcp__google-calendar__get-current-time`

### Phase 3: Analyze Available Time Slots
- Calculate free blocks by inverting busy periods for each participant
- Find overlapping free time across all participants
- Filter out blocks shorter than the requested duration
- Dismiss free blocks that are earlier than the current time
- Exclude weekends unless specifically requested
- Consider 9 AM - 6 PM as default preference

### Phase 4: Generate Meeting Suggestions
- Sort potential meeting times by preference (earlier in week, business hours, etc.)
- Present top 3–5 options with clear time formatting
- Display times in the user's primary calendar timezone
- Include day of week and date for clarity
- Provide alternative suggestions if no perfect matches found

### Phase 5: Error Handling
- Handle cases where no common free time exists
- Provide helpful suggestions (shorter duration, different date range)
- If you can't access a calendar, give up the operation gracefully. Then tell the user that the email address might be wrong
- Validate that all email addresses have accessible calendars

## Return Value
- **Format**: Structured list of available meeting times
- **Content**:
  - Meeting time options with date, time, and timezone
  - Duration confirmation
  - List of all participants
  - Alternative suggestions if limited availability

## Examples

1. **Basic usage with two people**:
   ```bash
   /calendar:find-time alice@company.com,bob@company.com 60
   ```

2. **Including date range**:
   ```bash
   /calendar:find-time team@company.com,manager@company.com 30 7
   ```

3. **Multiple participants with specific date**:
   ```bash
   /calendar:find-time alice@company.com,bob@company.com,carol@company.com 45 15
   ```

## Arguments
- `$1` (email_addresses): Comma-separated list of participant email addresses (required)
- `$2` (duration_in_minutes): Optional meeting duration in minutes
- `$3` (days_ahead): Optional number of days ahead to look up
