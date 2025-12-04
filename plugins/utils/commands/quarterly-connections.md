---
description: Generate quarterly connections responses based on GitHub activity and brief answers
---

## Name
utils:quarterly-connections

## Synopsis
```
/utils:quarterly-connections
```

## Description
The `utils:quarterly-connections` command helps generate thoughtful, well-written responses to quarterly connection questions. It analyzes your GitHub contributions in the openshift organization over the last quarter (~3 months), suggests accomplishments based on your actual work, asks you for brief answers to the standard quarterly questions, and then expands those brief answers into polished responses suitable for submission.

## Implementation

The command follows this workflow:

1. **Determine GitHub Username**: Extract the authenticated GitHub username
   - Run: `gh auth status` to get the currently authenticated GitHub account
   - Parse the output to extract the username (format: "Logged in to github.com as USERNAME")
   - If not authenticated, prompt the user to run `gh auth login`

2. **Fetch GitHub Activity**: Use the GitHub CLI to retrieve the user's contributions
   - Calculate the date from 3 months ago (quarter start date)
   - Search for merged PRs in the openshift organization from the last ~3 months
   - Use: `gh search prs --author=<username> --owner=openshift --merged --merged-at=">=YYYY-MM-DD" --limit 50 --json number,title,repository,closedAt,url`
   - Analyze the PR titles and repositories to identify themes and major contributions

3. **Analyze Contributions**: Identify key accomplishments from GitHub activity
   - Group PRs by theme (e.g., security features, version bumps, bug fixes, operator work)
   - Identify major features or initiatives (e.g., multiple PRs for the same JIRA or feature)
   - Count contributions across different repositories
   - Look for patterns indicating leadership or cross-team coordination

4. **Suggest Accomplishments**: Present GitHub-based accomplishment suggestions
   - Show 3-5 key accomplishments derived from the GitHub activity
   - **Emphasize HOW over WHAT**: Frame suggestions around approach, collaboration, and methodology rather than just listing deliverables
   - Avoid including specific counts in the suggestions (save detailed metrics for the appendix)
   - Use qualitative descriptions to convey scope (e.g., "across multiple components" instead of "across 17 components")
   - Include examples of the types of work done, but focus on the approach taken

5. **Ask Questions**: Prompt the user for brief answers
   - **Question 1**: "What accomplishments are you most proud of last quarter? Reflect not only on WHAT you've accomplished but also on HOW you've accomplished it."
     - Show the GitHub-based suggestions
     - Ask for a brief answer (1-2 sentences) that the user wants to highlight
     - User can reference the suggestions or provide their own

   - **Question 2**: "What are your top priorities for this quarter?"
     - Ask for a brief answer (1-2 sentences) about upcoming priorities

6. **Generate Responses**: Expand the brief answers into polished responses
   - **For Question 1 (Accomplishments)**:
     - Take the user's brief answer
     - **PRIORITIZE HOW over WHAT**: Focus on approach, methodology, collaboration, and problem-solving process
     - Avoid specific counts and numbers (e.g., "17+ operators", "50 PRs") - these belong in the appendix, not the main response
     - Instead of quantifying scale with numbers, describe the nature of the work (e.g., "across multiple components" instead of "across 17 components")
     - Emphasize collaboration patterns, technical approach, and leadership behaviors
     - When mentioning technical work, focus on the challenge solved or approach taken rather than counting deliverables
     - Keep the response concise but substantive (3-5 sentences)
     - Use a professional but personable tone

   - **For Question 2 (Priorities)**:
     - Take the user's brief answer
     - Expand with context about why these priorities matter
     - Connect to team/organizational goals if applicable
     - Keep the response concise (2-4 sentences)
     - Maintain focus and clarity

7. **Output Format**: Present the final responses
   - Display both expanded responses in a clear format
   - Save to `.work/quarterly-connections/YYYY-MM-DD-response.md`
   - Include the original brief answers as comments for reference
   - Provide the GitHub contribution summary as an appendix

## Guidelines for Response Generation

### Tone and Style
- Professional but personable
- Direct and concise - avoid unnecessary verbosity
- Focus on impact and outcomes
- Avoid superlatives and excessive praise
- Use active voice

### Expanding Brief Answers
- **Keep responses relatively short**: 3-5 sentences for accomplishments, 2-4 for priorities
- **For Question 1, emphasize HOW over WHAT**:
  - Focus on the process, approach, and methodology used
  - Describe collaboration patterns and cross-team coordination
  - Highlight problem-solving approaches and technical challenges navigated
  - Avoid listing counts or numbers (save these for the appendix)
  - Use qualitative descriptions instead of quantitative ones (e.g., "extensive coordination" instead of "across 20 repositories")
- Use specific examples from GitHub activity to illustrate the HOW, not just the WHAT
- Connect individual contributions to team/project outcomes
- For priorities, provide just enough context to show strategic thinking

### What to Avoid
- Don't make up details not evident in GitHub activity or user's brief answer
- Don't overstate or exaggerate accomplishments
- Don't write overly long responses - brevity is valued
- Don't use corporate jargon or buzzwords excessively
- Don't include information the user didn't mention or isn't in the GitHub data
- **Don't include specific counts or numbers in Question 1 responses** (e.g., "17+ operators", "50 PRs", "across 20 repositories")
- Don't list deliverables - instead describe the approach and challenges
- Don't focus on the WHAT at the expense of the HOW

## Return Value

The command generates:
1. A summary of GitHub contributions over the last quarter
2. Suggested accomplishments based on GitHub activity (emphasizing HOW over WHAT)
3. Two expanded responses ready for submission:
   - Response to Question 1 (Accomplishments - **prioritizing HOW over WHAT**, avoiding specific counts/numbers)
   - Response to Question 2 (Priorities)
4. A markdown file saved to `.work/quarterly-connections/YYYY-MM-DD-response.md`
   - The file includes an appendix with detailed GitHub metrics (this is where counts and numbers belong)

## Examples

### Example 1: Basic usage
```
/utils:quarterly-connections
```

**What happens:**
1. Determines GitHub username from `gh auth status`
2. Fetches last 3 months of merged PRs in openshift org
3. Analyzes PRs and suggests accomplishments like:
   - "Implemented authentication improvements across API server components through systematic code review and testing"
   - "Fixed critical networking bugs affecting hypershift deployments by collaborating with QE team"
   - "Contributed to CI infrastructure stability by methodically addressing test reliability issues"
4. Asks user for brief answer to Question 1
5. User responds: "Fixed several critical networking issues and improved our CI test reliability"
6. Asks user for brief answer to Question 2
7. User responds: "Focus on performance optimization and expanding test coverage"
8. Generates expanded responses and saves to file

### Example invocation and flow

```
$ /utils:quarterly-connections

Detecting GitHub username from authenticated session...
Found username: jdoe

Analyzing GitHub contributions for jdoe in openshift organization...

Found 32 merged PRs in the last 3 months. Key themes identified:

**Suggested Accomplishments:**
1. Networking Bug Fixes: Resolved critical networking issues affecting hypershift and bare metal deployments through systematic debugging and cross-team collaboration
2. CI Reliability: Improved test infrastructure stability by methodically addressing flaky tests and timeout issues
3. Documentation: Enhanced operator documentation and troubleshooting guides across multiple repositories
4. Code Review: Active reviewer helping maintain code quality and knowledge sharing across the team

---

Question 1: What accomplishments are you most proud of last quarter? Reflect not only on WHAT you've accomplished but also on HOW you've accomplished it.

Please provide a brief answer (1-2 sentences):
> Fixed several critical networking issues and improved our CI test reliability

---

Question 2: What are your top priorities for this quarter?

Please provide a brief answer (1-2 sentences):
> Focus on performance optimization and expanding test coverage

---

Generating expanded responses...

**Question 1 Response:**
Last quarter, I resolved several critical networking issues affecting hypershift and bare metal deployments by working closely with the QE team to systematically reproduce issues and verify fixes. I also improved our CI test reliability by taking a methodical approach to identifying and addressing flaky tests and timeout issues, collaborating with multiple teams to ensure comprehensive solutions. This work required balancing deep technical debugging with effective communication and coordination across different areas of the codebase.

**Question 2 Response:**
This quarter, I'm prioritizing performance optimization for our networking components, particularly around high-density cluster scenarios where we've identified bottlenecks. Additionally, I'll be expanding our test coverage to include more edge cases and platform-specific scenarios, which will improve our confidence in releases and reduce production issues.

---

Responses saved to: .work/quarterly-connections/2025-12-04-response.md
```

## Arguments

None - the command automatically detects the GitHub username from the authenticated session

## Notes

- Requires `gh` CLI to be installed and authenticated (`gh auth login`)
- The command fetches data from the last ~3 months (quarter) by default
- Only analyzes contributions in the openshift organization
- The expanded responses are guidelines - users should review and adjust as needed
- GitHub activity provides concrete examples but may not capture all accomplishments (meetings, design work, mentoring, etc.)
