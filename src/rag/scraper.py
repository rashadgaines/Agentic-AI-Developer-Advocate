"""
Scrapes docs.revenuecat.com and saves pages as JSON for RAG ingestion.
"""

import json
import time
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DOCS_BASE = "https://www.revenuecat.com/docs"
SITEMAP_URLS = [
    "https://www.revenuecat.com/sitemap.xml",
    "https://www.revenuecat.com/docs/sitemap.xml",
]
OUTPUT_DIR = Path("data/docs")
MAX_PAGES = 250
DELAY = 0.5  # seconds between requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RC-DevAdvocate-Bot/1.0; research)"
}


def get_doc_urls_from_sitemap() -> list[str]:
    """Try to extract doc URLs from sitemap XML."""
    urls = []
    for sitemap_url in SITEMAP_URLS:
        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.content, "xml")
            locs = soup.find_all("loc")
            for loc in locs:
                url = loc.text.strip()
                if "/docs" in url and "revenuecat.com" in url:
                    urls.append(url)
            if urls:
                print(f"  Found {len(urls)} doc URLs from {sitemap_url}")
                break
        except Exception as e:
            print(f"  Sitemap {sitemap_url} failed: {e}")
    return urls


def get_doc_urls_from_nav(base_url: str) -> list[str]:
    """Fallback: crawl the docs index page and collect links."""
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/docs") or "/docs/" in href:
                full = urljoin("https://www.revenuecat.com", href)
                # Strip anchors and query params
                full = full.split("#")[0].split("?")[0]
                if full.startswith("https://www.revenuecat.com/docs"):
                    urls.add(full)
        return list(urls)
    except Exception as e:
        print(f"  Nav crawl failed: {e}")
        return []


def parse_page(url: str, html: str) -> dict | None:
    """Extract title and clean text content from a page."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove nav, footer, scripts, styles
    for tag in soup(["nav", "footer", "script", "style", "header"]):
        tag.decompose()

    # Try to get title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    # Get main content area
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(class_=re.compile(r"content|docs|markdown", re.I))
        or soup.find("body")
    )

    if not main:
        return None

    text = main.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if len(text) < 100:
        return None

    return {"url": url, "title": title, "content": text}


def scrape(max_pages: int = MAX_PAGES) -> int:
    """Main scrape function. Returns number of pages saved."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching doc URLs...")
    urls = get_doc_urls_from_sitemap()
    if not urls:
        print("Falling back to nav crawl...")
        urls = get_doc_urls_from_nav(DOCS_BASE)

    if not urls:
        print("ERROR: Could not find any doc URLs.")
        return 0

    # Deduplicate and cap
    seen = set()
    unique_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    unique_urls = unique_urls[:max_pages]
    print(f"Scraping {len(unique_urls)} pages...")

    saved = 0
    for i, url in enumerate(unique_urls):
        slug = urlparse(url).path.strip("/").replace("/", "_") or "index"
        out_path = OUTPUT_DIR / f"{slug}.json"

        if out_path.exists():
            saved += 1
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue

            page = parse_page(url, resp.text)
            if page:
                out_path.write_text(json.dumps(page, ensure_ascii=False, indent=2))
                saved += 1
                if (i + 1) % 10 == 0:
                    print(f"  {i + 1}/{len(unique_urls)} — {saved} saved")

            time.sleep(DELAY)

        except Exception as e:
            print(f"  Error scraping {url}: {e}")

    print(f"\nDone. Saved {saved} pages to {OUTPUT_DIR}/")
    return saved


if __name__ == "__main__":
    scrape()
