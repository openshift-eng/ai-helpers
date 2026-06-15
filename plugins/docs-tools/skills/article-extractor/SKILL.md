---
name: article-extractor
description: Download HTML from websites and extract article content, removing HTML bloat. Specifically designed to extract content from <article> tags with aria-live="polite" attribute. Outputs clean, readable content for documentation sites like Red Hat docs.
author: Gabriel McGoldrick (gmcgoldr@redhat.com)
allowed-tools: Read, Bash, Write
---

# Article Extractor Skill

This skill downloads HTML from websites and extracts the article content, removing unnecessary HTML bloat. It's particularly useful for documentation websites that have large amounts of navigation, styling, and other non-content HTML.

## Capabilities

- **Download HTML**: Fetch HTML content from any publicly accessible URL
- **Extract Article Content**: Locate and extract content from `<article>` tags
- **Clean Output**: Remove unnecessary HTML bloat and format for readability
- **Multiple Output Formats**: Support for HTML, Markdown, and plain text output
- **Flexible Matching**: Find article tags by various attributes (aria-live, class, id)

## Usage

The skill uses a Python script that downloads and parses HTML content.

### Basic Usage

**Extract article from a URL:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/article_extractor.py --url "https://example.com/page"
```

**Extract with specific output format:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/article_extractor.py --url "https://example.com/page" --format markdown
```

**Save to file:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/article_extractor.py --url "https://example.com/page" --output article.md
```

**Extract with custom article selector:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/article_extractor.py --url "https://example.com/page" --selector "article.main-content"
```

### Command Line Options

- `--url URL`: The URL to fetch HTML from (required)
- `--format {html,markdown,text}`: Output format (default: markdown)
- `--output FILE`: Save output to file instead of stdout
- `--selector SELECTOR`: CSS selector for article content (default: article[aria-live="polite"])
- `--pretty`: Pretty-print HTML output with indentation
- `--strip-links`: Remove all hyperlinks from output

### Output Formats

**HTML (default):**
Extracts the article HTML content with all tags preserved but removes surrounding bloat.

**Markdown:**
Converts the article content to Markdown format for easy reading and documentation.

**Plain Text:**
Strips all HTML tags and returns plain text content.

## Examples

### Red Hat Documentation
```bash
# Extract from Red Hat OpenShift Lightspeed documentation
python3 ${CLAUDE_SKILL_DIR}/scripts/article_extractor.py \
  --url "https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/install/ols-installing-lightspeed" \
  --format markdown \
  --output openshift-lightspeed-install.md
```

### Generic Documentation Site
```bash
# Extract from any site with article tags
python3 ${CLAUDE_SKILL_DIR}/scripts/article_extractor.py \
  --url "https://example.com/docs/guide" \
  --selector "article.documentation" \
  --format text
```

## Dependencies

This skill requires the following Python packages:
- `requests`: For downloading HTML content
- `beautifulsoup4`: For parsing and extracting HTML
- `html2text`: For converting HTML to Markdown (optional, for markdown format)

Install dependencies:
```bash
python3 -m pip install requests beautifulsoup4 html2text
```

## Use Cases

1. **Documentation Archival**: Extract and save documentation pages for offline reading
2. **Content Migration**: Extract article content for migration to different platforms
3. **Clean Reading**: Get rid of navigation, ads, and other distractions
4. **Content Analysis**: Extract main content for text analysis or processing
5. **Markdown Conversion**: Convert HTML documentation to Markdown format

## Performance

The skill downloads and processes HTML efficiently:
- Single page extraction: ~1-3 seconds depending on page size and network
- No rate limiting by default (respect target site's robots.txt)
- Memory efficient streaming for large pages

## Limitations

- Only works with publicly accessible URLs (no authentication support)
- Requires the target page to use `<article>` tags or similar semantic HTML
- JavaScript-rendered content may not be extracted (uses static HTML only)
- Some complex HTML structures may not convert perfectly to Markdown
