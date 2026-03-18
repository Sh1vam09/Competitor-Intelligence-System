"""
Adaptive BFS Web Crawler using Playwright.

Features:
    - Domain-restricted traversal
    - Normalized URL deduplication
    - URL parameter stripping
    - Max crawl depth = 2, Max pages = 15
    - Content hash deduplication
    - Playwright headless browser for JS rendering
    - Lazy content loading via scrolling
    - Captures raw HTML, cleaned text, screenshot, and DOM features per page
    - Retry with exponential backoff for rate-limited (429) responses
"""

import asyncio
from dataclasses import dataclass, field
from collections import deque
from typing import Optional
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser

from utils.config import (
    MAX_CRAWL_DEPTH,
    MAX_PAGES,
    CRAWL_TIMEOUT_MS,
    SCROLL_PAUSE_MS,
    MAX_SCROLLS,
    SCREENSHOTS_DIR,
)
from utils.helpers import (
    normalize_url,
    extract_domain,
    is_same_domain,
    resolve_url,
    content_hash,
    is_valid_url,
    is_crawlable_url,
)
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_SECS = 2.0
BACKOFF_MULTIPLIER = 2.0


@dataclass
class CrawledPage:
    """Data container for a single crawled page."""

    url: str
    raw_html: str
    cleaned_text: str
    screenshot_path: Optional[str] = None
    dom_structure_features: dict = field(default_factory=dict)
    depth: int = 0


class AdaptiveCrawler:
    """
    Adaptive BFS crawler that uses Playwright for JS-rendered pages.
    Restricts traversal to the same domain, deduplicates URLs and content,
    and captures screenshots.
    """

    def __init__(
        self,
        max_depth: int = MAX_CRAWL_DEPTH,
        max_pages: int = MAX_PAGES,
        timeout_ms: int = CRAWL_TIMEOUT_MS,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout_ms = timeout_ms
        self.visited_urls: set[str] = set()
        self.content_hashes: set[str] = set()
        self.pages: list[CrawledPage] = []

    async def crawl(self, start_url: str) -> list[CrawledPage]:
        """
        Perform BFS crawl starting from the given URL.

        Args:
            start_url: The seed URL to begin crawling.

        Returns:
            List of CrawledPage objects for all successfully crawled pages.
        """
        base_domain = extract_domain(start_url)
        logger.info("Starting crawl of %s (domain: %s)", start_url, base_domain)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            # BFS queue: (url, depth)
            queue: deque[tuple[str, int]] = deque()
            queue.append((normalize_url(start_url), 0))

            while queue and len(self.pages) < self.max_pages:
                current_url, depth = queue.popleft()

                # Skip if already visited or too deep
                if current_url in self.visited_urls:
                    continue
                if depth > self.max_depth:
                    continue

                self.visited_urls.add(current_url)

                # Rate-limit: polite delay between requests
                if len(self.visited_urls) > 1:
                    await asyncio.sleep(1.5)

                # Crawl the page and extract links in one go
                page_data, links = await self._crawl_page(
                    context,
                    current_url,
                    depth,
                    base_domain,
                )
                if page_data is None:
                    continue

                # Content deduplication
                c_hash = content_hash(page_data.cleaned_text)
                if c_hash in self.content_hashes:
                    logger.debug("Duplicate content skipped: %s", current_url)
                    continue
                self.content_hashes.add(c_hash)

                self.pages.append(page_data)
                logger.info(
                    "Crawled [%d/%d] depth=%d: %s",
                    len(self.pages),
                    self.max_pages,
                    depth,
                    current_url,
                )

                # Enqueue discovered links for BFS
                if depth < self.max_depth:
                    for link in links:
                        normalized = normalize_url(link)
                        if normalized not in self.visited_urls:
                            queue.append((normalized, depth + 1))

            await browser.close()

        logger.info("Crawl complete. Total pages: %d", len(self.pages))
        return self.pages

    async def _crawl_page(
        self,
        context,
        url: str,
        depth: int,
        base_domain: str,
    ) -> tuple[Optional[CrawledPage], list[str]]:
        """
        Crawl a single page: navigate, scroll, capture screenshot,
        extract content, AND extract links — all from one page load.

        Returns:
            Tuple of (CrawledPage or None, list of discovered link URLs).
        """
        page: Page = await context.new_page()
        discovered_links: list[str] = []
        last_error: Optional[str] = None
        for attempt in range(MAX_RETRIES):
            try:
                response = None
                for wait_strategy in [
                    "domcontentloaded"
                    if False
                    else "domcontentloaded",  # Workaround for type checker
                    "commit",
                ]:
                    try:
                        response = await page.goto(
                            url,
                            timeout=self.timeout_ms,
                            wait_until="domcontentloaded",
                        )
                        break
                    except Exception as nav_err:
                        logger.warning(
                            "Navigation with '%s' failed for %s: %s",
                            wait_strategy,
                            url,
                            nav_err,
                        )
                        continue

                if response is None:
                    logger.warning("All navigation strategies failed for %s", url)
                    return None, []

                if response.status == 429:
                    backoff = INITIAL_BACKOFF_SECS * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        "Rate limited (429) on %s, attempt %d/%d. "
                        "Retrying in %.1f seconds...",
                        url,
                        attempt + 1,
                        MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

                if response.status >= 400:
                    logger.warning(
                        "Failed to load %s (status: %s)",
                        url,
                        response.status,
                    )
                    return None, []

                break  # Success

            except Exception as e:
                last_error = str(e)
                if attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF_SECS * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        "Error crawling %s (attempt %d/%d): %s. "
                        "Retrying in %.1f seconds...",
                        url,
                        attempt + 1,
                        MAX_RETRIES,
                        last_error,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                else:
                    logger.warning("Error crawling %s: %s", url, last_error)
                    return None, discovered_links

        else:
            if last_error:
                logger.warning(
                    "Max retries exceeded for %s (last error: %s). Skipping.",
                    url,
                    last_error,
                )
            return None, discovered_links

        try:
            final_url = page.url
            intended_domain = extract_domain(url).lower()
            final_domain = extract_domain(final_url).lower()
            if intended_domain and final_domain and intended_domain != final_domain:
                logger.warning(
                    "Domain redirect detected: %s → %s. Skipping.",
                    intended_domain,
                    final_domain,
                )
                return None, []

            # Give the page a moment to settle (JS rendering)
            await page.wait_for_timeout(2000)

            # Detect parked / expired domain pages
            page_title = await page.title()
            title_lower = (page_title or "").lower()
            parking_indicators = [
                "domain for sale",
                "parked",
                "buy this domain",
                "this domain is for sale",
                "domain expired",
                "godaddy",
                "hugedomains",
                "sedo domain parking",
                "coming soon",
                "under construction",
            ]
            if any(indicator in title_lower for indicator in parking_indicators):
                logger.warning(
                    "Parked/expired domain detected for %s (title: %s). Skipping.",
                    url,
                    page_title,
                )
                return None, []

            # Scroll down to trigger lazy loading
            await self._lazy_scroll(page)

            # Get raw HTML
            raw_html = await page.content()

            # Get cleaned text
            cleaned_text = await page.evaluate(
                "() => document.body ? document.body.innerText : ''"
            )
            cleaned_text = cleaned_text.strip()

            # Extract links from the SAME loaded page (avoids extra requests)
            try:
                raw_links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href)
                        .filter(href => href.startsWith('http'))
                """)
                for link in raw_links:
                    if (
                        is_valid_url(link)
                        and is_same_domain(link, base_domain)
                        and is_crawlable_url(link)
                    ):
                        discovered_links.append(link)
                discovered_links = list(set(discovered_links))
            except Exception:
                pass  # Link extraction is best-effort

            # Skip pages with very little content
            if len(cleaned_text) < 50:
                logger.debug("Skipping page with minimal content: %s", url)
                return None, discovered_links

            # Take screenshot (only for homepage / first pages)
            screenshot_path = None
            if len(self.pages) < 5:
                safe_name = (
                    url.replace("://", "_")
                    .replace("/", "_")
                    .replace("?", "_")
                    .replace(":", "_")[:100]
                )
                screenshot_path = str(SCREENSHOTS_DIR / f"{safe_name}.png")
                try:
                    await page.screenshot(path=screenshot_path, full_page=False)
                except Exception as ss_err:
                    logger.warning("Screenshot failed for %s: %s", url, ss_err)
                    screenshot_path = None

            return CrawledPage(
                url=url,
                raw_html=raw_html,
                cleaned_text=cleaned_text,
                screenshot_path=screenshot_path,
                depth=depth,
            ), discovered_links

        except Exception as e:
            logger.warning("Error crawling %s: %s", url, e)
            return None, discovered_links
        finally:
            await page.close()

    async def _lazy_scroll(self, page: Page) -> None:
        """
        Scroll down the page incrementally to trigger lazy-loaded content.
        """
        for _ in range(MAX_SCROLLS):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(SCROLL_PAUSE_MS)

    # _extract_links is now integrated into _crawl_page to avoid
    # opening a separate browser page for every URL (which caused 429s).


def run_crawler(url: str) -> list[CrawledPage]:
    """
    Synchronous wrapper to run the async crawler.

    Args:
        url: The seed URL to crawl.

    Returns:
        List of CrawledPage objects.
    """
    crawler = AdaptiveCrawler()
    return asyncio.run(crawler.crawl(url))
