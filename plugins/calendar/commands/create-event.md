---
description: Create a new event on Google Calendar.
argument-hint: <natural_language_prompt_for_the_event>
---

## Name
calendar:create-event

## Synopsis
```bash
/calendar:create-event <natural_language_prompt_for_the_event>
```

## Description
The `calendar:create-event` command creates a new calendar event on Google Calendar based on natural language input. It intelligently parses event details from user descriptions, automatically adds Google Meet links for virtual participation, and handles timezone conversions and date parsing.

## Implementation

### Phase 1: Parse Natural Language Input
- Parse `$ARGUMENTS` to extract key event details:
  - `summary` (event title/subject)
  - `start` (start date and time)
  - `end` (end date and time)
  - `attendees` (list of email addresses)
  - `description` (additional details, agenda, notes)
- Handle relative date expressions ("tomorrow", "next Friday", "in 2 hours")
- Parse time expressions ("9am", "2:30 PM", "noon")
- Extract participant information from various formats

### Phase 2: Validate and Clarify Missing Information
- Check for essential information (event summary and start time)
- If crucial details are missing, ask user for clarification with specific questions
- Validate email addresses for attendees
- Set reasonable defaults:
  - Duration: 1 hour if end time not specified
  - Location: Virtual (Google Meet) if not specified
- Convert relative dates to absolute dates with proper timezone handling

### Phase 3: Format Event Data
- Convert all dates and times to ISO 8601 format
- Use `mcp__google-calendar__get-current-time` function to determine user's timezone
- Ensure start time is before end time
- Format attendee list properly for calendar API
- Prepare event description with any additional context

### Phase 4: Ask For User Confirmation
- Display the summary, meeting time, attendees, description 
- Ask user to confirm
- If user confirms, proceed to phase 5, otherwise, modify the summary, meeting time, attendees, description based on user's input until user confirms you correctly interpreted the intent.

### Phase 5: Create Calendar Event
- Use the `mcp__google-calendar__create-event` function from the google-calendar MCP server
- Automatically attach Google Meet link for virtual participation using the `conferenceData` parameter
- Create event on user's primary calendar (calendarId: 'primary')
- Include all parsed attendees, description, and meeting details
- Handle calendar API responses and potential conflicts

### Phase 6: Confirmation and Error Handling
- Confirm successful event creation with key details
- Provide Google Meet link and calendar invitation status
- Handle common errors gracefully:
  - Calendar permission issues
  - Invalid attendee emails
  - Scheduling conflicts
  - Timezone conversion errors
- Suggest alternatives if event creation fails

## Return Value
- **Success Format**: Confirmation message with:
  - Event title and time details
  - List of invited attendees
  - Google Meet link for virtual participation
  - Calendar invitation status
- **Error Format**: Clear error message with:
  - Description of what went wrong
  - Specific suggestions for resolution
  - Alternative approaches if applicable

## Examples

1. **Simple meeting**:
   ```bash
   /calendar:create-event Team standup tomorrow at 9am for 30 minutes
   ```

2. **Meeting with specific attendees**:
   ```bash
   /calendar:create-event Project review Friday 2pm with alice@company.com and bob@company.com
   ```

3. **Detailed planning session**:
   ```bash
   /calendar:create-event Quarterly planning session next Monday 10am-12pm with the whole engineering team
   ```

4. **Quick 1:1 meeting**:
   ```bash
   /calendar:create-event Coffee chat with Sarah tomorrow 3pm for 45 minutes
   ```

5. **All-hands meeting**:
   ```bash
   /calendar:create-event Monthly all-hands meeting first Friday of next month 2-3pm with leadership team
   ```

## Arguments
- `natural_language_prompt_for_the_event` ($1): Natural language description of the event to create, including title, time, attendees, and any other relevant details (required)
