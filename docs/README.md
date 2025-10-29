# AI Helpers Website

This directory contains the GitHub Pages website for the ai-helpers project.

## Structure

- `index.html` - Main website with plugin browser
- `data.json` - Plugin and command metadata (generated)
- `.nojekyll` - Tells GitHub Pages not to use Jekyll processing

## Building

The website data is generated from the repository structure:

```bash
# From repository root
python3 scripts/build-website.py
```

This extracts information from:
- `.claude-plugin/marketplace.json` - Plugin registry
- `plugins/*/commands/*.md` - Command definitions
- `plugins/*/skills/*/SKILL.md` - Skill definitions
- `plugins/*/.claude-plugin/plugin.json` - Plugin metadata

## Local Development

To test the website locally:

```bash
cd docs
python3 -m http.server 8000
# Visit http://localhost:8000
```

## Deployment

The website is automatically deployed via GitHub Pages from the `docs/` directory.

To enable GitHub Pages:
1. Go to repository Settings > Pages
2. Set Source to "Deploy from a branch"
3. Select branch (e.g., `main`) and `/docs` folder
4. Save

The site will be available at: `https://openshift-eng.github.io/ai-helpers/`

## Updating

When plugins or commands are added/modified:

1. Run `python3 scripts/build-website.py` to regenerate `data.json`
2. Commit both `data.json` and any changes
3. Push to trigger GitHub Pages rebuild

Alternatively, set up a GitHub Action to automatically rebuild on changes.
