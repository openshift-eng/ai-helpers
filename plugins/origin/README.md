# Origin Plugin

Utilities and workflow helpers for developing and reviewing changes in the
openshift/origin repository.  
This plugin focuses on improving test quality, code consistency, and CI suite
integration for Origin contributions.

## Commands

### /origin:two-node-origin-pr-helper

Expert review tool for PRs that add or modify Two Node (Fencing or Arbiter) tests
under test/extended/two_node/.

This command performs:

- Automatic discovery of changed Two Node test files
- Analysis of Ginkgo Describe/It blocks, suite tags, and Serial annotations
- Review of test logic, determinism, cleanup behavior, and structure
- Suggestions for reusing existing Origin and Kubernetes utilities
- Identification of duplicated logic that should use shared helpers
- Recommendations for suite placement and Serial usage
- Recommendations for CI lane coverage in openshift/release
- Generation of ready-to-paste PR text for both Origin and Release repositories

Use this helper when contributing to Origin’s Two Node test suite or reviewing PRs
that affect Two Node behavior.

See the commands/ directory for full documentation.

## Installation

### From the Claude Code Plugin Marketplace

1. Add the OpenShift ai-helpers marketplace:

   /plugin marketplace add openshift-eng/ai-helpers

2. Install the origin plugin:

   /plugin install origin@ai-helpers

3. Use the command:

   /origin:two-node-origin-pr-helper

## Available Commands

### Two Node PR Review

#### /origin:two-node-origin-pr-helper — Review Two Node Tests in Origin

This command performs a full expert review of PRs that modify or add Two Node
(Fencing or Arbiter) tests under test/extended/two_node/.

The helper covers:

- Code correctness and logical consistency
- Ginkgo test structure and best practices
- Suite tagging and Serial analysis
- Utility/helper reuse (Origin + Kubernetes)
- CI suite and lane coverage recommendations
- PR description generation

See commands/two-node-origin-pr-helper.md for full documentation.

## Development

### Adding New Commands

To add a new command to this plugin:

1. Create a markdown file in commands/:

   touch plugins/origin/commands/your-command.md

2. Use existing commands as a template and include sections:

   - Name  
   - Synopsis  
   - Description  
   - Implementation behavior  
   - Return value / output structure  
   - Examples  
   - Arguments  
   - Error handling  
   - Additional context if needed

3. Test the command:

   /origin:your-command

## Plugin Structure

plugins/origin/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── two-node-origin-pr-helper.md
└── README.md

## Related Plugins

- openshift — General OpenShift development and CI helpers
- ci — Prow/CI-related workflow helpers
- git — Git workflow helpers
- jira — Jira automation helpers
- utils — General-purpose utilities

## Contributing

Contributions are welcome.

When adding Origin-specific commands:

- Ensure the workflow relates directly to openshift/origin
- Follow existing documentation patterns
- Provide actionable examples and behavior explanations
- Use realistic Origin repository paths and test patterns
- Update this README with any new commands

## License

See [LICENSE](../../LICENSE) for details.
