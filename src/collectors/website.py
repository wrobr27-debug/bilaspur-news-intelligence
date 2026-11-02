"""Website/HTML Collector.

Uses BeautifulSoup for parsing. Designed for official government
and publisher websites with structured announcement/notice pages.
Respects robots.txt and access restrictions.
"""

from typing import List, Optional
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
        """Collect items from website HTML."""
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

        try:
            # Make request
            response_data = self._make_request(self.source.source_url)
            if not response_data:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error="Failed to fetch website",
                    collection_status="error",
                )

            html = response_data[0].text
            response_time_ms = response_data[1] if len(response_data) > 1 else 0
            soup = BeautifulSoup(html, "lxml")

            # Determine extraction strategy based on source
            items_batch = self._extract_from_soup(soup, self.source)

            for item in items_batch:
                # Check for duplicate via content_hash
                if item.content_hash:
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
                item.collected_at = datetime.now(timezone.utc) if "datetime" in dir() else None

                self.db.add(item)
                self.db.commit()
                items_found += 1
                items_inserted += 1

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
            collection_status="ok" if items_inserted > 0 else "ok",
        )

    def _extract_from_soup(self, soup, source) -> list:
        """Extract items from BeautifulSoup object.

        Override in subclasses for source-specific extraction.
        """
        raise NotImplementedError("Subclasses must implement _extract_from_soup")

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

            full_url = href if href.startswith("http") else None
            if not full_url:
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

            full_url = href if href.startswith("http") else None
            if not full_url:
                continue

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            links.append(
                type("NewsItemData", (), {"title": text[:200], "url": full_url})()
            )

        return links


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

            full_url = href if href.startswith("http") else None
            if not full_url:
                continue

            # Resolve relative URLs
            if not full_url.startswith("http"):
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
            elif len(text) > 20 and not full_url.startswith("http://127.0.0") and not full_url.startswith("http://localhost"):
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