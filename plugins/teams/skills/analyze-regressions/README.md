# HTML Report Generation for Component Health Analysis

This directory contains resources for generating interactive HTML reports from component health regression data.

## Files

- `report_template.html` - HTML template with placeholders for data
- `generate_html_report.py` - Python script to generate reports from JSON data
- `README.md` - This file

## Template Variables

The HTML template uses the following placeholders (enclosed in `{{}}` double curly braces):

### Overall Metrics
- `{{RELEASE}}` - Release version (e.g., "4.20")
- `{{RELEASE_PERIOD}}` - Development period description
- `{{DATE_RANGE}}` - Date range for the analysis
- `{{GENERATED_DATE}}` - Report generation date

### Triage Coverage Metrics
- `{{TRIAGE_COVERAGE}}` - Percentage (e.g., "25.7")
- `{{TRIAGE_COVERAGE_CLASS}}` - CSS class (good/warning/poor)
- `{{TRIAGE_COVERAGE_GRADE}}` - Grade text with emoji
- `{{TRIAGE_COVERAGE_GRADE_CLASS}}` - Grade CSS class
- `{{TOTAL_REGRESSIONS}}` - Total regression count
- `{{TRIAGED_REGRESSIONS}}` - Triaged count
- `{{UNTRIAGED_REGRESSIONS}}` - Untriaged count

### Triage Timeliness Metrics
- `{{TRIAGE_TIME_AVG}}` - Average hours to triage
- `{{TRIAGE_TIME_AVG_DAYS}}` - Average days to triage
- `{{TRIAGE_TIME_MAX}}` - Maximum hours to triage
- `{{TRIAGE_TIME_MAX_DAYS}}` - Maximum days to triage
- `{{TRIAGE_TIME_CLASS}}` - CSS class
- `{{TRIAGE_TIME_GRADE}}` - Grade text
- `{{TRIAGE_TIME_GRADE_CLASS}}` - Grade CSS class

### Resolution Speed Metrics
- `{{RESOLUTION_TIME_AVG}}` - Average hours to close
- `{{RESOLUTION_TIME_AVG_DAYS}}` - Average days to close
- `{{RESOLUTION_TIME_MAX}}` - Maximum hours to close
- `{{RESOLUTION_TIME_MAX_DAYS}}` - Maximum days to close
- `{{RESOLUTION_TIME_CLASS}}` - CSS class
- `{{RESOLUTION_TIME_GRADE}}` - Grade text
- `{{RESOLUTION_TIME_GRADE_CLASS}}` - Grade CSS class

### Open/Closed Breakdown
- `{{OPEN_REGRESSIONS}}` - Open regression count
- `{{OPEN_TRIAGE_PERCENTAGE}}` - Open triage percentage
- `{{CLOSED_REGRESSIONS}}` - Closed regression count
- `{{CLOSED_TRIAGE_PERCENTAGE}}` - Closed triage percentage
- `{{OPEN_AGE_AVG}}` - Average age of open regressions (hours)
- `{{OPEN_AGE_AVG_DAYS}}` - Average age of open regressions (days)

### Dynamic Content
- `{{COMPONENT_ROWS}}` - HTML table rows for all components
- `{{ATTENTION_SECTIONS}}` - Alert boxes for critical issues
- `{{INSIGHTS}}` - List items for key insights
- `{{RECOMMENDATIONS}}` - List items for recommendations

## Usage with Python Script

### Using data files:
```bash
python3 generate_html_report.py \
    --release 4.20 \
    --data regression_data.json \
    --dates release_dates.json \
    --output report.html
```

### Using stdin:
```bash
cat regression_data.json | python3 generate_html_report.py \
    --release 4.20 \
    --dates release_dates.json \
    --output report.html
```

## Manual Template Usage (for Claude Code)

When generating reports directly in Claude Code without the Python script:

1. Read the template file
2. Replace all `{{VARIABLE}}` placeholders with actual values
3. Generate component rows dynamically
4. Build attention sections based on the data
5. Write the final HTML to `.work/teams-{release}/report.html`
6. Open with `open` command (macOS) or equivalent

## Grading Criteria

### Triage Coverage
- **Excellent (✅)**: 90-100%
- **Good (✅)**: 70-89%
- **Needs Improvement (⚠️)**: 50-69%
- **Poor (❌)**: <50%

### Triage Timeliness
- **Excellent (✅)**: <24 hours
- **Good (⚠️)**: 24-72 hours
- **Needs Improvement (⚠️)**: 72-168 hours (1 week)
- **Poor (❌)**: >168 hours

### Resolution Speed
- **Excellent (✅)**: <168 hours (1 week)
- **Good (⚠️)**: 168-336 hours (1-2 weeks)
- **Needs Improvement (⚠️)**: 336-720 hours (2-4 weeks)
- **Poor (❌)**: >720 hours (4+ weeks)

## Features

- **Interactive Filtering**: Search components by name and filter by health grade
- **Responsive Design**: Works on desktop and mobile devices
- **Visual Indicators**: Color-coded metrics (red/yellow/green)
- **Hover Effects**: Enhanced UX with hover states
- **Alert Sections**: Automatically highlights critical issues
- **Auto-generated Content**: Component rows and alerts generated from data

## Customization

To customize the report appearance:

1. Edit `report_template.html` - Modify CSS in the `<style>` section
2. Update color schemes by changing gradient values
3. Adjust thresholds in the grading logic
4. Add new sections by modifying the template structure
