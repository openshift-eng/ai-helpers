#!/usr/bin/env python3
"""
Generate an interactive Activity Type report as a self-contained HTML file.

Includes:
  - D3 sankey diagram (Project -> Activity Type)
  - Summary statistics
  - Interactive detail table with search, pagination, sort, CSV export, and Jira links

Usage:
    python3 generate_sankey.py \\
        --input classified_issues.json \\
        --output activity-type-report.html \\
        --title "Activity Type Report" \\
        --projects "DPTP,TRT,ART" \\
        --months 6

Input JSON format: array of objects with at least:
    issue_key, project_key, summary, activity_type
Optional fields: issue_type, status, components, description, created
"""

import argparse
import json
import sys
from html import escape as html_escape
from collections import Counter
from datetime import datetime
from pathlib import Path

JIRA_BASE_URL = "https://redhat.atlassian.net"

ACTIVITY_COLORS = {
    "Associate Wellness & Development": "#7BC8A4",
    "Incidents & Support": "#F5C542",
    "Security & Compliance": "#E89AC0",
    "Quality / Stability / Reliability": "#F0A070",
    "Future Sustainability": "#9B8FDB",
    "Product / Portfolio Work": "#6CC5D9",
    "Uncategorized": "#9E9E9E",
}


def _get_is_bot(issue):
    """Extract bot flag from an issue."""
    val = issue.get("IS_BOT", issue.get("is_bot", False))
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


def generate_d3_sankey(data, container_id="d3-sankey"):
    """Generate a pure-JS D3 sankey diagram."""
    if not data:
        return f'<div id="{container_id}" style="padding:2rem;text-align:center;color:var(--text-muted);">No issues in this view</div>'

    flow_counts = Counter()
    for issue in data:
        flow_counts[(issue["project_key"], issue["activity_type"])] += 1

    projects = sorted({k[0] for k in flow_counts})
    activity_types = sorted({k[1] for k in flow_counts})
    all_labels = projects + activity_types

    nodes_json = json.dumps([{"name": n} for n in all_labels])

    project_idx = {p: i for i, p in enumerate(projects)}
    at_idx = {a: i + len(projects) for i, a in enumerate(activity_types)}

    links = []
    for (proj, at), count in flow_counts.items():
        color = ACTIVITY_COLORS.get(at, "#9E9E9E")
        links.append({
            "source": project_idx[proj],
            "target": at_idx[at],
            "value": count,
            "color": color,
        })
    links_json = json.dumps(links)

    colors_json = json.dumps(
        [ACTIVITY_COLORS.get(n, "#555555") for n in all_labels]
    )

    return f"""
    <div id="{container_id}" style="width:100%;min-height:500px;"></div>
    <script>
    (function() {{
      var el = document.getElementById('{container_id}');
      var parent = el.parentElement;
      if ((parent && parent.style.display === 'none') || el.style.display === 'none') {{
        el.setAttribute('data-pending', 'true');
        return;
      }}
      const width = el.clientWidth || 800;
      const height = Math.max(500, {len(activity_types)} * 60 + 100);
      const svg = d3.select('#{container_id}').append('svg')
        .attr('width', width).attr('height', height);

      const sankey = d3.sankey()
        .nodeId(d => d.index)
        .nodeWidth(30).nodePadding(20)
        .extent([[20, 20], [width - 20, height - 20]]);

      const nodes = {nodes_json};
      const links = {links_json};
      const nodeColors = {colors_json};

      const graph = sankey({{
        nodes: nodes.map((d, i) => Object.assign({{}}, d, {{index: i}})),
        links: links.map(d => Object.assign({{}}, d))
      }});

      svg.append('g').selectAll('rect')
        .data(graph.nodes).enter().append('rect')
        .attr('x', d => d.x0).attr('y', d => d.y0)
        .attr('height', d => d.y1 - d.y0).attr('width', d => d.x1 - d.x0)
        .attr('fill', (d, i) => nodeColors[i])
        .attr('stroke', '#fff').attr('stroke-width', 0.5);

      svg.append('g').selectAll('path')
        .data(graph.links).enter().append('path')
        .attr('d', d3.sankeyLinkHorizontal())
        .attr('stroke', d => d.color)
        .attr('stroke-opacity', 0.4)
        .attr('stroke-width', d => Math.max(1, d.width))
        .attr('fill', 'none');

      svg.append('g').selectAll('text')
        .data(graph.nodes).enter().append('text')
        .attr('x', d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
        .attr('y', d => (d.y1 + d.y0) / 2)
        .attr('dy', '0.35em')
        .attr('text-anchor', d => d.x0 < width / 2 ? 'start' : 'end')
        .text(d => d.name)
        .style('font-size', '13px').style('font-family', 'Inter, system-ui, sans-serif');
    }})();
    </script>"""



def generate_summary_stats(data, estimates=None, estimates_key="overall"):
    """Generate summary statistics HTML.

    If estimates is provided (from sample_and_estimate.py), shows Bayesian
    credible intervals instead of raw counts. estimates_key selects which
    sub-estimate to use ("overall", "human", or "bot").
    """
    total = len(data)
    by_type = Counter(issue["activity_type"] for issue in data)
    by_project = Counter(issue["project_key"] for issue in data)

    rows = ""
    if estimates:
        # Sampling mode: show posterior estimates with credible intervals
        if estimates_key in estimates and estimates[estimates_key]:
            est_section = estimates[estimates_key]
        else:
            est_section = estimates.get("overall", estimates)
        ci_pct = int(est_section.get("confidence", estimates.get("confidence", 0.95)) * 100)
        for est in est_section.get("estimates", []):
            cat = est["category"]
            color = ACTIVITY_COLORS.get(cat, "#9E9E9E")
            mean_pct = est["posterior_mean"] * 100
            lo_pct = est["ci_low"] * 100
            hi_pct = est["ci_high"] * 100
            observed = est["observed_count"]
            rows += f"""<tr>
              <td><span class="color-dot" style="background:{color}"></span>{cat}</td>
              <td style="text-align:right">{observed}</td>
              <td style="text-align:right">{mean_pct:.1f}%</td>
              <td style="text-align:right;color:var(--text-muted);font-size:0.85rem;">[{lo_pct:.1f}% &ndash; {hi_pct:.1f}%]</td>
            </tr>"""
        header = (f"<th>Activity Type</th>"
                  f"<th style='text-align:right'>Observed</th>"
                  f"<th style='text-align:right'>Est. %</th>"
                  f"<th style='text-align:right'>{ci_pct}% CI</th>")
    else:
        for at in sorted(by_type, key=by_type.get, reverse=True):
            count = by_type[at]
            pct = count / total * 100 if total > 0 else 0
            color = ACTIVITY_COLORS.get(at, "#9E9E9E")
            rows += f"""<tr>
              <td><span class="color-dot" style="background:{color}"></span>{at}</td>
              <td style="text-align:right">{count}</td>
              <td style="text-align:right">{pct:.1f}%</td>
            </tr>"""
        header = "<th>Activity Type</th><th style='text-align:right'>Count</th><th style='text-align:right'>%</th>"

    # Build stat cards — use per-population stats when viewing human or bot
    sample_info = ""
    if estimates:
        if estimates_key in ("human", "bot") and est_section:
            sample_size = est_section.get("sample_size",
                                          estimates.get("sample_size", total))
            pop_size = est_section.get("population",
                                       estimates.get("total_population", total))
            sample_frac = sample_size / pop_size if pop_size else 0
        else:
            sample_size = estimates.get("sample_size", total)
            pop_size = estimates.get("total_population", total)
            sample_frac = estimates.get("sample_fraction", 1.0)
        pop_label = {"human": "Human Population", "bot": "Bot Population"
                     }.get(estimates_key, "Total Population")
        sample_info = f"""
      <div class="stat-card">
        <div class="stat-value">{pop_size}</div>
        <div class="stat-label">{pop_label}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{sample_size}</div>
        <div class="stat-label">Classified Sample ({sample_frac*100:.1f}%)</div>
      </div>"""
    else:
        sample_info = f"""
      <div class="stat-card">
        <div class="stat-value">{total}</div>
        <div class="stat-label">Total Issues</div>
      </div>"""

    return f"""
    <div class="stats-grid">
      {sample_info}
      <div class="stat-card">
        <div class="stat-value">{len(by_project)}</div>
        <div class="stat-label">Projects</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(by_type)}</div>
        <div class="stat-label">Activity Types</div>
      </div>
    </div>
    <table class="summary-table">
      <thead><tr>{header}</tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def generate_ci_chart(estimates, container_id="ci-chart", estimates_key="overall"):
    """Generate a D3 horizontal bar chart with credible interval whiskers."""
    if not estimates:
        return ""

    if estimates_key in estimates:
        sub = estimates[estimates_key]
    else:
        sub = estimates.get("overall", estimates)
    if not sub or "estimates" not in sub:
        return ""

    est_data = json.dumps(sub["estimates"])
    colors_json = json.dumps(ACTIVITY_COLORS)
    ci_pct = int(sub.get("confidence", estimates.get("confidence", 0.95)) * 100)
    sample_size = sub.get("sample_size", estimates.get("sample_size", 0))
    total_pop = sub.get("population", estimates.get("total_population", 0))
    sample_frac = (sample_size / total_pop * 100) if total_pop else 0

    return f"""
    <div class="section">
      <h2>Estimated Distribution ({ci_pct}% Credible Intervals)</h2>
      <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem;">
        Based on a Bayesian Dirichlet-Multinomial model.
        Classified {sample_size} of {total_pop} issues ({sample_frac:.1f}%).
        Bars show posterior mean; whiskers show {ci_pct}% credible intervals.
      </p>
      <div id="{container_id}" style="width:100%;min-height:300px;"></div>
    </div>
    <script>
    (function() {{
      var el = document.getElementById('{container_id}');
      if (!el || el.clientWidth === 0) {{
        el.setAttribute('data-pending', 'true');
        return;
      }}
      var data = {est_data};
      var colors = {colors_json};
      var margin = {{top: 20, right: 60, bottom: 40, left: 280}};
      var containerWidth = el.clientWidth;
      var width = containerWidth - margin.left - margin.right;
      var height = data.length * 45;
      var svg = d3.select('#{container_id}').append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g')
        .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

      var x = d3.scaleLinear().domain([0, d3.max(data, function(d) {{ return d.ci_high; }}) * 1.1]).range([0, width]);
      var y = d3.scaleBand().domain(data.map(function(d) {{ return d.category; }})).range([0, height]).padding(0.3);

      // Grid lines
      svg.append('g').attr('transform', 'translate(0,' + height + ')')
        .call(d3.axisBottom(x).ticks(6).tickFormat(function(d) {{ return (d * 100).toFixed(0) + '%'; }}))
        .selectAll('text').style('fill', '#8b8d98').style('font-size', '11px');
      svg.selectAll('.domain').style('stroke', '#2a2d3a');
      svg.selectAll('.tick line').style('stroke', '#2a2d3a');

      // CI whiskers (background)
      svg.selectAll('.ci-whisker')
        .data(data).enter().append('line')
        .attr('x1', function(d) {{ return x(d.ci_low); }})
        .attr('x2', function(d) {{ return x(d.ci_high); }})
        .attr('y1', function(d) {{ return y(d.category) + y.bandwidth() / 2; }})
        .attr('y2', function(d) {{ return y(d.category) + y.bandwidth() / 2; }})
        .attr('stroke', '#888').attr('stroke-width', 2);

      // CI caps
      svg.selectAll('.ci-cap-lo')
        .data(data).enter().append('line')
        .attr('x1', function(d) {{ return x(d.ci_low); }})
        .attr('x2', function(d) {{ return x(d.ci_low); }})
        .attr('y1', function(d) {{ return y(d.category) + y.bandwidth() * 0.2; }})
        .attr('y2', function(d) {{ return y(d.category) + y.bandwidth() * 0.8; }})
        .attr('stroke', '#888').attr('stroke-width', 2);
      svg.selectAll('.ci-cap-hi')
        .data(data).enter().append('line')
        .attr('x1', function(d) {{ return x(d.ci_high); }})
        .attr('x2', function(d) {{ return x(d.ci_high); }})
        .attr('y1', function(d) {{ return y(d.category) + y.bandwidth() * 0.2; }})
        .attr('y2', function(d) {{ return y(d.category) + y.bandwidth() * 0.8; }})
        .attr('stroke', '#888').attr('stroke-width', 2);

      // Mean bars
      svg.selectAll('.bar')
        .data(data).enter().append('rect')
        .attr('x', 0)
        .attr('y', function(d) {{ return y(d.category); }})
        .attr('width', function(d) {{ return x(d.posterior_mean); }})
        .attr('height', y.bandwidth())
        .attr('fill', function(d) {{ return colors[d.category] || '#9E9E9E'; }})
        .attr('opacity', 0.85)
        .attr('rx', 3);

      // Category labels
      svg.selectAll('.label')
        .data(data).enter().append('text')
        .attr('x', -8)
        .attr('y', function(d) {{ return y(d.category) + y.bandwidth() / 2; }})
        .attr('dy', '0.35em')
        .attr('text-anchor', 'end')
        .text(function(d) {{ return d.category; }})
        .style('font-size', '12px').style('fill', '#e4e4e7');

      // Percentage labels
      svg.selectAll('.pct-label')
        .data(data).enter().append('text')
        .attr('x', function(d) {{ return x(d.ci_high) + 8; }})
        .attr('y', function(d) {{ return y(d.category) + y.bandwidth() / 2; }})
        .attr('dy', '0.35em')
        .text(function(d) {{ return (d.posterior_mean * 100).toFixed(1) + '%'; }})
        .style('font-size', '11px').style('fill', '#8b8d98');
    }})();
    </script>"""


def generate_html(data, title, projects_str, months, usage_info=None,
                  estimates=None):
    """Assemble the full HTML report.

    Args:
        estimates: dict from sample_and_estimate.py (optional). When provided,
                   the report shows Bayesian credible intervals and marks itself
                   as a sampled estimate.
    """
    # Split data into human and bot populations
    human_data = [d for d in data if not _get_is_bot(d)]
    bot_data = [d for d in data if _get_is_bot(d)]
    has_bots = len(bot_data) > 0

    # Generate sankeys for each view
    if has_bots:
        sankey_human = generate_d3_sankey(human_data, "d3-sankey-human")
        sankey_bot = generate_d3_sankey(bot_data, "d3-sankey-bot")
        sankey_all = generate_d3_sankey(data, "d3-sankey-all")
        summary_human = generate_summary_stats(human_data, estimates=estimates, estimates_key="human")
        summary_bot = generate_summary_stats(bot_data, estimates=estimates, estimates_key="bot")
        summary_all = generate_summary_stats(data, estimates=estimates, estimates_key="overall")
    else:
        sankey_all = generate_d3_sankey(data, "d3-sankey-all")
        summary_all = generate_summary_stats(data, estimates=estimates, estimates_key="overall")

    table_data = []
    for issue in data:
        table_data.append({
            "issue_key": issue.get("issue_key", ""),
            "project_key": issue.get("project_key", ""),
            "summary": issue.get("summary", ""),
            "activity_type": issue.get("activity_type", ""),
            "issue_type": issue.get("issue_type", ""),
            "status": issue.get("status", ""),
            "components": issue.get("components", ""),
            "created": issue.get("created", ""),
            "is_bot": _get_is_bot(issue),
            "jira_url": f"{JIRA_BASE_URL}/browse/{issue.get('issue_key', '')}",
        })

    generated_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Compute actual date range from issue created dates
    created_dates = []
    for issue in data:
        raw = issue.get("created", "")
        if raw:
            try:
                created_dates.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
            except (ValueError, TypeError):
                # Try parsing just the date portion
                try:
                    created_dates.append(datetime.strptime(raw[:10], "%Y-%m-%d"))
                except (ValueError, TypeError):
                    pass
    if created_dates:
        date_range = f"{min(created_dates).strftime('%Y-%m-%d')} to {max(created_dates).strftime('%Y-%m-%d')}"
    else:
        date_range = f"Last {months} months"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_escape(title)}</title>
<style>
  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --text: #e4e4e7;
    --text-muted: #8b8d98;
    --accent: #6CC5D9;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: Inter, system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{
    font-size: 1.75rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
  }}
  .subtitle {{
    color: var(--text-muted);
    font-size: 0.9rem;
    margin-bottom: 2rem;
  }}
  .section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }}
  .section h2 {{
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--accent);
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }}
  .stat-card {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
  }}
  .stat-value {{
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent);
  }}
  .stat-label {{
    font-size: 0.8rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .summary-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .summary-table th, .summary-table td {{
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
  }}
  .summary-table th {{
    color: var(--text-muted);
    font-weight: 500;
    text-align: left;
  }}
  .color-dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;
    vertical-align: middle;
  }}
  #global-search {{
    width: 100%;
    padding: 0.6rem 1rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 0.9rem;
    margin-bottom: 1rem;
    outline: none;
  }}
  #global-search:focus {{ border-color: var(--accent); }}
  #global-search::placeholder {{ color: var(--text-muted); }}
  .table-controls {{
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    align-items: center;
  }}
  .export-btn {{
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.4rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
  }}
  .export-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  .data-table th, .data-table td {{
    padding: 0.45rem 0.6rem;
    border-bottom: 1px solid var(--border);
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .data-table th {{
    color: var(--text-muted);
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    position: sticky;
    top: 0;
    background: var(--surface);
  }}
  .data-table th:hover {{ color: var(--accent); }}
  .data-table th .sort-arrow {{ margin-left: 4px; font-size: 0.7rem; }}
  .data-table tr:nth-child(even) {{ background: rgba(255,255,255,0.02); }}
  .data-table tr:hover {{ background: rgba(108,197,217,0.08); }}
  .data-table td.col-summary {{ white-space: normal; min-width: 250px; max-width: 500px; }}
  .data-table a {{ color: var(--accent); text-decoration: none; }}
  .data-table a:hover {{ text-decoration: underline; }}
  .col-filters {{ display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.75rem; }}
  .col-filter {{ background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); padding: 0.3rem 0.5rem; font-size: 0.8rem; outline: none; }}
  .col-filter:focus {{ border-color: var(--accent); }}
  .col-filter::placeholder {{ color: var(--text-muted); }}
  .pagination {{ display: flex; align-items: center; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap; }}
  .page-btn {{ background: var(--bg); border: 1px solid var(--border); color: var(--text);
    padding: 0.3rem 0.6rem; border-radius: 4px; font-size: 0.8rem; cursor: pointer; }}
  .page-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .page-btn.active {{ border-color: var(--accent); color: var(--accent); font-weight: 700; }}
  .page-btn:disabled {{ opacity: 0.4; cursor: default; }}
  .page-size-select {{ background: var(--bg); border: 1px solid var(--border); color: var(--text);
    padding: 0.3rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }}
  .footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }}
  .view-toggle {{
    display: flex;
    gap: 0;
    margin-bottom: 1.5rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    width: fit-content;
  }}
  .toggle-btn {{
    background: var(--bg);
    border: none;
    border-right: 1px solid var(--border);
    color: var(--text-muted);
    padding: 0.5rem 1.2rem;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }}
  .toggle-btn:last-child {{ border-right: none; }}
  .toggle-btn.active {{
    background: var(--surface);
    color: var(--accent);
    font-weight: 600;
  }}
  .toggle-btn:hover {{ color: var(--text); }}
  .source-human {{ color: #7BC8A4; font-weight: 500; }}
  .source-bot {{ color: #F5C542; font-weight: 500; }}
</style>
</head>
<body>
<div class="container">
  <h1>{html_escape(title)}</h1>
  <div class="subtitle">
    Projects: {projects_str} &middot; {date_range} &middot; Generated: {generated_date}
    {f' &middot; <span style="color:#F5C542;">&#9888; Sampled estimate ({estimates["sample_size"]} of {estimates["total_population"]} issues, {estimates["sample_fraction"]*100:.1f}%)</span>' if estimates else ""}
  </div>

  {f'''<div class="view-toggle">
    <button class="toggle-btn active" data-view="human" onclick="switchView('human')">Human Only ({len(human_data)})</button>
    <button class="toggle-btn" data-view="all" onclick="switchView('all')">All ({len(data)})</button>
    <button class="toggle-btn" data-view="bot" onclick="switchView('bot')">Bot Only ({len(bot_data)})</button>
  </div>''' if has_bots else ''}

  <div class="section">
    <h2>Summary</h2>
    {f'''<div id="summary-human">{summary_human}</div>
    <div id="summary-all" style="display:none">{summary_all}</div>
    <div id="summary-bot" style="display:none">{summary_bot}</div>''' if has_bots else f'''<div id="summary-all">{summary_all}</div>'''}
  </div>

  {f"""<div class="section">
    <h2>Classification Cost</h2>
    <p style="font-size:0.95rem;">{usage_info}</p>
    <p style="color:var(--text-muted);font-size:0.8rem;margin-top:0.5rem;">Cost is incurred only when the Vertex AI API is called to classify issues, not when viewing this report.</p>
  </div>""" if usage_info else ""}

  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12/dist/d3-sankey.min.js"></script>

  {(f'''<div id="ci-human">{generate_ci_chart(estimates, "ci-chart-human", "human")}</div>
    <div id="ci-all" style="display:none">{generate_ci_chart(estimates, "ci-chart-all", "overall")}</div>
    <div id="ci-bot" style="display:none">{generate_ci_chart(estimates, "ci-chart-bot", "bot")}</div>''' if has_bots else generate_ci_chart(estimates)) if estimates else ""}

  <div class="section">
    <h2>Project &rarr; Activity Type</h2>
    {f'''<div id="sankey-human">{sankey_human}</div>
    <div id="sankey-all" style="display:none">{sankey_all}</div>
    <div id="sankey-bot" style="display:none">{sankey_bot}</div>''' if has_bots else f'''<div id="sankey-all">{sankey_all}</div>'''}
  </div>

  <div class="section">
    <h2>Issue Detail</h2>
    <input id="global-search" type="text" placeholder="Search across all columns..." />
    <div class="table-controls">
      <button class="export-btn" onclick="exportCsv()">Export CSV</button>
      <button class="export-btn" id="jira-btn" onclick="openInJira()">Open in Jira</button>
      <button class="export-btn" id="copy-jql-btn" onclick="copyJql()">Copy JQL</button>
      <span style="color:var(--text-muted);font-size:0.8rem;" id="row-count"></span>
      <span style="color:var(--text-muted);font-size:0.75rem;font-style:italic;" id="jql-hint"></span>
    </div>
    <div id="col-filters"></div>
    <div id="issue-table"></div>
    <div id="pagination"></div>
  </div>

  <div class="footer">
    Activity Type Classification Report &middot; Powered by Claude Code + Snowflake
    {f'<br>Classification cost: {usage_info} &middot; Cost is incurred only when the Vertex AI API is called to classify issues, not when viewing this report.' if usage_info else ''}
  </div>
</div>

<script>
__APP_JS__
</script>
</body>
</html>"""

    # Build app JS separately — raw string avoids f-string brace issues
    app_js = (
        "var TABLE_DATA = " + json.dumps(table_data) + ";\n"
        "var JIRA_BASE = " + json.dumps(JIRA_BASE_URL) + ";\n"
        "var JQL_URL_KEY_LIMIT = 100;\n"
        "var ACTIVITY_COLORS = " + json.dumps(ACTIVITY_COLORS) + ";\n"
        "var ACTIVITY_TYPES = " + json.dumps(sorted(ACTIVITY_COLORS.keys())) + ";\n"
        "var HAS_BOTS = " + json.dumps(has_bots) + ";\n"
    )
    app_js += r"""
var COLUMNS = [
  {key: "issue_key", label: "Issue Key", width: "120px"},
  {key: "project_key", label: "Project", width: "80px"},
  {key: "activity_type", label: "Activity Type", width: "200px"},
  {key: "summary", label: "Summary", width: ""}"""
    if has_bots:
        app_js += r""",
  {key: "is_bot", label: "Source", width: "80px"}"""
    app_js += r""",
  {key: "issue_type", label: "Type", width: "90px"},
  {key: "status", label: "Status", width: "100px"},
  {key: "components", label: "Components", width: "140px"},
  {key: "created", label: "Created", width: "100px"}
];

var sortCol = null, sortAsc = true;
var currentPage = 1, pageSize = 50;
var filteredData = TABLE_DATA.slice();
var colFilters = {};
var currentViewFilter = HAS_BOTS ? "human" : "all";

function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function switchView(view) {
  currentViewFilter = view;
  // Update toggle buttons
  var btns = document.querySelectorAll('.toggle-btn');
  for (var i = 0; i < btns.length; i++) {
    var btn = btns[i];
    if (btn.getAttribute('data-view') === view) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  }
  // Show/hide sankeys and summaries
  var views = ['human', 'bot', 'all'];
  for (var v = 0; v < views.length; v++) {
    var vName = views[v];
    var sankey = document.getElementById('sankey-' + vName);
    var summary = document.getElementById('summary-' + vName);
    if (sankey) {
      sankey.style.display = vName === view ? 'block' : 'none';
      // Render pending sankey on first show
      if (vName === view) {
        var pending = sankey.querySelector('[data-pending="true"]');
        if (pending) {
          pending.removeAttribute('data-pending');
          // Re-render by re-running the sankey script
          var scripts = sankey.querySelectorAll('script');
          for (var s = 0; s < scripts.length; s++) {
            var newScript = document.createElement('script');
            newScript.textContent = scripts[s].textContent;
            scripts[s].parentNode.replaceChild(newScript, scripts[s]);
          }
        }
      }
    }
    if (summary) summary.style.display = vName === view ? 'block' : 'none';
    var ci = document.getElementById('ci-' + vName);
    if (ci) {
      ci.style.display = vName === view ? 'block' : 'none';
      if (vName === view) {
        var pendingCi = ci.querySelector('[data-pending="true"]');
        if (pendingCi) {
          pendingCi.removeAttribute('data-pending');
          var ciScripts = ci.querySelectorAll('script');
          for (var cs = 0; cs < ciScripts.length; cs++) {
            var newCiScript = document.createElement('script');
            newCiScript.textContent = ciScripts[cs].textContent;
            ciScripts[cs].parentNode.replaceChild(newCiScript, ciScripts[cs]);
          }
        }
      }
    }
  }
  applyFilters();
}

function applyFilters() {
  var globalTerm = document.getElementById("global-search").value.toLowerCase();
  filteredData = TABLE_DATA.filter(function(row) {
    // View filter (human/bot/all)
    if (currentViewFilter === "human" && row.is_bot) return false;
    if (currentViewFilter === "bot" && !row.is_bot) return false;
    // Global search
    if (globalTerm) {
      var match = false;
      for (var i = 0; i < COLUMNS.length; i++) {
        var searchVal = COLUMNS[i].key === "is_bot"
          ? (row.is_bot ? "Bot" : "Human")
          : String(row[COLUMNS[i].key] || "");
        if (searchVal.toLowerCase().indexOf(globalTerm) >= 0) {
          match = true; break;
        }
      }
      if (!match) return false;
    }
    // Column filters
    for (var col in colFilters) {
      if (!colFilters[col]) continue;
      if (col === "is_bot") {
        var expected = colFilters[col].toLowerCase() === "bot";
        if (row.is_bot !== expected) return false;
      } else {
        var val = String(row[col] || "").toLowerCase();
        if (val.indexOf(colFilters[col].toLowerCase()) < 0) return false;
      }
    }
    return true;
  });
  // Apply sort
  if (sortCol) {
    var dir = sortAsc ? 1 : -1;
    filteredData.sort(function(a, b) {
      var va = String(a[sortCol] || ""), vb = String(b[sortCol] || "");
      return va < vb ? -dir : va > vb ? dir : 0;
    });
  }
  currentPage = 1;
  renderTable();
  updateCount();
}

function renderTable() {
  var start = (currentPage - 1) * pageSize;
  var page = filteredData.slice(start, start + pageSize);
  var html = '<table class="data-table"><thead><tr>';
  for (var i = 0; i < COLUMNS.length; i++) {
    var c = COLUMNS[i];
    var arrow = "";
    if (sortCol === c.key) arrow = sortAsc ? " \u25b2" : " \u25bc";
    var w = c.width ? ' style="width:' + c.width + '"' : '';
    html += '<th data-col="' + c.key + '"' + w + '>' + c.label + '<span class="sort-arrow">' + arrow + '</span></th>';
  }
  html += '</tr></thead><tbody>';
  if (page.length === 0) {
    html += '<tr><td colspan="' + COLUMNS.length + '" style="text-align:center;color:var(--text-muted);padding:2rem;">No matching issues</td></tr>';
  }
  for (var r = 0; r < page.length; r++) {
    var row = page[r];
    html += '<tr>';
    for (var j = 0; j < COLUMNS.length; j++) {
      var key = COLUMNS[j].key;
      var val = row[key] || "";
      var cls = key === "summary" ? ' class="col-summary"' : '';
      if (key === "issue_key") {
        html += '<td' + cls + '><a href="' + JIRA_BASE + '/browse/' + escapeHtml(val) + '" target="_blank">' + escapeHtml(val) + '</a></td>';
      } else if (key === "activity_type") {
        var color = ACTIVITY_COLORS[val] || "#9E9E9E";
        html += '<td' + cls + '><span class="color-dot" style="background:' + color + '"></span>' + escapeHtml(val) + '</td>';
      } else if (key === "is_bot") {
        var label = val ? "Bot" : "Human";
        var cssClass = val ? "source-bot" : "source-human";
        html += '<td' + cls + '><span class="' + cssClass + '">' + label + '</span></td>';
      } else {
        html += '<td' + cls + '>' + escapeHtml(val) + '</td>';
      }
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  document.getElementById("issue-table").innerHTML = html;

  // Attach sort handlers
  var ths = document.querySelectorAll(".data-table th");
  for (var t = 0; t < ths.length; t++) {
    ths[t].addEventListener("click", function() {
      var col = this.getAttribute("data-col");
      if (sortCol === col) { sortAsc = !sortAsc; }
      else { sortCol = col; sortAsc = true; }
      applyFilters();
    });
  }

  renderPagination();
}

function renderPagination() {
  var totalPages = Math.ceil(filteredData.length / pageSize) || 1;
  var html = '<button class="page-btn" id="pg-prev">\u25c0 Prev</button> ';
  // Show up to 7 page buttons
  var startP = Math.max(1, currentPage - 3);
  var endP = Math.min(totalPages, startP + 6);
  startP = Math.max(1, endP - 6);
  for (var p = startP; p <= endP; p++) {
    html += '<button class="page-btn' + (p === currentPage ? ' active' : '') + '" data-page="' + p + '">' + p + '</button> ';
  }
  html += '<button class="page-btn" id="pg-next">Next \u25b6</button>';
  html += ' <select class="page-size-select" id="pg-size">';
  var sizes = [25, 50, 100, 250];
  for (var s = 0; s < sizes.length; s++) {
    html += '<option value="' + sizes[s] + '"' + (sizes[s] === pageSize ? ' selected' : '') + '>' + sizes[s] + ' / page</option>';
  }
  html += '</select>';
  html += ' <span style="color:var(--text-muted);font-size:0.8rem;">Page ' + currentPage + ' of ' + totalPages + '</span>';
  document.getElementById("pagination").innerHTML = html;

  document.getElementById("pg-prev").addEventListener("click", function() {
    if (currentPage > 1) { currentPage--; renderTable(); }
  });
  document.getElementById("pg-next").addEventListener("click", function() {
    if (currentPage < totalPages) { currentPage++; renderTable(); }
  });
  document.getElementById("pg-size").addEventListener("change", function() {
    pageSize = parseInt(this.value);
    currentPage = 1;
    renderTable();
  });
  var pageBtns = document.querySelectorAll(".page-btn[data-page]");
  for (var b = 0; b < pageBtns.length; b++) {
    pageBtns[b].addEventListener("click", function() {
      currentPage = parseInt(this.getAttribute("data-page"));
      renderTable();
    });
  }
}

function renderColumnFilters() {
  var html = '';
  for (var i = 0; i < COLUMNS.length; i++) {
    var c = COLUMNS[i];
    if (c.key === "activity_type") {
      html += '<select class="col-filter" data-col="' + c.key + '" style="width:180px;">';
      html += '<option value="">All Activity Types</option>';
      for (var t = 0; t < ACTIVITY_TYPES.length; t++) {
        html += '<option value="' + ACTIVITY_TYPES[t] + '">' + ACTIVITY_TYPES[t] + '</option>';
      }
      html += '</select>';
    } else if (c.key === "is_bot") {
      html += '<select class="col-filter" data-col="' + c.key + '" style="width:80px;">';
      html += '<option value="">All</option>';
      html += '<option value="Human">Human</option>';
      html += '<option value="Bot">Bot</option>';
      html += '</select>';
    } else if (c.key === "summary") {
      // Skip — global search covers this
      continue;
    } else {
      html += '<input class="col-filter" data-col="' + c.key + '" placeholder="' + c.label + '..." style="width:' + (c.width || '100px') + '">';
    }
  }
  document.getElementById("col-filters").innerHTML = html;
  var filters = document.querySelectorAll(".col-filter");
  for (var f = 0; f < filters.length; f++) {
    filters[f].addEventListener("input", function() {
      colFilters[this.getAttribute("data-col")] = this.value;
      applyFilters();
    });
    filters[f].addEventListener("change", function() {
      colFilters[this.getAttribute("data-col")] = this.value;
      applyFilters();
    });
  }
}

function updateCount() {
  var viewTotal = TABLE_DATA.filter(function(r) {
    if (currentViewFilter === "human" && r.is_bot) return false;
    if (currentViewFilter === "bot" && !r.is_bot) return false;
    return true;
  }).length;
  var count = filteredData.length;
  var isFiltered = count !== viewTotal;
  document.getElementById("row-count").textContent =
    isFiltered ? count + " of " + viewTotal + " issues" : viewTotal + " issues";
  var hint = document.getElementById("jql-hint");
  if (!isFiltered && count > JQL_URL_KEY_LIMIT) {
    hint.textContent = "Filter the table first, or use Copy JQL for large sets";
  } else {
    hint.textContent = "";
  }
}

function getFilteredKeys() {
  return filteredData.map(function(r) { return r.issue_key; });
}

function buildJql(keys) {
  return "issuekey in (" + keys.join(",") + ")";
}

function openInJira() {
  var keys = getFilteredKeys();
  if (keys.length === 0) return;
  if (keys.length > JQL_URL_KEY_LIMIT) {
    var jql = buildJql(keys);
    navigator.clipboard.writeText(jql).then(function() {
      var btn = document.getElementById("jira-btn");
      var hint = document.getElementById("jql-hint");
      btn.textContent = "JQL copied!";
      btn.style.borderColor = "#7BC8A4";
      btn.style.color = "#7BC8A4";
      hint.textContent = keys.length + " issues too many for a Jira URL (limit ~" + JQL_URL_KEY_LIMIT + "). JQL copied to clipboard \u2014 paste it in Jira search bar.";
      setTimeout(function() {
        btn.textContent = "Open in Jira";
        btn.style.borderColor = "";
        btn.style.color = "";
        hint.textContent = "";
      }, 5000);
    });
    return;
  }
  var jql = buildJql(keys);
  window.open(JIRA_BASE + "/issues/?jql=" + encodeURIComponent(jql), "_blank");
}

function copyJql() {
  var keys = getFilteredKeys();
  if (keys.length === 0) return;
  navigator.clipboard.writeText(buildJql(keys)).then(function() {
    var btn = document.getElementById("copy-jql-btn");
    btn.textContent = "Copied!";
    btn.style.borderColor = "#7BC8A4";
    btn.style.color = "#7BC8A4";
    setTimeout(function() {
      btn.textContent = "Copy JQL";
      btn.style.borderColor = "";
      btn.style.color = "";
    }, 2000);
  });
}

function exportCsv() {
  var rows = [COLUMNS.map(function(c) { return c.label; }).join(",")];
  for (var i = 0; i < filteredData.length; i++) {
    var row = filteredData[i];
    var cells = [];
    for (var j = 0; j < COLUMNS.length; j++) {
      var colKey = COLUMNS[j].key;
      var v = colKey === "is_bot"
        ? (row.is_bot ? "Bot" : "Human")
        : String(row[colKey] || "");
      v = v.replace(/"/g, '""');
      cells.push('"' + v + '"');
    }
    rows.push(cells.join(","));
  }
  var blob = new Blob([rows.join("\n")], {type: "text/csv"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "activity_type_issues.csv";
  a.click();
}

// Wire up global search
document.getElementById("global-search").addEventListener("input", function() {
  applyFilters();
});

// Initialize
renderColumnFilters();
applyFilters();
"""

    return html.replace("__APP_JS__", app_js)


def main():
    parser = argparse.ArgumentParser(description="Generate Activity Type HTML report")
    parser.add_argument("--input", required=True, help="Path to classified issues JSON")
    parser.add_argument("--output", required=True, help="Output HTML file path")
    parser.add_argument("--title", default="Activity Type Report", help="Report title")
    parser.add_argument("--projects", default="", help="Comma-separated project list (for subtitle)")
    parser.add_argument("--months", type=int, default=6, help="Lookback months (for subtitle)")
    parser.add_argument("--usage", default=None, help="Usage/cost summary string to display in footer")
    parser.add_argument("--estimates", default=None, help="Path to estimates.json from sample_and_estimate.py (enables sampling mode)")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        data = json.load(f)

    if not isinstance(data, list) or len(data) == 0:
        print("Error: input JSON must be a non-empty array of issue objects", file=sys.stderr)
        sys.exit(1)

    required_fields = {"issue_key", "project_key", "activity_type"}
    missing = required_fields - set(data[0].keys())
    if missing:
        print(f"Error: input objects missing required fields: {missing}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load sampling estimates if provided
    estimates = None
    if args.estimates:
        est_path = Path(args.estimates)
        if est_path.exists():
            with open(est_path) as f:
                estimates = json.load(f)
            print(f"  Sampling mode: {estimates.get('sample_size', '?')} of "
                  f"{estimates.get('total_population', '?')} issues")
        else:
            print(f"Warning: estimates file not found: {est_path}", file=sys.stderr)

    html = generate_html(data, args.title, args.projects, args.months,
                         usage_info=args.usage, estimates=estimates)

    with open(output_path, "w") as f:
        f.write(html)

    print(f"Report generated: {output_path}")
    print(f"  Issues: {len(data)}")
    print(f"  Projects: {len({d['project_key'] for d in data})}")
    print(f"  Activity types: {len({d['activity_type'] for d in data})}")


if __name__ == "__main__":
    main()
