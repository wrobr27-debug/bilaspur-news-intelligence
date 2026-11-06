"""Instagram Collector.

Extracts public Instagram profile posts, reels, and individual post data
from Instagram profile and post URLs. Uses public HTML meta tags and
embedded JSON-LD data — no authentication required.

Supports:
- Instagram profile pages: instagram.com/username/
- Instagram post pages: instagram.com/p/shortcode/
- Instagram reels: instagram.com/reel/shortcode/
"""

from typing import List, Optional
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import Sources, CollectedItems
from src.config import settings
import logging
import re
import hashlib
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class InstagramCollector(BaseCollector):
    """Instagram public data collector.

    Scrapes public Instagram pages (profiles, posts, reels) using
    Open Graph meta tags and embedded JSON-LD. No API key or login
    required — works with publicly accessible content only.
    """

    def can_collect(self, source) -> bool:
        """Check if source is an Instagram URL."""
        url = (source.source_url or "") + " " + (source.api_url or "")
        return bool(
            "instagram.com" in url
            and source.collection_method in ["instagram", "html", "manual"]
        )

    def collect(self) -> CollectionResult:
        """Collect public Instagram data from configured URL."""
        url = self.source.source_url or self.source.api_url or ""
        if not url or "instagram.com" not in url:
            return CollectionResult(
                source_id=self.source.source_id,
                error="No Instagram URL configured",
                collection_status="error",
            )

        items = []
        items_found = 0
        items_inserted = 0
        items_duplicate = 0
        error = None

        try:
            # Fetch the Instagram page
            response_data = self._make_request(url)
            if not response_data:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error="Failed to fetch Instagram page",
                    collection_status="error",
                )

            html = response_data[0].text

            # Determine if this is a profile or a post/reel
            is_post = bool(re.search(r"/p/|/reel/", url))

            if is_post:
                item = self._extract_post(html, url)
                if item:
                    items.append(item)
                    items_found += 1
                    try:
                        self.db.add(item)
                        self.db.commit()
                        items_inserted += 1
                    except Exception as e:
                        self.db.rollback()
                        logger.error(f"DB error inserting Instagram item: {e}")
                        items_duplicate += 1
            else:
                # Profile page — extract recent posts from embedded data
                profile_items = self._extract_profile(html, url)
                for item in profile_items:
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

                    item.source_id = self.source.id
                    item.collected_at = datetime.now(timezone.utc)

                    try:
                        self.db.add(item)
                        self.db.commit()
                        items_inserted += 1
                    except Exception as e:
                        self.db.rollback()
                        logger.error(f"DB error inserting Instagram item: {e}")
                        items_duplicate += 1

                    items.append(item)
                    items_found += 1

        except Exception as e:
            error = f"Instagram collection error: {e}"
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

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_post(self, html: str, url: str) -> Optional[CollectedItems]:
        """Extract a single Instagram post/reel from page HTML."""
        data = self._parse_instagram_page(html)
        if not data:
            return None

        title = data.get("title", "") or data.get("og_title", "") or ""
        description = data.get("description", "") or data.get("og_description", "") or ""
        image_url = data.get("image", "") or data.get("og_image", "") or ""
        author = data.get("author", "") or self._extract_username_from_url(url)
        published_at = data.get("published_at")

        # Determine media type
        is_reel = "/reel/" in url
        media_type = "video" if is_reel else ("video" if image_url.endswith(".mp4") else "image")
        item_type = "video" if is_reel else "article"

        content_hash = self._generate_content_hash(title, url)

        return CollectedItems(
            source_id=self.source.id,
            external_id=self._extract_shortcode(url) or url,
            title=title[:200] if title else f"Instagram post by {author}",
            original_url=url,
            canonical_url=url,
            description=description[:500] if description else "",
            content_snippet=description[:200] if description else "",
            author=author,
            published_at=published_at,
            language="en",
            item_type=item_type,
            media_type=media_type,
            image_url=image_url,
            video_url=url if is_reel else "",
            raw_metadata=data.get("raw", {}),
            content_hash=content_hash,
            collection_status="collected",
        )

    def _extract_profile(self, html: str, url: str) -> List[CollectedItems]:
        """Extract recent posts from an Instagram profile page."""
        items = []
        data = self._parse_instagram_page(html)
        if not data:
            return items

        username = data.get("username", "") or self._extract_username_from_url(url)
        posts = data.get("posts", [])

        for post in posts[:10]:  # Limit to 10 recent posts per collection
            post_url = post.get("url", url)
            title = post.get("title", "") or f"Instagram post by {username}"
            description = post.get("description", "") or ""
            image_url = post.get("image", "") or ""
            is_reel = post.get("is_reel", False)
            published_at = post.get("published_at")

            content_hash = self._generate_content_hash(title, post_url)

            items.append(
                CollectedItems(
                    source_id=self.source.id,
                    external_id=post.get("shortcode", post_url),
                    title=title[:200],
                    original_url=post_url,
                    canonical_url=post_url,
                    description=description[:500] if description else "",
                    content_snippet=description[:200] if description else "",
                    author=username,
                    published_at=published_at,
                    language="en",
                    item_type="video" if is_reel else "article",
                    media_type="video" if is_reel else ("video" if image_url.endswith(".mp4") else "image"),
                    image_url=image_url,
                    video_url=post_url if is_reel else "",
                    raw_metadata=post.get("raw", {}),
                    content_hash=content_hash,
                    collection_status="collected",
                )
            )

        return items

    def _parse_instagram_page(self, html: str) -> Optional[dict]:
        """Parse Instagram page HTML for Open Graph and JSON-LD data."""
        result: dict = {}

        # --- Open Graph meta tags ---
        og_patterns = {
            "og_title": r'<meta property="og:title"\s+content="([^"]*)"',
            "og_description": r'<meta property="og:description"\s+content="([^"]*)"',
            "og_image": r'<meta property="og:image"\s+content="([^"]*)"',
            "og_url": r'<meta property="og:url"\s+content="([^"]*)"',
            "og_type": r'<meta property="og:type"\s+content="([^"]*)"',
        }
        for key, pattern in og_patterns.items():
            match = re.search(pattern, html)
            if match:
                result[key] = match.group(1)

        # Also try name-based meta tags (Instagram uses these too)
        name_patterns = {
            "description": r'<meta name="description"\s+content="([^"]*)"',
        }
        for key, pattern in name_patterns.items():
            if key not in result:
                match = re.search(pattern, html)
                if match:
                    result[key] = match.group(1)

        # Map og_* to cleaner keys
        if "og_title" in result:
            result["title"] = result["og_title"]
        if "og_description" in result:
            result["description"] = result["og_description"]
        if "og_image" in result:
            result["image"] = result["og_image"]
        if "og_url" in result:
            result["canonical_url"] = result["og_url"]

        # --- JSON-LD structured data ---
        jsonld_pattern = r'<script type="application/ld\+json">\s*(.*?)\s*</script>'
        jsonld_match = re.search(jsonld_pattern, html, re.DOTALL)
        if jsonld_match:
            try:
                ld_data = json.loads(jsonld_match.group(1))
                if isinstance(ld_data, list):
                    ld_data = ld_data[0] if ld_data else {}

                if isinstance(ld_data, dict):
                    if not result.get("title"):
                        result["title"] = ld_data.get("name", ld_data.get("headline", ""))
                    if not result.get("description"):
                        result["description"] = ld_data.get("description", "")
                    if not result.get("image"):
                        image = ld_data.get("image", "")
                        if isinstance(image, list):
                            image = image[0] if image else ""
                        result["image"] = image
                    if not result.get("author"):
                        author = ld_data.get("author", "")
                        if isinstance(author, dict):
                            author = author.get("name", "")
                        result["author"] = author

                    # Published date
                    date_published = ld_data.get("datePublished") or ld_data.get("uploadDate")
                    if date_published:
                        try:
                            result["published_at"] = datetime.fromisoformat(
                                date_published.replace("Z", "+00:00")
                            )
                        except Exception:
                            pass

                    result["raw"] = ld_data
            except Exception as e:
                logger.debug(f"JSON-LD parse error: {e}")

        # --- Embedded shared data (Instagram's internal JSON) ---
        shared_data_pattern = r'window\._sharedData\s*=\s*(\{.*?\});</script>'
        shared_match = re.search(shared_data_pattern, html, re.DOTALL)
        if shared_match:
            try:
                shared = json.loads(shared_match.group(1))
                result["raw_shared"] = shared
                # Try to extract username
                entry_data = shared.get("entry_data", {})
                for key, val in entry_data.items():
                    if isinstance(val, list) and len(val) > 0:
                        profile = val[0].get("graphql", {}).get("user", {})
                        if profile:
                            if not result.get("username"):
                                result["username"] = profile.get("username", "")
                            if not result.get("author"):
                                result["author"] = profile.get("full_name", profile.get("username", ""))
                            break
            except Exception as e:
                logger.debug(f"Shared data parse error: {e}")

        # --- Try to extract posts from profile page ---
        posts = self._extract_posts_from_html(html)
        if posts:
            result["posts"] = posts

        # Username from og:url or URL patterns
        if not result.get("username"):
            username_match = re.search(r"instagram\.com/([^/?]+)", result.get("og_url", ""))
            if username_match:
                result["username"] = username_match.group(1)

        # Only return if we got something useful
        if result.get("title") or result.get("description") or result.get("image") or result.get("posts"):
            return result

        return None

    def _extract_posts_from_html(self, html: str) -> List[dict]:
        """Extract post shortcodes and data from profile page HTML."""
        posts = []

        # Look for post links in the HTML
        post_pattern = r'href="(https://www\.instagram\.com/(?:p|reel)/([^"/]+)/?)"'
        seen = set()
        for match in re.finditer(post_pattern, html):
            full_url = match.group(1)
            shortcode = match.group(2)
            if shortcode in seen:
                continue
            seen.add(shortcode)

            # Try to find associated image near this link
            # Look for img tags in proximity
            img_match = re.search(
                r'<img[^>]+src="([^"]+)"[^>]*>', html[match.start():match.start() + 2000]
            )
            image_url = img_match.group(1) if img_match else ""

            posts.append({
                "shortcode": shortcode,
                "url": full_url,
                "image": image_url,
                "is_reel": "/reel/" in full_url,
                "title": f"Instagram post {shortcode}",
                "raw": {},
            })

        return posts

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_username_from_url(url: str) -> str:
        """Extract Instagram username from a URL."""
        match = re.search(r"instagram\.com/([^/?]+)", url)
        if match:
            return match.group(1)
        return "unknown"

    @staticmethod
    def _extract_shortcode(url: str) -> Optional[str]:
        """Extract Instagram post/reel shortcode from URL."""
        match = re.search(r"(?:/p/|/reel/)([^/?]+)", url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _generate_content_hash(title: str, url: str) -> str:
        """Generate a content hash for deduplication."""
        raw = f"{title}:{url}"
        return hashlib.sha256(raw.encode()).hexdigest()
