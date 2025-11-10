---
description: Generate comprehensive test activity reports across OpenShift projects with contributor tracking
argument-hint: "[--days-back <days>] [--project-limit <num>] [--keywords <words>] [--output <file>]"
---

## Name
polarion:activity

## Synopsis
```bash
/polarion:activity [--days-back <days>] [--project-limit <num>] [--keywords <words>] [--output <file>] [--format <json|csv>] [--verbose]
```

## Description

The `activity` command generates comprehensive test activity reports across OpenShift projects in Polarion, providing detailed analysis of test runs, test cases, and team member contributions. This command is designed for weekly team reporting, management summaries, and test execution activity tracking.

This command is useful for:
- Weekly team standup reporting
- Management test activity summaries  
- Individual contributor tracking
- Project activity trend analysis
- Cross-project test coordination

## Prerequisites

Before using this command, ensure you have:

1. **Polarion API Token**: Valid authentication token with read permissions
   - Get from: <https://polarion.engineering.redhat.com> → User Settings → Security → API Tokens
   - Set environment variable: `export POLARION_TOKEN="your_token_here"`
   - Verify with: `/polarion:health-check`

2. **Network Access**: Connectivity to Red Hat Polarion
   - Access to `polarion.engineering.redhat.com`
   - Corporate proxy configured if applicable
   - Verify with: `curl -H "Authorization: Bearer $POLARION_TOKEN" https://polarion.engineering.redhat.com/polarion/rest/v1/projects`

3. **Project Permissions**: Read access to OpenShift-related projects
   - Minimum: View test runs and test cases
   - Recommended: Access to multiple OpenShift projects for comprehensive analysis

## Arguments

- **--days-back <days>** (optional): Number of days to look back for activity analysis
  - Default: 7 days
  - Range: 1-90 days
  - Example: `--days-back 14` for two weeks of data

- **--project-limit <num>** (optional): Maximum number of projects to analyze
  - Default: 5 projects
  - Range: 1-20 projects  
  - Example: `--project-limit 10` for broader analysis

- **--keywords <words>** (optional): Space-separated keywords to filter projects
  - Default: `["openshift", "splat", "ocp", "platform", "container"]`
  - Case-insensitive matching against project names and IDs
  - Example: `--keywords "openshift" "storage" "networking"`

- **--output <file>** (optional): Export results to specified file
  - Supports relative and absolute paths
  - File extension determines format if --format not specified
  - Example: `--output qe-weekly-$(date +%Y%m%d).json`

- **--format <json|csv>** (optional): Output format for exported data
  - Default: `json` (structured data)
  - `csv`: Flat tabular format for spreadsheet import
  - Auto-detected from file extension if not specified

- **--verbose** (optional): Enable detailed output with debug information
  - Shows API request details
  - Includes processing timing
  - Displays additional context for troubleshooting

## Implementation

The command performs the following analysis workflow:

### 1. Environment Validation

Check prerequisites and authentication:

```bash
# Verify Polarion client availability
if ! python -c "import sys; sys.path.append('/path/to/polarion-client'); from polarion_client import PolarionClient" 2>/dev/null; then
    echo "Error: Polarion client not found. Installing dependencies..."
    pip install requests
    
    # Copy polarion_client.py to working directory if needed
    CLIENT_PATH="/path/to/polarion-client/polarion_client.py"
    if [ ! -f "$CLIENT_PATH" ]; then
        echo "Error: Polarion client not found at expected location."
        echo "Please ensure polarion_client.py is available."
        exit 1
    fi
fi

# Test authentication
if [ -z "$POLARION_TOKEN" ]; then
    echo "Error: POLARION_TOKEN environment variable not set."
    echo "Please set: export POLARION_TOKEN='your_token_here'"
    exit 1
fi

# Test connectivity
python -c "
import sys, os
sys.path.append('/path/to/polarion-client')
from polarion_client import PolarionClient
client = PolarionClient()
if not client.test_connection():
    print('Error: Cannot connect to Polarion API')
    exit(1)
print('✓ Polarion connectivity verified')
"
```

### 2. Parse Command Arguments

Process command-line arguments with defaults:

```bash
# Set defaults
DAYS_BACK=7
PROJECT_LIMIT=5
KEYWORDS="openshift splat ocp platform container"
OUTPUT_FILE=""
OUTPUT_FORMAT="json"
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --days-back)
            DAYS_BACK="$2"
            shift 2
            ;;
        --project-limit)
            PROJECT_LIMIT="$2"
            shift 2
            ;;
        --keywords)
            shift
            KEYWORDS=""
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                KEYWORDS="$KEYWORDS $1"
                shift
            done
            ;;
        --output)
            OUTPUT_FILE="$2"
            # Auto-detect format from extension
            if [[ "$OUTPUT_FILE" =~ \.csv$ ]]; then
                OUTPUT_FORMAT="csv"
            fi
            shift 2
            ;;
        --format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate arguments
if ! [[ "$DAYS_BACK" =~ ^[0-9]+$ ]] || [ "$DAYS_BACK" -lt 1 ] || [ "$DAYS_BACK" -gt 90 ]; then
    echo "Error: days-back must be between 1 and 90"
    exit 1
fi

if ! [[ "$PROJECT_LIMIT" =~ ^[0-9]+$ ]] || [ "$PROJECT_LIMIT" -lt 1 ] || [ "$PROJECT_LIMIT" -gt 20 ]; then
    echo "Error: project-limit must be between 1 and 20"
    exit 1
fi
```

### 3. Generate Activity Report

Execute the comprehensive analysis:

```python
#!/usr/bin/env python3

import sys
import os
import json
import argparse
from datetime import datetime

# Add polarion client to path
sys.path.append('/path/to/polarion-client')
from polarion_client import PolarionClient

def main():
    # Parse arguments from environment (set by bash script)
    days_back = int(os.getenv('DAYS_BACK', 7))
    project_limit = int(os.getenv('PROJECT_LIMIT', 5))
    keywords = os.getenv('KEYWORDS', 'openshift splat ocp platform container').split()
    output_file = os.getenv('OUTPUT_FILE', '')
    output_format = os.getenv('OUTPUT_FORMAT', 'json')
    verbose = os.getenv('VERBOSE', 'false').lower() == 'true'
    
    # Initialize client
    try:
        client = PolarionClient()
        if verbose:
            print(f"✓ Connected to Polarion")
    except Exception as e:
        print(f"❌ Failed to initialize Polarion client: {e}")
        sys.exit(1)
    
    # Test connection
    if not client.test_connection():
        print("❌ Failed to connect to Polarion API")
        sys.exit(1)
    
    if verbose:
        print(f"📊 Analyzing test activity:")
        print(f"  - Time period: {days_back} days")
        print(f"  - Project limit: {project_limit}")
        print(f"  - Keywords: {', '.join(keywords)}")
    
    # Get comprehensive activity summary
    try:
        # Override search keywords if specified
        if keywords != ['openshift', 'splat', 'ocp', 'platform', 'container']:
            # Temporarily override search method
            original_search = client.search_projects
            client.search_projects = lambda kw=None, case_sensitive=False, limit=None: original_search(keywords if kw is None else kw, case_sensitive, limit)
        
        summary = client.get_qe_activity_summary(
            days_back=days_back,
            project_limit=project_limit
        )
        
        if verbose:
            print(f"✓ Analysis complete")
            
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)
    
    # Display results
    display_summary(summary, verbose)
    
    # Export if requested
    if output_file:
        try:
            if client.export_data(summary, output_file, output_format):
                print(f"💾 Report exported to {output_file}")
            else:
                print(f"❌ Failed to export report")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Export error: {e}")
            sys.exit(1)

def display_summary(summary, verbose=False):
    """Display formatted activity summary."""
    
    # Header
    start_date = summary['period_start'][:10]
    end_date = summary['period_end'][:10]
    
    print(f"\n📊 QE Activity Summary ({start_date} to {end_date})")
    print("=" * 60)
    
    # Key metrics
    print(f"📈 Key Metrics:")
    print(f"  • Total Test Runs: {summary['total_test_runs']}")
    print(f"  • Total Test Cases Updated: {summary['total_test_cases']}")
    print(f"  • Active Projects: {len(summary['projects'])}")
    print(f"  • Active Test Contributors: {len(summary['activity_by_member'])}")
    
    # Project breakdown
    if summary['project_statistics']:
        print(f"\n🏢 Project Activity Breakdown:")
        sorted_projects = sorted(
            summary['project_statistics'].items(),
            key=lambda x: x[1]['test_runs'] + x[1]['test_cases'],
            reverse=True
        )
        
        for project_id, stats in sorted_projects:
            total_activity = stats['test_runs'] + stats['test_cases']
            print(f"  • {stats['name'][:35]:35} | "
                  f"Runs: {stats['test_runs']:3} | "
                  f"Cases: {stats['test_cases']:3} | "
                  f"Members: {stats['active_members']:2} | "
                  f"Total: {total_activity}")
    
    # Top contributors
    if summary['activity_by_member']:
        print(f"\n👥 Top Test Contributors:")
        sorted_members = sorted(
            summary['activity_by_member'].items(),
            key=lambda x: x[1]['test_runs_created'] + x[1]['test_cases_updated'],
            reverse=True
        )
        
        for i, (member_id, activity) in enumerate(sorted_members[:10], 1):
            total_activity = activity['test_runs_created'] + activity['test_cases_updated']
            project_count = len(activity['projects'])
            
            print(f"  {i:2}. {activity['name'][:25]:25} | "
                  f"Runs: {activity['test_runs_created']:3} | "
                  f"Cases: {activity['test_cases_updated']:3} | "
                  f"Projects: {project_count:2} | "
                  f"Total: {total_activity}")
    
    # Activity trends (if verbose)
    if verbose and summary['projects']:
        print(f"\n📅 Project Details:")
        for project in summary['projects'][:5]:
            print(f"\n  📁 {project['name']} ({project['id']})")
            print(f"     Test Runs: {len(project.get('test_runs', []))}")
            print(f"     Test Cases: {len(project.get('test_cases', []))}")
            
            if project.get('test_runs'):
                recent_runs = sorted(
                    project['test_runs'],
                    key=lambda x: x.get('created', ''),
                    reverse=True
                )[:3]
                
                print(f"     Recent Test Runs:")
                for run in recent_runs:
                    title = run.get('title', 'N/A')[:40]
                    status = run.get('status', 'N/A')
                    created = run.get('created', 'N/A')[:10]
                    print(f"       • {title:40} | {status:12} | {created}")
    
    # Recommendations
    total_activity = summary['total_test_runs'] + summary['total_test_cases']
    print(f"\n💡 Insights:")
    
    if total_activity == 0:
        print("  ⚠️  No test activity detected in this period")
        print("     - Verify project permissions and time period")
        print("     - Check if projects have recent test activity")
    elif total_activity < 10:
        print("  📈 Light activity period")
        print("     - Consider extending time period for more data")
        print("     - Verify project keyword filters")
    elif len(summary['activity_by_member']) < 3:
        print("  👥 Limited contributor diversity")
        print("     - Consider expanding project scope")
        print("     - Verify member permission levels")
    else:
        print("  ✅ Healthy test activity detected")
        
        # Find most active project
        if summary['project_statistics']:
            most_active = max(
                summary['project_statistics'].items(),
                key=lambda x: x[1]['test_runs'] + x[1]['test_cases']
            )
            print(f"     - Most active project: {most_active[1]['name']}")
        
        # Find top contributor
        if summary['activity_by_member']:
            top_contributor = max(
                summary['activity_by_member'].items(),
                key=lambda x: x[1]['test_runs_created'] + x[1]['test_cases_updated']
            )
            print(f"     - Top contributor: {top_contributor[1]['name']}")

if __name__ == "__main__":
    main()
```

### 4. Error Handling and Validation

Comprehensive error handling for common issues:

```bash
# Validate results
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ test activity analysis completed successfully"
    
    if [ -n "$OUTPUT_FILE" ]; then
        echo "📄 Report available at: $OUTPUT_FILE"
        
        # Show file size and format info
        if [ -f "$OUTPUT_FILE" ]; then
            SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
            echo "   File size: $SIZE"
            echo "   Format: $OUTPUT_FORMAT"
        fi
    fi
    
    # Suggest follow-up actions
    echo ""
    echo "💡 Next Steps:"
    echo "   • Share report with team in standup"
    echo "   • Archive report for historical tracking"
    echo "   • Use /polarion:projects for project details"
    echo "   • Use /polarion:test-runs PROJECT for deep dive"
    
else
    echo "❌ test activity analysis failed"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   • Check authentication: /polarion:health-check"
    echo "   • Verify project access permissions"
    echo "   • Try smaller time period: --days-back 3"
    echo "   • Use --verbose for detailed error information"
    exit 1
fi
```

## Examples

### Example 1: Weekly team standup report
```bash
/polarion:activity
```

Output:
```text
📊 QE Activity Summary (2024-01-08 to 2024-01-15)
============================================================
📈 Key Metrics:
  • Total Test Runs: 47
  • Total Test Cases Updated: 123
  • Active Projects: 4
  • Active Test Contributors: 8

🏢 Project Activity Breakdown:
  • OpenShift Container Platform      | Runs:  22 | Cases:  65 | Members:  5 | Total: 87
  • SPLAT Testing                     | Runs:  15 | Cases:  31 | Members:  3 | Total: 46
  • Container Storage                 | Runs:   8 | Cases:  19 | Members:  2 | Total: 27
  • Platform Networking              | Runs:   2 | Cases:   8 | Members:  2 | Total: 10

👥 Top Test Contributors:
   1. Member-A                      | Runs:  12 | Cases:  28 | Projects:  2 | Total: 40
   2. Member-B                      | Runs:   8 | Cases:  22 | Projects:  3 | Total: 30
   3. Member-C                      | Runs:  10 | Cases:  15 | Projects:  1 | Total: 25

💡 Insights:
  ✅ Healthy test activity detected
     - Most active project: OpenShift Container Platform
     - Top contributor: Member-A

✅ test activity analysis completed successfully
```

### Example 2: Monthly management summary with export
```bash
/polarion:activity --days-back 30 --project-limit 10 --output monthly-qe-summary.json
```

### Example 3: Custom project focus with verbose output
```bash
/polarion:activity --keywords "storage" "networking" --days-back 14 --verbose
```

Output:
```text
✓ Connected to Polarion
📊 Analyzing test activity:
  - Time period: 14 days
  - Project limit: 5
  - Keywords: storage, networking
✓ Analysis complete

📊 QE Activity Summary (2024-01-01 to 2024-01-15)
...

📅 Project Details:

  📁 Container Storage Interface (CSI)
     Test Runs: 12
     Test Cases: 24
     Recent Test Runs:
       • CSI Volume Lifecycle Tests           | passed     | 2024-01-14
       • CSI Snapshot Feature Tests           | passed     | 2024-01-13
       • CSI Multi-attach Validation         | failed     | 2024-01-12

...
```

### Example 4: CSV export for spreadsheet analysis
```bash
/polarion:activity --days-back 7 --output weekly-activity.csv --format csv
```

## Return Value

The command returns different exit codes based on execution:

- **Exit 0**: Analysis completed successfully
- **Exit 1**: Authentication, network, or API errors

**Output Formats**:

**Console Output** (default): Human-readable summary with emoji indicators and formatted tables

**JSON Export**: Structured data suitable for automation and further processing:
```json
{
  "period_start": "2024-01-08T00:00:00",
  "period_end": "2024-01-15T00:00:00",
  "total_test_runs": 47,
  "total_test_cases": 123,
  "projects": [...],
  "activity_by_member": {...},
  "project_statistics": {...}
}
```

**CSV Export**: Flattened tabular format for spreadsheet import with columns for project, member, runs, cases, and dates

## Common Use Cases

### Weekly Team Standup
```bash
# Quick 7-day summary for standup discussion
/polarion:activity --days-back 7

# Export for email or Slack sharing
/polarion:activity --days-back 7 --output standup-$(date +%Y%m%d).json
```

### Management Reporting
```bash
# Comprehensive monthly analysis
/polarion:activity --days-back 30 --project-limit 15 --output monthly-qe-metrics.csv --format csv

# Quarterly trends analysis
/polarion:activity --days-back 90 --project-limit 20 --verbose
```

### Project Health Assessment
```bash
# Focus on specific project family
/polarion:activity --keywords "openshift" "platform" --days-back 14

# Cross-project collaboration analysis
/polarion:activity --project-limit 10 --verbose
```

### Individual Contributor Tracking
```bash
# Detailed analysis with member breakdown
/polarion:activity --days-back 14 --verbose
```

## Integration with Other Tools

### Slack Notifications
```bash
# Generate summary and post to Slack
SUMMARY_FILE="qe-weekly-$(date +%Y%m%d).json"
/polarion:activity --output "$SUMMARY_FILE"

# Extract key metrics for Slack message
RUNS=$(jq '.total_test_runs' "$SUMMARY_FILE")
CASES=$(jq '.total_test_cases' "$SUMMARY_FILE")
MEMBERS=$(jq '.activity_by_member | keys | length' "$SUMMARY_FILE")

curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\": \"📊 Weekly QE Activity: $RUNS test runs, $CASES test cases, $MEMBERS active members\"}" \
  "$SLACK_WEBHOOK_URL"
```

### Email Reports
```bash
# Generate formatted email report
/polarion:activity --days-back 7 --output qe-weekly.json
python generate-email-report.py qe-weekly.json | mail -s "Weekly QE Summary" team@company.com
```

### CI/CD Integration
```bash
# Health check in deployment pipeline
/polarion:activity --days-back 3 --project-limit 3 | grep -q "Healthy test activity" || {
  echo "WARNING: Low test activity detected"
  exit 1
}
```

## Security Considerations

- **Token Security**: API token provides read access to Polarion projects
- **Data Privacy**: Reports may contain project names and member information  
- **Network Security**: All API communication uses HTTPS encryption
- **Access Control**: Results limited to user's Polarion project permissions

## See Also

- Related commands: `/polarion:projects`, `/polarion:test-runs`, `/polarion:health-check`
- JIRA integration: `/jira:status-rollup` for correlating with development activity
- CI analysis: `/ci:ask-sippy` for test failure correlation

## Notes

- Analysis reflects Polarion data quality and project activity patterns
- Large project limits may impact performance; start small and increase as needed
- Cross-project analysis requires permissions across multiple OpenShift projects  
- Export files are suitable for version control and historical trending
- Command designed for interactive use and automation integration