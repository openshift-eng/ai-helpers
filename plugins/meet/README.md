# Meet Plugin

Google Calendar integration for Claude Code, providing AI-powered tools to find meeting times and schedule events seamlessly.

## Features

- 🔍 **Smart Time Finding** - Find overlapping free time across multiple participants' calendars
- 📅 **Natural Language Event Creation** - Create calendar events using intuitive natural language descriptions
- 🌐 **Timezone Handling** - Automatic timezone detection and conversion for global teams
- 🤖 **Google Meet Integration** - Automatically adds Google Meet links to virtual meetings
- ⚡ **Intelligent Parsing** - Understands relative dates, time expressions, and participant lists
- 🎯 **Business Hours Optimization** - Prioritizes business hours and excludes weekends by default

## Prerequisites

- Claude Code installed
- Google Calendar API access configured
- Google Calendar MCP server(bundled)

## Setup

### 1. Google Cloud Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) for your project. Ensure that the right project is selected from the top bar before enabling the API
4. Create OAuth 2.0 credentials:
   - Go to **Credentials**
   - Click **"Create Credentials"** > **"OAuth client ID"**
   - Choose **"User data"** for the type of data that the app will be accessing
   - Add your app name and contact information
   - Add the following scopes:
     - `https://www.googleapis.com/auth/calendar.events`
     - `https://www.googleapis.com/auth/calendar`
   - Select **"Desktop app"** as the application type (Important!)
   - Download the auth key

### 2. Environment Configuration

After completing previous step, you must specify the credentials file path using the `GOOGLE_OAUTH_CREDENTIALS` environment variable prior to starting Claude Code, this tells the `google-calendar-mcp` MCP server where to look for auth keys.

```bash
export GOOGLE_OAUTH_CREDENTIALS=~/.config/client_secret_xxxxxxxxx.json
claude
```

## Installation

```bash
# Add the marketplace (one-time setup)
/plugin marketplace add openshift-eng/ai-helpers

# Install the plugin
/plugin install meet@ai-helpers
```

## Available Commands

### `/meet:find-time` - Find Overlapping Free Time

Find overlapping available time with multiple participants by analyzing calendar availability and suggesting optimal meeting times.

**Usage:**
```bash
# Basic usage with two people
/meet:find-time alice@company.com,bob@company.com 60

# Including custom date range
/meet:find-time team@company.com,manager@company.com 30 7

# Multiple participants with longer timeline
/meet:find-time alice@company.com,bob@company.com,carol@company.com 45 15
```

**Features:**
- Analyzes free/busy information across all participants
- Filters out blocks shorter than requested duration
- Excludes weekends unless specifically requested
- Prioritizes business hours
- Provides alternative suggestions if no perfect matches found
- Displays times in user's primary calendar timezone

See [commands/find-time.md](commands/find-time.md) for full documentation.

---

### `/meet:create-event` - Create Calendar Events

Create new calendar events using natural language descriptions with automatic Google Meet integration and intelligent parsing.

**Usage:**
```bash
# Simple meeting
/meet:create-event Team standup tomorrow at 9am for 30 minutes

# Meeting with specific attendees
/meet:create-event Project review Friday 2pm with alice@company.com and bob@company.com

# Detailed planning session
/meet:create-event Quarterly planning session next Monday 10am-12pm with the whole engineering team

# Quick 1:1 meeting
/meet:create-event Coffee chat with Sarah tomorrow 3pm for 45 minutes

# All-hands meeting
/meet:create-event Monthly all-hands meeting first Friday of next month 2-3pm with leadership team
```

**Features:**
- Natural language parsing for dates, times, and attendees
- Automatic Google Meet link generation
- Intelligent defaults (1-hour duration, virtual location)
- Handles relative dates ("tomorrow", "next Friday", "in 2 hours")
- Timezone conversion and validation
- Email validation for attendees
- Graceful error handling with helpful suggestions

See [commands/create-event.md](commands/create-event.md) for full documentation.

---

## Workflow Examples

### Planning a Team Meeting

1. **Find available time:**
   ```bash
   /meet:find-time team-lead@company.com,dev1@company.com,dev2@company.com,designer@company.com 60 5
   ```

2. **Create the meeting:**
   ```bash
   /meet:create-event Sprint planning session Thursday 2pm with team-lead@company.com,dev1@company.com,dev2@company.com,designer@company.com
   ```

### Scheduling a Quick Sync

```bash
# One command to create immediate meeting
/meet:create-event Quick sync with John tomorrow 11am for 15 minutes
```

### Cross-timezone Meeting

```bash
# Find time considering global participants
/meet:find-time alice@us.company.com,bob@uk.company.com,carol@asia.company.com 30 10

# Create with specific timezone considerations
/meet:create-event Global standup next Monday 8am PST with alice@us.company.com,bob@uk.company.com,carol@asia.company.com
```

## Troubleshooting

### "Could not access calendar for {email}"
- Verify the email address is correct
- Ensure the user has shared their calendar or given appropriate permissions
- Check that your Google Calendar API credentials have the necessary scopes

### "No overlapping free time found"
- Try a shorter meeting duration
- Expand the date range (more days ahead)
- Consider including weekend options
- Check if participants have conflicting recurring meetings

### OAuth/Authentication Issues
- Verify `GOOGLE_OAUTH_CREDENTIALS` environment variable is set correctly
- Ensure the credentials file exists and is readable
- Check that the Google Calendar API is enabled in your Google Cloud project
- Verify OAuth scopes include calendar access

### MCP Server Issues
- Ensure `@cocal/google-calendar-mcp` is available via npm
- Check that the MCP server is properly configured
- Verify network connectivity for API calls

For command-specific troubleshooting, see the individual command documentation.

## Security and Privacy

- **Credentials**: OAuth credentials are stored locally and never transmitted to AI Helpers
- **Calendar Data**: Free/busy information is queried in real-time and not stored
- **Privacy**: Only calendar availability is accessed, not detailed event content
- **Scope**: The plugin only requests minimal necessary Calendar API permissions

