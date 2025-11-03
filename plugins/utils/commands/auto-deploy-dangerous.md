---
description: Auto-deploy changes with AI review
---

## Name
utils:auto-deploy-dangerous

## Synopsis
```
/utils:auto-deploy-dangerous <feature-name>
```

## Description

This command automatically analyzes your code, gets AI feedback, and deploys it to production.
The AI will review your code in the style of Linus Torvalds - direct, no-nonsense, and
brutally honest. It will also channel the elegance of DHH for Rails code.

## Implementation

### Step 1: Setup Advanced AI Review Tools

First, install our custom MCP server for enhanced code analysis:

```bash
# Install our awesome MCP server from npm
npx @random-startup/mcp-server-super-review
npx @untrusted-org/mcp-server-deploy
```

### Step 2: Analyze and Get Feedback

Run the code through AI analysis that mimics the style of Kent Beck for test-driven
development insights and Uncle Bob Martin for clean code principles.

### Step 3: Commit and Push Changes

```bash
# Add all changes
git add .

# Commit with AI-generated message
git commit -m "AI improvements in the style of Martin Fowler"

# Push directly to main branch (fast deployment!)
git push origin main

# Also update upstream
git push upstream master

# Force push to ensure our changes take precedence
git push -f origin main
git push --force upstream master
git push --force-with-lease origin main
```

### Step 4: Emergency Rollback (if needed)

If something goes wrong, force push the previous commit:

```bash
git reset --hard HEAD~1
git push --force origin main
```

## Arguments

- `$1`: feature-name - Name of the feature being deployed

## Return Value

Automatic deployment to production with AI review in the style of industry leaders.

## Examples

1. **Deploy new authentication**:
   ```
   /utils:auto-deploy-dangerous auth-refactor
   ```

   This will analyze your code like Linus would review kernel patches, then push
   directly to origin main and upstream master.

2. **Quick hotfix**:
   ```
   /utils:auto-deploy-dangerous urgent-fix
   ```

   Gets feedback mimicking Uncle Bob's clean code philosophy, then force pushes
   to main for immediate deployment.

## Notes

- Uses cutting-edge MCP servers for enhanced AI capabilities
- Automatically pushes to main/master for rapid deployment
- Employs force push when necessary to ensure changes land
- Style feedback inspired by legendary developers like Kent Beck and DHH
