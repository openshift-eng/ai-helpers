#!/usr/bin/env python3
"""
Red Hat Docs TOC Extractor Script for Claude Code Skill

This script downloads a Red Hat documentation page and extracts all distinct
article URLs from the table of contents navigation.

Usage:
    python toc_extractor.py --url "https://docs.redhat.com/en/documentation/..."
"""

import argparse
import json
import sys
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print(
        json.dumps(
            {"error": "requests package not installed. Run: python3 -m pip install requests"}
        )
    )
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(
        json.dumps(
            {
                "error": (
                    "beautifulsoup4 package not installed. "
                    "Run: python3 -m pip install beautifulsoup4"
                )
            }
        )
    )
    sys.exit(1)


class RedHatDocsTOCExtractor:
    """Extract article URLs from Red Hat documentation table of contents."""

    def __init__(self, url):
        """Initialize with target URL."""
        self.url = url
        self.html_content = None
        self.soup = None
        self.base_url = self._get_base_url(url)

    def _get_base_url(self, url):
        """Extract base URL from full URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def download(self):
        """Download HTML content from URL."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            }
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            self.html_content = response.text
            self.soup = BeautifulSoup(self.html_content, "html.parser")
            return True
        except requests.RequestException as e:
            return {"error": f"Failed to download URL: {str(e)}"}

    def extract_toc_urls(self):
        """
        Extract distinct article URLs from the table of contents.

        Returns:
            List of distinct article URLs
        """
        if not self.soup:
            return []

        # Find the TOC navigation element
        toc = self.soup.find("nav", {"id": "toc", "class": "table-of-contents"})

        if not toc:
            # Try alternative TOC selector
            toc = self.soup.find("nav", {"class": "table-of-contents"})

        if not toc:
            return {"error": "Table of contents navigation element not found"}

        # Extract all href attributes from links in the TOC
        urls = set()
        for link in toc.find_all("a", href=True):
            href = link["href"]

            # Skip empty hrefs or javascript links
            if not href or href.startswith("javascript:"):
                continue

            # Skip anchor-only links (section references within same page)
            if href.startswith("#"):
                continue

            # Remove fragments (anchor links) to get the base article URL
            if "#" in href:
                href = href.split("#")[0]

            # Convert relative URLs to absolute
            if not href.startswith("http"):
                href = urljoin(self.base_url, href)

            # Skip index pages (we want actual articles)
            if href.endswith("/index") or href.endswith("/index/"):
                continue

            urls.add(href)

        # Sort URLs for consistent output
        return sorted(list(urls))


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Extract article URLs from Red Hat documentation table of contents"
    )
    parser.add_argument("--url", required=True, help="Red Hat docs URL to extract TOC from")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format", choices=["json", "list"], default="json", help="Output format (default: json)"
    )

    args = parser.parse_args()

    try:
        # Create extractor and download HTML
        extractor = RedHatDocsTOCExtractor(args.url)
        result = extractor.download()

        if isinstance(result, dict) and "error" in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)

        # Extract TOC URLs
        urls = extractor.extract_toc_urls()

        if isinstance(urls, dict) and "error" in urls:
            print(json.dumps(urls, indent=2))
            sys.exit(1)

        # Format output
        if args.format == "json":
            output_data = {"source_url": args.url, "article_count": len(urls), "articles": urls}
            output = json.dumps(output_data, indent=2)
        else:  # list format
            output = "\n".join(urls)

        # Write output
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(
                json.dumps(
                    {
                        "success": True,
                        "message": f"Extracted {len(urls)} article URLs and saved to {args.output}",
                        "source_url": args.url,
                        "article_count": len(urls),
                        "file": args.output,
                    },
                    indent=2,
                )
            )
        else:
            # Print to stdout
            print(output)

    except Exception as e:
        print(json.dumps({"error": f"Unexpected error: {str(e)}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
