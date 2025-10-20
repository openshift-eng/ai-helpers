# Changelog

All notable changes to the Prow Job Extract Must-Gather skill will be documented in this file.

## [1.0.0] - 2025-01-17

### Added
- Initial release of Prow Job Extract Must-Gather skill
- Command file: `plugins/prow-job/commands/extract-must-gather.md`
- Comprehensive SKILL.md with detailed implementation instructions
- `extract_archives.py` script for recursive archive extraction
  - Extracts must-gather.tar to specified directory
  - Renames long "-ci-" containing subdirectory to "content/"
  - Recursively processes nested .tar.gz, .tgz, and .gz archives
  - Removes original compressed files after extraction
  - Handles up to 10 levels of nesting
  - Reports extraction statistics
- `generate_html_report.py` script for HTML file browser generation
  - Scans directory tree and collects file metadata
  - Classifies files by type (log, yaml, json, xml, cert, archive, script, config, other)
  - Generates interactive HTML with dark theme matching analyze-resource skill
  - Multi-select file type filters
  - Regex pattern filter for powerful file searches
  - Text search for file names and paths
  - Direct links to files with relative paths
  - Statistics dashboard showing file counts and sizes
  - Scroll to top button
- Comprehensive README.md documentation
- Working directory structure: `.work/prow-job-extract-must-gather/{build_id}/`
- Subdirectory organization: `logs/` for extracted content, `tmp/` for temporary files
- Same URL parsing logic as analyze-resource skill
- Support for caching extracted content (ask user before re-extracting)
- Error handling for corrupted archives, missing files, and invalid URLs
- Progress indicators for all long-running operations
- Platform-aware browser opening (xdg-open, open, start)

### Features
- **Automatic Archive Extraction**: Handles all nested archive formats automatically
- **Directory Renaming**: Shortens long subdirectory names for better usability
- **Interactive File Browser**: Modern HTML interface with powerful filtering
- **Regex Pattern Matching**: Search files using full regex syntax
- **File Type Classification**: Automatic detection and categorization of file types
- **Relative File Links**: Click to open files directly from HTML browser
- **Statistics Dashboard**: Visual overview of extracted content
- **Extraction Caching**: Avoid re-extracting by reusing cached content
- **Error Recovery**: Continue processing despite individual archive failures

### Technical Details
- Python 3 scripts using standard library (tarfile, gzip, os, pathlib)
- No external dependencies required
- Memory-efficient incremental processing
- Follows same patterns as analyze-resource skill
- Integrated with Claude Code permissions system
- Uses `.work/` directory (already in .gitignore)
