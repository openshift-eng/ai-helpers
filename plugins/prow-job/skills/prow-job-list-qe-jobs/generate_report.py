#!/usr/bin/env python3
"""
HTML Report Generator

This script generates HTML reports from a template and job data.

Usage:
    python3 generate_report.py --template template.html --output report.html --data jobs.json
    python3 generate_report.py --template template.html --output report.html --data jobs.json --keywords "release-4.21 upgrade"

Data format (JSON):
    [
        {
            "name": "job-name-1",
            "state": "pending",
            "url": "http://example.com/job1"
        },
        {
            "name": "job-name-2",
            "state": "success",
            "url": "http://example.com/job2"
        }
    ]
"""

import json
import sys
import argparse
import html
from datetime import datetime
from collections import Counter


def load_template(template_file):
    """Load HTML template from file."""
    try:
        with open(template_file, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Template file '{template_file}' not found.")
        sys.exit(1)
    except OSError as e:
        print(f"Error loading template: {e}")
        sys.exit(1)


def load_job_data(data_file):
    """Load job data from JSON file."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)

    except FileNotFoundError:
        print(f"Error: Data file '{data_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON data: {e}")
        sys.exit(1)
    except OSError as e:
        print(f"Error loading data: {e}")
        sys.exit(1)
    else:
        if not isinstance(data, list):
            print("Error: Job data must be a JSON array/list.")
            sys.exit(1)

        return data


def generate_stats_cards(jobs):
    """Generate HTML for statistics cards."""
    state_counts = Counter(job.get('state', 'unknown') for job in jobs)

    stats_html = ''
    for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
        stats_html += f'''            <div class="stat-card">
                <strong>{html.escape(state)}</strong>
                <span>{count}</span>
            </div>
'''

    return stats_html


def generate_state_options(jobs):
    """Generate HTML options for state filter dropdown."""
    states = set(
        job.get('state', 'unknown')
        for job in jobs
        if isinstance(job, dict)
    )

    options_html = ''
    for state in sorted(states):
        options_html += f'                    <option value="{html.escape(state, quote=True)}">{html.escape(state)}</option>\n'

    return options_html


def generate_job_rows(jobs):
    """Generate HTML table rows for jobs."""
    rows_html = ''

    for job in jobs:
        # Provide safe defaults for missing keys
        name = job.get('name', 'Unknown Job')
        state = job.get('state', 'unknown')
        url = job.get('url', '#')
        
        state_lower = state.lower()
        state_escaped = html.escape(state_lower, quote=True)
        rows_html += f'''                    <tr data-state="{state_escaped}">
                        <td class="job-name">{html.escape(name)}</td>
                        <td><span class="state state-{state_escaped}">{html.escape(state)}</span></td>
                        <td>
                           <a href="{html.escape(url, quote=True)}" class="job-url" target="_blank">View Job</a>
                        </td>
                    </tr>
 '''
 
    return rows_html


def generate_report(template_file, data_file, output_file, keywords=''):
    """Generate HTML report from template and job data."""
    # Load template and data
    template = load_template(template_file)
    jobs = load_job_data(data_file)
    
    # Ensure we only process well-formed job dicts
    jobs = [job for job in jobs if isinstance(job, dict)]

    # Filter by keywords if provided
    if keywords:
        keyword_list = keywords.lower().split()
        jobs = [
            job 
            for job in jobs
            if all(
                kw in job.get('name', '').lower() 
                for kw in keyword_list)
            ]

    # Generate components
    stats_cards = generate_stats_cards(jobs)
    state_options = generate_state_options(jobs)
    job_rows = generate_job_rows(jobs)

    # Replace placeholders
    output_html = template.replace('{{KEYWORDS}}', html.escape(keywords if keywords else 'All Jobs'))
    output_html = output_html.replace('{{TOTAL_JOBS}}', str(len(jobs)))
    output_html = output_html.replace('{{GENERATED_TIME}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    output_html = output_html.replace('{{STATS_CARDS}}', stats_cards)
    output_html = output_html.replace('{{STATE_OPTIONS}}', state_options)
    output_html = output_html.replace('{{JOB_ROWS}}', job_rows)

    # Write output
    try:
        with open(output_file, 'w') as f:
            f.write(output_html)
        print(f"✓ Report generated successfully: {output_file}")
        print(f"✓ Total jobs: {len(jobs)}")

        # Print statistics (defensive against missing state keys)
        state_counts = Counter(
            job.get('state', 'unknown')
            for job in jobs
            if isinstance(job, dict)
        )
        
        print("✓ Statistics:")
        for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {state}: {count}")
    except OSError as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Generate HTML report from template and job data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '-t', '--template',
        required=True,
        help='Path to HTML template file'
    )

    parser.add_argument(
        '-d', '--data',
        required=True,
        help='Path to JSON data file containing job list'
    )

    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Path to output HTML report file'
    )

    parser.add_argument(
        '-k', '--keywords',
        default='',
        help='Keywords/description for the report (optional)'
    )

    args = parser.parse_args()

    generate_report(args.template, args.data, args.output, args.keywords)


if __name__ == '__main__':
    main()
