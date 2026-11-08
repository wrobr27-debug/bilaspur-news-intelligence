"""X (Twitter) Collector.

Uses the official X API v2 to collect public posts from authorized accounts.
Does NOT scrape login-protected or unauthorized content.

Collects accessible public posts, IDs, timestamps, author information and links
according to API access permissions.

Requires X API Bearer Token for authentication.
"""

from typing import List, Optional
from datetime import datetime, timezone
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import Sources, CollectedItems
from src.config import settings
import logging
import hashlib
import re
import httpx

logger = logging.getLogger(__name__)


class XCollector(BaseCollector):
    """X (Twitter) API v2 Collector.

    Collects accessible public posts using the official X API v2.
    Requires a valid X API Bearer Token.

    Does NOT implement unauthorized scraping.
    """

    def can_collect(self, source) -> bool:
        """Check if source is an X/Twitter account with API configured."""
        url = (source.source_url or "") + " " + (source.api_url or "")
        return bool(
            ("x.com" in url or "twitter.com" in url)
            and source.collection_method in ["api", "html", "manual"]
            and bool(getattr(settings, 'x_api_bearer_token', None))
        )

    def collect(self) -> CollectionResult:
        """Collect X posts via X API v2."""
        bearer_token = getattr(settings, 'x_api_bearer_token', None)
        if not bearer_token:
            return CollectionResult(
                source_id=self.source.source_id,
                error="X API Bearer Token not configured",
                collection_status="error",
            )

        url = self.source.source_url or self.source.api_url or ""
        if not url:
            return CollectionResult(
                source_id=self.source.source_id,
                error="No X/Twitter URL configured",
                collection_status="error",
            )

        # Extract username from URL
        username = self._extract_username(url)
        if not username:
            return CollectionResult(
                source_id=self.source.source_id,
                error="Could not extract X/Twitter username from URL",
                collection_status="error",
            )

        items = []
        items_found = 0
        items_inserted = 0
        items_duplicate = 0
        error = None

        try:
            # Step 1: Look up user ID from username
            user_lookup_url = (
                f"https://api.twitter.com/2/users/by/username/{username}"
                f"?user.fields=created_at,description,verified"
            )

            timeout_config = httpx.Timeout(
                connect=self.connect_timeout,
                read=self.timeout,
                write=self.connect_timeout,
                pool=self.connect_timeout,
            )
            headers = {
                "Authorization": f"Bearer {bearer_token}",
                "User-Agent": "BilaspurNewsIntelligence/0.1",
            }

            user_response = httpx.get(
                user_lookup_url,
                timeout=timeout_config,
                headers=headers,
            )

            if user_response.status_code == 401:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error="X API returned HTTP 401 — invalid or expired Bearer Token",
                    http_status=401,
                    collection_status="error",
                )
            if user_response.status_code == 403:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=(
                        "X API returned HTTP 403 — "
                        "access token may not have permission for this endpoint."
                    ),
                    http_status=403,
                    collection_status="error",
                )
            if user_response.status_code == 404:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=(
                        f"X API returned HTTP 404 — "
                        f"user '{username}' not found."
                    ),
                    http_status=404,
                    collection_status="error",
                )
            if user_response.status_code == 429:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=(
                        "X API returned HTTP 429 — "
                        "rate limit exceeded."
                    ),
                    http_status=429,
                    collection_status="error",
                )
            if user_response.status_code != 200:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=f"X API returned HTTP {user_response.status_code} during user lookup",
                    http_status=user_response.status_code,
                    collection_status="error",
                )

            user_data = user_response.json()

            # Check for X API error in response
            if "errors" in user_data:
                errors = user_data["errors"]
                error_messages = [e.get("message", "Unknown error") for e in errors]
                error = f"X API user lookup error: {'; '.join(error_messages)}"
                logger.error(error)
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=error,
                    collection_status="error",
                )

            user_info = user_data.get("data", {})
            user_id = user_info.get("id", "")

            if not user_id:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=f"No user ID returned for X user '{username}'",
                    collection_status="error",
                )

            # Step 2: Fetch user's tweets
            tweets_url = (
                f"https://api.twitter.com/2/users/{user_id}/tweets"
                f"?tweet.fields=created_at,text,author_id,public_metrics,entities,"
                f"attachments,context_annotations"
                f"&max_results=25"
            )

            tweets_response = httpx.get(
                tweets_url,
                timeout=timeout_config,
                headers=headers,
            )

            if tweets_response.status_code == 429:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=(
                        "X API returned HTTP 429 — "
                        "rate limit exceeded during tweet fetch."
                    ),
                    http_status=429,
                    collection_status="error",
                )
            if tweets_response.status_code != 200:
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=f"X API returned HTTP {tweets_response.status_code} during tweet fetch",
                    http_status=tweets_response.status_code,
                    collection_status="error",
                )

            tweets_data = tweets_response.json()

            if "errors" in tweets_data:
                errors = tweets_data["errors"]
                error_messages = [e.get("message", "Unknown error") for e in errors]
                error = f"X API tweet fetch error: {'; '.join(error_messages)}"
                logger.error(error)
                return CollectionResult(
                    source_id=self.source.source_id,
                    error=error,
                    collection_status="error",
                )

            tweets = tweets_data.get("data", [])

            for tweet in tweets:
                tweet_id = tweet.get("id", "")
                tweet_text = tweet.get("text", "")
                created_at_str = tweet.get("created_at", "")
                author_id = tweet.get("author_id", "")

                # Build tweet URL
                tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"

                # Parse published date
                published_at = None
                if created_at_str:
                    try:
                        published_at = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                # Extract media URLs from attachments
                media_urls = []
                attachments = tweet.get("attachments", {})
                media_keys = attachments.get("media_keys", [])
                includes = tweets_data.get("includes", {})
                media_list = includes.get("media", [])

                for media in media_list:
                    if media.get("media_key") in media_keys:
                        media_url = media.get("url", "")
                        media_type = media.get("type", "")
                        if media_type == "photo":
                            media_urls.append(media_url)
                        elif media_type in ("video", "animated_gif"):
                            variants = media.get("variants", [])
                            # Get the highest bitrate variant
                            best_variant = max(
                                variants,
                                key=lambda v: v.get("bit_rate", 0),
                                default=None,
                            ) if variants else None
                            if best_variant:
                                media_urls.append(best_variant.get("url", ""))

                # Determine item type based on content
                has_media = len(media_urls) > 0
                item_type = "video" if any("video" in m.lower() for m in media_urls) else "article"
                media_type = "video" if item_type == "video" else ("image" if media_urls else "text")

                content_hash = self._generate_content_hash(tweet_text or tweet_id, tweet_url)

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
                    .filter(CollectedItems.canonical_url == tweet_url)
                    .filter(CollectedItems.source_id == self.source.id)
                    .first()
                )
                if existing_url:
                    items_duplicate += 1
                    continue

                item = CollectedItems(
                    source_id=self.source.id,
                    external_id=tweet_id,
                    title=tweet_text[:200] if tweet_text else f"X post by {username}",
                    original_url=tweet_url,
                    canonical_url=tweet_url,
                    description=tweet_text[:500] if tweet_text else "",
                    content_snippet=tweet_text[:200] if tweet_text else "",
                    author=username,
                    published_at=published_at,
                    language="en",
                    item_type=item_type,
                    media_type=media_type,
                    image_url=media_urls[0] if media_urls and media_type == "image" else "",
                    video_url=media_urls[0] if media_urls and media_type == "video" else "",
                    raw_metadata={
                        "tweet_id": tweet_id,
                        "author_id": author_id,
                        "public_metrics": tweet.get("public_metrics", {}),
                        "media_urls": media_urls,
                    },
                    content_hash=content_hash,
                    collection_status="collected",
                )

                try:
                    self.db.add(item)
                    self.db.commit()
                    items_inserted += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"DB error inserting X item: {e}")
                    items_duplicate += 1
                    continue

                items.append(item)
                items_found += 1

        except Exception as e:
            error = f"X collection error: {e}"
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

    def _extract_username(self, url: str) -> Optional[str]:
        """Extract X/Twitter username from URL.

        Supports:
        - twitter.com/username
        - twitter.com/username/
        - x.com/username
        - x.com/username/
        - twitter.com/i/user/123456 (numeric ID not supported directly)
        """
        url = url.strip()

        match = re.search(r"(?:twitter\.com|x\.com)/(?:i/user/)?([A-Za-z0-9_]{1,15})(?:/|$|\?)", url)
        if match:
            username = match.group(1)
            # Skip common non-user paths
            skip = {"home", "notifications", "messages", "search", "explore",
                    "settings", "logout", "signup", "login", "intent",
                    "hashtag", "compose"}
            if username.lower() not in skip:
                return username

        return None

    @staticmethod
    def _generate_content_hash(title: str, url: str) -> str:
        """Generate a content hash for deduplication."""
        raw = f"{title}:{url}"
        return hashlib.sha256(raw.encode()).hexdigest()
