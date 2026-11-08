"""Facebook Page Collector.

Uses the official Meta Graph API to collect posts from authorized Facebook Pages.
Does NOT scrape login-protected content.

Collects accessible post IDs, text, timestamps, URLs and permitted media metadata.
Requires a valid Meta Graph API access token with pages_read_engagement permission.
"""

from typing import List, Optional
from datetime import datetime, timezone
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import Sources, CollectedItems
from src.config import settings
import logging
import hashlib
import httpx
import re

logger = logging.getLogger(__name__)


class FacebookCollector(BaseCollector):
    """Facebook Page collector using Meta Graph API.

    Collects accessible post IDs, text, timestamps, URLs and permitted media
    metadata from Facebook Pages that the access token has permission to read.

    Does NOT scrape login-protected content.
    """

    def can_collect(self, source) -> bool:
        """Check if source is a Facebook Page with Graph API configured."""
        url = (source.source_url or "") + " " + (source.api_url or "")
        return bool(
            ("facebook.com" in url or "fb.com" in url)
            and source.collection_method in ["api", "html", "manual"]
            and bool(getattr(settings, 'facebook_graph_api_token', None))
        )

    def collect(self) -> CollectionResult:
        """Collect Facebook Page posts via Meta Graph API."""
        graph_token = getattr(settings, 'facebook_graph_api_token', None)
        if not graph_token:
            return CollectionResult(
                source_id=self.source.source_id,
                error="Facebook Graph API token not configured",
                collection_status="error",
            )

        url = self.source.source_url or self.source.api_url or ""
        if not url:
            return CollectionResult(
                source_id=self.source.source_id,
                error="No Facebook Page URL configured",
                collection_status="error",
            )

        # Extract page ID or username from URL
        page_identifier = self._extract_page_identifier(url)
        if not page_identifier:
            return CollectionResult(
                source_id=self.source.source_id,
                error="Could not extract Facebook Page identifier from URL",
                collection_status="error",
            )

        items = []
        items_found = 0
        items_inserted = 0
        items_duplicate = 0
        error = None

        try:
            # Get page posts via Graph API
            graph_url = (
                f"https://graph.facebook.com/v18.0/{page_identifier}/posts"
                f"?fields=id,message,created_time,permalink,full_picture,"
                f"type,status_message,description"
                f"&access_token={graph_token}"
                f"&limit=25"
            )

            timeout_config = httpx.Timeout(
                connect=self.connect_timeout,
                read=self.timeout,
                write=self.connect_timeout,
                pool=self.connect_timeout,
            )
            response = httpx.get(
                graph_url,
                timeout=timeout_config,
                headers={"User-Agent": "BilaspurNewsIntelligence/0.1"},
            )

            if response.status_code == 403:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=(
                        "Facebook Graph API returned HTTP 403 — "
                        "access token may not have permission to read this Page."
                    ),
                    http_status=403,
                    collection_status="error",
                )
            if response.status_code == 404:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=(
                        "Facebook Graph API returned HTTP 404 — "
                        "Page not found or inaccessible."
                    ),
                    http_status=404,
                    collection_status="error",
                )
            if response.status_code != 200:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=f"Facebook Graph API returned HTTP {response.status_code}",
                    http_status=response.status_code,
                    collection_status="error",
                )

            data = response.json()

            # Check for Graph API error in response
            if "error" in data:
                err = data["error"]
                error_msg = err.get("message", "Unknown Graph API error")
                err_type = err.get("type", "")

                if "OAuthException" in err_type or "invalid token" in error_msg.lower():
                    error = f"Facebook Graph API authentication error: {error_msg}"
                elif "limit" in error_msg.lower():
                    error = f"Facebook Graph API rate limit: {error_msg}"
                else:
                    error = f"Facebook Graph API error: {error_msg}"

                logger.error(error)
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=error,
                    collection_status="error",
                )

            posts = data.get("data", [])

            for post in posts:
                post_id = post.get("id", "")
                post_url = post.get("permalink", url)
                message = post.get("message") or post.get("message", "") or ""
                status_message = post.get("status_message", "") or ""
                description = post.get("description", "") or ""
                created_time_str = post.get("created_time", "")
                full_picture = post.get("full_picture", "")
                post_type = post.get("type", "status")

                # Combine text content
                text_content = message or status_message or description or ""
                title = text_content[:200] if text_content else f"Facebook post by {page_identifier}"

                # Parse published date
                published_at = None
                if created_time_str:
                    try:
                        published_at = datetime.fromisoformat(
                            created_time_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                # Determine media type
                media_type_map = {
                    "photo": "image",
                    "video": "video",
                    "link": "text",
                    "status": "text",
                }
                media_type = media_type_map.get(post_type, "text")
                item_type = "video" if post_type == "video" else "article"

                content_hash = self._generate_content_hash(text_content or post_id, post_url)

                # Check for duplicate via content_hash
                existing = (
                    self.db.query(CollectedItems)
                    .filter(CollectedItems.content_hash == content_hash)
                    .first()
                )
                if existing:
                    items_duplicate += 1
                    continue

                # Check for duplicate via canonical_url
                existing_url = (
                    self.db.query(CollectedItems)
                    .filter(CollectedItems.canonical_url == post_url)
                    .filter(CollectedItems.source_id == self.source.id)
                    .first()
                )
                if existing_url:
                    items_duplicate += 1
                    continue

                item = CollectedItems(
                    source_id=self.source.id,
                    external_id=post_id,
                    title=title[:200],
                    original_url=post_url,
                    canonical_url=post_url,
                    description=text_content[:500] if text_content else "",
                    content_snippet=text_content[:200] if text_content else "",
                    author=page_identifier,
                    published_at=published_at,
                    language="en",
                    item_type=item_type,
                    media_type=media_type,
                    image_url=full_picture if media_type == "image" else "",
                    video_url=full_picture if media_type == "video" else "",
                    raw_metadata=post,
                    content_hash=content_hash,
                    collection_status="collected",
                )

                try:
                    self.db.add(item)
                    self.db.commit()
                    items_inserted += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"DB error inserting Facebook item: {e}")
                    items_duplicate += 1
                    continue

                items.append(item)
                items_found += 1

        except Exception as e:
            error = f"Facebook collection error: {e}"
            logger.error(error, exc_info=True)

        return CollectionResult(
            source_id=self.source.source_id,
            items=items,
            items_found=items_found,
            items_inserted=items_inserted,
            items_duplicate=items_duplicate,
            error=error,
            collection_status="ok" if not error else "error",
        )

    def _extract_page_identifier(self, url: str) -> Optional[str]:
        """Extract Facebook Page ID or username from URL.

        Supports:
        - facebook.com/PageName
        - facebook.com/PageName/
        - facebook.com/pg/PageName
        - facebook.com/123456789 (numeric page ID)
        """
        url = url.strip()

        # Numeric page ID
        match = re.search(r"facebook\.com/(\d+)(?:/|$|\?)", url)
        if match:
            return match.group(1)

        # Page name / username
        match = re.search(r"facebook\.com/(?:pg/)?([A-Za-z0-9_.-]+)(?:/|$|\?)", url)
        if match:
            name = match.group(1)
            # Skip common non-page paths
            skip = {"home", "watch", "marketplace", "groups", "events", "fundraisers",
                    "about", "create", "pages", "settings", "help", "legal",
                    "gaming", "dating", "jobs", "messages", "friends"}
            if name.lower() not in skip:
                return name

        return None

    @staticmethod
    def _generate_content_hash(title: str, url: str) -> str:
        """Generate a content hash for deduplication."""
        raw = f"{title}:{url}"
        return hashlib.sha256(raw.encode()).hexdigest()
