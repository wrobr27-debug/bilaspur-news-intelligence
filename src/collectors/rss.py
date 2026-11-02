"""RSS/Atom Feed Collector.

Uses feedparser library to parse RSS and Atom feeds.
Normalizes all entries into CollectedItems with standardized fields.
"""

from typing import List, Optional
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import Sources, CollectedItems
import feedparser
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """RSS/Atom Feed Collector.

    Supports RSS 2.0 and RSS 1.0 (RDF) feeds using feedparser.
    Normalizes all entries into CollectedItems with standardized fields.
    """

    def can_collect(self, source) -> bool:
        """Check if source has an RSS/Atom URL."""
        return bool(source.rss_url and source.collection_method in ["rss", "atom", "html"])

    def collect(self) -> CollectionResult:
        """Collect items from RSS/Atom feed."""
        if not self.source.rss_url:
            return CollectionResult(
                source_id=self.source.source_id,
                error=f"No RSS URL configured for source {self.source.source_name}",
                collection_status="error",
            )

        items = []
        items_found = 0
        items_inserted = 0
        items_duplicate = 0
        error = None

        # Parse the feed
        feed = feedparser.parse(self.source.rss_url)

        if not feed.entries:
            logger.warning(f"No entries found in RSS feed: {self.source.rss_url}")
            return CollectionResult(
                source_id=self.source.source_id,
                items_found=0,
                collection_status="ok",
                error="No entries found in feed",
            )

        for entry in feed.entries:
            try:
                # Generate content hash for deduplication
                title = self._safe_text(getattr(entry, "title", ""))
                link = getattr(entry, "link", "")
                content_hash = self._generate_content_hash(title, link) if link else None

                # Extract published date
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published_at = datetime(
                            *entry.published_parsed[:6],
                            tzinfo=timezone.utc,
                        )
                    except (ValueError, TypeError):
                        published_at = datetime.now(timezone.utc)

                # Extract summary/description
                summary = self._safe_text(
                    getattr(entry, "summary", getattr(entry, "description", ""))
                )

                # Extract author
                author = self._safe_text(getattr(entry, "author", ""))

                # Extract categories
                categories = []
                if hasattr(entry, "tags"):
                    categories = [tag.get("term", "") for tag in entry.tags if tag.get("term")]

                # Extract image if available
                image_url = ""
                # Check enclosures
                if hasattr(entry, "enclosures"):
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image/"):
                            image_url = enc.get("href", "")
                            break
                # Check media:content
                if not image_url and "media_content" in entry:
                    media = entry.media_content
                    if isinstance(media, list) and len(media) > 0:
                        img = media[0]
                        image_url = img.get("url", "")
                    elif isinstance(media, dict):
                        image_url = media.get("url", "")

                # Create CollectedItems
                item = CollectedItems(
                    source_id=self.source.id,
                    external_id=getattr(entry, "id", link or ""),
                    title=title,
                    original_url=link or "",
                    canonical_url=link or "",
                    description=summary[:300] if summary else "",
                    content_snippet=summary[:200] if summary else "",
                    author=author,
                    published_at=published_at,
                    language=self._normalize_language(
                        getattr(entry, "language", "en")
                    ),
                    item_type="article",
                    media_type="image" if image_url else "text",
                    image_url=image_url,
                    video_url="",
                    raw_metadata=self._extract_raw_metadata(entry),
                    content_hash=content_hash,
                    collection_status="collected",
                )

                # Check for duplicate via content_hash
                if content_hash:
                    existing = (
                        self.db.query(CollectedItems)
                        .filter(CollectedItems.content_hash == content_hash)
                        .first()
                    )
                    if existing:
                        items_duplicate += 1
                        continue

                items.append(item)
                items_found += 1

            except Exception as e:
                logger.warning(f"Error processing RSS entry: {e}", exc_info=True)
                items_duplicate += 1  # Count as duplicate to avoid breaking

        # Mark items as inserted in database
        now = datetime.now(timezone.utc)
        for item in items:
            item.collected_at = now
            try:
                self.db.add(item)
                self.db.commit()
                items_inserted += 1
            except Exception as e:
                self.db.rollback()
                logger.error(f"DB error inserting item: {e}")
                items_duplicate += 1

        return CollectionResult(
            source_id=self.source.source_id,
            items=items,
            items_found=items_found,
            items_inserted=items_inserted,
            items_duplicate=items_duplicate,
            error=error,
            collection_status="ok" if items_inserted > 0 else "ok",
        )

    def _extract_raw_metadata(self, entry) -> dict:
        """Extract raw metadata from feed entry as dict."""
        metadata = {}
        for key in dir(entry):
            if not key.startswith("_") and key not in [
                "updated_parsed",
                "published_parsed",
                "enclosures",
                "media_content",
                "tags",
            ]:
                try:
                    val = getattr(entry, key)
                    if not callable(val):
                        metadata[key] = val
                except Exception:
                    pass
        return metadata

    @staticmethod
    def _generate_content_hash(title: str, url: str) -> str:
        """Generate a content hash for deduplication."""
        import hashlib
        raw = f"{title}:{url}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _normalize_language(text: str, detected_lang: str = "en") -> str:
        """Normalize language detection."""
        if not text:
            return detected_lang
        return detected_lang

    @staticmethod
    def _safe_text(text: str, maxlen: int = 500) -> str:
        """Safely truncate text."""
        if not text:
            return ""
        return text[:maxlen].strip()