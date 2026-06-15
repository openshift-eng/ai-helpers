#!/usr/bin/env python3
"""
Article Extractor Script for Claude Code Skill

This script downloads HTML from a URL and extracts article content,
removing HTML bloat and supporting multiple output formats.

Usage:
    python article_extractor.py --url "https://example.com/page"
    python article_extractor.py --url "https://example.com/page" --format markdown
    python article_extractor.py --url "https://example.com/page" --output article.md
"""

import argparse
import json
import re
import sys

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


class ArticleExtractor:
    """Extract article content from HTML pages."""

    def __init__(self, url):
        """Initialize with target URL."""
        self.url = url
        self.html_content = None
        self.soup = None

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

    def extract_article(self, selector='article[aria-live="polite"]'):
        """
        Extract article content using CSS selector.

        Args:
            selector: CSS selector to find the article element

        Returns:
            BeautifulSoup element containing the article, or None if not found
        """
        if not self.soup:
            return None

        # Try the provided selector first
        article = self.soup.select_one(selector)

        # If not found, try fallback selectors
        if not article:
            fallback_selectors = [
                "article[aria-live]",
                "article.main-content",
                "article.content",
                "article",
                "main article",
                '[role="article"]',
                ".article-content",
                "#article-content",
            ]

            for fallback in fallback_selectors:
                article = self.soup.select_one(fallback)
                if article:
                    break

        return article

    def clean_html(self, element):
        """
        Clean HTML element by removing scripts, styles, and unnecessary attributes.

        Args:
            element: BeautifulSoup element to clean

        Returns:
            Cleaned BeautifulSoup element
        """
        if not element:
            return None

        # Remove script and style tags
        for tag in element.find_all(["script", "style", "noscript"]):
            tag.decompose()

        # Remove comments
        from bs4 import Comment

        for comment in element.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove "Copy link" tooltips and buttons (common in Red Hat docs)
        for tag in element.find_all(["rh-tooltip", "rh-button"]):
            tag.decompose()

        # Remove elements that contain "Copy link" text
        for tag in element.find_all(
            class_=[
                "copy-link-btn",
                "copy-link-text",
                "copy-link-text-confirmation",
                "tooltip-content",
                "section-link",
            ]
        ):
            tag.decompose()

        # Remove data attributes and other noise
        for tag in element.find_all(True):
            # Keep only essential attributes
            attrs_to_keep = ["href", "src", "alt", "title", "id", "class"]
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in attrs_to_keep}

        return element

    def to_html(self, article, pretty=False):
        """
        Convert article to HTML string.

        Args:
            article: BeautifulSoup element
            pretty: Whether to pretty-print the HTML

        Returns:
            HTML string
        """
        if not article:
            return ""

        if pretty:
            return article.prettify()
        return str(article)

    def to_markdown(self, article):
        """
        Convert article to Markdown.

        Args:
            article: BeautifulSoup element

        Returns:
            Markdown string
        """
        if not article:
            return ""

        try:
            import html2text

            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_emphasis = False
            h.body_width = 0  # Don't wrap lines
            return h.handle(str(article))
        except ImportError:
            # Fallback: simple HTML to markdown conversion
            return self._simple_html_to_markdown(article)

    def _simple_html_to_markdown(self, article):
        """
        Simple HTML to Markdown conversion without html2text library.

        Args:
            article: BeautifulSoup element

        Returns:
            Markdown-like string
        """
        # This is a simplified converter for when html2text is not available
        text = article.get_text(separator="\n", strip=True)

        # Clean up multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text

    def to_text(self, article):
        """
        Convert article to plain text.

        Args:
            article: BeautifulSoup element

        Returns:
            Plain text string
        """
        if not article:
            return ""

        # Get text content
        text = article.get_text(separator="\n", strip=True)

        # Clean up multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Clean up multiple spaces
        text = re.sub(r" {2,}", " ", text)

        return text

    def strip_links(self, article):
        """
        Remove all hyperlinks from article.

        Args:
            article: BeautifulSoup element

        Returns:
            BeautifulSoup element with links removed
        """
        for a_tag in article.find_all("a"):
            a_tag.unwrap()
        return article


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Extract article content from HTML pages")
    parser.add_argument("--url", required=True, help="URL to fetch HTML from")
    parser.add_argument(
        "--format",
        choices=["html", "markdown", "text"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument(
        "--selector",
        default='article[aria-live="polite"]',
        help='CSS selector for article element (default: article[aria-live="polite"])',
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print HTML output (only for HTML format)"
    )
    parser.add_argument(
        "--strip-links", action="store_true", help="Remove all hyperlinks from output"
    )

    args = parser.parse_args()

    try:
        # Create extractor and download HTML
        extractor = ArticleExtractor(args.url)
        result = extractor.download()

        if isinstance(result, dict) and "error" in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)

        # Calculate original HTML size
        original_html_size = len(extractor.html_content)

        # Extract article
        article = extractor.extract_article(args.selector)

        if not article:
            error_msg = {
                "error": f"No article found with selector: {args.selector}",
                "url": args.url,
                "suggestion": (
                    "Try using a different selector or check if the page has an <article> tag"
                ),
            }
            print(json.dumps(error_msg, indent=2))
            sys.exit(1)

        # Clean the article
        article = extractor.clean_html(article)

        # Calculate article HTML size (before format conversion)
        article_html_size = len(str(article))

        # Calculate markdown size for stats (always, regardless of output format)
        article_markdown_size = len(extractor.to_markdown(article).encode("utf-8"))

        # Strip links if requested
        if args.strip_links:
            article = extractor.strip_links(article)

        # Convert to requested format
        if args.format == "html":
            output = extractor.to_html(article, pretty=args.pretty)
        elif args.format == "markdown":
            output = extractor.to_markdown(article)
        else:  # text
            output = extractor.to_text(article)

        # Write output
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)

            print(
                json.dumps(
                    {
                        "success": True,
                        "message": f"Article extracted and saved to {args.output}",
                        "url": args.url,
                        "format": args.format,
                        "file": args.output,
                        "file_sizes": {
                            "original_html_bytes": original_html_size,
                            "article_html_bytes": article_html_size,
                            "article_markdown_bytes": article_markdown_size,
                        },
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
