---
description: Generate automated weekly test activity reports optimized for team communication
argument-hint: "[--keywords <words>] [--output <file>] [--format <markdown|json>]"
---

## Name
polarion:weekly-report

## Synopsis
```bash
/polarion:weekly-report [--keywords <words>] [--output <file>] [--format <markdown|json|slack>] [--template <template>] [--verbose]
```

## Description

The `weekly-report` command generates formatted weekly test activity reports optimized for team communication, standup meetings, and management updates. It provides a concise yet comprehensive view of testing activity with clear metrics and actionable insights.

This command is useful for:
- Weekly team standup presentations
- Management test activity summaries
- Automated team reporting pipelines
- Historical activity tracking
- Cross-team QE coordination
- Release readiness communication

## Prerequisites

Before using this command, ensure you have:

1. **Polarion API Token**: Valid authentication token with read permissions
   - Get from: <https://polarion.engineering.redhat.com> → User Settings → Security → API Tokens
   - Set environment variable: `export POLARION_TOKEN="your_token_here"`
   - Verify with: `/polarion:health-check`

2. **Network Access**: Connectivity to Red Hat Polarion
   - Access to `polarion.engineering.redhat.com`
   - Corporate proxy configured if applicable

3. **Project Permissions**: Read access to OpenShift-related projects
   - Access to project test runs and metadata
   - Sufficient permissions for activity analysis

## Arguments

- **--keywords <words>** (optional): Space-separated keywords to filter projects
  - Default: `["openshift", "splat", "ocp", "platform", "container"]`
  - Case-insensitive matching against project names and IDs
  - Example: `--keywords "storage" "networking" "security"`

- **--output <file>** (optional): Export report to specified file
  - Supports relative and absolute paths
  - File extension determines format if --format not specified
  - Example: `--output weekly-report-$(date +%Y%m%d).md`

- **--format <markdown|json|slack>** (optional): Report output format
  - Default: `markdown` (human-readable formatted report)
  - `json`: Structured data for automation and integration
  - `slack`: Optimized format for Slack message posting
  - Auto-detected from file extension if not specified

- **--template <template>** (optional): Report template style
  - Default: `standard` (comprehensive weekly summary)
  - `executive`: High-level summary for management
  - `technical`: Detailed technical analysis for engineers
  - `standup`: Concise format for daily/weekly standups

- **--verbose** (optional): Enable detailed output and diagnostics
  - Shows data collection progress
  - Includes additional context and explanations
  - Provides troubleshooting information

## Implementation

The command generates weekly reports through the following workflow:

### 1. Data Collection and Analysis

Gather comprehensive test activity data for the reporting period:

```bash
# Validate environment and setup
if [ -z "$POLARION_TOKEN" ]; then
    echo "Error: POLARION_TOKEN environment variable not set."
    echo "Please set: export POLARION_TOKEN='your_token_here'"
    exit 1
fi

# Verify Polarion client availability
if ! python -c "import sys; sys.path.append('/path/to/polarion-client'); from polarion_client import PolarionClient" 2>/dev/null; then
    echo "Error: Polarion client not found"
    exit 1
fi

# Parse command arguments
KEYWORDS="openshift splat ocp platform container"
OUTPUT_FILE=""
OUTPUT_FORMAT="markdown"
TEMPLATE="standard"
VERBOSE=false

# Process arguments
while [[ $# -gt 0 ]]; do
    case $1 in
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
            if [[ "$OUTPUT_FILE" =~ \.md$ ]]; then
                OUTPUT_FORMAT="markdown"
            elif [[ "$OUTPUT_FILE" =~ \.json$ ]]; then
                OUTPUT_FORMAT="json"
            elif [[ "$OUTPUT_FILE" =~ \.txt$ ]]; then
                OUTPUT_FORMAT="slack"
            fi
            shift 2
            ;;
        --format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        --template)
            TEMPLATE="$2"
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
```

### 2. Weekly Report Generation

Generate comprehensive weekly analysis with appropriate formatting:

```python
#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime, timedelta
import textwrap

# Add polarion client to path
sys.path.append('/path/to/polarion-client')
from polarion_client import PolarionClient

def main():
    # Parse arguments from environment
    keywords = os.getenv('KEYWORDS', 'openshift splat ocp platform container').split()
    output_file = os.getenv('OUTPUT_FILE', '')
    output_format = os.getenv('OUTPUT_FORMAT', 'markdown')
    template = os.getenv('TEMPLATE', 'standard')
    verbose = os.getenv('VERBOSE', 'false').lower() == 'true'
    
    # Initialize client and collect data
    try:
        client = PolarionClient()
        if verbose:
            print("✓ Connected to Polarion")
            print(f"📊 Generating weekly report with {template} template")
    except Exception as e:
        print(f"❌ Failed to initialize Polarion client: {e}")
        sys.exit(1)
    
    # Collect weekly activity data
    if verbose:
        print("📈 Collecting weekly activity data...")
    
    try:
        # Override search keywords if specified
        if keywords != ['openshift', 'splat', 'ocp', 'platform', 'container']:
            original_search = client.search_projects
            client.search_projects = lambda kw=None, case_sensitive=False, limit=None: original_search(keywords if kw is None else kw, case_sensitive, limit)
        
        # Get comprehensive weekly summary
        summary = client.get_qe_activity_summary(days_back=7, project_limit=8)
        
        if verbose:
            print(f"✓ Collected data for {len(summary['projects'])} projects")
            
    except Exception as e:
        print(f"❌ Error collecting activity data: {e}")
        sys.exit(1)
    
    # Generate report based on format and template
    try:
        if output_format == 'json':
            report_content = generate_json_report(summary, template)
        elif output_format == 'slack':
            report_content = generate_slack_report(summary, template)
        else:  # markdown (default)
            report_content = generate_markdown_report(summary, template)
        
        # Display or save report
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            print(f"💾 Weekly report saved to {output_file}")
        else:
            print(report_content)
            
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        sys.exit(1)

def generate_markdown_report(summary, template):
    """Generate markdown-formatted weekly report."""
    
    # Extract key metrics
    start_date = summary['period_start'][:10]
    end_date = summary['period_end'][:10]
    total_runs = summary['total_test_runs']
    total_cases = summary['total_test_cases']
    active_projects = len(summary['projects'])
    active_members = len(summary['activity_by_member'])
    
    # Select template-appropriate content
    if template == 'executive':
        return generate_executive_markdown(summary, start_date, end_date)
    elif template == 'technical':
        return generate_technical_markdown(summary, start_date, end_date)
    elif template == 'standup':
        return generate_standup_markdown(summary, start_date, end_date)
    else:  # standard
        return generate_standard_markdown(summary, start_date, end_date)

def generate_standard_markdown(summary, start_date, end_date):
    """Generate standard weekly report in markdown format."""
    
    total_runs = summary['total_test_runs']
    total_cases = summary['total_test_cases']
    active_projects = len(summary['projects'])
    active_members = len(summary['activity_by_member'])
    
    report = f"""# Weekly Test Activity Report

**Reporting Period:** {start_date} to {end_date}  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 📊 Executive Summary

- **Total Test Runs:** {total_runs}
- **Test Cases Updated:** {total_cases}
- **Active Projects:** {active_projects}
- **Active QE Members:** {active_members}
- **Overall Activity:** {"🟢 High" if total_runs + total_cases > 50 else "🟡 Moderate" if total_runs + total_cases > 20 else "🔴 Low"}

"""

    # Project Activity Section
    if summary['project_statistics']:
        report += "## 🏢 Project Activity\n\n"
        
        sorted_projects = sorted(
            summary['project_statistics'].items(),
            key=lambda x: x[1]['test_runs'] + x[1]['test_cases'],
            reverse=True
        )
        
        report += "| Project | Test Runs | Test Cases | Active Members | Total Activity |\n"
        report += "|---------|-----------|------------|----------------|----------------|\n"
        
        for project_id, stats in sorted_projects:
            total_activity = stats['test_runs'] + stats['test_cases']
            activity_trend = "📈" if total_activity > 10 else "📊" if total_activity > 5 else "📉"
            
            report += f"| {stats['name'][:25]} | {stats['test_runs']} | {stats['test_cases']} | {stats['active_members']} | {activity_trend} {total_activity} |\n"
    
    # Team Activity Section
    if summary['activity_by_member']:
        report += "\n## 👥 Team Activity\n\n"
        
        sorted_members = sorted(
            summary['activity_by_member'].items(),
            key=lambda x: x[1]['test_runs_created'] + x[1]['test_cases_updated'],
            reverse=True
        )
        
        report += "| Test Contributor | Test Runs | Test Cases | Projects | Total |\n"
        report += "|-----------|-----------|------------|----------|-------|\n"
        
        for member_id, activity in sorted_members[:8]:
            total_activity = activity['test_runs_created'] + activity['test_cases_updated']
            project_count = len(activity['projects'])
            
            # Anonymize member names for public reports
            member_name = activity['name'].split()[0] if activity['name'] != 'Unknown' else 'QE Member'
            
            report += f"| {member_name} | {activity['test_runs_created']} | {activity['test_cases_updated']} | {project_count} | {total_activity} |\n"
    
    # Key Insights Section
    report += "\n## 💡 Key Insights\n\n"
    
    # Calculate insights
    if total_runs + total_cases == 0:
        report += "- ⚠️ **No test activity detected** - Verify project access and activity periods\n"
    elif total_runs + total_cases < 20:
        report += "- 📊 **Light activity week** - Normal for maintenance periods or holidays\n"
    else:
        report += "- ✅ **Active testing week** - Good QE engagement across projects\n"
    
    if active_projects > 0:
        most_active_project = max(
            summary['project_statistics'].items(),
            key=lambda x: x[1]['test_runs'] + x[1]['test_cases']
        )
        report += f"- 🎯 **Most active project:** {most_active_project[1]['name']}\n"
    
    if active_members > 0:
        report += f"- 👥 **Team engagement:** {active_members} QE members contributed this week\n"
        
        if active_members < 3:
            report += "- ℹ️ **Limited contributor diversity** - Consider expanding team engagement\n"
    
    # Trends and Recommendations
    report += "\n## 📈 Trends & Recommendations\n\n"
    
    if total_runs > total_cases:
        report += "- **Test Execution Focus:** More test runs than case updates - good execution cadence\n"
    elif total_cases > total_runs * 2:
        report += "- **Test Development Focus:** High test case activity - active test development\n"
    
    report += "- **Next Week:** Continue current activity levels and monitor project health\n"
    report += "- **Action Items:** Review any failed test runs and address infrastructure issues\n"
    
    # Footer
    report += f"\n---\n*Report generated by Polarion QE Analytics • {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
    
    return report

def generate_executive_markdown(summary, start_date, end_date):
    """Generate executive summary format."""
    
    total_activity = summary['total_test_runs'] + summary['total_test_cases']
    active_projects = len(summary['projects'])
    active_members = len(summary['activity_by_member'])
    
    # Calculate health score
    health_score = min(100, (total_activity * 2) + (active_projects * 10) + (active_members * 5))
    health_status = "🟢 Excellent" if health_score >= 80 else "🟡 Good" if health_score >= 60 else "🔴 Needs Attention"
    
    report = f"""# Test Weekly Executive Summary

**Week of {start_date} to {end_date}**

## 🎯 Key Metrics

| Metric | Value | Status |
|--------|--------|--------|
| Test Health Score | {health_score}/100 | {health_status} |
| Test Execution | {summary['total_test_runs']} runs | {"📈 Active" if summary['total_test_runs'] > 20 else "📊 Moderate"} |
| Test Development | {summary['total_test_cases']} cases | {"📈 Active" if summary['total_test_cases'] > 30 else "📊 Moderate"} |
| Project Coverage | {active_projects} projects | {"✅ Good" if active_projects >= 4 else "⚠️ Limited"} |
| Team Engagement | {active_members} members | {"✅ Good" if active_members >= 5 else "⚠️ Limited"} |

## 📊 Summary

"""
    
    if health_score >= 80:
        report += "QE activities are performing excellently this week with strong team engagement across multiple projects. "
    elif health_score >= 60:
        report += "QE activities are performing well with good coverage across key projects. "
    else:
        report += "QE activities need attention - consider reviewing team capacity and project priorities. "
    
    if summary['total_test_runs'] > 0:
        report += f"Test execution activity shows {summary['total_test_runs']} runs across {active_projects} projects. "
    
    if active_members > 0:
        report += f"Team engagement includes {active_members} active QE contributors."
    
    report += "\n\n## 🔍 Focus Areas\n\n"
    
    # Identify top project for executive attention
    if summary['project_statistics']:
        top_project = max(
            summary['project_statistics'].items(),
            key=lambda x: x[1]['test_runs'] + x[1]['test_cases']
        )
        report += f"- **Primary Focus:** {top_project[1]['name']} - highest activity with {top_project[1]['test_runs'] + top_project[1]['test_cases']} activities\n"
    
    # Risk assessment
    if health_score < 60:
        report += "- **Risk:** Below-target test activity levels may impact release quality\n"
        report += "- **Mitigation:** Review resource allocation and project priorities\n"
    else:
        report += "- **Status:** QE activities aligned with project goals\n"
    
    report += f"\n---\n*Executive Summary • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
    
    return report

def generate_technical_markdown(summary, start_date, end_date):
    """Generate detailed technical analysis."""
    
    # This would include detailed technical metrics, failure analysis, etc.
    # For brevity, using a simplified version
    
    report = f"""# QE Technical Weekly Analysis

**Analysis Period:** {start_date} to {end_date}

## 🔬 Detailed Metrics

### Test Execution Analysis
- **Total Runs:** {summary['total_test_runs']}
- **Run Distribution:** Across {len(summary['projects'])} projects
- **Average per Project:** {summary['total_test_runs'] / max(1, len(summary['projects'])):.1f} runs

### Test Development Analysis
- **Test Cases Updated:** {summary['total_test_cases']}
- **Development Activity:** {"High" if summary['total_test_cases'] > 50 else "Moderate" if summary['total_test_cases'] > 20 else "Low"}

"""
    
    # Add project-specific technical details
    if summary['project_statistics']:
        report += "## 📋 Project Technical Details\n\n"
        for project_id, stats in summary['project_statistics'].items():
            report += f"### {stats['name']} ({project_id})\n"
            report += f"- Test Runs: {stats['test_runs']}\n"
            report += f"- Test Cases: {stats['test_cases']}\n"
            report += f"- Active Members: {stats['active_members']}\n"
            report += f"- Activity Ratio: {stats['test_runs']}/{stats['test_cases']} (runs/cases)\n\n"
    
    return report

def generate_standup_markdown(summary, start_date, end_date):
    """Generate concise standup format."""
    
    total_activity = summary['total_test_runs'] + summary['total_test_cases']
    
    report = f"""# Test Weekly Standup Summary

**{start_date} to {end_date}**

## 📊 This Week
- **{summary['total_test_runs']}** test runs executed
- **{summary['total_test_cases']}** test cases updated  
- **{len(summary['projects'])}** projects active
- **{len(summary['activity_by_member'])}** team members contributing

## 🎯 Highlights
"""
    
    if summary['project_statistics']:
        top_project = max(
            summary['project_statistics'].items(),
            key=lambda x: x[1]['test_runs'] + x[1]['test_cases']
        )
        report += f"- Most active: {top_project[1]['name']}\n"
    
    if total_activity > 50:
        report += "- High activity week ✅\n"
    elif total_activity > 20:
        report += "- Moderate activity week 📊\n"
    else:
        report += "- Light activity week ⚠️\n"
    
    report += "\n## 👀 Next Week\n- Continue current testing cadence\n- Monitor project health\n"
    
    return report

def generate_slack_report(summary, template):
    """Generate Slack-optimized report format."""
    
    total_runs = summary['total_test_runs']
    total_cases = summary['total_test_cases']
    active_projects = len(summary['projects'])
    active_members = len(summary['activity_by_member'])
    
    start_date = summary['period_start'][:10]
    end_date = summary['period_end'][:10]
    
    if template == 'executive':
        health_score = min(100, (total_runs * 2) + (active_projects * 10) + (active_members * 5))
        status_emoji = "🟢" if health_score >= 80 else "🟡" if health_score >= 60 else "🔴"
        
        report = f"""📊 *Test Weekly Executive Summary*
*Week of {start_date} to {end_date}*

{status_emoji} *Test Health: {health_score}/100*
• Test Runs: {total_runs}
• Test Cases: {total_cases}  
• Projects: {active_projects}
• Team Members: {active_members}
"""
    elif template == 'standup':
        activity_emoji = "🟢" if total_runs + total_cases > 50 else "🟡" if total_runs + total_cases > 20 else "🔴"
        
        report = f"""📈 *Test Weekly Standup*
{start_date} → {end_date}

{activity_emoji} *This Week:*
• {total_runs} test runs
• {total_cases} test cases updated
• {active_projects} projects active
• {active_members} contributors
"""
    else:  # standard
        report = f"""📊 *Weekly Test Activity Report*
*{start_date} to {end_date}*

*Summary:*
• Test Runs: {total_runs}
• Test Cases: {total_cases}
• Active Projects: {active_projects}
• QE Members: {active_members}

*Activity Level:* {"🟢 High" if total_runs + total_cases > 50 else "🟡 Moderate" if total_runs + total_cases > 20 else "🔴 Low"}
"""
    
    return report

def generate_json_report(summary, template):
    """Generate JSON format report for automation."""
    
    # Add template-specific metadata
    template_metadata = {
        'template': template,
        'format': 'json',
        'generated_at': datetime.now().isoformat(),
        'report_type': 'weekly_qe_summary'
    }
    
    # Combine with existing summary data
    report_data = {
        'metadata': template_metadata,
        'summary': summary
    }
    
    return json.dumps(report_data, indent=2)

if __name__ == "__main__":
    main()
```

### 3. Report Formatting and Output

Handle different output formats and provide integration options:

```bash
# Execute Python report generation
python << 'EOF'
# (The Python code above would be executed here)
EOF

# Check execution status
if [ $? -eq 0 ]; then
    echo ""
    if [ -z "$OUTPUT_FILE" ]; then
        echo "✅ Weekly report generated successfully"
    else
        echo "✅ Weekly report saved to $OUTPUT_FILE"
        
        # Show file info
        if [ -f "$OUTPUT_FILE" ]; then
            SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
            echo "   File size: $SIZE"
            echo "   Format: $OUTPUT_FORMAT"
            
            # Provide format-specific usage suggestions
            case $OUTPUT_FORMAT in
                markdown)
                    echo "   Usage: View in markdown viewer or convert to PDF"
                    ;;
                slack)
                    echo "   Usage: Copy content for Slack message posting"
                    ;;
                json)
                    echo "   Usage: Integrate with automation tools or dashboards"
                    ;;
            esac
        fi
    fi
    
    echo ""
    echo "💡 Next Steps:"
    echo "   • Share report with team in standup or via email"
    echo "   • Archive report for historical tracking"
    echo "   • Use insights to plan upcoming week activities"
    echo "   • Set up automated weekly reporting if not already configured"
    
else
    echo "❌ Weekly report generation failed"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   • Check authentication: /polarion:health-check"
    echo "   • Verify project access permissions"  
    echo "   • Try different template: --template standup"
    echo "   • Use --verbose for detailed error information"
    exit 1
fi
```

## Examples

### Example 1: Standard weekly report for team standup
```bash
/polarion:weekly-report
```

Output:
```markdown
# Weekly Test Activity Report

**Reporting Period:** 2024-01-08 to 2024-01-15  
**Generated:** 2024-01-15 09:30

## 📊 Executive Summary

- **Total Test Runs:** 47
- **Test Cases Updated:** 123
- **Active Projects:** 4
- **Active QE Members:** 8
- **Overall Activity:** 🟢 High

## 🏢 Project Activity

| Project | Test Runs | Test Cases | Active Members | Total Activity |
|---------|-----------|------------|----------------|----------------|
| OpenShift Container Platform | 22 | 65 | 5 | 📈 87 |
| SPLAT Testing | 15 | 31 | 3 | 📊 46 |
| Container Storage | 8 | 19 | 2 | 📊 27 |
| Platform Networking | 2 | 8 | 2 | 📉 10 |

## 👥 Team Activity

| Test Contributor | Test Runs | Test Cases | Projects | Total |
|-----------|-----------|------------|----------|-------|
| Member-A | 12 | 28 | 2 | 40 |
| Member-B | 8 | 22 | 3 | 30 |
| Member-C | 10 | 15 | 1 | 25 |

## 💡 Key Insights

- ✅ **Active testing week** - Good QE engagement across projects
- 🎯 **Most active project:** OpenShift Container Platform
- 👥 **Team engagement:** 8 QE members contributed this week

## 📈 Trends & Recommendations

- **Test Execution Focus:** More test runs than case updates - good execution cadence
- **Next Week:** Continue current activity levels and monitor project health
- **Action Items:** Review any failed test runs and address infrastructure issues

---
*Report generated by Polarion QE Analytics • 2024-01-15 09:30*
```

### Example 2: Executive summary with export
```bash
/polarion:weekly-report --template executive --output executive-summary.md
```

### Example 3: Slack-formatted standup report
```bash
/polarion:weekly-report --template standup --format slack
```

Output:
```text
📈 *Test Weekly Standup*
2024-01-08 → 2024-01-15

🟢 *This Week:*
• 47 test runs
• 123 test cases updated
• 4 projects active
• 8 contributors
```

### Example 4: Technical report for engineering team
```bash
/polarion:weekly-report --template technical --keywords "storage" "networking" --output technical-weekly.md --verbose
```

### Example 5: JSON export for automation
```bash
/polarion:weekly-report --format json --output weekly-data.json
```

## Return Value

The command returns different exit codes based on execution:

- **Exit 0**: Report generated successfully
- **Exit 1**: Authentication, data collection, or generation errors

**Output Formats**:

**Markdown** (default): Human-readable formatted report with tables and sections
**JSON**: Structured data suitable for automation and dashboard integration  
**Slack**: Optimized text format for Slack messaging and team communication

## Common Use Cases

### Team Standup Integration
```bash
# Generate weekly standup report
/polarion:weekly-report --template standup --format slack > standup-message.txt

# Post to Slack (example with webhook)
curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\": \"$(cat standup-message.txt)\"}" \
  "$SLACK_WEBHOOK_URL"
```

### Management Reporting
```bash
# Executive summary for management
/polarion:weekly-report --template executive --output exec-summary-$(date +%Y%m%d).md

# Email to management
mail -s "Weekly Test Summary" management@company.com < exec-summary-$(date +%Y%m%d).md
```

### Automated Weekly Pipeline
```bash
#!/bin/bash
# Weekly reporting automation

DATE=$(date +%Y%m%d)
REPORT_DIR="/reports/weekly/$DATE"
mkdir -p "$REPORT_DIR"

# Generate multiple report formats
/polarion:weekly-report --output "$REPORT_DIR/team-report.md"
/polarion:weekly-report --template executive --output "$REPORT_DIR/executive-summary.md"
/polarion:weekly-report --format json --output "$REPORT_DIR/data-export.json"

# Archive and distribute
tar -czf "/archive/weekly-report-$DATE.tar.gz" "$REPORT_DIR"
```

### Historical Tracking
```bash
# Weekly historical data collection
/polarion:weekly-report --format json --output "history/week-$(date +%Y%U).json"

# Trend analysis (requires historical data processing)
python analyze-trends.py history/week-*.json
```

## Integration Examples

### Email Automation
```bash
# Generate and email weekly report
REPORT_FILE="weekly-report-$(date +%Y%m%d).md"
/polarion:weekly-report --output "$REPORT_FILE"

# Convert markdown to HTML for better email formatting
pandoc "$REPORT_FILE" -o "${REPORT_FILE%.md}.html"

# Send via email
mail -a "Content-Type: text/html" \
  -s "Weekly Test Activity Report" \
  team@company.com < "${REPORT_FILE%.md}.html"
```

### Dashboard Integration
```bash
# Generate JSON data for dashboard
/polarion:weekly-report --format json --output /dashboard/data/weekly-qe.json

# Update dashboard timestamp
echo "$(date)" > /dashboard/data/last-update.txt

# Trigger dashboard refresh
curl -X POST http://dashboard.company.com/api/refresh/qe-weekly
```

### Confluence Integration
```bash
# Generate report and upload to Confluence
REPORT_FILE="weekly-qe-$(date +%Y%m%d).md"
/polarion:weekly-report --output "$REPORT_FILE"

# Convert to Confluence format and upload
confluence-upload.py --space QE --title "Weekly Report $(date +%Y-%m-%d)" --file "$REPORT_FILE"
```

## Security Considerations

- **Data Privacy**: Reports may contain project names and contributor information
- **Access Control**: Report content limited to user's Polarion project permissions  
- **Export Security**: Exported files should be stored securely if containing sensitive data
- **Automation Security**: Tokens for automated reporting should be properly secured

## See Also

- Data source: `/polarion:activity` for detailed activity analysis
- Setup validation: `/polarion:health-check` for connectivity verification
- Project discovery: `/polarion:projects` for available project information

## Notes

- Reports reflect activity from the past 7 days (fixed weekly period)
- Template selection affects content depth and target audience appropriateness
- Export formats designed for different integration and sharing needs  
- Regular weekly reporting helps establish test activity baselines and trends
- Command optimized for both manual use and automated reporting pipelines