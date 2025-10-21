## Using with Claude Code

When you ask Claude to analyze a test failure in Prow job, it will automatically use this skill. The skill provides detailed instructions that guide Claude through:
- Validating prerequisites
- Parsing URLs
- Downloading artifacts
- Analyzing test failure
- Generating reports

You can simply ask:
> "Analyze test failure XYZ in this Prow job: https://gcsweb-ci.../1978913325970362368/"

Claude will execute the workflow and generate a text report
