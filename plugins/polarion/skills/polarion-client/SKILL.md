---
name: Polarion Client Integration
description: Comprehensive skill for integrating with Polarion test management system for test execution analysis
---

# Polarion Client Integration

This skill provides comprehensive guidance for integrating with the Polarion test management system to analyze test execution activities, track test runs, and generate reports for OpenShift projects.

## When to Use This Skill

Use this skill when you need to:
- Analyze QE activity across OpenShift projects in Polarion
- Generate comprehensive reports on test runs and test cases
- Track individual contributor activity and team metrics
- Integrate Polarion data with other development workflows
- Set up automated test reporting pipelines
- Troubleshoot Polarion API connectivity and access issues

## Prerequisites

Before using this skill, ensure you have:

1. **Polarion API Access**:
   - Valid Red Hat Polarion account
   - API token with read permissions for OpenShift projects
   - Network access to `polarion.engineering.redhat.com`

2. **Environment Setup**:
   - Python 3.6+ with requests library
   - Polarion client library (see Implementation section)
   - Environment variables configured

3. **Project Permissions**:
   - Read access to relevant OpenShift projects in Polarion
   - Permissions to view test runs and test cases

## Implementation Steps

### Step 1: Environment Setup and Authentication

Set up the Polarion client environment and verify authentication:

```bash
# Set environment variables
export POLARION_TOKEN="your_polarion_jwt_token_here"
export POLARION_BASE_URL="https://polarion.engineering.redhat.com"  # Optional

# Verify token format
if [[ ! "$POLARION_TOKEN" =~ ^[A-Za-z0-9+/=._-]+$ ]]; then
    echo "Warning: Token format may be invalid"
fi
```

**Key Implementation Details**:
- Token should be a valid JWT from Polarion web UI
- Store token securely and rotate regularly (90-day recommendation)
- Test basic connectivity before proceeding with analysis

### Step 2: Initialize Polarion Client

Set up the client library for API interactions:

```python
#!/usr/bin/env python3
"""
Polarion Client Setup and Basic Usage
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class PolarionClient:
    def __init__(self, base_url: str = "https://polarion.engineering.redhat.com", token: str = None):
        """Initialize Polarion client with authentication."""
        self.base_url = base_url.rstrip('/')
        self.token = token or os.getenv('POLARION_TOKEN')
        
        if not self.token:
            raise ValueError("Polarion token not provided and POLARION_TOKEN env var not set")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def test_connection(self) -> bool:
        """Test connectivity and authentication."""
        try:
            response = self.session.get(
                f"{self.base_url}/polarion/rest/v1/projects", 
                params={'pageSize': 1}, 
                timeout=30
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def _make_request(self, endpoint: str, params: Dict = None, retry_count: int = 3) -> Optional[Dict]:
        """Make authenticated request with retry logic."""
        url = f"{self.base_url}/polarion/rest/v1/{endpoint.lstrip('/')}"
        
        for attempt in range(retry_count):
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limited
                    import time
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None
                    
            except requests.exceptions.RequestException:
                if attempt == retry_count - 1:
                    return None
                import time
                time.sleep(1)
        
        return None

# Test the setup
if __name__ == "__main__":
    client = PolarionClient()
    if client.test_connection():
        print("✅ Polarion client setup successful")
    else:
        print("❌ Polarion client setup failed")
```

**Error Handling**:
- Always test connectivity before performing analysis
- Implement exponential backoff for rate limiting
- Provide clear error messages for authentication failures

### Step 3: Project Discovery and Filtering

Discover OpenShift-related projects with intelligent filtering:

```python
def discover_openshift_projects(client: PolarionClient) -> List[Dict]:
    """Discover and filter OpenShift-related projects."""
    
    # Get all projects
    all_projects = client.get_projects(limit=100)
    
    # OpenShift-related keywords (prioritized)
    openshift_keywords = [
        'openshift', 'ocp', 'splat', 'platform', 
        'container', 'storage', 'networking', 'security'
    ]
    
    # Filter projects by keywords
    openshift_projects = []
    for project in all_projects:
        project_name = project.get('name', '').lower()
        project_id = project.get('id', '').lower()
        
        # Check for OpenShift relevance
        relevance_score = 0
        for keyword in openshift_keywords:
            if keyword in project_name:
                relevance_score += 2
            if keyword in project_id:
                relevance_score += 1
        
        if relevance_score > 0:
            project['relevance_score'] = relevance_score
            openshift_projects.append(project)
    
    # Sort by relevance
    openshift_projects.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    return openshift_projects

# Enhanced project access verification
def verify_project_access(client: PolarionClient, project_id: str) -> Dict:
    """Verify and categorize project access level."""
    
    access_info = {
        'project_id': project_id,
        'accessible': False,
        'has_test_runs': False,
        'recent_activity': False,
        'access_level': 'none'
    }
    
    try:
        # Test basic project access
        project = client.get_project_by_id(project_id)
        if project:
            access_info['accessible'] = True
            access_info['access_level'] = 'basic'
            
            # Test test run access
            test_runs = client.get_test_runs(project_id, days_back=7, limit=5)
            if test_runs:
                access_info['has_test_runs'] = True
                access_info['access_level'] = 'full'
                access_info['recent_activity'] = len(test_runs) > 0
                
    except Exception as e:
        access_info['error'] = str(e)
    
    return access_info
```

**Best Practices**:
- Use keyword-based filtering for OpenShift project identification
- Verify access permissions before attempting data collection
- Cache project lists to reduce API calls during analysis

### Step 4: QE Activity Analysis

Implement comprehensive test execution analysis:

```python
def analyze_qe_activity(client: PolarionClient, days_back: int = 7, project_limit: int = 5) -> Dict:
    """Perform comprehensive test execution analysis."""
    
    # Discover projects
    projects = discover_openshift_projects(client)[:project_limit]
    
    summary = {
        'period_start': (datetime.now() - timedelta(days=days_back)).isoformat(),
        'period_end': datetime.now().isoformat(),
        'projects': [],
        'total_test_runs': 0,
        'total_test_cases': 0,
        'qe_members': set(),
        'activity_by_member': {},
        'project_statistics': {}
    }
    
    for project in projects:
        project_id = project['id']
        project_analysis = analyze_project_activity(client, project_id, days_back)
        
        summary['projects'].append(project_analysis)
        summary['total_test_runs'] += project_analysis['test_runs_count']
        summary['total_test_cases'] += project_analysis['test_cases_count']
        
        # Aggregate member activity
        for member, activity in project_analysis['member_activity'].items():
            if member not in summary['activity_by_member']:
                summary['activity_by_member'][member] = {
                    'test_runs_created': 0,
                    'test_cases_updated': 0,
                    'projects': set()
                }
            
            summary['activity_by_member'][member]['test_runs_created'] += activity['test_runs']
            summary['activity_by_member'][member]['test_cases_updated'] += activity['test_cases']
            summary['activity_by_member'][member]['projects'].add(project_id)
        
        # Project statistics
        summary['project_statistics'][project_id] = {
            'name': project.get('name', project_id),
            'test_runs': project_analysis['test_runs_count'],
            'test_cases': project_analysis['test_cases_count'],
            'active_members': len(project_analysis['member_activity'])
        }
    
    # Convert sets to lists for JSON serialization
    for member_data in summary['activity_by_member'].values():
        member_data['projects'] = list(member_data['projects'])
    
    return summary

def analyze_project_activity(client: PolarionClient, project_id: str, days_back: int) -> Dict:
    """Analyze activity for a specific project."""
    
    # Get test runs
    test_runs = client.get_test_runs(project_id, days_back=days_back)
    
    # Get test cases
    test_cases = client.get_work_items(project_id, 'testcase', days_back=days_back)
    
    # Analyze member contributions
    member_activity = {}
    
    for run in test_runs:
        author = run.get('author', {})
        if author:
            author_id = author.get('id', 'unknown')
            if author_id not in member_activity:
                member_activity[author_id] = {
                    'name': author.get('name', author_id),
                    'test_runs': 0,
                    'test_cases': 0
                }
            member_activity[author_id]['test_runs'] += 1
    
    for case in test_cases:
        author = case.get('author', {})
        if author:
            author_id = author.get('id', 'unknown')
            if author_id not in member_activity:
                member_activity[author_id] = {
                    'name': author.get('name', author_id),
                    'test_runs': 0,
                    'test_cases': 0
                }
            member_activity[author_id]['test_cases'] += 1
    
    return {
        'project_id': project_id,
        'test_runs_count': len(test_runs),
        'test_cases_count': len(test_cases),
        'member_activity': member_activity,
        'test_runs': test_runs[:10],  # Sample for analysis
        'test_cases': test_cases[:10]  # Sample for analysis
    }
```

**Analysis Features**:
- Multi-project activity correlation
- Individual contributor tracking
- Time-based filtering and trends
- Project activity ranking and comparison

### Step 5: Report Generation and Export

Generate comprehensive reports in multiple formats:

```python
def generate_activity_report(summary: Dict, format: str = 'markdown') -> str:
    """Generate formatted activity report."""
    
    if format == 'json':
        return json.dumps(summary, indent=2, default=str)
    
    elif format == 'csv':
        return generate_csv_report(summary)
    
    else:  # markdown (default)
        return generate_markdown_report(summary)

def generate_markdown_report(summary: Dict) -> str:
    """Generate markdown-formatted report."""
    
    start_date = summary['period_start'][:10]
    end_date = summary['period_end'][:10]
    
    report = f"""# QE Activity Report

**Period:** {start_date} to {end_date}  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Summary

- **Total Test Runs:** {summary['total_test_runs']}
- **Total Test Cases:** {summary['total_test_cases']}
- **Active Projects:** {len(summary['projects'])}
- **Active QE Members:** {len(summary['activity_by_member'])}

## Project Activity

"""
    
    # Project statistics table
    if summary['project_statistics']:
        report += "| Project | Test Runs | Test Cases | Members |\n"
        report += "|---------|-----------|------------|----------|\n"
        
        for project_id, stats in summary['project_statistics'].items():
            report += f"| {stats['name'][:30]} | {stats['test_runs']} | {stats['test_cases']} | {stats['active_members']} |\n"
    
    # Member activity
    if summary['activity_by_member']:
        report += "\n## QE Member Activity\n\n"
        
        sorted_members = sorted(
            summary['activity_by_member'].items(),
            key=lambda x: x[1]['test_runs_created'] + x[1]['test_cases_updated'],
            reverse=True
        )
        
        report += "| Member | Test Runs | Test Cases | Projects |\n"
        report += "|--------|-----------|------------|----------|\n"
        
        for member_id, activity in sorted_members:
            project_count = len(activity['projects'])
            member_name = activity.get('name', member_id)[:20]
            
            report += f"| {member_name} | {activity['test_runs_created']} | {activity['test_cases_updated']} | {project_count} |\n"
    
    report += f"\n---\n*Generated by Polarion QE Analytics*\n"
    
    return report

def export_data(data: Dict, filename: str, format: str = 'json') -> bool:
    """Export data to file in specified format."""
    
    try:
        if format.lower() == 'json':
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        elif format.lower() == 'csv':
            import csv
            if isinstance(data, dict) and 'activity_by_member' in data:
                # Export member activity as CSV
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Member', 'Test Runs', 'Test Cases', 'Projects', 'Total Activity'])
                    
                    for member_id, activity in data['activity_by_member'].items():
                        total = activity['test_runs_created'] + activity['test_cases_updated']
                        projects = len(activity['projects'])
                        writer.writerow([
                            activity.get('name', member_id),
                            activity['test_runs_created'],
                            activity['test_cases_updated'],
                            projects,
                            total
                        ])
        
        return True
        
    except Exception:
        return False
```

**Export Capabilities**:
- Multiple format support (JSON, CSV, Markdown)
- Structured data for automation integration
- Human-readable reports for team communication

### Step 6: Integration and Automation

Set up integration with existing workflows:

```python
def setup_automated_reporting():
    """Example automation setup for regular test reporting."""
    
    # Weekly reporting script
    weekly_script = """#!/bin/bash
# Weekly QE Activity Report Automation

export POLARION_TOKEN="your_token_here"
DATE=$(date +%Y%m%d)
REPORT_DIR="/reports/weekly"

# Generate comprehensive weekly report
python polarion_analysis.py \\
    --days-back 7 \\
    --project-limit 10 \\
    --output "$REPORT_DIR/qe-weekly-$DATE.json" \\
    --format json

# Generate markdown summary for team
python polarion_analysis.py \\
    --days-back 7 \\
    --project-limit 10 \\
    --output "$REPORT_DIR/qe-summary-$DATE.md" \\
    --format markdown

# Email to team (example)
mail -s "Weekly QE Summary" team@company.com < "$REPORT_DIR/qe-summary-$DATE.md"
"""
    
    return weekly_script

# Integration with CI/CD pipelines
def integrate_with_cicd():
    """Example CI/CD integration for QE health checks."""
    
    ci_script = """#!/bin/bash
# CI/CD QE Health Check

# Quick QE activity validation
if ! python -c "
from polarion_client import PolarionClient
client = PolarionClient()
summary = client.get_qe_activity_summary(days_back=3, project_limit=3)
if summary['total_test_runs'] + summary['total_test_cases'] < 5:
    print('WARNING: Low QE activity detected')
    exit(1)
print('QE activity check passed')
"; then
    echo "WARNING: QE activity below threshold"
    # Continue with deployment but flag for attention
fi
"""
    
    return ci_script
```

## Error Handling

Implement comprehensive error handling for robust operation:

```python
def robust_polarion_operation(operation_func, *args, **kwargs):
    """Wrapper for robust Polarion operations with error handling."""
    
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            return operation_func(*args, **kwargs)
            
        except requests.exceptions.ConnectionError:
            print(f"Connection error (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))
            
        except requests.exceptions.Timeout:
            print(f"Request timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print("Authentication failed - check token")
                break
            elif e.response.status_code == 403:
                print("Access forbidden - check permissions")
                break
            elif e.response.status_code == 429:
                print("Rate limited - waiting before retry")
                time.sleep(retry_delay * 10)
            else:
                print(f"HTTP error {e.response.status_code}")
                
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
    
    return None

# Common error scenarios and solutions
ERROR_SOLUTIONS = {
    'authentication_failed': [
        'Verify POLARION_TOKEN is set correctly',
        'Check if token has expired',
        'Regenerate token in Polarion web UI',
        'Verify network access to Polarion'
    ],
    'no_projects_found': [
        'Check user permissions for OpenShift projects',
        'Verify project naming conventions',
        'Try broader keyword search',
        'Contact Polarion administrator'
    ],
    'empty_results': [
        'Extend time period with --days-back',
        'Check project activity levels',
        'Verify user has read access to test data',
        'Try different projects or keywords'
    ],
    'network_issues': [
        'Check internet connectivity',
        'Configure corporate proxy if needed',
        'Verify firewall allows HTTPS (port 443)',
        'Test basic connectivity: curl `https://polarion.engineering.redhat.com`'
    ]
}
```

## Performance Optimization

Optimize for large-scale analysis and automation:

```python
# Rate limiting and courtesy delays
def rate_limited_requests(client: PolarionClient, requests_list: List, delay: float = 0.5):
    """Execute requests with rate limiting."""
    
    results = []
    for i, request_params in enumerate(requests_list):
        result = client._make_request(**request_params)
        results.append(result)
        
        # Courtesy delay between requests
        if i < len(requests_list) - 1:
            time.sleep(delay)
    
    return results

# Caching for repeated operations
class CachedPolarionClient(PolarionClient):
    """Polarion client with basic caching for repeated operations."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._project_cache = {}
        self._cache_timeout = 300  # 5 minutes
    
    def get_projects_cached(self, limit: int = None):
        """Get projects with caching."""
        
        cache_key = f"projects_{limit}"
        current_time = time.time()
        
        if (cache_key in self._project_cache and 
            current_time - self._project_cache[cache_key]['timestamp'] < self._cache_timeout):
            return self._project_cache[cache_key]['data']
        
        # Fetch fresh data
        projects = self.get_projects(limit=limit)
        self._project_cache[cache_key] = {
            'data': projects,
            'timestamp': current_time
        }
        
        return projects
```

## Security Best Practices

Ensure secure handling of authentication and data:

```python
# Secure token handling
def get_secure_token():
    """Securely retrieve Polarion token."""
    
    # Priority order: environment variable > keyring > prompt
    token = os.getenv('POLARION_TOKEN')
    
    if not token:
        try:
            import keyring
            token = keyring.get_password("polarion", "api_token")
        except ImportError:
            pass
    
    if not token:
        import getpass
        token = getpass.getpass("Enter Polarion API token: ")
    
    return token

# Data sanitization for reports
def sanitize_report_data(data: Dict) -> Dict:
    """Sanitize sensitive data from reports."""
    
    sanitized = data.copy()
    
    # Remove or anonymize sensitive fields
    if 'activity_by_member' in sanitized:
        for member_id, activity in sanitized['activity_by_member'].items():
            # Optionally anonymize member names
            if 'name' in activity:
                activity['name'] = activity['name'].split()[0] if activity['name'] else 'QE Member'
    
    return sanitized
```

## Testing and Validation

Implement testing for reliable operation:

```python
def validate_setup():
    """Validate complete setup and configuration."""
    
    checks = {
        'token_available': bool(os.getenv('POLARION_TOKEN')),
        'network_accessible': False,
        'authentication_valid': False,
        'projects_accessible': False
    }
    
    # Network connectivity check
    try:
        import urllib.request
        urllib.request.urlopen('https://polarion.engineering.redhat.com', timeout=10)
        checks['network_accessible'] = True
    except:
        pass
    
    # Authentication check
    if checks['token_available']:
        try:
            client = PolarionClient()
            checks['authentication_valid'] = client.test_connection()
            
            if checks['authentication_valid']:
                projects = client.get_projects(limit=1)
                checks['projects_accessible'] = len(projects) > 0
        except:
            pass
    
    return checks

# Integration testing
def test_complete_workflow():
    """Test complete analysis workflow."""
    
    try:
        client = PolarionClient()
        
        # Test project discovery
        projects = discover_openshift_projects(client)
        print(f"✓ Discovered {len(projects)} OpenShift projects")
        
        # Test activity analysis
        if projects:
            summary = analyze_qe_activity(client, days_back=7, project_limit=2)
            print(f"✓ Analyzed {summary['total_test_runs']} test runs")
            
            # Test report generation
            report = generate_markdown_report(summary)
            print(f"✓ Generated report ({len(report)} characters)")
            
            return True
        else:
            print("⚠ No projects found for testing")
            return False
            
    except Exception as e:
        print(f"✗ Workflow test failed: {e}")
        return False
```

## Monitoring and Maintenance

Set up monitoring for production use:

```python
def monitor_polarion_health():
    """Monitor Polarion integration health."""
    
    health_metrics = {
        'timestamp': datetime.now().isoformat(),
        'connectivity': False,
        'authentication': False,
        'api_latency': None,
        'project_count': 0,
        'last_activity': None
    }
    
    start_time = time.time()
    
    try:
        client = PolarionClient()
        
        # Test connectivity and measure latency
        health_metrics['connectivity'] = client.test_connection()
        health_metrics['api_latency'] = time.time() - start_time
        
        if health_metrics['connectivity']:
            health_metrics['authentication'] = True
            
            # Get project count
            projects = client.get_projects(limit=10)
            health_metrics['project_count'] = len(projects)
            
            # Check for recent activity
            if projects:
                summary = client.get_qe_activity_summary(days_back=1, project_limit=3)
                if summary['total_test_runs'] > 0:
                    health_metrics['last_activity'] = summary['period_end']
        
    except Exception as e:
        health_metrics['error'] = str(e)
    
    return health_metrics

# Automated health checks
def setup_health_monitoring():
    """Set up automated health monitoring."""
    
    cron_job = """#!/bin/bash
# Polarion Health Check - runs every hour
# 0 * * * * /path/to/polarion_health_check.py

export POLARION_TOKEN="your_token"

python -c "
from polarion_skill import monitor_polarion_health
import json

health = monitor_polarion_health()
with open('/var/log/polarion-health.log', 'a') as f:
    f.write(json.dumps(health) + '\\n')

if not health['connectivity']:
    print('ALERT: Polarion connectivity failed')
    # Send alert notification
"
"""
    
    return cron_job
```

## Examples

Complete example workflows for common scenarios:

```python
# Example 1: Weekly Team Report
def weekly_team_report():
    """Generate weekly report for team standup."""
    
    client = PolarionClient()
    summary = analyze_qe_activity(client, days_back=7, project_limit=5)
    
    report = generate_markdown_report(summary)
    
    # Save report
    filename = f"weekly-report-{datetime.now().strftime('%Y%m%d')}.md"
    with open(filename, 'w') as f:
        f.write(report)
    
    print(f"📄 Weekly report saved to {filename}")
    return filename

# Example 2: Management Dashboard Data
def management_dashboard_export():
    """Export data for management dashboard."""
    
    client = PolarionClient()
    summary = analyze_qe_activity(client, days_back=30, project_limit=15)
    
    # Prepare dashboard metrics
    dashboard_data = {
        'timestamp': datetime.now().isoformat(),
        'period_days': 30,
        'total_activity': summary['total_test_runs'] + summary['total_test_cases'],
        'active_projects': len(summary['projects']),
        'team_size': len(summary['activity_by_member']),
        'project_breakdown': summary['project_statistics'],
        'health_score': calculate_health_score(summary)
    }
    
    # Export for dashboard
    with open('/dashboard/data/qe-metrics.json', 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    return dashboard_data

def calculate_health_score(summary: Dict) -> int:
    """Calculate overall QE health score."""
    
    total_activity = summary['total_test_runs'] + summary['total_test_cases']
    active_projects = len(summary['projects'])
    team_size = len(summary['activity_by_member'])
    
    # Weighted scoring
    score = min(100, (total_activity * 1.5) + (active_projects * 8) + (team_size * 5))
    return int(score)

# Example 3: CI/CD Integration
def cicd_health_check():
    """QE health check for CI/CD pipelines."""
    
    try:
        client = PolarionClient()
        
        # Quick connectivity check
        if not client.test_connection():
            return {'status': 'error', 'message': 'Polarion not accessible'}
        
        # Check recent activity
        summary = analyze_qe_activity(client, days_back=3, project_limit=3)
        recent_activity = summary['total_test_runs'] + summary['total_test_cases']
        
        if recent_activity < 5:
            return {'status': 'warning', 'message': 'Low QE activity detected'}
        
        return {'status': 'healthy', 'message': f'{recent_activity} test execution activities in last 3 days'}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
```

## Troubleshooting Guide

Common issues and their solutions:

### Authentication Problems
**Symptoms**: 401 errors, "Authentication failed" messages
**Solutions**:
1. Verify token in environment: `echo $POLARION_TOKEN | wc -c`
2. Test token in browser: `https://polarion.engineering.redhat.com`
3. Regenerate token in Polarion web UI
4. Check token expiration date

### Network Connectivity Issues
**Symptoms**: Connection timeouts, network errors
**Solutions**:
1. Test basic connectivity: `curl -I https://polarion.engineering.redhat.com`
2. Configure proxy: `export HTTPS_PROXY=http://proxy:port`
3. Check firewall rules for port 443
4. Verify DNS resolution: `nslookup polarion.engineering.redhat.com`

### Empty or Limited Results
**Symptoms**: No projects found, zero activity data
**Solutions**:
1. Verify project permissions in Polarion web UI
2. Extend time period: increase `days_back` parameter
3. Check project naming: try broader keywords
4. Validate user access to test run data

### Performance Issues
**Symptoms**: Slow responses, timeouts on large datasets
**Solutions**:
1. Reduce `project_limit` and `days_back` parameters
2. Implement request batching with delays
3. Use caching for repeated operations
4. Monitor API rate limits and implement backoff

This skill provides comprehensive guidance for implementing robust Polarion integration with proper error handling, security practices, and automation capabilities.