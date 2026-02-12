---
description: Watch open Enhancement PRs from other teams that may impact OLM
argument-hint: ""
---

## Name
olm-team:ep-watch

## Synopsis
```
/olm-team:ep-watch
```

## Description
The `olm-team:ep-watch` command watches open Enhancement Proposal PRs in the openshift/enhancements repository that are **not created by the OLM team** but may have impacts on OLM work. This helps the OLM team maintain visibility into what other teams are designing that could affect operator lifecycle management.

The command:
- Fetches open PRs from openshift/enhancements repository
- Filters out PRs created by known OLM team members
- Analyzes PR content for OLM-related topics
- Returns up to 3 most relevant PRs with impact assessment

This is useful for:
- Discovering cross-team dependencies early
- Identifying potential impacts on OLM architecture
- Participating in relevant enhancement discussions
- Staying informed about OpenShift-wide changes affecting operators

## Implementation

### Step 1: Define OLM-Related Topics

Create a list of topics that could impact OLM:

**High Priority Topics (Weight: 10):**
OLMv1-specific terms that indicate direct relevance:
- olmv1, olm v1
- operator-controller
- catalogd
- rukpak
- ClusterExtension
- boxcutter

**Medium Priority Topics (Weight: 5-8):**
OLM-specific but broader terms:
- olmv0, olm v0
- operator lifecycle manager, operator-lifecycle-manager
- operator lifecycle
- operator framework
- operator bundle
- operator catalog
- operator registry
- operator hub, operatorhub
- cluster extension (weight: 8)

**Low Priority Topics (Weight: 3-4):**
Related terms that must appear in specific context:
- subscription (with "operator")
- csv (with "operator")
- installplan
- catalogsource

**Excluded Generic Terms:**
To reduce false positives, the following generic terms are NOT searched:
- "operator" alone (too broad - matches any operator)
- "marketplace" alone (matches unrelated marketplace mentions)
- "CRD" alone (too generic)
- "webhook" alone (too generic)

### Step 2: Identify OLM Team Members

Define list of known OLM team members (GitHub usernames):

```
OLM_TEAM_MEMBERS = [
  "grokspawn",
  "joelanford",
  "perdasilva",
  "tmshort",
  "oceanc80",
  "dtfranz",
  "anik120",
  "rashmigottipati",
  "pedjak",
  "ankitathomas",
  "trgeiger",
  # Add current OLM team members as needed
]
```

### Step 3: Fetch Open Enhancement PRs

Use GitHub API to get open PRs:

```bash
# Fetch open PRs from openshift/enhancements
curl -s \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/openshift/enhancements/pulls?state=open&per_page=100" \
  > /tmp/enhancement-prs.json
```

### Step 4: Filter and Score PRs

For each open PR:

1. **Filter out OLM team PRs**
   - Check if PR author is in OLM_TEAM_MEMBERS list
   - Skip if created by OLM team

2. **Score relevance**
   - Fetch PR title, body, and changed files
   - Count mentions of OLM-related topics
   - Higher score = more topic matches
   - Bonus points for:
     - Multiple topic matches
     - Topics in PR title (weighted higher)
     - Topics in summary section
     - Changes to operator-related directories

3. **Extract key information**
   - PR number and title
   - Author
   - Created date
   - Files changed
   - Matched topics (why it's relevant)
   - Link to PR

### Step 5: Rank and Return Top 3

Sort PRs by relevance score and return top 3.

### Step 6: Format Results

```
🔍 Found X open Enhancement PRs from other teams that may impact OLM

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 PR #XXXX: [Title]
👤 Author: @username (Team: [team-name if identifiable])
📅 Opened: X days ago
🎯 Relevance: [HIGH/MEDIUM]

**Why this matters to OLM:**
- Mentions: [list of matched topics]
- Potential impacts: [brief analysis]

**Files changed:**
- enhancements/[area]/[filename].md

🔗 https://github.com/openshift/enhancements/pull/XXXX

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 7: Provide Actionable Recommendations

For each PR, suggest:
- Whether OLM should review/comment
- Potential action items
- Team members who might be interested

## Return Value
- **Text output**: Up to 3 open Enhancement PRs with impact analysis
- **Links**: Direct URLs to each PR
- **Recommendations**: Suggested actions for OLM team

## Examples

1. **Basic usage**:
   ```
   /olm-team:ep-prs-watch
   ```

   Example output:
   ```
   🔍 Found 12 open Enhancement PRs from other teams, showing top 3 relevant to OLM

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📋 PR #1234: Add support for operator webhooks in hypershift
   👤 Author: @other-team-member (HyperShift Team)
   📅 Opened: 5 days ago
   🎯 Relevance: HIGH

   **Why this matters to OLM:**
   - Mentions: operator, webhook, ClusterExtension, operator lifecycle
   - Potential impacts: Changes how operator webhooks work in hosted control planes
     Could affect OLMv1 webhook support in HyperShift clusters

   **Files changed:**
   - enhancements/hypershift/operator-webhooks.md

   🔗 https://github.com/openshift/enhancements/pull/1234

   **Recommended action:** Review and comment on webhook integration approach
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

## Implementation Details

### GitHub API Authentication

Requires GITHUB_TOKEN for higher rate limits:

```bash
# Check for token
if [ -z "$GITHUB_TOKEN" ]; then
  echo "⚠️  Warning: GITHUB_TOKEN not set. API rate limits will be restrictive."
  echo "Set with: export GITHUB_TOKEN=your_token"
fi
```

### Scoring Algorithm

The scoring algorithm uses **weighted keywords** to prioritize OLMv1-specific content:

```python
def score_pr_relevance(pr_data, weighted_topics):
    score = 0

    # Each topic has a weight (10=high, 5=medium, 3=low)
    for topic, weight in weighted_topics.items():
        topic_lower = topic.lower()

        # Title matches get 3x multiplier
        if topic_lower in pr_data['title'].lower():
            score += (weight * 3)

        # Body matches get 1x weight
        elif topic_lower in pr_data['body'].lower():
            score += weight

    return score

# Relevance levels:
# HIGH: score >= 30 (e.g., "olmv1" or "catalogd" in title)
# MEDIUM: score >= 10
# LOW: score < 10
# Minimum threshold: 5 (PRs with score < 5 are filtered out)
```

**Example Scoring:**
- PR title contains "olmv1": 10 * 3 = 30 points (HIGH)
- PR title contains "operator-controller": 10 * 3 = 30 points (HIGH)
- PR body mentions "catalogd": 10 points (MEDIUM)
- PR body mentions "operator bundle": 5 points (MEDIUM)
- PR with generic "marketplace" only: 0 points (excluded)

### Caching

To avoid rate limits, cache results:
```bash
CACHE_FILE="/tmp/olm-ep-prs-watch-cache.json"
CACHE_TTL=3600  # 1 hour

if [ -f "$CACHE_FILE" ]; then
    age=$(($(date +%s) - $(stat -f %m "$CACHE_FILE")))
    if [ $age -lt $CACHE_TTL ]; then
        echo "Using cached results (${age}s old)"
        cat "$CACHE_FILE"
        exit 0
    fi
fi
```

### Error Handling

```bash
# Handle API failures
if ! response=$(curl -s -w "\n%{http_code}" "$api_url"); then
    echo "❌ Failed to fetch PRs from GitHub API"
    exit 1
fi

http_code=$(echo "$response" | tail -n1)
if [ "$http_code" != "200" ]; then
    echo "❌ GitHub API returned status $http_code"
    if [ "$http_code" = "403" ]; then
        echo "Rate limit exceeded. Try again later or set GITHUB_TOKEN"
    fi
    exit 1
fi
```

## Arguments
- None - The command runs without arguments and fetches all relevant open PRs

## Prerequisites

1. **GitHub CLI (optional but recommended)**
   - Check: `which gh`
   - Install: https://cli.github.com/
   - Alternative: Use curl with GitHub API

2. **GITHUB_TOKEN (recommended)**
   - Set: `export GITHUB_TOKEN=your_token`
   - Without token: Limited to 60 API requests/hour
   - With token: 5000 API requests/hour
   - Create at: https://github.com/settings/tokens

3. **jq (for JSON parsing)**
   - Check: `which jq`
   - Install: `brew install jq` (macOS) or `apt install jq` (Linux)

4. **Internet access**
   - Required to access GitHub API

## Notes

- The command focuses on **open PRs** (not merged or closed)
- PRs are refreshed each run (with caching to avoid rate limits)
- The OLM team member list should be kept up-to-date
- Topic list can be expanded based on team feedback
- Results are ranked by relevance, not recency
- Consider running this weekly during team meetings

## Advanced Usage

### Custom Topic Filtering

To search for specific topics only:
```bash
# Modify the script to accept topic arguments
/olm-team:ep-prs-watch webhooks catalog
```

### Adjust Result Limit

To return more or fewer results:
```bash
# Show top 5 instead of 3
/olm-team:ep-prs-watch --limit 5
```

### Include OLM Team PRs

To see ALL relevant PRs (including OLM team):
```bash
/olm-team:ep-prs-watch --include-team
```

## Future Enhancements

- Auto-post weekly summary to Slack
- Subscribe to specific topics
- Email notifications for high-relevance PRs
- Integration with team calendar for review sessions
- Track PRs over time to see new vs. previously flagged

## See Also

- [OpenShift Enhancements Repository](https://github.com/openshift/enhancements)
- [Enhancement Proposal Process](https://github.com/openshift/enhancements/blob/master/README.md)
- GitHub CLI: `gh pr list`
- `/olm-team:ep-search` - Search existing Enhancement Proposals
