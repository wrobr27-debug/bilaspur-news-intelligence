"""Website/HTML Collector.

Uses BeautifulSoup for parsing. Designed for official government
and publisher websites with structured announcement/notice pages.
Respects robots.txt and access restrictions.
Falls back to Playwright browser automation for JS-heavy sites
(like CG government portals), following the News-Agent pattern.
"""

from typing import List, Optional
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import Sources, CollectedItems
from bs4 import BeautifulSoup
import httpx
import logging
import re

logger = logging.getLogger(__name__)


class WebsiteCollector(BaseCollector):
    """HTML Website Collector.

    Uses BeautifulSoup for parsing. Designed for official government
    and publisher websites with structured announcement/notice pages.
    Respects robots.txt and access restrictions.
    """

    def can_collect(self, source) -> bool:
        """Check if source has a website URL and HTML collection method."""
        return bool(
            source.source_url
            and source.collection_method in ["html", "manual"]
        )

    def collect(self) -> CollectionResult:
        """Collect items from website HTML.

        Follows News-Agent pattern: try httpx first, fall back to
        Playwright browser automation for JS-heavy sites (CG gov portals).
        Per-source errors are caught so one failing source doesn't kill
        the whole pipeline.
        """
        if not self.source.source_url:
            return CollectionResult(
                source_id=self.source.source_id,
                error="No source URL configured",
                collection_status="error",
            )

        items = []
        items_found = 0
        items_inserted = 0
        items_duplicate = 0
        error = None
        last_http_status = None

        try:
            # --- Step 1: Try httpx (fast, for static HTML sites) ---
            response_data = self._make_request(self.source.source_url)
            html = None
            if response_data:
                html = response_data[0].text
                last_http_status = response_data[0].status_code

            if html:
                soup = BeautifulSoup(html, "lxml")
                items_batch = self._extract_from_soup(soup, self.source)
                items.extend(items_batch)

            # --- Step 2: Fallback to Playwright for JS-heavy sites ---
            # (News-Agent does this for CMO and other SPA government sites)
            if not items:
                logger.info(
                    f"No items from httpx for {self.source.source_id}, "
                    f"trying Playwright browser fallback..."
                )
                playwright_items = self._scrape_with_playwright(self.source.source_url)
                items.extend(playwright_items)

            # --- Step 3: Process and insert all collected items ---
            for item in items[:20]:  # Limit to 20 items per collection
                try:
                    # Check for duplicate via content_hash
                    if getattr(item, "content_hash", None):
                        existing = (
                            self.db.query(CollectedItems)
                            .filter(CollectedItems.content_hash == item.content_hash)
                            .first()
                        )
                        if existing:
                            items_duplicate += 1
                            continue

                    # Set source and timestamps
                    item.source_id = self.source.id
                    item.collected_at = datetime.now(timezone.utc)

                    self.db.add(item)
                    self.db.commit()
                    items_found += 1
                    items_inserted += 1
                except Exception as e:
                    logger.warning(f"Error inserting item: {e}")

        except Exception as e:
            error = f"Website collection error: {e}"
            logger.error(error, exc_info=True)

        return CollectionResult(
            source_id=self.source.source_id,
            items=items,
            items_found=items_found,
            items_inserted=items_inserted,
            items_duplicate=items_duplicate,
            error=error,
            http_status=last_http_status,
            collection_status="ok" if not error and items_inserted > 0 else ("error" if error else "ok"),
        )

    def _scrape_with_playwright(self, url: str) -> list:
        """Use Playwright browser automation for JS-heavy sites.

        Follows News-Agent's government.py pattern: launch headless
        Chromium, wait for DOM content, extract links via JS evaluation.
        """
        items = []
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                page = browser.new_page()
                try:
                    page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    page.wait_for_timeout(3000)

                    links = page.evaluate("""() => {
                        const results = [];
                        const seen = new Set();
                        const tags = document.querySelectorAll('a, h2, h3, h4');
                        for (const t of tags) {
                            const text = t.innerText?.trim();
                            const href = t.tagName === 'A'
                                ? (t.href || '')
                                : (t.querySelector('a')?.href || '');
                            if (text && text.length > 10 && !seen.has(text)) {
                                seen.add(text);
                                results.push({
                                    text: text.slice(0, 200),
                                    href: href.slice(0, 500)
                                });
                            }
                        }
                        return results;
                    }""")

                    from urllib.parse import urljoin
                    from datetime import datetime, timezone
                    import hashlib

                    for link in links:
                        href = link["href"] or url
                        if not href.startswith("http"):
                            href = urljoin(url, href)

                        # Generate content_hash for dedup (same as httpx path)
                        content_hash = hashlib.sha256(
                            f"{link['text']}:{href}".encode()
                        ).hexdigest()

                        # Create actual CollectedItems instance (not dynamic type)
                        item = CollectedItems(
                            source_id=self.source.id,
                            title=link["text"][:200],
                            original_url=href,
                            canonical_url=href,
                            description="",
                            content_snippet="",
                            author="",
                            published_at=None,
                            language="en",
                            item_type="article",
                            media_type="text",
                            image_url="",
                            video_url="",
                            raw_metadata={},
                            content_hash=content_hash,
                            collected_at=datetime.now(timezone.utc),
                        )
                        items.append(item)
                except Exception as e:
                    logger.warning(f"Playwright scrape failed for {url}: {e}")
                finally:
                    browser.close()
        except ImportError:
            logger.warning("Playwright not installed, skipping browser fallback")
        except Exception as e:
            logger.warning(f"Playwright error for {url}: {e}")

        return items

    def _extract_from_soup(self, soup, source) -> list:
        """Extract items from BeautifulSoup object.

        Default implementation extracts news-like links from any website.
        Override in subclasses for source-specific extraction.
        """
        links = self._find_news_links(soup)

        results = []
        for link in links[:20]:  # Limit to 20 items per collection
            try:
                item = CollectedItems(
                    source_id=source.id,
                    title=link.title,
                    original_url=link.url,
                    canonical_url=link.url,
                    description="",
                    content_snippet="",
                    author="",
                    published_at=None,
                    language="en",
                    item_type="article",
                    media_type="text",
                    image_url="",
                    video_url="",
                    raw_metadata={},
                    content_hash=self._generate_content_hash(link.title, link.url),
                )
                results.append(item)
            except Exception as e:
                logger.warning(f"Error creating item: {e}")

        return results

    def _find_announcement_links(self, soup):
        """Find announcement/notice links from homepage."""
        links = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)

            if not text or len(text) < 10:
                continue

            # Skip javascript and anchors
            if href.startswith("javascript:") or href == "#":
                continue

            full_url = urljoin(self.source.source_url, href)
            parsed = urlparse(full_url)
            if parsed.scheme not in ("http", "https"):
                continue

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Match keywords relevant to news/announcements
            keywords = [
                "notice", "announcement", "tender", "recruit", "admit",
                "result", "exam", "circular", "order", "notification",
                "press release", "whats new", "update"
            ]
            text_lower = text.lower()
            if any(k in text_lower for k in keywords):
                links.append(
                    type("NewsItemData", (), {"title": text[:200], "url": full_url})()
                )

        return links

    def _find_news_links(self, soup):
        """Find general news links from homepage."""
        links = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)

            if not text or len(text) < 15:
                continue

            if href.startswith("javascript:") or href == "#":
                continue

            full_url = urljoin(self.source.source_url, href)
            parsed = urlparse(full_url)
            if parsed.scheme not in ("http", "https"):
                continue

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            links.append(
                type("NewsItemData", (), {"title": text[:200], "url": full_url})()
            )

        return links

    def _generate_content_hash(self, title: str, url: str) -> str:
        """Generate a content hash for deduplication."""
        import hashlib
        raw = f"{title}:{url}"
        return hashlib.sha256(raw.encode()).hexdigest()


class GovtWebsiteCollector(WebsiteCollector):
    """Collector for government website announcement pages."""

    def can_collect(self, source) -> bool:
        """Government sources with notice/announcement pages."""
        return bool(
            source.source_url
            and source.collection_method in ["html", "manual"]
            and source.source_type in ["government", "police", "education", "transport", "health"]
        )

    def _extract_from_soup(self, soup, source) -> list:
        """Extract announcement links from government website."""
        links = self._find_announcement_links(soup)

        results = []
        for link in links[:20]:  # Limit to 20 items per collection
            try:
                item = CollectedItems(
                    source_id=source.id,
                    title=link.title,
                    original_url=link.url,
                    canonical_url=link.url,
                    description="",
                    content_snippet="",
                    author="",
                    published_at=None,
                    language="en",
                    item_type="announcement",
                    media_type="text",
                    image_url="",
                    video_url="",
                    raw_metadata={},
                    content_hash=self._generate_content_hash(link.title, link.url),
                )
                results.append(item)
            except Exception as e:
                logger.warning(f"Error creating item: {e}")

        return results

    def _find_announcement_links(self, soup):
        """Find announcement/notice links with govt-specific keywords."""
        links = []
        seen_urls = set()

        keywords = [
            "notice", "announcement", "tender", "recruit", "admit",
            "result", "exam", "circular", "order", "notification",
            "press release", "whats new", "update", "caution"
        ]

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)

            if not text or len(text) < 10:
                continue

            if href.startswith("javascript:") or href == "#":
                continue

            full_url = urljoin(self.source.source_url, href)
            parsed = urlparse(full_url)
            if parsed.scheme not in ("http", "https"):
                continue

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            text_lower = text.lower()
            # Check for keyword match
            if any(k in text_lower for k in keywords):
                links.append(
                    type("NewsItemData", (), {"title": text[:200], "url": full_url})()
                )
            # Also include links with significant govt-related text (len > 20)
            elif len(text) > 20:
                # Include but mark for review
                links.append(
                    type("NewsItemData", (), {"title": text[:200], "url": full_url})()
                )

        return links

    # Fix: define keywords at module level or as class attribute
    keywords = [
        "notice", "announcement", "tender", "recruit", "admit",
        "result", "exam", "circular", "order", "notification",
        "press release", "whats new", "update", "caution"
    ]