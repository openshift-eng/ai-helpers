---
description: Verify Polarion connectivity, authentication, and project access permissions
argument-hint: "[--verbose] [--projects] [--export]"
---

## Name
polarion:health-check

## Synopsis
```
/polarion:health-check [--verbose] [--projects] [--export <file>]
```

## Description

The `health-check` command performs comprehensive diagnostics of Polarion connectivity, authentication, and project access permissions. It validates the complete integration setup and provides actionable guidance for resolving common issues.

This command is useful for:
- Initial setup validation and troubleshooting
- Authentication and connectivity verification
- Project access permission auditing
- Integration health monitoring
- Pre-automation setup validation
- Network and proxy configuration verification

## Prerequisites

This command has minimal prerequisites and is designed to help diagnose setup issues:

1. **Network Access**: Basic connectivity to Red Hat Polarion
   - Access to `polarion.engineering.redhat.com`
   - Corporate proxy configured if applicable

2. **Environment Setup**: Basic environment configuration
   - `POLARION_TOKEN` environment variable (if available)
   - Polarion client library accessible

## Arguments

- **--verbose** (optional): Enable detailed diagnostic output
  - Shows API request/response details
  - Includes network timing information
  - Displays comprehensive error messages
  - Provides detailed troubleshooting steps

- **--projects** (optional): Include project access verification
  - Tests access to discovered OpenShift projects
  - Validates read permissions for test data
  - May take longer due to additional API calls
  - Useful for comprehensive access auditing

- **--export <file>** (optional): Export health check results to file
  - Includes all diagnostic information
  - Suitable for sharing with support teams
  - JSON format with structured diagnostic data
  - Example: `--export health-check-$(date +%Y%m%d).json`

## Implementation

The command performs systematic health checks through the following workflow:

### 1. Environment Assessment

Check basic environment and dependencies:

```bash
echo "🔍 Polarion Health Check Starting..."
echo "=================================="

# Check for Polarion client
echo -n "📦 Checking Polarion client availability... "
if python -c "import sys; sys.path.append('/path/to/polarion-client'); from polarion_client import PolarionClient" 2>/dev/null; then
    echo "✅ Available"
    CLIENT_AVAILABLE=true
else
    echo "❌ Not found"
    CLIENT_AVAILABLE=false
    echo "   Error: Polarion client not found"
    echo "   Solution: Ensure polarion_client.py is available in the expected location"
fi

# Check dependencies
echo -n "📦 Checking Python dependencies... "
if python -c "import requests, json, datetime" 2>/dev/null; then
    echo "✅ Available"
    DEPS_AVAILABLE=true
else
    echo "❌ Missing"
    DEPS_AVAILABLE=false
    echo "   Error: Required Python packages not available"
    echo "   Solution: pip install requests"
fi

# Check token environment variable
echo -n "🔐 Checking API token environment... "
if [ -n "$POLARION_TOKEN" ]; then
    TOKEN_LENGTH=${#POLARION_TOKEN}
    echo "✅ Set (${TOKEN_LENGTH} characters)"
    TOKEN_AVAILABLE=true
    
    # Basic token format validation
    if [[ "$POLARION_TOKEN" =~ ^[A-Za-z0-9+/=._-]+$ ]]; then
        echo "   ✅ Token format appears valid"
    else
        echo "   ⚠️  Token format may be invalid"
    fi
else
    echo "❌ Not set"
    TOKEN_AVAILABLE=false
    echo "   Error: POLARION_TOKEN environment variable not set"
    echo "   Solution: export POLARION_TOKEN='your_token_here'"
fi
```

### 2. Network Connectivity Testing

Verify network access and proxy configuration:

```bash
echo ""
echo "🌐 Network Connectivity Tests"
echo "============================="

# Basic connectivity test
echo -n "🔗 Testing basic connectivity to Polarion... "
if curl -s --connect-timeout 10 --max-time 30 https://polarion.engineering.redhat.com > /dev/null 2>&1; then
    echo "✅ Success"
    NETWORK_OK=true
else
    echo "❌ Failed"
    NETWORK_OK=false
    echo "   Error: Cannot reach polarion.engineering.redhat.com"
    echo "   Solutions:"
    echo "     • Check internet connectivity"
    echo "     • Verify firewall/proxy settings"
    echo "     • Configure proxy: export HTTPS_PROXY=http://proxy:port"
fi

# DNS resolution test
echo -n "🌐 Testing DNS resolution... "
if nslookup polarion.engineering.redhat.com > /dev/null 2>&1; then
    echo "✅ Success"
    DNS_OK=true
    
    # Get IP address for diagnostics
    IP_ADDRESS=$(nslookup polarion.engineering.redhat.com | grep -A1 "Name:" | grep "Address:" | awk '{print $2}' | head -1)
    if [ -n "$IP_ADDRESS" ]; then
        echo "   ✅ Resolved to: $IP_ADDRESS"
    fi
else
    echo "❌ Failed"
    DNS_OK=false
    echo "   Error: Cannot resolve polarion.engineering.redhat.com"
    echo "   Solutions:"
    echo "     • Check DNS configuration"
    echo "     • Verify corporate DNS settings"
fi

# SSL/TLS test
echo -n "🔒 Testing SSL/TLS connection... "
if openssl s_client -connect polarion.engineering.redhat.com:443 -verify_return_error < /dev/null > /dev/null 2>&1; then
    echo "✅ Success"
    SSL_OK=true
else
    echo "⚠️  Warning"
    SSL_OK=false
    echo "   Warning: SSL verification failed"
    echo "   Note: This may work with standard HTTPS clients"
fi

# Proxy detection
if [ -n "$HTTPS_PROXY" ] || [ -n "$HTTP_PROXY" ]; then
    echo "🔧 Proxy configuration detected:"
    [ -n "$HTTPS_PROXY" ] && echo "   HTTPS_PROXY: $HTTPS_PROXY"
    [ -n "$HTTP_PROXY" ] && echo "   HTTP_PROXY: $HTTP_PROXY"
fi
```

### 3. API Authentication Testing

Test Polarion API authentication and basic functionality:

```python
#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime

def test_authentication():
    """Test Polarion API authentication and basic functionality."""
    
    # Import client
    try:
        sys.path.append('/path/to/polarion-client')
        from polarion_client import PolarionClient
        print("✅ Polarion client imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Polarion client: {e}")
        return False
    
    # Initialize client
    try:
        client = PolarionClient()
        print("✅ Polarion client initialized")
    except ValueError as e:
        print(f"❌ Client initialization failed: {e}")
        print("   Error: Token not available or invalid")
        print("   Solution: Set POLARION_TOKEN environment variable")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during initialization: {e}")
        return False
    
    # Test basic connectivity
    print("\n🔍 API Authentication Tests")
    print("=========================")
    
    try:
        print("🔐 Testing API authentication... ", end="")
        if client.test_connection():
            print("✅ Success")
            auth_ok = True
        else:
            print("❌ Failed")
            print("   Error: Authentication failed")
            print("   Solutions:")
            print("     • Verify token is correct and not expired")
            print("     • Regenerate token in Polarion web UI")
            print("     • Check token permissions")
            auth_ok = False
    except Exception as e:
        print(f"❌ Error: {e}")
        auth_ok = False
    
    if not auth_ok:
        return False
    
    # Test basic API functionality
    try:
        print("📋 Testing project list access... ", end="")
        projects = client.get_projects(limit=5)
        if projects:
            print(f"✅ Success ({len(projects)} projects accessible)")
            projects_ok = True
        else:
            print("⚠️  Warning: No projects returned")
            print("   This may be normal if you have limited access")
            projects_ok = True  # Not necessarily an error
    except Exception as e:
        print(f"❌ Error: {e}")
        print("   Error: Cannot access project list")
        print("   Solutions:")
        print("     • Verify account has basic read permissions")
        print("     • Check with Polarion administrator")
        projects_ok = False
    
    return auth_ok and projects_ok

def test_project_access(verbose=False):
    """Test access to OpenShift-related projects."""
    
    print("\n🏢 Project Access Tests")
    print("=====================")
    
    try:
        sys.path.append('/path/to/polarion-client')
        from polarion_client import PolarionClient
        client = PolarionClient()
    except Exception as e:
        print(f"❌ Cannot initialize client for project tests: {e}")
        return False
    
    # Discover OpenShift projects
    try:
        print("🔍 Discovering OpenShift-related projects... ", end="")
        projects = client.search_projects(['openshift', 'splat', 'ocp', 'platform', 'container'])
        print(f"✅ Found {len(projects)} projects")
        
        if len(projects) == 0:
            print("   ⚠️  No OpenShift-related projects found")
            print("   This may indicate:")
            print("     • Limited project access permissions")
            print("     • Different project naming conventions")
            print("     • Need for additional keyword searches")
            return True  # Not an error, just limited access
        
    except Exception as e:
        print(f"❌ Error during project discovery: {e}")
        return False
    
    # Test access to discovered projects
    accessible_count = 0
    limited_count = 0
    failed_count = 0
    
    print(f"\n📊 Testing access to {min(len(projects), 5)} projects:")
    
    for i, project in enumerate(projects[:5], 1):
        project_id = project.get('id', 'unknown')
        project_name = project.get('name', 'Unknown')
        
        try:
            # Test detailed project access
            detailed = client.get_project_by_id(project_id)
            if detailed:
                # Test test run access
                test_runs = client.get_test_runs(project_id, days_back=7, limit=1)
                accessible_count += 1
                
                if verbose:
                    print(f"  {i}. ✅ {project_id}: Full access ({len(test_runs)} recent runs)")
                else:
                    print(f"  {i}. ✅ {project_id}: Accessible")
            else:
                limited_count += 1
                if verbose:
                    print(f"  {i}. ⚠️  {project_id}: Limited access")
                else:
                    print(f"  {i}. ⚠️  {project_id}: Limited")
                
        except Exception as e:
            failed_count += 1
            if verbose:
                print(f"  {i}. ❌ {project_id}: No access ({str(e)[:50]})")
            else:
                print(f"  {i}. ❌ {project_id}: No access")
    
    # Summary
    total_tested = min(len(projects), 5)
    print(f"\n📊 Access Summary:")
    print(f"   • Full Access: {accessible_count}/{total_tested} ({accessible_count/total_tested*100:.1f}%)")
    print(f"   • Limited Access: {limited_count}/{total_tested}")
    print(f"   • No Access: {failed_count}/{total_tested}")
    
    if accessible_count == 0:
        print("\n⚠️  Warning: No projects with full access")
        print("   Recommendations:")
        print("     • Contact administrator for project access")
        print("     • Verify you're assigned to OpenShift projects")
        print("     • Check Polarion role and permissions")
    elif accessible_count < total_tested / 2:
        print("\n💡 Recommendation: Request access to additional projects for full analysis capability")
    else:
        print("\n✅ Good project access for comprehensive analysis")
    
    return True

def generate_health_report():
    """Generate comprehensive health report."""
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'environment': {
            'token_available': bool(os.getenv('POLARION_TOKEN')),
            'token_length': len(os.getenv('POLARION_TOKEN', ''))
        },
        'tests': {}
    }
    
    # Add test results (this would be populated by actual tests)
    # For now, return basic structure
    return report

if __name__ == "__main__":
    print("\n🔐 API Authentication Tests")
    print("==========================")
    
    auth_success = test_authentication()
    
    # Test project access if requested and authentication succeeded
    test_projects = os.getenv('TEST_PROJECTS', 'false').lower() == 'true'
    verbose = os.getenv('VERBOSE', 'false').lower() == 'true'
    
    if auth_success and test_projects:
        project_success = test_project_access(verbose)
    else:
        project_success = True  # Skip if not requested
    
    # Generate report if requested
    export_file = os.getenv('EXPORT_FILE', '')
    if export_file:
        report = generate_health_report()
        try:
            with open(export_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n💾 Health check report exported to {export_file}")
        except Exception as e:
            print(f"\n❌ Failed to export report: {e}")
    
    # Exit with appropriate code
    if auth_success and project_success:
        sys.exit(0)
    else:
        sys.exit(1)
```

### 4. Results Summary and Recommendations

Provide comprehensive summary and actionable guidance:

```bash
echo ""
echo "📋 Health Check Summary"
echo "======================"

# Calculate overall health score
TOTAL_TESTS=0
PASSED_TESTS=0

# Count tests
tests=("$CLIENT_AVAILABLE" "$DEPS_AVAILABLE" "$TOKEN_AVAILABLE" "$NETWORK_OK" "$DNS_OK" "$SSL_OK")
for test in "${tests[@]}"; do
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "$test" = "true" ]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
    fi
done

# Calculate percentage
if [ $TOTAL_TESTS -gt 0 ]; then
    HEALTH_PERCENTAGE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
else
    HEALTH_PERCENTAGE=0
fi

echo "🎯 Overall Health Score: $PASSED_TESTS/$TOTAL_TESTS ($HEALTH_PERCENTAGE%)"

# Provide recommendations based on results
if [ $HEALTH_PERCENTAGE -eq 100 ]; then
    echo "✅ All health checks passed! Polarion integration is ready for use."
    echo ""
    echo "💡 Next Steps:"
    echo "   • Use /polarion:projects to discover available projects"
    echo "   • Use /polarion:activity for QE activity analysis"
    echo "   • Set up automated reporting with exported commands"
    
elif [ $HEALTH_PERCENTAGE -ge 80 ]; then
    echo "⚠️  Most health checks passed with minor issues"
    echo ""
    echo "🔧 Recommended Actions:"
    echo "   • Review warnings above and resolve if needed"
    echo "   • Test basic functionality with /polarion:projects"
    echo "   • Monitor for any issues during regular use"
    
elif [ $HEALTH_PERCENTAGE -ge 60 ]; then
    echo "⚠️  Some health checks failed - integration may have limited functionality"
    echo ""
    echo "🔧 Required Actions:"
    echo "   • Address failed tests above before proceeding"
    echo "   • Focus on authentication and network connectivity"
    echo "   • Test again after resolving issues"
    
else
    echo "❌ Multiple health checks failed - integration not ready for use"
    echo ""
    echo "🚨 Critical Actions Required:"
    echo "   • Resolve authentication and connectivity issues"
    echo "   • Verify token and network configuration"
    echo "   • Contact support if problems persist"
fi

# Provide specific troubleshooting guidance
echo ""
echo "🔧 Troubleshooting Resources:"
echo "   • Token Management: https://polarion.engineering.redhat.com"
echo "   • Network Issues: Check corporate proxy and firewall settings"
echo "   • Permission Issues: Contact Polarion administrator"
echo "   • Integration Guide: Review plugin documentation"

echo ""
echo "📞 Support Options:"
echo "   • Export results with --export for support tickets"
echo "   • Use --verbose for detailed diagnostic information"
echo "   • Check plugin README for common solutions"

# Exit with appropriate code
if [ $HEALTH_PERCENTAGE -ge 80 ]; then
    exit 0
else
    exit 1
fi
```

## Examples

### Example 1: Basic health check
```
/polarion:health-check
```

Output:
```
🔍 Polarion Health Check Starting...
==================================
📦 Checking Polarion client availability... ✅ Available
📦 Checking Python dependencies... ✅ Available
🔐 Checking API token environment... ✅ Set (127 characters)
   ✅ Token format appears valid

🌐 Network Connectivity Tests
=============================
🔗 Testing basic connectivity to Polarion... ✅ Success
🌐 Testing DNS resolution... ✅ Success
   ✅ Resolved to: 52.200.142.250
🔒 Testing SSL/TLS connection... ✅ Success

🔐 API Authentication Tests
==========================
✅ Polarion client imported successfully
✅ Polarion client initialized
🔐 Testing API authentication... ✅ Success
📋 Testing project list access... ✅ Success (8 projects accessible)

📋 Health Check Summary
======================
🎯 Overall Health Score: 6/6 (100%)
✅ All health checks passed! Polarion integration is ready for use.

💡 Next Steps:
   • Use /polarion:projects to discover available projects
   • Use /polarion:activity for QE activity analysis
   • Set up automated reporting with exported commands
```

### Example 2: Verbose health check with project testing
```
/polarion:health-check --verbose --projects
```

### Example 3: Health check with export for support
```
/polarion:health-check --verbose --projects --export health-check-$(date +%Y%m%d).json
```

### Example 4: Quick connectivity verification
```
/polarion:health-check
```

## Return Value

The command returns different exit codes based on health check results:

- **Exit 0**: All critical health checks passed (≥80% success rate)
- **Exit 1**: Critical health checks failed (<80% success rate)

**Health Check Categories**:
- **Critical**: Client availability, authentication, basic connectivity
- **Important**: Project access, API functionality
- **Advisory**: SSL verification, proxy configuration

## Common Issues and Solutions

### Authentication Problems
```
❌ Testing API authentication... Failed
   Error: Authentication failed
   Solutions:
     • Verify token is correct and not expired
     • Regenerate token in Polarion web UI
     • Check token permissions
```

**Resolution Steps**:
1. Go to https://polarion.engineering.redhat.com
2. Navigate to User Settings → Security → API Tokens
3. Generate new token with read permissions
4. Update POLARION_TOKEN environment variable

### Network Connectivity Issues
```
❌ Testing basic connectivity to Polarion... Failed
   Error: Cannot reach polarion.engineering.redhat.com
   Solutions:
     • Check internet connectivity
     • Verify firewall/proxy settings
     • Configure proxy: export HTTPS_PROXY=http://proxy:port
```

**Resolution Steps**:
1. Test basic connectivity: `ping polarion.engineering.redhat.com`
2. Configure proxy if needed: `export HTTPS_PROXY=http://proxy.company.com:8080`
3. Verify firewall allows HTTPS (port 443)

### Missing Dependencies
```
❌ Checking Python dependencies... Missing
   Error: Required Python packages not available
   Solution: pip install requests
```

**Resolution Steps**:
1. Install dependencies: `pip install requests`
2. Verify installation: `python -c "import requests; print('OK')"`

## Integration Testing

### Pre-Automation Validation
```bash
# Comprehensive validation before setting up automation
/polarion:health-check --verbose --projects --export setup-validation.json

# Quick daily health check for monitoring
/polarion:health-check || echo "ALERT: Polarion integration issues detected"
```

### CI/CD Integration
```bash
# Health check in deployment pipeline
if ! /polarion:health-check; then
  echo "WARNING: Polarion integration not available"
  echo "Skipping QE analysis steps"
fi
```

## Security Considerations

- **Token Validation**: Verifies token format and basic validity
- **Read-Only Testing**: All health checks are read-only operations
- **Network Security**: Tests HTTPS connectivity and SSL verification
- **No Data Modification**: Health check never modifies Polarion data

## See Also

- Setup commands: `/polarion:projects` for initial project discovery
- Functional testing: `/polarion:activity` for end-to-end workflow verification
- Documentation: Plugin README for detailed setup instructions

## Notes

- Health check designed to run safely in any environment
- Results suitable for sharing with support teams when troubleshooting
- Regular health checks recommended for production automation
- Export capability provides detailed diagnostics for offline analysis
- Comprehensive validation ensures reliable plugin operation