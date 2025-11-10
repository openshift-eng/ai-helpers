---
description: Analyze test runs for specific projects with detailed filtering and export options
argument-hint: "<project-id> [--days-back <days>] [--limit <num>] [--output <file>]"
---

## Name
polarion:test-runs

## Synopsis
```bash
/polarion:test-runs <project-id> [--days-back <days>] [--limit <num>] [--output <file>] [--format <json|csv>] [--verbose]
```

## Description

The `test-runs` command analyzes test runs for a specific OpenShift project in Polarion, providing detailed information about test execution, results, and trends. It offers comprehensive filtering, analysis, and export capabilities for individual project deep-dive analysis.

This command is useful for:
- Individual project test activity analysis
- Test run trend tracking and monitoring
- Test execution quality assessment
- Project-specific test reporting
- Test failure pattern identification
- Release readiness evaluation

## Prerequisites

Before using this command, ensure you have:

1. **Polarion API Token**: Valid authentication token with read permissions
   - Get from: <https://polarion.engineering.redhat.com> → User Settings → Security → API Tokens
   - Set environment variable: `export POLARION_TOKEN="your_token_here"`
   - Verify with: `/polarion:health-check`

2. **Network Access**: Connectivity to Red Hat Polarion
   - Access to `polarion.engineering.redhat.com`
   - Corporate proxy configured if applicable

3. **Project Access**: Read permissions for the specified project
   - Access to project test runs and test records
   - Verify access with: `/polarion:projects --keywords PROJECT_NAME`

## Arguments

- **project-id** (required): Polarion project identifier to analyze
  - Examples: `SPLAT`, `OPENSHIFT`, `CONTAINER_STORAGE`
  - Case-sensitive exact match
  - Use `/polarion:projects` to discover available project IDs

- **--days-back <days>** (optional): Number of days to look back for test runs
  - Default: 14 days
  - Range: 1-90 days
  - Example: `--days-back 30` for monthly analysis

- **--limit <num>** (optional): Maximum number of test runs to analyze
  - Default: 50 test runs
  - Range: 1-500 runs
  - Example: `--limit 100` for comprehensive analysis

- **--output <file>** (optional): Export results to specified file
  - Supports relative and absolute paths
  - File extension determines format if --format not specified
  - Example: `--output splat-runs-$(date +%Y%m%d).json`

- **--format <json|csv>** (optional): Output format for exported data
  - Default: `json` (structured data with full metadata)
  - `csv`: Flat tabular format for spreadsheet analysis
  - Auto-detected from file extension if not specified

- **--verbose** (optional): Enable detailed output with comprehensive analysis
  - Shows individual test run details
  - Includes test record analysis when available
  - Displays failure patterns and trends
  - Provides performance timing information

## Implementation

The command performs test run analysis through the following workflow:

### 1. Project Validation and Setup

Verify project access and initialize analysis:

```bash
# Validate required arguments
if [ -z "$1" ]; then
    echo "Error: project-id is required"
    echo "Usage: /polarion:test-runs <project-id> [options]"
    echo "Use /polarion:projects to discover available projects"
    exit 1
fi

PROJECT_ID="$1"
shift

# Verify Polarion client availability
if ! python -c "import sys; sys.path.append('/path/to/polarion-client'); from polarion_client import PolarionClient" 2>/dev/null; then
    echo "Error: Polarion client not found"
    exit 1
fi

# Validate authentication
if [ -z "$POLARION_TOKEN" ]; then
    echo "Error: POLARION_TOKEN environment variable not set."
    echo "Please set: export POLARION_TOKEN='your_token_here'"
    exit 1
fi

# Test project access
python -c "
import sys
sys.path.append('/path/to/polarion-client')
from polarion_client import PolarionClient
client = PolarionClient()
project = client.get_project_by_id('$PROJECT_ID')
if not project:
    print(f'❌ Cannot access project: $PROJECT_ID')
    print('   • Verify project ID with /polarion:projects')
    print('   • Check project permissions')
    exit(1)
print(f'✓ Project access verified: {project.get(\"name\", \"$PROJECT_ID\")}')
" || exit 1
```

### 2. Parse Command Arguments

Process and validate command-line options:

```bash
# Set defaults
DAYS_BACK=14
LIMIT=50
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
        --limit)
            LIMIT="$2"
            shift 2
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

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [ "$LIMIT" -lt 1 ] || [ "$LIMIT" -gt 500 ]; then
    echo "Error: limit must be between 1 and 500"
    exit 1
fi
```

### 3. Test Run Analysis and Data Collection

Execute comprehensive test run analysis:

```python
#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

# Add polarion client to path
sys.path.append('/path/to/polarion-client')
from polarion_client import PolarionClient

def main():
    # Parse arguments from environment
    project_id = os.getenv('PROJECT_ID')
    days_back = int(os.getenv('DAYS_BACK', 14))
    limit = int(os.getenv('LIMIT', 50))
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
    
    # Get project details
    try:
        project = client.get_project_by_id(project_id)
        if not project:
            print(f"❌ Project not found: {project_id}")
            sys.exit(1)
        
        project_name = project.get('name', project_id)
        if verbose:
            print(f"📁 Analyzing project: {project_name} ({project_id})")
            
    except Exception as e:
        print(f"❌ Error accessing project: {e}")
        sys.exit(1)
    
    # Get test runs
    try:
        if verbose:
            print(f"🔍 Retrieving test runs:")
            print(f"  - Time period: {days_back} days")
            print(f"  - Limit: {limit}")
        
        test_runs = client.get_test_runs(project_id, days_back=days_back, limit=limit)
        
        if not test_runs:
            print(f"❌ No test runs found for project {project_id}")
            print(f"💡 Troubleshooting:")
            print(f"   • Try longer time period: --days-back {days_back * 2}")
            print(f"   • Verify project has test activity")
            print(f"   • Check permissions for test run access")
            sys.exit(1)
        
        if verbose:
            print(f"✓ Found {len(test_runs)} test runs")
            
    except Exception as e:
        print(f"❌ Error retrieving test runs: {e}")
        sys.exit(1)
    
    # Enhance test runs with additional analysis
    enhanced_runs = []
    test_records_data = {}
    
    for i, run in enumerate(test_runs, 1):
        if verbose and i <= 10:  # Limit verbose output
            run_id = run.get('id', 'unknown')
            print(f"📊 Analyzing run {i}/{len(test_runs)}: {run_id}")
        
        enhanced_run = enhance_test_run_data(client, project_id, run, verbose and i <= 5)
        enhanced_runs.append(enhanced_run)
        
        # Collect test records for detailed analysis (limited to avoid API overload)
        if i <= 5:  # Only get records for first 5 runs
            run_id = run.get('id')
            if run_id:
                try:
                    records = client.get_test_records(project_id, run_id)
                    test_records_data[run_id] = records
                    enhanced_run['test_records_count'] = len(records)
                except:
                    enhanced_run['test_records_count'] = 0
    
    # Perform comprehensive analysis
    analysis_results = perform_analysis(enhanced_runs, test_records_data, project_name, verbose)
    
    # Display results
    display_analysis_results(analysis_results, verbose)
    
    # Export if requested
    if output_file:
        try:
            export_data = prepare_export_data(analysis_results, output_format)
            if client.export_data(export_data, output_file, output_format):
                print(f"💾 Test run analysis exported to {output_file}")
            else:
                print(f"❌ Failed to export analysis")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Export error: {e}")
            sys.exit(1)

def enhance_test_run_data(client, project_id, run, verbose=False):
    """Enhance test run data with additional metadata and analysis."""
    
    enhanced = run.copy()
    run_id = run.get('id', 'unknown')
    
    # Parse and enhance timestamp data
    created = run.get('created', '')
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            enhanced['created_timestamp'] = created_dt.isoformat()
            # Use timezone-aware comparison
            enhanced['age_days'] = (datetime.now(timezone.utc) - created_dt).days
        except:
            enhanced['age_days'] = 0
    
    # Analyze test run status and quality
    status = run.get('status', '').lower()
    enhanced['status_category'] = categorize_status(status)
    enhanced['is_successful'] = status in ['passed', 'success', 'completed']
    enhanced['needs_attention'] = status in ['failed', 'error', 'blocked', 'cancelled']
    
    # Extract author information
    author = run.get('author', {})
    enhanced['author_name'] = author.get('name', 'Unknown')
    enhanced['author_id'] = author.get('id', 'unknown')
    
    # Calculate derived metrics
    enhanced['title_length'] = len(run.get('title', ''))
    enhanced['has_description'] = bool(run.get('description', '').strip())
    
    return enhanced

def categorize_status(status):
    """Categorize test run status into standard categories."""
    
    status_lower = status.lower()
    
    if status_lower in ['passed', 'success', 'completed', 'finished']:
        return 'success'
    elif status_lower in ['failed', 'failure', 'error', 'broken']:
        return 'failure'
    elif status_lower in ['running', 'executing', 'in_progress']:
        return 'running'
    elif status_lower in ['blocked', 'cancelled', 'aborted', 'stopped']:
        return 'blocked'
    elif status_lower in ['pending', 'queued', 'waiting', 'scheduled']:
        return 'pending'
    else:
        return 'other'

def perform_analysis(test_runs, test_records_data, project_name, verbose=False):
    """Perform comprehensive analysis of test runs."""
    
    if not test_runs:
        return {}
    
    # Basic statistics
    total_runs = len(test_runs)
    status_counts = Counter(run.get('status_category', 'other') for run in test_runs)
    success_rate = (status_counts.get('success', 0) / total_runs * 100) if total_runs > 0 else 0
    
    # Time-based analysis
    time_analysis = analyze_time_trends(test_runs)
    
    # Author analysis
    author_analysis = analyze_authors(test_runs)
    
    # Quality analysis
    quality_analysis = analyze_quality_metrics(test_runs)
    
    # Test records analysis (if available)
    records_analysis = analyze_test_records(test_records_data) if test_records_data else {}
    
    # Recent activity analysis
    recent_analysis = analyze_recent_activity(test_runs)
    
    return {
        'project_name': project_name,
        'analysis_timestamp': datetime.now().isoformat(),
        'summary': {
            'total_test_runs': total_runs,
            'success_rate': round(success_rate, 1),
            'status_breakdown': dict(status_counts),
            'time_period_days': (datetime.now() - datetime.fromisoformat(test_runs[-1].get('created_timestamp', datetime.now().isoformat()))).days if test_runs else 0
        },
        'time_trends': time_analysis,
        'author_activity': author_analysis,
        'quality_metrics': quality_analysis,
        'test_records': records_analysis,
        'recent_activity': recent_analysis,
        'test_runs': test_runs[:10],  # Include sample of test runs
        'recommendations': generate_recommendations(test_runs, success_rate, status_counts)
    }

def analyze_time_trends(test_runs):
    """Analyze time-based patterns in test runs."""
    
    # Group by day
    daily_counts = defaultdict(int)
    daily_success = defaultdict(int)
    
    for run in test_runs:
        created = run.get('created_timestamp', '')
        if created:
            try:
                date = created.split('T')[0]  # Extract date part
                daily_counts[date] += 1
                if run.get('is_successful'):
                    daily_success[date] += 1
            except:
                continue
    
    # Calculate trends
    dates = sorted(daily_counts.keys())
    recent_activity = sum(daily_counts[date] for date in dates[-3:]) if dates else 0
    avg_daily = sum(daily_counts.values()) / len(dates) if dates else 0
    
    return {
        'daily_counts': dict(daily_counts),
        'daily_success_rates': {date: (daily_success[date] / daily_counts[date] * 100) if daily_counts[date] > 0 else 0 for date in dates},
        'recent_3day_activity': recent_activity,
        'average_daily_runs': round(avg_daily, 1),
        'most_active_day': max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None,
        'trend_direction': analyze_trend_direction(daily_counts, dates)
    }

def analyze_trend_direction(daily_counts, dates):
    """Analyze whether activity is trending up, down, or stable."""
    
    if len(dates) < 7:
        return 'insufficient_data'
    
    # Compare recent week to previous week
    recent_week = sum(daily_counts[date] for date in dates[-7:])
    previous_week = sum(daily_counts[date] for date in dates[-14:-7])
    
    if recent_week > previous_week * 1.2:
        return 'increasing'
    elif recent_week < previous_week * 0.8:
        return 'decreasing'
    else:
        return 'stable'

def analyze_authors(test_runs):
    """Analyze author activity and contribution patterns."""
    
    author_stats = defaultdict(lambda: {'runs': 0, 'successes': 0, 'failures': 0})
    
    for run in test_runs:
        author = run.get('author_name', 'Unknown')
        author_stats[author]['runs'] += 1
        
        if run.get('is_successful'):
            author_stats[author]['successes'] += 1
        elif run.get('needs_attention'):
            author_stats[author]['failures'] += 1
    
    # Calculate success rates
    for stats in author_stats.values():
        total = stats['runs']
        stats['success_rate'] = (stats['successes'] / total * 100) if total > 0 else 0
    
    # Sort by activity level
    sorted_authors = sorted(author_stats.items(), key=lambda x: x[1]['runs'], reverse=True)
    
    return {
        'total_authors': len(author_stats),
        'most_active': sorted_authors[:5],
        'author_details': dict(author_stats)
    }

def analyze_quality_metrics(test_runs):
    """Analyze overall quality metrics and patterns."""
    
    total_runs = len(test_runs)
    
    # Calculate quality indicators
    has_description = sum(1 for run in test_runs if run.get('has_description'))
    recent_failures = sum(1 for run in test_runs[:10] if run.get('needs_attention'))  # Recent 10 runs
    
    # Age distribution
    age_distribution = defaultdict(int)
    for run in test_runs:
        age = run.get('age_days', 0)
        if age <= 1:
            age_distribution['today'] += 1
        elif age <= 7:
            age_distribution['this_week'] += 1
        elif age <= 30:
            age_distribution['this_month'] += 1
        else:
            age_distribution['older'] += 1
    
    return {
        'documentation_rate': (has_description / total_runs * 100) if total_runs > 0 else 0,
        'recent_failure_rate': (recent_failures / min(10, total_runs) * 100) if total_runs > 0 else 0,
        'age_distribution': dict(age_distribution),
        'average_age_days': sum(run.get('age_days', 0) for run in test_runs) / total_runs if total_runs > 0 else 0
    }

def analyze_test_records(test_records_data):
    """Analyze test records when available."""
    
    if not test_records_data:
        return {}
    
    total_records = sum(len(records) for records in test_records_data.values())
    runs_with_records = len(test_records_data)
    
    # Analyze record patterns
    record_counts = [len(records) for records in test_records_data.values()]
    avg_records_per_run = sum(record_counts) / len(record_counts) if record_counts else 0
    
    return {
        'total_test_records': total_records,
        'runs_with_records': runs_with_records,
        'average_records_per_run': round(avg_records_per_run, 1),
        'max_records_in_run': max(record_counts) if record_counts else 0,
        'min_records_in_run': min(record_counts) if record_counts else 0
    }

def analyze_recent_activity(test_runs):
    """Analyze recent activity patterns for immediate insights."""
    
    if not test_runs:
        return {}
    
    # Focus on most recent 10 runs
    recent_runs = test_runs[:10]
    
    recent_status = Counter(run.get('status_category', 'other') for run in recent_runs)
    recent_authors = set(run.get('author_name', 'Unknown') for run in recent_runs)
    
    # Check for patterns
    consecutive_failures = 0
    for run in recent_runs:
        if run.get('needs_attention'):
            consecutive_failures += 1
        else:
            break
    
    return {
        'recent_10_status': dict(recent_status),
        'recent_active_authors': len(recent_authors),
        'consecutive_failures': consecutive_failures,
        'last_success': next((i for i, run in enumerate(recent_runs) if run.get('is_successful')), None)
    }

def generate_recommendations(test_runs, success_rate, status_counts):
    """Generate actionable recommendations based on analysis."""
    
    recommendations = []
    
    # Success rate recommendations
    if success_rate < 50:
        recommendations.append({
            'type': 'critical',
            'title': 'Low Success Rate',
            'message': f'Success rate is {success_rate:.1f}%. Investigate test failures and infrastructure issues.',
            'action': 'Review failed test runs and identify common failure patterns'
        })
    elif success_rate < 75:
        recommendations.append({
            'type': 'warning',
            'title': 'Moderate Success Rate',
            'message': f'Success rate is {success_rate:.1f}%. Consider improving test reliability.',
            'action': 'Analyze failure trends and implement stability improvements'
        })
    else:
        recommendations.append({
            'type': 'positive',
            'title': 'Good Success Rate',
            'message': f'Success rate is {success_rate:.1f}%. Maintain current quality standards.',
            'action': 'Continue monitoring and maintain best practices'
        })
    
    # Activity level recommendations
    total_runs = len(test_runs)
    if total_runs < 5:
        recommendations.append({
            'type': 'info',
            'title': 'Low Activity',
            'message': 'Few test runs detected. Consider increasing test frequency.',
            'action': 'Schedule regular test runs or extend analysis time period'
        })
    
    # Failure pattern recommendations
    failure_count = status_counts.get('failure', 0)
    if failure_count > total_runs * 0.3:
        recommendations.append({
            'type': 'warning',
            'title': 'High Failure Rate',
            'message': f'{failure_count} of {total_runs} runs failed. Investigate failure causes.',
            'action': 'Analyze failure logs and implement fixes'
        })
    
    return recommendations

def display_analysis_results(analysis, verbose=False):
    """Display comprehensive analysis results."""
    
    if not analysis:
        print("❌ No analysis data available")
        return
    
    project_name = analysis.get('project_name', 'Unknown Project')
    summary = analysis.get('summary', {})
    
    print(f"\n📊 Test Run Analysis: {project_name}")
    print("=" * 70)
    
    # Summary statistics
    print(f"📈 Summary Statistics:")
    print(f"  • Total Test Runs: {summary.get('total_test_runs', 0)}")
    print(f"  • Success Rate: {summary.get('success_rate', 0):.1f}%")
    print(f"  • Analysis Period: {summary.get('time_period_days', 0)} days")
    
    # Status breakdown
    status_breakdown = summary.get('status_breakdown', {})
    if status_breakdown:
        print(f"\n📋 Status Breakdown:")
        for status, count in status_breakdown.items():
            percentage = (count / summary.get('total_test_runs', 1)) * 100
            status_icon = {'success': '✅', 'failure': '❌', 'running': '⏳', 'blocked': '🚫', 'pending': '⏸️'}.get(status, '❓')
            print(f"  • {status_icon} {status.title()}: {count} ({percentage:.1f}%)")
    
    # Time trends
    time_trends = analysis.get('time_trends', {})
    if time_trends:
        print(f"\n📅 Activity Trends:")
        trend_direction = time_trends.get('trend_direction', 'unknown')
        trend_icon = {'increasing': '📈', 'decreasing': '📉', 'stable': '➡️'}.get(trend_direction, '❓')
        
        print(f"  • Recent Trend: {trend_icon} {trend_direction.title()}")
        print(f"  • Average Daily Runs: {time_trends.get('average_daily_runs', 0)}")
        print(f"  • Recent 3-Day Activity: {time_trends.get('recent_3day_activity', 0)} runs")
        
        if time_trends.get('most_active_day'):
            most_active = time_trends['most_active_day']
            print(f"  • Most Active Day: {most_active[0]} ({most_active[1]} runs)")
    
    # Author activity
    author_activity = analysis.get('author_activity', {})
    if author_activity:
        print(f"\n👥 Author Activity:")
        print(f"  • Total Contributors: {author_activity.get('total_authors', 0)}")
        
        most_active = author_activity.get('most_active', [])
        if most_active:
            print(f"  • Top Contributors:")
            for i, (author, stats) in enumerate(most_active[:3], 1):
                print(f"    {i}. {author}: {stats['runs']} runs ({stats['success_rate']:.1f}% success)")
    
    # Quality metrics
    quality = analysis.get('quality_metrics', {})
    if quality:
        print(f"\n🔍 Quality Metrics:")
        print(f"  • Documentation Rate: {quality.get('documentation_rate', 0):.1f}% (runs with descriptions)")
        print(f"  • Recent Failure Rate: {quality.get('recent_failure_rate', 0):.1f}% (last 10 runs)")
        print(f"  • Average Run Age: {quality.get('average_age_days', 0):.1f} days")
    
    # Test records analysis
    records = analysis.get('test_records', {})
    if records:
        print(f"\n📊 Test Records Analysis:")
        print(f"  • Total Test Records: {records.get('total_test_records', 0)}")
        print(f"  • Average Records per Run: {records.get('average_records_per_run', 0)}")
        print(f"  • Runs with Records: {records.get('runs_with_records', 0)}")
    
    # Recent activity analysis
    recent = analysis.get('recent_activity', {})
    if recent and verbose:
        print(f"\n🔍 Recent Activity (Last 10 Runs):")
        recent_status = recent.get('recent_10_status', {})
        for status, count in recent_status.items():
            print(f"  • {status.title()}: {count}")
        
        consecutive_failures = recent.get('consecutive_failures', 0)
        if consecutive_failures > 0:
            print(f"  ⚠️  Consecutive Failures: {consecutive_failures}")
        
        last_success = recent.get('last_success')
        if last_success is not None:
            print(f"  ✅ Last Success: {last_success + 1} runs ago")
    
    # Recommendations
    recommendations = analysis.get('recommendations', [])
    if recommendations:
        print(f"\n💡 Recommendations:")
        for rec in recommendations:
            rec_icon = {'critical': '🚨', 'warning': '⚠️', 'positive': '✅', 'info': 'ℹ️'}.get(rec.get('type'), '💡')
            print(f"  {rec_icon} {rec.get('title', 'Recommendation')}")
            print(f"     {rec.get('message', 'No details available')}")
            if verbose and rec.get('action'):
                print(f"     Action: {rec['action']}")
    
    # Sample test runs (if verbose)
    if verbose:
        sample_runs = analysis.get('test_runs', [])[:5]
        if sample_runs:
            print(f"\n📋 Recent Test Runs (Sample):")
            for i, run in enumerate(sample_runs, 1):
                title = run.get('title', 'No Title')[:50]
                status = run.get('status', 'Unknown')
                author = run.get('author_name', 'Unknown')
                created = run.get('created_timestamp', '')[:10] if run.get('created_timestamp') else 'Unknown'
                
                status_icon = {'success': '✅', 'failure': '❌', 'running': '⏳', 'blocked': '🚫'}.get(run.get('status_category'), '❓')
                
                print(f"  {i:2}. {status_icon} {title}")
                print(f"      Status: {status} | Author: {author} | Date: {created}")

def prepare_export_data(analysis, format_type):
    """Prepare analysis data for export in specified format."""
    
    if format_type == 'csv':
        # Flatten test runs for CSV export
        csv_data = []
        test_runs = analysis.get('test_runs', [])
        
        for run in test_runs:
            csv_data.append({
                'id': run.get('id', ''),
                'title': run.get('title', ''),
                'status': run.get('status', ''),
                'status_category': run.get('status_category', ''),
                'author': run.get('author_name', ''),
                'created': run.get('created_timestamp', ''),
                'age_days': run.get('age_days', 0),
                'is_successful': run.get('is_successful', False),
                'needs_attention': run.get('needs_attention', False),
                'has_description': run.get('has_description', False)
            })
        
        return csv_data
    else:
        # Full JSON export
        return analysis

if __name__ == "__main__":
    main()
```

### 4. Results Processing and Export

Handle results and provide actionable next steps:

```bash
# Check Python script exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Test run analysis completed successfully"
    
    if [ -n "$OUTPUT_FILE" ]; then
        echo "📄 Analysis available at: $OUTPUT_FILE"
        
        if [ -f "$OUTPUT_FILE" ]; then
            SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
            echo "   File size: $SIZE"
            echo "   Format: $OUTPUT_FORMAT"
        fi
    fi
    
    echo ""
    echo "💡 Next Steps:"
    echo "   • Review recommendations for improvement opportunities"
    echo "   • Investigate any failed test runs for root causes"
    echo "   • Share analysis with project team"
    echo "   • Use /polarion:activity for cross-project comparison"
    echo "   • Monitor trends with regular analysis"
    
else
    echo "❌ Test run analysis failed"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   • Verify project ID: /polarion:projects --keywords $PROJECT_ID"
    echo "   • Check project permissions"
    echo "   • Try shorter time period: --days-back 7"
    echo "   • Use --verbose for detailed error information"
    exit 1
fi
```

## Examples

### Example 1: Basic project analysis
```bash
/polarion:test-runs SPLAT
```

Output:
```text
✓ Project access verified: SPLAT Testing Framework
📊 Test Run Analysis: SPLAT Testing Framework
======================================================================
📈 Summary Statistics:
  • Total Test Runs: 27
  • Success Rate: 74.1%
  • Analysis Period: 14 days

📋 Status Breakdown:
  • ✅ Success: 20 (74.1%)
  • ❌ Failure: 5 (18.5%)
  • ⏳ Running: 1 (3.7%)
  • 🚫 Blocked: 1 (3.7%)

📅 Activity Trends:
  • Recent Trend: 📈 Increasing
  • Average Daily Runs: 1.9
  • Recent 3-Day Activity: 8 runs
  • Most Active Day: 2024-01-12 (4 runs)

👥 Author Activity:
  • Total Contributors: 5
  • Top Contributors:
    1. User1: 12 runs (83.3% success)
    2. User2: 8 runs (75.0% success)
    3. User3: 4 runs (50.0% success)

💡 Recommendations:
  ✅ Good Success Rate
     Success rate is 74.1%. Maintain current quality standards.
  ⚠️  High Failure Rate
     5 of 27 runs failed. Investigate failure causes.
```

### Example 2: Detailed monthly analysis with export
```bash
/polarion:test-runs OPENSHIFT --days-back 30 --limit 100 --verbose --output openshift-monthly.json
```

### Example 3: Quick recent activity check
```bash
/polarion:test-runs CONTAINER_STORAGE --days-back 7 --limit 20
```

### Example 4: CSV export for spreadsheet analysis
```bash
/polarion:test-runs SPLAT --days-back 30 --output splat-test-runs.csv --format csv
```

## Return Value

The command returns different exit codes based on execution:

- **Exit 0**: Analysis completed successfully
- **Exit 1**: Project not found, access denied, or API errors

**Output Formats**:

**Console Output** (default): Comprehensive analysis with trends, recommendations, and quality metrics

**JSON Export**: Full analysis data including trends, author statistics, and raw test run data

**CSV Export**: Flattened test run data suitable for spreadsheet analysis and pivot tables

## Common Use Cases

### Project Health Assessment
```bash
# Quick project health check
/polarion:test-runs PROJECT --days-back 7

# Comprehensive monthly review
/polarion:test-runs PROJECT --days-back 30 --verbose
```

### Release Readiness Evaluation
```bash
# Pre-release quality assessment
/polarion:test-runs OPENSHIFT --days-back 14 --verbose

# Export for release report
/polarion:test-runs OPENSHIFT --days-back 30 --output release-testing.json
```

### Trend Monitoring
```bash
# Regular trend analysis
/polarion:test-runs SPLAT --days-back 14 --output trend-$(date +%Y%m%d).json

# Compare with historical data
```

### Team Performance Analysis
```bash
# Team activity overview
/polarion:test-runs PROJECT --verbose

# Export for team retrospective
/polarion:test-runs PROJECT --days-back 21 --output team-analysis.csv --format csv
```

## Security Considerations

- **Data Privacy**: Test run data may contain sensitive project information
- **Access Control**: Results limited to user's Polarion project permissions
- **Token Security**: Ensure POLARION_TOKEN is properly secured and rotated

## See Also

- Related commands: `/polarion:activity`, `/polarion:projects`, `/polarion:health-check`
- Cross-project analysis: `/polarion:activity` for multi-project QE activity
- Project discovery: `/polarion:projects` to find project IDs

## Notes

- Analysis quality depends on test run data completeness and project activity
- Large datasets may impact performance; use --limit to control scope
- Trend analysis requires sufficient historical data for meaningful insights
- Export formats designed for further analysis and historical tracking
- Command optimized for both quick checks and comprehensive analysis