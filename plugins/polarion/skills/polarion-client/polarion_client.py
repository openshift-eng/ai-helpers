#!/usr/bin/env python3
"""
Polarion Client for Test Data Retrieval and Case Tracking

This client provides comprehensive access to Polarion test management data
including test runs, test cases, work items, and test execution activity tracking.
"""

import os
import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import sys
import argparse
import logging


class PolarionClient:
    """
    A comprehensive client for interacting with the Polarion test management system.
    
    Features:
    - Authentication via Bearer token
    - Test run and test case retrieval
    - Work item management
    - Project discovery and filtering
    - test execution analysis
    - Comprehensive error handling and retry logic
    """
    
    def __init__(self, base_url: str = "https://polarion.engineering.redhat.com", token: str = None):
        """
        Initialize the Polarion client.
        
        Args:
            base_url: Base URL for Polarion instance (default: Red Hat Polarion)
            token: API token, will fallback to POLARION_TOKEN environment variable
        """
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
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def _make_request(self, endpoint: str, params: Dict = None, retry_count: int = 3) -> Optional[Dict]:
        """
        Make authenticated request to Polarion API with retry logic.
        
        Args:
            endpoint: API endpoint (will be prefixed with /polarion/rest/v1/)
            params: Query parameters
            retry_count: Number of retries on failure
            
        Returns:
            JSON response data or None on failure
        """
        url = f"{self.base_url}/polarion/rest/v1/{endpoint.lstrip('/')}"
        
        for attempt in range(retry_count):
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    self.logger.error(f"Authentication failed for Polarion API")
                    return None
                elif response.status_code == 403:
                    self.logger.error(f"Access forbidden for endpoint: {endpoint}")
                    return None
                elif response.status_code == 429:  # Rate limited
                    self.logger.warning(f"Rate limited, retrying in {2 ** attempt} seconds...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    self.logger.error(f"Polarion API request failed: {response.status_code} - {response.text}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt == retry_count - 1:
                    return None
                time.sleep(1)
        
        return None
    
    def test_connection(self) -> bool:
        """
        Test the connection to Polarion API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            data = self._make_request('projects')
            return data is not None
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def get_projects(self, limit: int = None) -> List[Dict]:
        """
        Get list of available projects.
        
        Args:
            limit: Maximum number of projects to return
            
        Returns:
            List of project dictionaries
        """
        params = {}
        if limit:
            params['pageSize'] = limit
            
        data = self._make_request('projects', params)
        if data and 'data' in data:
            projects = data['data']
            self.logger.info(f"Retrieved {len(projects)} projects")
            return projects
        return []
    
    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """
        Get specific project by ID.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project dictionary or None if not found
        """
        data = self._make_request(f'projects/{project_id}')
        if data and 'data' in data:
            return data['data']
        return None
    
    def get_test_runs(self, project_id: str, days_back: int = 7, limit: int = None) -> List[Dict]:
        """
        Get test runs for a project within specified days.
        
        Args:
            project_id: Project identifier
            days_back: Number of days to look back
            limit: Maximum number of test runs to return
            
        Returns:
            List of test run dictionaries
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            'query': f'project.id:{project_id} AND created:[{start_date.strftime("%Y-%m-%d")} TO {end_date.strftime("%Y-%m-%d")}]'
        }
        if limit:
            params['pageSize'] = limit
        
        data = self._make_request(f'projects/{project_id}/testruns', params)
        if data and 'data' in data:
            test_runs = data['data']
            self.logger.info(f"Retrieved {len(test_runs)} test runs for project {project_id}")
            return test_runs
        return []
    
    def get_test_records(self, project_id: str, test_run_id: str) -> List[Dict]:
        """
        Get test records for a specific test run.
        
        Args:
            project_id: Project identifier
            test_run_id: Test run identifier
            
        Returns:
            List of test record dictionaries
        """
        data = self._make_request(f'projects/{project_id}/testruns/{test_run_id}/records')
        if data and 'data' in data:
            records = data['data']
            self.logger.info(f"Retrieved {len(records)} test records for test run {test_run_id}")
            return records
        return []
    
    def get_work_items(self, project_id: str, work_item_type: str = None, days_back: int = 7) -> List[Dict]:
        """
        Get work items (test cases, requirements, etc.) updated recently.
        
        Args:
            project_id: Project identifier
            work_item_type: Filter by work item type (e.g., 'testcase', 'requirement')
            days_back: Number of days to look back
            
        Returns:
            List of work item dictionaries
        """
        data = self._make_request(f'projects/{project_id}/workitems')
        if data and 'data' in data:
            items = data['data']
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            filtered_items = []
            for item in items:
                # Filter by type if specified
                if work_item_type and item.get('type') != work_item_type:
                    continue
                    
                # Filter by date
                updated_str = item.get('updated')
                if updated_str:
                    try:
                        updated_date = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                        # Convert to naive datetime for comparison
                        if updated_date.tzinfo is not None:
                            updated_date = updated_date.replace(tzinfo=None)
                        if start_date <= updated_date <= end_date:
                            filtered_items.append(item)
                    except (ValueError, TypeError) as e:
                        # Skip items with malformed timestamps
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(f"Skipping item with invalid timestamp: {e}")
                        continue
                        
            self.logger.info(f"Retrieved {len(filtered_items)} work items for project {project_id}")
            return filtered_items
        return []
    
    def search_projects(self, keywords: List[str] = None, case_sensitive: bool = False) -> List[Dict]:
        """
        Search for projects matching keywords.
        
        Args:
            keywords: List of keywords to search for in project name/ID
            case_sensitive: Whether search should be case sensitive
            
        Returns:
            List of matching project dictionaries
        """
        if not keywords:
            keywords = ['openshift', 'splat', 'ocp', 'platform', 'container']
        
        projects = self.get_projects(limit=1000)
        matching_projects = []
        
        for project in projects:
            project_name = project.get('name', '')
            project_id = project.get('id', '')
            
            if not case_sensitive:
                project_name = project_name.lower()
                project_id = project_id.lower()
                search_keywords = [k.lower() for k in keywords]
            else:
                search_keywords = keywords
            
            if any(keyword in project_name or keyword in project_id for keyword in search_keywords):
                matching_projects.append(project)
        
        self.logger.info(f"Found {len(matching_projects)} projects matching keywords: {keywords}")
        return matching_projects
    
    def get_qe_activity_summary(self, days_back: int = 7, project_limit: int = 5) -> Dict:
        """
        Get comprehensive QE activity summary across projects.
        
        Args:
            days_back: Number of days to analyze
            project_limit: Maximum number of projects to analyze
            
        Returns:
            Comprehensive activity summary dictionary
        """
        summary = {
            'period_start': (datetime.now() - timedelta(days=days_back)).isoformat(),
            'period_end': datetime.now().isoformat(),
            'projects': [],
            'total_test_runs': 0,
            'total_test_cases': 0,
            'total_test_records': 0,
            'qe_members': [],
            'activity_by_member': {},
            'project_statistics': {}
        }
        
        # Find relevant projects
        projects = self.search_projects()
        
        for project in projects[:project_limit]:
            project_id = project['id']
            project_summary = {
                'id': project_id,
                'name': project.get('name', ''),
                'description': project.get('description', ''),
                'test_runs': [],
                'test_cases': [],
                'activity': []
            }
            
            try:
                # Get test runs
                test_runs = self.get_test_runs(project_id, days_back)
                project_summary['test_runs'] = test_runs
                summary['total_test_runs'] += len(test_runs)
                
                # Get test cases
                test_cases = self.get_work_items(project_id, 'testcase', days_back)
                project_summary['test_cases'] = test_cases
                summary['total_test_cases'] += len(test_cases)
                
                # Process activity by members
                for test_run in test_runs:
                    author = test_run.get('author', {})
                    if author:
                        member_id = author.get('id', 'unknown')
                        if member_id not in summary['activity_by_member']:
                            summary['activity_by_member'][member_id] = {
                                'name': author.get('name', member_id),
                                'test_runs_created': 0,
                                'test_cases_updated': 0,
                                'projects': set()
                            }
                        summary['activity_by_member'][member_id]['test_runs_created'] += 1
                        summary['activity_by_member'][member_id]['projects'].add(project_id)
                
                for test_case in test_cases:
                    author = test_case.get('author', {})
                    assignee = test_case.get('assignee', {})
                    for member in [author, assignee]:
                        if member:
                            member_id = member.get('id', 'unknown')
                            if member_id not in summary['activity_by_member']:
                                summary['activity_by_member'][member_id] = {
                                    'name': member.get('name', member_id),
                                    'test_runs_created': 0,
                                    'test_cases_updated': 0,
                                    'projects': set()
                                }
                            summary['activity_by_member'][member_id]['test_cases_updated'] += 1
                            summary['activity_by_member'][member_id]['projects'].add(project_id)
                
                # Project statistics
                summary['project_statistics'][project_id] = {
                    'name': project.get('name', ''),
                    'test_runs': len(test_runs),
                    'test_cases': len(test_cases),
                    'active_members': len(set(
                        [tr.get('author', {}).get('id') for tr in test_runs if tr.get('author')] +
                        [tc.get('author', {}).get('id') for tc in test_cases if tc.get('author')]
                    ))
                }
                
                summary['projects'].append(project_summary)
                
            except Exception as e:
                self.logger.error(f"Error processing project {project_id}: {e}")
                continue
        
        # Convert sets to lists for JSON serialization
        for member_data in summary['activity_by_member'].values():
            member_data['projects'] = list(member_data['projects'])
        
        return summary
    
    def export_data(self, data: Union[Dict, List], filename: str, format: str = 'json') -> bool:
        """
        Export data to file in specified format.
        
        Args:
            data: Data to export
            filename: Output filename
            format: Export format ('json', 'csv')
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            if format.lower() == 'json':
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            elif format.lower() == 'csv':
                import csv
                if isinstance(data, list) and data:
                    with open(filename, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
                else:
                    self.logger.error("CSV export requires list of dictionaries")
                    return False
            else:
                self.logger.error(f"Unsupported export format: {format}")
                return False
                
            self.logger.info(f"Data exported to {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return False


def main():
    """Command-line interface for Polarion client."""
    parser = argparse.ArgumentParser(description='Polarion Test Management Client')
    parser.add_argument('--token', help='Polarion API token (or set POLARION_TOKEN env var)')
    parser.add_argument('--base-url', default='https://polarion.engineering.redhat.com',
                       help='Polarion base URL')
    parser.add_argument('--days-back', type=int, default=14,
                       help='Days to look back for activity (default: 14)')
    parser.add_argument('--project-limit', type=int, default=5,
                       help='Maximum projects to analyze (default: 5)')
    parser.add_argument('--output', '-o', help='Output file for results')
    parser.add_argument('--format', choices=['json', 'csv'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test connection command
    subparsers.add_parser('test', help='Test connection to Polarion')
    
    # List projects command
    projects_parser = subparsers.add_parser('projects', help='List available projects')
    projects_parser.add_argument('--keywords', nargs='+', 
                                help='Keywords to filter projects')
    projects_parser.add_argument('--limit', type=int, default=20, help='Limit number of results (default: 20, range: 1-100)')
    
    # Test activity command
    activity_parser = subparsers.add_parser('activity', help='Get test activity summary')
    activity_parser.add_argument('--keywords', nargs='+',
                                help='Keywords to filter projects')
    activity_parser.add_argument('--days-back', type=int, default=7,
                                help='Days to look back for activity (default: 7, range: 1-90)')
    activity_parser.add_argument('--project-limit', type=int, default=5,
                                help='Maximum projects to analyze (default: 5, range: 1-20)')
    
    # Test runs command
    testruns_parser = subparsers.add_parser('testruns', help='Get test runs for project')
    testruns_parser.add_argument('project_id', help='Project ID')
    testruns_parser.add_argument('--days-back', type=int, default=14,
                                help='Days to look back for test runs (default: 14, range: 1-90)')
    testruns_parser.add_argument('--limit', type=int, default=50, help='Limit number of results (default: 50, range: 1-500)')
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
    
    try:
        client = PolarionClient(base_url=args.base_url, token=args.token)
        
        if args.command == 'test':
            if client.test_connection():
                print("✓ Connection to Polarion successful")
            else:
                print("✗ Connection to Polarion failed")
                sys.exit(1)
                
        elif args.command == 'projects':
            # Validate limit argument
            if args.limit is not None and (args.limit < 1 or args.limit > 100):
                print("Error: limit must be between 1 and 100")
                sys.exit(1)
            
            if args.keywords:
                projects = client.search_projects(args.keywords)
                # Apply limit to search results if specified
                if args.limit:
                    projects = projects[:args.limit]
            else:
                projects = client.get_projects(limit=args.limit)
            
            print(f"Found {len(projects)} projects:")
            for project in projects:
                print(f"  {project.get('id', 'N/A'):20} - {project.get('name', 'N/A')}")
            
            if args.output:
                client.export_data(projects, args.output, args.format)
                
        elif args.command == 'activity':
            # Validate arguments
            if args.days_back < 1 or args.days_back > 90:
                print("Error: days-back must be between 1 and 90")
                sys.exit(1)
            if args.project_limit < 1 or args.project_limit > 20:
                print("Error: project-limit must be between 1 and 20")
                sys.exit(1)
                
            keywords = args.keywords if args.keywords else None
            if keywords:
                # Override search keywords
                original_search = client.search_projects
                client.search_projects = lambda case_sensitive=False, **kwargs: original_search(keywords, case_sensitive, **kwargs)
            summary = client.get_qe_activity_summary(args.days_back, args.project_limit)
            
            print(f"\nTest Activity Summary ({summary['period_start'][:10]} to {summary['period_end'][:10]}):")
            print(f"  Total Test Runs: {summary['total_test_runs']}")
            print(f"  Total Test Cases Updated: {summary['total_test_cases']}")
            print(f"  Active Projects: {len(summary['projects'])}")
            print(f"  Active Test Contributors: {len(summary['activity_by_member'])}")
            
            if summary['activity_by_member']:
                print("\nActive Test Contributors:")
                for member_id, activity in summary['activity_by_member'].items():
                    projects_count = len(activity['projects'])
                    print(f"  - {activity['name']}: {activity['test_runs_created']} test runs, "
                          f"{activity['test_cases_updated']} test cases, {projects_count} projects")
            
            if args.output:
                client.export_data(summary, args.output, args.format)
                
        elif args.command == 'testruns':
            # Validate arguments
            if args.days_back < 1 or args.days_back > 90:
                print("Error: days-back must be between 1 and 90")
                sys.exit(1)
            if args.limit is not None and (args.limit < 1 or args.limit > 500):
                print("Error: limit must be between 1 and 500")
                sys.exit(1)
                
            test_runs = client.get_test_runs(args.project_id, args.days_back, args.limit)
            
            print(f"Found {len(test_runs)} test runs for project {args.project_id}:")
            for run in test_runs:
                status = run.get('status', 'N/A')
                title = run.get('title', 'N/A')
                created = run.get('created', 'N/A')[:10] if run.get('created') else 'N/A'
                print(f"  {run.get('id', 'N/A'):15} - {title[:50]:50} - {status:15} - {created}")
            
            if args.output:
                client.export_data(test_runs, args.output, args.format)
        
        else:
            # Default: show activity summary
            print("Polarion client initialized successfully")
            print("\nFetching OpenShift-related projects...")
            
            projects = client.search_projects()
            if projects:
                print(f"Found {len(projects)} OpenShift-related projects:")
                for project in projects[:10]:
                    print(f"  - {project.get('name', 'Unknown')} ({project.get('id', 'Unknown')})")
            
            print("\nFetching QE activity summary...")
            summary = client.get_qe_activity_summary(args.days_back, args.project_limit)
            
            print(f"\nTest Activity Summary ({summary['period_start'][:10]} to {summary['period_end'][:10]}):")
            print(f"  Total Test Runs: {summary['total_test_runs']}")
            print(f"  Total Test Cases Updated: {summary['total_test_cases']}")
            print(f"  Active Projects: {len(summary['projects'])}")
            print(f"  Active Test Contributors: {len(summary['activity_by_member'])}")
            
            if summary['activity_by_member']:
                print("\nActive Test Contributors:")
                for member_id, activity in summary['activity_by_member'].items():
                    projects_count = len(activity['projects'])
                    print(f"  - {activity['name']}: {activity['test_runs_created']} test runs, "
                          f"{activity['test_cases_updated']} test cases, {projects_count} projects")
            
            if args.output:
                client.export_data(summary, args.output, args.format)
                print(f"\nDetailed summary saved to {args.output}")
                
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()