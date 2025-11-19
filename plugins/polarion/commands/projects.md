---
description: Discover and list OpenShift-related projects in Polarion with advanced filtering
argument-hint: "[--keywords <words>] [--limit <num>] [--output <file>]"
---

## Name
polarion:projects

## Synopsis
```
/polarion:projects [--keywords <words>] [--limit <num>] [--output <file>] [--format <json|csv>] [--verbose]
```

## Description

The `projects` command discovers and lists OpenShift-related projects in Polarion with intelligent filtering and search capabilities. It provides project metadata, access verification, and export options for project inventory and access auditing.

This command is useful for:
- Project discovery and inventory
- Access permission verification
- Project metadata collection
- Integration planning and setup
- Team onboarding and project mapping

## Prerequisites

Before using this command, ensure you have:

1. **Polarion API Token**: Valid authentication token with read permissions
   - Get from: https://polarion.engineering.redhat.com → User Settings → Security → API Tokens
   - Set environment variable: `export POLARION_TOKEN="your_token_here"`
   - Verify with: `/polarion:health-check`

2. **Network Access**: Connectivity to Red Hat Polarion
   - Access to `polarion.engineering.redhat.com`
   - Corporate proxy configured if applicable

3. **Basic Permissions**: Read access to project list
   - Minimum: View project names and basic metadata
   - Individual project access varies based on user permissions

## Arguments

- **--keywords <words>** (optional): Space-separated keywords to filter projects
  - Default: `["openshift", "splat", "ocp", "platform", "container"]`
  - Case-insensitive matching against project names and IDs
  - Supports multiple keywords for broader or narrower search
  - Example: `--keywords "storage" "networking" "csi"`

- **--limit <num>** (optional): Maximum number of projects to return
  - Default: 20 projects
  - Range: 1-100 projects
  - Useful for limiting output or testing
  - Example: `--limit 50` for larger inventories

- **--output <file>** (optional): Export results to specified file
  - Supports relative and absolute paths
  - File extension determines format if --format not specified
  - Example: `--output openshift-projects-$(date +%Y%m%d).json`

- **--format <json|csv>** (optional): Output format for exported data
  - Default: `json` (structured data with full metadata)
  - `csv`: Flat tabular format for spreadsheet analysis
  - Auto-detected from file extension if not specified

- **--verbose** (optional): Enable detailed output with additional metadata
  - Shows project descriptions
  - Includes access status for each project
  - Displays creation and modification dates
  - Provides troubleshooting information

## Implementation

The command performs project discovery through the following workflow:

### 1. Environment Setup and Validation

Initialize client and verify connectivity:

```bash
# Verify Polarion client availability
if ! python -c "import sys; sys.path.append('/path/to/polarion-client'); from polarion_client import PolarionClient" 2>/dev/null; then
    echo "Error: Polarion client not found. Installing dependencies..."
    pip install requests
    
    CLIENT_PATH="/path/to/polarion-client/polarion_client.py"
    if [ ! -f "$CLIENT_PATH" ]; then
        echo "Error: Polarion client not found at expected location."
        echo "Please ensure polarion_client.py is available."
        exit 1
    fi
fi

# Validate authentication
if [ -z "$POLARION_TOKEN" ]; then
    echo "Error: POLARION_TOKEN environment variable not set."
    echo "Please set: export POLARION_TOKEN='your_token_here'"
    exit 1
fi

# Test connectivity
python -c "
import sys
sys.path.append('/path/to/polarion-client')
from polarion_client import PolarionClient
client = PolarionClient()
if not client.test_connection():
    print('❌ Cannot connect to Polarion API')
    exit(1)
print('✓ Polarion connectivity verified')
" || exit 1
```

### 2. Parse Command Arguments

Process and validate command-line arguments:

```bash
# Set defaults
KEYWORDS="openshift splat ocp platform container"
LIMIT=20
OUTPUT_FILE=""
OUTPUT_FORMAT="json"
VERBOSE=false

# Parse arguments
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
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [ "$LIMIT" -lt 1 ] || [ "$LIMIT" -gt 100 ]; then
    echo "Error: limit must be between 1 and 100"
    exit 1
fi

# Convert keywords to array for Python
KEYWORDS_ARRAY=$(echo $KEYWORDS | tr ' ' ',' | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/')
```

### 3. Project Discovery and Analysis

Execute project search with metadata collection:

```python
#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime

# Add polarion client to path
sys.path.append('/path/to/polarion-client')
from polarion_client import PolarionClient

def main():
    # Parse arguments from environment
    keywords_str = os.getenv('KEYWORDS', 'openshift splat ocp platform container')
    keywords = keywords_str.split() if keywords_str.strip() else []
    limit = int(os.getenv('LIMIT', 20))
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
    
    if verbose:
        print(f"🔍 Searching for projects:")
        print(f"  - Keywords: {', '.join(keywords) if keywords else 'None (all projects)'}")
        print(f"  - Limit: {limit}")
    
    # Discover projects
    try:
        if keywords:
            projects = client.search_projects(keywords)
        else:
            projects = client.get_projects(limit=limit)
        
        # Limit results
        projects = projects[:limit]
        
        if verbose:
            print(f"✓ Found {len(projects)} matching projects")
            
    except Exception as e:
        print(f"❌ Error during project discovery: {e}")
        sys.exit(1)
    
    # Enhance project data with additional metadata
    enhanced_projects = []
    for i, project in enumerate(projects, 1):
        if verbose:
            print(f"📁 Processing project {i}/{len(projects)}: {project.get('id', 'Unknown')}")
        
        enhanced_project = enhance_project_metadata(client, project, verbose)
        enhanced_projects.append(enhanced_project)
    
    # Display results
    display_projects(enhanced_projects, verbose)
    
    # Export if requested
    if output_file:
        try:
            export_data = prepare_export_data(enhanced_projects, output_format)
            if client.export_data(export_data, output_file, output_format):
                print(f"💾 Project list exported to {output_file}")
            else:
                print(f"❌ Failed to export project list")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Export error: {e}")
            sys.exit(1)

def enhance_project_metadata(client, project, verbose=False):
    """Enhance project data with additional metadata and access verification."""
    
    enhanced = project.copy()
    project_id = project.get('id', 'unknown')
    
    try:
        # Try to get detailed project information to verify access
        detailed_project = client.get_project_by_id(project_id)
        
        if detailed_project:
            enhanced.update(detailed_project)
            enhanced['access_status'] = 'accessible'
            enhanced['access_verified'] = True
            
            # Try to get recent activity to gauge project health
            try:
                test_runs = client.get_test_runs(project_id, days_back=7, limit=5)
                enhanced['recent_test_runs'] = len(test_runs)
                enhanced['has_recent_activity'] = len(test_runs) > 0
            except:
                enhanced['recent_test_runs'] = 0
                enhanced['has_recent_activity'] = False
                
        else:
            enhanced['access_status'] = 'limited'
            enhanced['access_verified'] = False
            enhanced['recent_test_runs'] = 0
            enhanced['has_recent_activity'] = False
            
    except Exception as e:
        if verbose:
            print(f"  ⚠️  Limited access to project {project_id}: {str(e)[:50]}")
        
        enhanced['access_status'] = 'no_access'
        enhanced['access_verified'] = False
        enhanced['recent_test_runs'] = 0
        enhanced['has_recent_activity'] = False
        enhanced['access_error'] = str(e)[:100]
    
    # Add analysis metadata
    enhanced['analysis_timestamp'] = datetime.now().isoformat()
    enhanced['project_relevance'] = calculate_relevance_score(enhanced)
    
    return enhanced

def calculate_relevance_score(project):
    """Calculate relevance score based on project metadata."""
    
    score = 0
    name = project.get('name', '').lower()
    project_id = project.get('id', '').lower()
    description = project.get('description', '').lower()
    
    # OpenShift-related keywords (weighted)
    openshift_keywords = {
        'openshift': 10,
        'ocp': 8,
        'platform': 6,
        'container': 6,
        'splat': 8,
        'storage': 5,
        'networking': 5,
        'security': 5,
        'authentication': 4,
        'monitoring': 4
    }
    
    # Check in project name (highest weight)
    for keyword, weight in openshift_keywords.items():
        if keyword in name:
            score += weight * 2
        if keyword in project_id:
            score += weight * 1.5
        if keyword in description:
            score += weight * 0.5
    
    # Bonus for verified access
    if project.get('access_verified'):
        score += 5
    
    # Bonus for recent activity
    if project.get('has_recent_activity'):
        score += 3
    
    return score

def display_projects(projects, verbose=False):
    """Display formatted project list."""
    
    if not projects:
        print("\n❌ No projects found matching the criteria")
        print("\n💡 Troubleshooting:")
        print("   • Try broader keywords or remove --keywords filter")
        print("   • Increase --limit for more results")
        print("   • Check permissions with /polarion:health-check")
        return
    
    # Sort by relevance score
    projects.sort(key=lambda x: x.get('project_relevance', 0), reverse=True)
    
    print(f"\n📋 Found {len(projects)} OpenShift-Related Projects")
    print("=" * 70)
    
    # Summary statistics
    accessible = len([p for p in projects if p.get('access_verified')])
    with_activity = len([p for p in projects if p.get('has_recent_activity')])
    
    print(f"📊 Quick Stats:")
    print(f"  • Total Projects: {len(projects)}")
    print(f"  • Accessible: {accessible} ({accessible/len(projects)*100:.1f}%)")
    print(f"  • Recently Active: {with_activity} ({with_activity/len(projects)*100:.1f}%)")
    
    # Project list
    print(f"\n🏢 Project Details:")
    
    for i, project in enumerate(projects, 1):
        project_id = project.get('id', 'Unknown')
        name = project.get('name', 'Unknown')
        access_status = project.get('access_status', 'unknown')
        recent_runs = project.get('recent_test_runs', 0)
        relevance = project.get('project_relevance', 0)
        
        # Status indicator
        if access_status == 'accessible':
            status_icon = "✅"
        elif access_status == 'limited':
            status_icon = "⚠️ "
        else:
            status_icon = "❌"
        
        # Activity indicator
        activity_icon = "🟢" if recent_runs > 0 else "⚪"
        
        print(f"\n  {i:2}. {status_icon} {project_id}")
        print(f"      Name: {name[:60]}")
        
        if verbose:
            description = project.get('description', 'No description')
            print(f"      Description: {description[:80]}{'...' if len(description) > 80 else ''}")
            print(f"      Access: {access_status}")
            print(f"      Recent Activity: {recent_runs} test runs (7 days)")
            print(f"      Relevance Score: {relevance:.1f}")
            
            if project.get('access_error'):
                print(f"      Error: {project['access_error']}")
        else:
            print(f"      Access: {access_status} | Activity: {activity_icon} {recent_runs} runs | Score: {relevance:.1f}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    
    if accessible == 0:
        print("   ❌ No accessible projects found")
        print("      • Check Polarion permissions with administrator")
        print("      • Verify project access through Polarion web UI")
        print("      • Try /polarion:health-check for diagnostics")
    elif accessible < len(projects) / 2:
        print("   ⚠️  Limited project access detected")
        print("      • Request access to additional projects if needed")
        print("      • Focus on accessible projects for analysis")
    else:
        print("   ✅ Good project access coverage")
        
    if with_activity == 0:
        print("   📊 No recent activity in discovered projects")
        print("      • Projects may be in maintenance phase")
        print("      • Try longer time period: /polarion:activity --days-back 30")
    elif with_activity > 0:
        print(f"   📈 {with_activity} projects show recent test activity")
        print("      • Use /polarion:activity for detailed analysis")
        print("      • Use /polarion:test-runs PROJECT for specific deep dive")

def prepare_export_data(projects, format_type):
    """Prepare data for export in specified format."""
    
    if format_type == 'csv':
        # Flatten for CSV export
        csv_data = []
        for project in projects:
            csv_data.append({
                'id': project.get('id', ''),
                'name': project.get('name', ''),
                'description': project.get('description', '')[:100],  # Truncate for CSV
                'access_status': project.get('access_status', ''),
                'recent_test_runs': project.get('recent_test_runs', 0),
                'has_recent_activity': project.get('has_recent_activity', False),
                'relevance_score': project.get('project_relevance', 0),
                'analysis_timestamp': project.get('analysis_timestamp', '')
            })
        return csv_data
    else:
        # Full JSON export
        return {
            'projects': projects,
            'summary': {
                'total_projects': len(projects),
                'accessible_projects': len([p for p in projects if p.get('access_verified')]),
                'active_projects': len([p for p in projects if p.get('has_recent_activity')]),
                'analysis_timestamp': datetime.now().isoformat()
            }
        }

if __name__ == "__main__":
    main()
```

### 4. Results Validation and Error Handling

Validate results and provide actionable guidance:

```bash
# Check Python script exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Project discovery completed successfully"
    
    if [ -n "$OUTPUT_FILE" ]; then
        echo "📄 Project list available at: $OUTPUT_FILE"
        
        if [ -f "$OUTPUT_FILE" ]; then
            SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
            COUNT=$(if [ "$OUTPUT_FORMAT" = "json" ]; then jq '.projects | length' "$OUTPUT_FILE" 2>/dev/null || echo "unknown"; else wc -l < "$OUTPUT_FILE"; fi)
            echo "   File size: $SIZE"
            echo "   Projects: $COUNT"
            echo "   Format: $OUTPUT_FORMAT"
        fi
    fi
    
    echo ""
    echo "💡 Next Steps:"
    echo "   • Use /polarion:activity for QE activity analysis"
    echo "   • Use /polarion:test-runs PROJECT for specific project analysis"
    echo "   • Request access to projects showing 'limited' or 'no_access'"
    echo "   • Share project list with team for coordination"
    
else
    echo "❌ Project discovery failed"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   • Verify authentication: /polarion:health-check"
    echo "   • Check network connectivity to Polarion"
    echo "   • Try without keyword filters"
    echo "   • Use --verbose for detailed error information"
    exit 1
fi
```

## Examples

### Example 1: Basic project discovery with default OpenShift keywords
```
/polarion:projects
```

Output:
```
🔍 Searching for projects:
  - Keywords: openshift, splat, ocp, platform, container
  - Limit: 20
✓ Found 8 matching projects

📋 Found 8 OpenShift-Related Projects
======================================================================
📊 Quick Stats:
  • Total Projects: 8
  • Accessible: 6 (75.0%)
  • Recently Active: 4 (50.0%)

🏢 Project Details:

   1. ✅ SPLAT
      Name: SPLAT Testing Framework
      Access: accessible | Activity: 🟢 15 runs | Score: 24.0

   2. ✅ OPENSHIFT
      Name: OpenShift Container Platform
      Access: accessible | Activity: 🟢 22 runs | Score: 20.0

   3. ✅ CONTAINER_STORAGE
      Name: Container Storage Interface Testing
      Access: accessible | Activity: 🟢 8 runs | Score: 16.5

   4. ✅ OCP_NETWORKING
      Name: OpenShift Container Platform Networking
      Access: accessible | Activity: ⚪ 0 runs | Score: 15.0

💡 Recommendations:
   ✅ Good project access coverage
   📈 4 projects show recent test activity
      • Use /polarion:activity for detailed analysis
      • Use /polarion:test-runs PROJECT for specific deep dive
```

### Example 2: Custom keyword search with verbose output
```
/polarion:projects --keywords "storage" "csi" "persistent" --verbose
```

Output:
```
✓ Connected to Polarion
🔍 Searching for projects:
  - Keywords: storage, csi, persistent
  - Limit: 20
📁 Processing project 1/3: CONTAINER_STORAGE
📁 Processing project 2/3: CSI_DRIVERS
📁 Processing project 3/3: PERSISTENT_VOLUMES
✓ Found 3 matching projects

📋 Found 3 OpenShift-Related Projects
======================================================================
📊 Quick Stats:
  • Total Projects: 3
  • Accessible: 2 (66.7%)
  • Recently Active: 2 (66.7%)

🏢 Project Details:

   1. ✅ CONTAINER_STORAGE
      Name: Container Storage Interface Testing
      Description: Comprehensive testing framework for CSI drivers and storage...
      Access: accessible
      Recent Activity: 12 test runs (7 days)
      Relevance Score: 18.5

   2. ✅ CSI_DRIVERS
      Name: CSI Driver Validation Suite
      Description: Validation and certification testing for CSI storage drivers
      Access: accessible
      Recent Activity: 6 test runs (7 days)
      Relevance Score: 16.0

   3. ⚠️  PERSISTENT_VOLUMES
      Name: Persistent Volume Testing
      Description: Legacy testing framework for persistent volume operations
      Access: limited
      Recent Activity: 0 test runs (7 days)
      Relevance Score: 12.0

💡 Recommendations:
   ✅ Good project access coverage
   📈 2 projects show recent test activity
      • Use /polarion:activity for detailed analysis
      • Use /polarion:test-runs PROJECT for specific deep dive
```

### Example 3: Export to CSV for spreadsheet analysis
```
/polarion:projects --limit 50 --output openshift-projects.csv --format csv
```

### Example 4: Comprehensive project inventory
```
/polarion:projects --keywords "openshift" "platform" "container" --limit 100 --output project-inventory.json --verbose
```

## Return Value

The command returns different exit codes based on execution:

- **Exit 0**: Project discovery completed successfully  
- **Exit 1**: Authentication, network, or API errors

**Output Formats**:

**Console Output** (default): Formatted project list with metadata, access status, and recommendations

**JSON Export**: Structured data with full project metadata:
```json
{
  "projects": [
    {
      "id": "SPLAT",
      "name": "SPLAT Testing Framework",
      "description": "Comprehensive testing...",
      "access_status": "accessible",
      "access_verified": true,
      "recent_test_runs": 15,
      "has_recent_activity": true,
      "project_relevance": 24.0,
      "analysis_timestamp": "2024-01-15T10:30:00"
    }
  ],
  "summary": {
    "total_projects": 8,
    "accessible_projects": 6,
    "active_projects": 4,
    "analysis_timestamp": "2024-01-15T10:30:00"
  }
}
```

**CSV Export**: Flattened tabular format:
```csv
id,name,description,access_status,recent_test_runs,has_recent_activity,relevance_score
SPLAT,"SPLAT Testing Framework","Comprehensive testing...","accessible",15,true,24.0
```

## Common Use Cases

### Project Onboarding
```bash
# Discover available projects for new team member
/polarion:projects --verbose

# Export comprehensive list for reference
/polarion:projects --output team-projects.json
```

### Access Audit
```bash
# Check current project access
/polarion:projects --limit 100 --verbose

# Generate audit report
/polarion:projects --limit 100 --output access-audit-$(date +%Y%m%d).csv --format csv
```

### Integration Planning
```bash
# Find projects for specific domain
/polarion:projects --keywords "storage" "networking" "security"

# Export for tool integration planning
/polarion:projects --keywords "openshift" --output integration-projects.json
```

### Team Coordination
```bash
# Share project list with team
/polarion:projects --output shared-projects.json

# Focus on accessible projects only
/polarion:projects --verbose | grep -A 5 "accessible"
```

## Security Considerations

- **Read-Only Access**: Command only reads project metadata, no modifications
- **Permission Respect**: Results limited to user's Polarion project access
- **Data Privacy**: Project names and descriptions may contain sensitive information
- **Token Security**: Ensure POLARION_TOKEN environment variable is properly secured

## See Also

- Related commands: `/polarion:activity`, `/polarion:test-runs`, `/polarion:health-check`
- Project analysis: `/polarion:test-runs PROJECT` for detailed project examination
- Team reporting: `/polarion:activity` for QE activity across discovered projects

## Notes

- Project access verification performed in real-time during discovery
- Relevance scoring helps prioritize OpenShift-related projects
- Results reflect current user permissions and project activity
- Export formats suitable for further analysis and integration
- Command optimized for both interactive use and automation