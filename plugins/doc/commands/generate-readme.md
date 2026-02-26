---
description: Generate or update README.md for a repository
argument-hint: [--type <type>] [--style <style>] [--force]
---

## Name
doc:generate-readme

## Synopsis
```
/doc:generate-readme [--type <type>] [--style <style>] [--force]
```

## Description
The `doc:generate-readme` command analyzes the current directory and generates or updates README.md based on project structure, code, dependencies, and tests. It intelligently detects project type and extracts accurate content to create professional documentation.

**Key behaviors:**
- **New README**: Generates complete documentation from scratch
- **Existing README**: Intelligently updates outdated sections while preserving custom content
- **Smart merging**: Analyzes existing structure and refreshes auto-detectable content (dependencies, installation, usage examples)
- **Backup**: Always creates `README.md.backup` before making changes

## Implementation

### 1. Analyze Current Directory
- Validate current directory is accessible
- Check for existing README.md
- Detect git repository (enhances content extraction)

### 2. Project Type Detection
Auto-detect by scanning for indicator files:

**Project Types:**
- **Go**: `go.mod`, `go.sum` → Extract module name, dependencies, Go version
- **Python**: `requirements.txt`, `pyproject.toml`, `setup.py` → Extract packages, Python version
- **Node.js**: `package.json` → Extract scripts, dependencies, metadata
- **Operator**: `PROJECT`, `config/`, Makefile with operator-sdk → Extract CRD info
- **Container**: `Dockerfile`, `Containerfile` → Extract base image, ports, env vars
- **Generic**: Makefile, build scripts → Extract build commands

### 3. Content Extraction

**From Code:**
- Main entry points and purpose
- Exported functions and APIs
- Usage examples from test files

**From Configuration:**
- Dependencies and versions from manifests
- Environment variables from Dockerfiles and code
- Build commands from Makefile, package.json scripts
- CI/CD setup from `.github/workflows/`, `.gitlab-ci.yml`

**From Existing Docs:**
- LICENSE file → License type
- CONTRIBUTING.md → Link to contribution guidelines
- Existing README.md → Custom sections to preserve

### 4. README Generation Strategy

**For New README (no existing file):**
1. Generate all standard sections based on detected content
2. Write to README.md
3. Display summary

**For Existing README (file exists):**
1. **Parse existing structure**: Identify custom vs auto-generated sections
2. **Preserve custom content**:
   - Architecture diagrams
   - Design decisions
   - Manually written examples
   - Custom troubleshooting guides
3. **Update auto-detectable sections**:
   - Dependencies (from go.mod, package.json, etc.)
   - Installation commands (from package managers)
   - Usage examples (from test files)
   - Prerequisites (from dependency files)
   - Build commands (from Makefile, scripts)
4. **Smart merge**:
   - Keep section ordering from existing README
   - Add missing standard sections at appropriate positions
   - Update section content with current project state
   - Refresh outdated version numbers and commands
5. **Create backup**: Save original to `README.md.backup`
6. **Write updated README**: Merged content with refreshed data

**If `--force` not specified and README exists:**
- Show preview of changes
- Prompt for confirmation: "Update existing README? [y/N]"
- User can review backup if needed

### 5. Generated Sections

**Standard sections (included when content available):**
- **Title**: Project name from directory/manifest
- **Description**: From package metadata or code analysis
- **Table of Contents**: Auto-generated for READMEs >100 lines
- **Features**: Extracted from code capabilities
- **Prerequisites**: Dependencies with versions
- **Installation**: Package manager commands, build instructions
- **Usage**: Examples from tests and entry points
- **Configuration**: Environment variables, config files
- **Development**: Setup, build, and test commands
- **Contributing**: Link to CONTRIBUTING.md or basic guidelines
- **License**: From LICENSE file

**Style variations:**
- `minimal`: Title, Description, Installation, Usage only
- `standard`: Common sections with moderate detail (default)
- `comprehensive`: All sections with detailed examples

### 6. Formatting and Output

- Proper markdown formatting with syntax highlighting
- Consistent heading hierarchy
- Clean code blocks with language tags
- Write to `README.md` in current directory
- Display generation summary

## Return Value

**Success output:**
```
✅ README.md updated successfully!

Project type: Go module (v1.21)
Style: standard
Action: Updated existing README (backup created)

Sections updated:
  • Dependencies (12 direct)
  • Installation commands
  • Usage examples (4 from tests)
  • Prerequisites

Sections preserved:
  • Architecture
  • Design Decisions

README.md: 287 lines, 1,850 words
💾 Backup: README.md.backup

💡 Tip: Review changes with: diff README.md.backup README.md
```

## Examples

### 1. Generate README for new project
```
cd my-new-project
/doc:generate-readme
```

### 2. Update existing README with current project state
```
cd existing-project
/doc:generate-readme
```
Analyzes existing README, updates dependencies and commands, preserves custom sections.

### 3. Force regeneration
```
/doc:generate-readme --force
```
Updates without prompting (backup still created).

### 4. Minimal documentation
```
/doc:generate-readme --style minimal
```
Essential sections only.

### 5. Comprehensive documentation
```
/doc:generate-readme --style comprehensive
```
All available sections with detailed content.

### 6. Force specific project type
```
/doc:generate-readme --type operator
```
Treat as OpenShift operator regardless of auto-detection.

## Arguments

**`--type <project-type>`** (optional)
- Force specific project type
- Values: `go`, `python`, `nodejs`, `operator`, `container`, `library`, `cli`, `generic`
- Default: auto-detect
- Example: `--type operator`

**`--style <style>`** (optional)
- README detail level
- Values: `minimal`, `standard`, `comprehensive`
- Default: `standard`
- Example: `--style comprehensive`

**`--force`** (optional)
- Update without prompting
- Creates backup before overwriting
- Example: `--force`

## Error Handling

**Directory not accessible:**
```
Error: Cannot access current directory
```

**No project type detected:**
```
Warning: Could not auto-detect project type.
Specify with --type flag or ensure project has standard files (go.mod, package.json, etc.)
```

**Existing README without --force:**
```
⚠️  README.md already exists.

Preview of changes:
  - Will update: Dependencies, Installation, Usage
  - Will preserve: Architecture, Design Decisions

Update existing README? [y/N]:
```

## Notes

### Smart Update Strategy

When updating an existing README, the command:

1. **Identifies custom sections** by analyzing content patterns
   - Sections with unique headings (not in standard templates)
   - Hand-written examples and explanations
   - Architectural diagrams and design docs

2. **Refreshes auto-generated content**
   - Dependency lists from current manifests
   - Installation commands from current package managers
   - Usage examples from current test files
   - Version numbers and compatibility info

3. **Maintains document structure**
   - Keeps existing section ordering
   - Preserves heading levels
   - Maintains custom formatting preferences

### Best Practices

1. **Review changes**: Always check the diff after updating
   ```bash
   diff README.md.backup README.md
   ```

2. **Commit before updating**: Easy to revert if needed
   ```bash
   git add README.md
   git commit -m "Update before README regeneration"
   ```

3. **Iterative refinement**: Generate, review, manually adjust, then re-run to keep documentation current

4. **Use version control**: Backups are created but git provides better history

### Project-Specific Tips

**Go projects**: Keep godoc comments updated for better descriptions
**Python projects**: Maintain docstrings for accurate usage examples
**Operators**: Keep CRD samples in `config/samples/` for documentation
**Container projects**: Document ENV vars in Dockerfile comments

## See Also

- `/doc:note` - Generate engineering notes
- `/git:summary` - Summarize repository changes
