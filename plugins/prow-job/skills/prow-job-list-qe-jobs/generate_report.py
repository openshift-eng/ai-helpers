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
            "job": "job-name-1",
            "state": "pending",
            "url": "http://example.com/job1"
        },
        {
            "job": "job-name-2",
            "state": "success",
            "url": "http://example.com/job2"
        }
    ]

Alternative key names supported:
    - "job" or "name"
    - "state" or "status"
    - "url" or "link"
"""

import json
import sys
import argparse
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
    except Exception as e:
        print(f"Error loading template: {e}")
        sys.exit(1)


def load_job_data(data_file):
    """Load job data from JSON file."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("Error: Job data must be a JSON array/list.")
            sys.exit(1)

        return data
    except FileNotFoundError:
        print(f"Error: Data file '{data_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON data: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)


def generate_stats_cards(jobs):
    """Generate HTML for statistics cards."""
    state_counts = Counter(job['state'] for job in jobs)

    stats_html = ''
    for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
        stats_html += f'''            <div class="stat-card">
                <strong>{state}</strong>
                <span>{count}</span>
            </div>
'''

    return stats_html


def generate_state_options(jobs):
    """Generate HTML options for state filter dropdown."""
    states = set(job['state'] for job in jobs)

    options_html = ''
    for state in sorted(states):
        options_html += f'                    <option value="{state}">{state}</option>\n'

    return options_html


def generate_job_rows(jobs):
    """Generate HTML table rows for jobs."""
    rows_html = ''

    for job in jobs:
        state = job['state'].lower()
        rows_html += f'''                    <tr data-state="{state}">
                        <td class="job-name">{job['name']}</td>
                        <td><span class="state state-{state}">{job['state']}</span></td>
                        <td>
                            <a href="{job['url']}" class="job-url" target="_blank">View Job</a>
                        </td>
                    </tr>
'''

    return rows_html


def generate_report(template_file, data_file, output_file, keywords=''):
    """Generate HTML report from template and job data."""
    # Load template and data
    template = load_template(template_file)
    jobs = load_job_data(data_file)

    # Filter by keywords if provided
    if keywords:
        keyword_list = keywords.lower().split()
        jobs = [job for job in jobs
                if all(kw in job['name'].lower() for kw in keyword_list)]

    # Generate components
    stats_cards = generate_stats_cards(jobs)
    state_options = generate_state_options(jobs)
    job_rows = generate_job_rows(jobs)

    # Replace placeholders
    html = template.replace('{{KEYWORDS}}', keywords if keywords else 'All Jobs')
    html = html.replace('{{TOTAL_JOBS}}', str(len(jobs)))
    html = html.replace('{{GENERATED_TIME}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    html = html.replace('{{STATS_CARDS}}', stats_cards)
    html = html.replace('{{STATE_OPTIONS}}', state_options)
    html = html.replace('{{JOB_ROWS}}', job_rows)

    # Write output
    try:
        with open(output_file, 'w') as f:
            f.write(html)
        print(f"✓ Report generated successfully: {output_file}")
        print(f"✓ Total jobs: {len(jobs)}")

        # Print statistics
        state_counts = Counter(job['state'] for job in jobs)
        print(f"✓ Statistics:")
        for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {state}: {count}")
    except Exception as e:
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
