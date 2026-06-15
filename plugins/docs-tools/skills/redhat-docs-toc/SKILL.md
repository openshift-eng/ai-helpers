---
name: redhat-docs-toc
description: Extract distinct article URLs from Red Hat documentation table of contents pages. Parse the TOC navigation to find all separate documentation articles. Useful for crawling and processing multi-page Red Hat documentation.
author: Gabriel McGoldrick (gmcgoldr@redhat.com)
allowed-tools: Read, Bash, Write
---

# Red Hat Docs TOC Extractor Skill

This skill extracts distinct article URLs from Red Hat documentation table of contents (TOC) pages. It parses the navigation element to find all separate documentation articles, making it easy to process or download entire documentation sections.

## Capabilities

- **Extract Article URLs**: Find all distinct article pages from a docs index
- **Parse TOC Navigation**: Locate and parse `<nav id="toc">` elements
- **Filter Duplicates**: Remove duplicate URLs and section anchors
- **Sort Results**: Return alphabetically sorted article URLs
- **JSON Output**: Structured output with article count and URLs

## Usage

The skill uses a Python script that downloads and parses Red Hat docs pages.

### Basic Usage

**Extract article URLs from a docs index:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/toc_extractor.py --url "https://docs.redhat.com/en/documentation/product/version/html/guide/index"
```

**Save to file:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/toc_extractor.py --url "https://docs.redhat.com/..." --output articles.json
```

**List format output:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/toc_extractor.py --url "https://docs.redhat.com/..." --format list
```

### Command Line Options

- `--url URL`: The Red Hat docs URL to extract TOC from (required)
- `--output FILE`: Save output to file instead of stdout
- `--format {json,list}`: Output format (default: json)

### Output Formats

**JSON (default):**
```json
{
  "source_url": "https://docs.redhat.com/...",
  "article_count": 3,
  "articles": [
    "https://docs.redhat.com/.../article1",
    "https://docs.redhat.com/.../article2",
    "https://docs.redhat.com/.../article3"
  ]
}
```

**List:**
```
https://docs.redhat.com/.../article1
https://docs.redhat.com/.../article2
https://docs.redhat.com/.../article3
```

## Examples

### OpenShift Lightspeed Configure Documentation
```bash
# Extract all articles from the Configure guide
python3 ${CLAUDE_SKILL_DIR}/scripts/toc_extractor.py \
  --url "https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/configure/index"
```

Output:
```json
{
  "source_url": "https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/configure/index",
  "article_count": 3,
  "articles": [
    "https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/configure/legal-notice",
    "https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/configure/ols-configuring-openshift-lightspeed",
    "https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/configure/olsconfig-api"
  ]
}
```

### Combined with Article Extractor

Extract TOC URLs then download each article:

```bash
# Step 1: Extract article URLs
python3 ${CLAUDE_SKILL_DIR}/scripts/toc_extractor.py \
  --url "https://docs.redhat.com/.../configure/index" \
  --format list > /tmp/articles.txt

# Step 2: Download each article
while read url; do
  filename=$(basename "$url").md
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/article-extractor/scripts/article_extractor.py \
    --url "$url" \
    --format markdown \
    --output "$filename"
done < /tmp/articles.txt
```

## Dependencies

This skill requires the following Python packages:
- `requests`: For downloading HTML content
- `beautifulsoup4`: For parsing HTML

Install dependencies:
```bash
python3 -m pip install requests beautifulsoup4
```

## How It Works

1. **Download Page**: Fetches the HTML from the provided Red Hat docs URL
2. **Locate TOC**: Finds the `<nav id="toc" class="table-of-contents">` element
3. **Extract Links**: Parses all `<a>` tags within the TOC
4. **Filter URLs**:
   - Removes anchor-only links (`#section`)
   - Removes section fragments (`page#section` → `page`)
   - Skips index pages
   - Converts relative to absolute URLs
5. **Deduplicate**: Removes duplicate URLs
6. **Sort**: Returns alphabetically sorted list

## Use Cases

1. **Documentation Crawling**: Get all article URLs for batch processing
2. **Documentation Archival**: Download entire documentation sections
3. **Content Analysis**: Analyze documentation structure and organization
4. **Automated Testing**: Verify all documentation pages are accessible
5. **Documentation Migration**: Extract content for migration to different platforms

## Performance

- Single page extraction: ~1-3 seconds depending on network
- Memory efficient: streams HTML parsing
- No rate limiting by default (respect Red Hat's robots.txt)

## Limitations

- Only works with Red Hat documentation pages that use `<nav id="toc">` structure
- Requires the page to be publicly accessible (no authentication support)
- Returns only distinct article pages (not subsections within articles)
- Depends on Red Hat's documentation HTML structure

## TOC Structure

Red Hat documentation uses a consistent TOC structure:

```html
<nav id="toc" class="table-of-contents" aria-label="Table of contents">
  <ol id="toc-list">
    <li class="item chapter">
      <a class="link" href="/path/to/article">Article Title</a>
    </li>
    <li class="item chapter">
      <details>
        <summary>Chapter Title</summary>
        <ol class="sub-nav">
          <li class="item sub-chapter">
            <a class="link" href="/path/to/subarticle">Subarticle</a>
          </li>
        </ol>
      </details>
    </li>
  </ol>
</nav>
```

The script extracts all `href` attributes from links and filters for distinct article pages.
