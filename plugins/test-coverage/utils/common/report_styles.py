#!/usr/bin/env python3
"""
Shared CSS styles for HTML reports across all test coverage skills
"""


def get_common_css() -> str:
    """Shared CSS styles for HTML reports"""
    return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f7fa;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header .meta {
            opacity: 0.9;
            font-size: 0.95em;
        }

        .section {
            padding: 30px;
        }

        .section h2 {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }

        .score-section {
            padding: 30px;
            background: #f8f9fa;
        }

        .overall-score {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 8px;
            margin-bottom: 30px;
        }

        .score-circle {
            width: 200px;
            height: 200px;
            border-radius: 50%;
            background: conic-gradient(#667eea calc(var(--score) * 1%), #e5e7eb 0);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 20px;
            position: relative;
        }

        .score-circle::before {
            content: '';
            width: 160px;
            height: 160px;
            border-radius: 50%;
            background: white;
            position: absolute;
        }

        .score-value {
            font-size: 3em;
            font-weight: bold;
            color: #667eea;
            z-index: 1;
        }

        .score-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .score-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .score-card h3 {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
        }

        .score-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }

        .matrix-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .matrix-table th {
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }

        .matrix-table td {
            padding: 15px;
            border-bottom: 1px solid #e5e7eb;
        }

        .matrix-table tr:last-child td {
            border-bottom: none;
        }

        .matrix-table tr:hover {
            background: #f9fafb;
        }

        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .status-tested {
            background: #d1fae5;
            color: #065f46;
        }

        .status-not-tested {
            background: #fee2e2;
            color: #991b1b;
        }

        .priority-high {
            background: #fee2e2;
            color: #991b1b;
        }

        .priority-medium {
            background: #fef3c7;
            color: #92400e;
        }

        .priority-low {
            background: #dbeafe;
            color: #1e40af;
        }

        .gap-card {
            background: white;
            border-left: 4px solid #ef4444;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .gap-card.medium {
            border-left-color: #f59e0b;
        }

        .gap-card.low {
            border-left-color: #3b82f6;
        }

        .gap-card h4 {
            margin-bottom: 10px;
            color: #111;
        }

        .gap-card .impact {
            color: #666;
            margin: 8px 0;
            font-size: 0.95em;
        }

        .gap-card .recommendation {
            background: #f9fafb;
            padding: 12px;
            border-radius: 4px;
            margin-top: 10px;
            font-style: italic;
        }

        .progress-bar {
            height: 30px;
            background: #e5e7eb;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 0.9em;
            transition: width 0.3s ease;
        }

        .test-cases {
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }

        .test-case {
            background: white;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
            border-left: 3px solid #667eea;
        }

        .test-case .line {
            color: #666;
            font-size: 0.85em;
        }

        .test-case .test-targets {
            color: #666;
            font-size: 0.85em;
            margin-top: 5px;
        }

        .tags {
            margin-top: 5px;
        }

        .tag {
            display: inline-block;
            padding: 2px 8px;
            background: #e5e7eb;
            border-radius: 3px;
            font-size: 0.8em;
            margin-right: 5px;
            color: #555;
        }

        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }

        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }

        .stat-card h3 {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }

        .stat-card .subvalue {
            font-size: 1em;
            color: #999;
            margin-top: 5px;
        }
    """
