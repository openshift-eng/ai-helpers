#!/usr/bin/env python3
"""Extract content from web pages with recursive crawling support."""

import subprocess
import sys

# Auto-install missing dependencies
def ensure_deps():
    required = [("trafilatura", "trafilatura"), ("bs4", "beautifulsoup4"), ("requests", "requests")]
    missing = []
    for imp, pip in required:
        try:
            __import__(imp)
        except ImportError:
            missing.append(pip)
    if missing:
        print(f"📦 Installing: {', '.join(missing)}", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet"] + missing)
        print("✅ Dependencies installed!", file=sys.stderr)

ensure_deps()

import argparse
import hashlib
import json
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    # Remove fragment
    url, _ = urldefrag(url)
    # Remove trailing slash
    url = url.rstrip('/')
    # Lowercase the scheme and host
    parsed = urlparse(url)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
    )
    return normalized.geturl()


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs are on the same domain."""
    domain1 = urlparse(url1).netloc.lower()
    domain2 = urlparse(url2).netloc.lower()
    
    # Handle www prefix
    domain1 = domain1.removeprefix('www.')
    domain2 = domain2.removeprefix('www.')
    
    return domain1 == domain2


def get_url_prefix(url: str) -> str:
    """Get the base URL prefix for prefix-based crawling.
    
    Examples:
        https://spiffe.io/docs/ -> https://spiffe.io/docs/
        https://kubernetes.io/docs/concepts/ -> https://kubernetes.io/docs/concepts/
        https://example.com/ -> https://example.com/
    """
    parsed = urlparse(url)
    # Normalize: ensure path ends with / for prefix matching
    path = parsed.path.rstrip('/') + '/'
    # If path is just /, use domain-only matching
    if path == '/':
        return f"{parsed.scheme}://{parsed.netloc}/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def is_under_prefix(url: str, prefix: str) -> bool:
    """Check if URL is under the given prefix.
    
    Examples:
        is_under_prefix("https://spiffe.io/docs/concepts/", "https://spiffe.io/docs/") -> True
        is_under_prefix("https://spiffe.io/blog/", "https://spiffe.io/docs/") -> False
    """
    # Normalize both URLs
    url_normalized = url.lower().rstrip('/')
    prefix_normalized = prefix.lower().rstrip('/')
    
    # Check if URL starts with prefix
    return url_normalized.startswith(prefix_normalized)


def is_valid_page_url(url: str) -> bool:
    """Check if URL is likely a valid page (not a file download, etc.)."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # Skip common non-page extensions
    skip_extensions = {
        '.pdf', '.zip', '.tar', '.gz', '.exe', '.dmg', '.pkg',
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.webp',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv',
        '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.css', '.js', '.json', '.xml', '.rss', '.atom',
    }
    
    for ext in skip_extensions:
        if path.endswith(ext):
            return False
    
    # Skip common non-content paths
    skip_patterns = [
        '/login', '/logout', '/signin', '/signout', '/signup',
        '/auth/', '/oauth/', '/api/', '/admin/',
        '/search', '/cart', '/checkout',
        '#', 'javascript:', 'mailto:', 'tel:',
    ]
    
    url_lower = url.lower()
    for pattern in skip_patterns:
        if pattern in url_lower:
            return False
    
    return True


def extract_links(html: str, base_url: str) -> list:
    """Extract all links from HTML content."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback to regex if BeautifulSoup not available
        link_pattern = r'href=["\']([^"\']+)["\']'
        matches = re.findall(link_pattern, html)
        links = []
        for match in matches:
            absolute_url = urljoin(base_url, match)
            if absolute_url.startswith('http'):
                links.append(absolute_url)
        return links
    
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        # Convert relative URLs to absolute
        absolute_url = urljoin(base_url, href)
        
        # Only include http/https URLs
        if absolute_url.startswith('http'):
            links.append(absolute_url)
    
    return links


def extract_single_page(url: str, config) -> dict:
    """Extract content from a single web page.
    
    Returns:
        dict with content, title, and found links
    """
    try:
        import trafilatura
        from trafilatura.settings import use_config
    except ImportError:
        return {
            "success": False,
            "error": "trafilatura not installed. Run: pip install trafilatura",
        }
    
    try:
        import requests
    except ImportError:
        return {
            "success": False,
            "error": "requests not installed. Run: pip install requests",
        }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; +https://github.com/openshift-eng/ai-helpers)"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        html = response.text
        
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch URL: {str(e)}",
        }
    
    # Extract content
    result = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_links=False,
        output_format="markdown",
        config=config,
    )
    
    if not result:
        result = trafilatura.extract(
            html,
            include_comments=False,
            no_fallback=False,
            config=config,
        )
    
    # Extract metadata
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata and metadata.title else urlparse(url).path.split('/')[-1] or urlparse(url).netloc
    
    # Extract links for recursive crawling
    links = extract_links(html, url)
    
    return {
        "success": True,
        "content": result or "",
        "title": title,
        "links": links,
    }


def extract_web(
    url: str,
    output_dir: str,
    recursive: bool = True,
    max_depth: int = 3,
    max_pages: int = 50,
    same_domain_only: bool = True,
    prefix_only: bool = True,
) -> dict:
    """Extract content from web pages with optional recursive crawling.
    
    Args:
        url: Starting URL
        output_dir: Directory to save extracted content
        recursive: Whether to crawl linked pages
        max_depth: Maximum depth for recursive crawling
        max_pages: Maximum number of pages to crawl
        same_domain_only: Only follow links on the same domain
        prefix_only: Only follow links under the same URL prefix (default: True)
                     e.g., https://spiffe.io/docs/ only crawls /docs/* pages
        
    Returns:
        dict with extraction result
    """
    try:
        from trafilatura.settings import use_config
        config = use_config()
        config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
    except ImportError:
        return {
            "success": False,
            "error": "trafilatura not installed. Run: pip install trafilatura beautifulsoup4",
            "url": url,
        }
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Track visited URLs and pages to visit
    visited = set()
    # Queue: (url, depth)
    queue = deque([(normalize_url(url), 0)])
    
    extracted_pages = []
    failed_pages = []
    
    start_domain = urlparse(url).netloc.lower().removeprefix('www.')
    start_prefix = get_url_prefix(url)
    
    print(f"Starting crawl from: {url}", file=sys.stderr)
    print(f"Mode: {'recursive (depth={}, max={})'.format(max_depth, max_pages) if recursive else 'single page'}", file=sys.stderr)
    if prefix_only and recursive:
        print(f"Prefix filter: {start_prefix}*", file=sys.stderr)
    
    while queue and len(extracted_pages) < max_pages:
        current_url, depth = queue.popleft()
        
        # Skip if already visited
        normalized = normalize_url(current_url)
        if normalized in visited:
            continue
        
        visited.add(normalized)
        
        # Skip if not valid page URL
        if not is_valid_page_url(current_url):
            continue
        
        # Check domain restriction
        if same_domain_only and not is_same_domain(current_url, url):
            continue
        
        print(f"  [{len(extracted_pages)+1}/{max_pages}] Fetching (depth={depth}): {current_url[:80]}...", file=sys.stderr)
        
        # Extract page content
        result = extract_single_page(current_url, config)
        
        if not result["success"]:
            failed_pages.append({"url": current_url, "error": result.get("error", "Unknown error")})
            continue
        
        if not result["content"] or len(result["content"].strip()) < 100:
            # Skip pages with minimal content
            continue
        
        # Generate file ID
        url_hash = hashlib.md5(current_url.encode()).hexdigest()[:8]
        domain = urlparse(current_url).netloc.replace(".", "-")
        file_id = f"{domain}-{url_hash}"
        
        # Save content
        output_file = output_path / f"{file_id}.md"
        
        content = f"""---
source_type: web
source_url: {current_url}
source_title: {result['title']}
crawl_depth: {depth}
extracted_at: {datetime.now(timezone.utc).isoformat()}
---

# {result['title']}

{result['content']}
"""
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        extracted_pages.append({
            "url": current_url,
            "title": result["title"],
            "file_id": file_id,
            "output_file": str(output_file),
            "depth": depth,
            "word_count": len(result["content"].split()),
        })
        
        # Add linked pages to queue if recursive
        if recursive and depth < max_depth:
            for link in result.get("links", []):
                link_normalized = normalize_url(link)
                
                if link_normalized not in visited:
                    # Check prefix restriction (default: only crawl under same path prefix)
                    if prefix_only:
                        if not is_under_prefix(link, start_prefix):
                            continue
                    # Check domain restriction (fallback if prefix_only is False)
                    elif same_domain_only:
                        link_domain = urlparse(link).netloc.lower().removeprefix('www.')
                        if link_domain != start_domain:
                            continue
                    
                    if is_valid_page_url(link):
                        queue.append((link, depth + 1))
        
        # Be nice to servers
        time.sleep(0.5)
    
    total_words = sum(p.get("word_count", 0) for p in extracted_pages)
    
    print(f"\nCrawl complete: {len(extracted_pages)} pages extracted, {len(failed_pages)} failed", file=sys.stderr)
    
    return {
        "success": len(extracted_pages) > 0,
        "start_url": url,
        "mode": "recursive" if recursive else "single",
        "max_depth": max_depth if recursive else 0,
        "pages_extracted": len(extracted_pages),
        "pages_failed": len(failed_pages),
        "total_words": total_words,
        "pages": extracted_pages,
        "failed": failed_pages if failed_pages else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract content from web pages")
    parser.add_argument("--url", required=True, help="URL to extract")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--single", action="store_true", 
                        help="Only extract the single provided URL (default: recursive)")
    parser.add_argument("--depth", type=int, default=3, 
                        help="Maximum crawl depth (default: 3)")
    parser.add_argument("--max-pages", type=int, default=50, 
                        help="Maximum pages to crawl (default: 50)")
    parser.add_argument("--allow-external", action="store_true",
                        help="Allow following links to external domains")
    parser.add_argument("--full-domain", action="store_true",
                        help="Crawl entire domain instead of just the URL prefix path")
    
    args = parser.parse_args()
    
    result = extract_web(
        args.url,
        args.output,
        recursive=not args.single,
        max_depth=args.depth,
        max_pages=args.max_pages,
        same_domain_only=not args.allow_external,
        prefix_only=not args.full_domain,  # Default: only crawl under same prefix
    )
    
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
