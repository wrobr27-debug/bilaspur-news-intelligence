"""YouTube Data API Collector.

Uses the official YouTube Data API v3 to collect channel and video metadata.
Does NOT download or transcribe video content (Stage 2).
Quota-aware requests with proper error handling.
"""

from typing import List, Optional
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import Sources, CollectedItems
from src.config import settings
import logging
import re

logger = logging.getLogger(__name__)


class YouTubeCollector(BaseCollector):
    """YouTube Data API Collector.

    Uses the official YouTube Data API v3 to collect channel and video metadata.
    Does NOT download or transcribe video content (Stage 2).
    Quota-aware requests with proper error handling.
    """

    def can_collect(self, source) -> bool:
        """Check if source has a YouTube channel and API key is available."""
        return (
            bool(source.api_url or source.source_url)
            and source.source_type == "youtube"
            and bool(settings.youtube_api_key)
        )

    def collect(self) -> CollectionResult:
        """Collect YouTube channel and video metadata."""
        if not settings.youtube_api_key:
            return CollectionResult(
                source_id=self.source.source_id,
                error="YouTube API key not configured",
                collection_status="error",
            )

        items = []
        items_found = 0
        items_inserted = 0
        items_duplicate = 0
        error = None

        try:
            # Build YouTube API client
            from googleapiclient.discovery import build
            youtube = build(
                "youtube", "v3",
                developerKey=settings.youtube_api_key,
                cache=None,  # Disable caching for fresh data
            )

            # Collect from configured channels
            channel_ids = self._extract_channel_ids()

            if not channel_ids:
                logger.warning(
                    f"No channel IDs found for YouTube source {self.source.source_name}"
                )
                return CollectionResult(
                    source_id=self.source.source_id,
                    error="No channel IDs configured",
                    collection_status="error",
                )

            all_items_from_api = []

            for channel_id in channel_ids:
                try:
                    # Get channel details
                    channel_request = youtube.channels().list(
                        part="snippet,contentDetails,statistics",
                        id=channel_id,
                    )
                    channel_response = channel_request.execute()

                    if not channel_response.get("items"):
                        logger.warning(f"No channel found for ID: {channel_id}")
                        continue

                    channel = channel_response["items"][0]
                    snippet = channel.get("snippet", {})

                    # Extract channel metadata
                    channel_title = snippet.get("channelTitle", "")
                    channel_description = snippet.get("description", "")
                    published_at = snippet.get("publishedAt", "")

                    # Get uploads playlist ID
                    uploads_playlist_id = (
                        channel.get("contentDetails", {})
                        .get("relatedPlaylist", {})
                        .get("uploads", "")
                    )

                    if not uploads_playlist_id:
                        continue

                    # Fetch recent videos from uploads playlist
                    # Use pagination - limit to recent videos
                    next_page_token = None
                    videos_collected = 0

                    while videos_collected < 10:  # Limit to 10 videos per collection run
                        playlist_request = youtube.playlistItems().list(
                            part="snippet,contentDetails",
                            playlistId=uploads_playlist_id,
                            maxResults=5,
                            pageToken=next_page_token,
                        )
                        playlist_response = playlist_request.execute()

                        for item in playlist_response.get("items", []):
                            snippet = item.get("snippet", {})
                            resource_id = snippet.get("resourceId", {})

                            video_id = resource_id.get("videoId", "")
                            if not video_id:
                                continue

                            video_title = snippet.get("title", "")
                            video_description = snippet.get("description", "")
                            published_str = snippet.get("publishedAt", "")
                            video_url = f"https://www.youtube.com/watch?v={video_id}"

                            # Parse published date
                            published_at = None
                            if published_str:
                                try:
                                    from dateutil import parser
                                    published_at = parser.parse(published_str)
                                except Exception:
                                    published_at = datetime.now(timezone.utc) if "datetime" in dir() else None

                            # Extract thumbnails
                            thumbnails = snippet.get("thumbnails", {})
                            thumbnail_url = (
                                thumbnails.get("high", {})
                                .get("url", "")
                                or thumbnails.get("medium", {})
                                .get("url", "")
                                or thumbnails.get("default", {})
                                .get("url", "")
                            )

                            # Generate content hash
                            content_hash = self._generate_content_hash(
                                video_title, video_url
                            )

                            # Check for duplicate
                            existing = (
                                self.db.query(CollectedItems)
                                .filter(CollectedItems.content_hash == content_hash)
                                .first()
                            )
                            if existing:
                                items_duplicate += 1
                                continue

                            item = CollectedItems(
                                source_id=self.source.id,
                                external_id=video_id,
                                title=video_title[:200],
                                original_url=video_url,
                                canonical_url=video_url,
                                description=video_description[:500] if video_description else "",
                                content_snippet=video_description[:200] if video_description else "",
                                author=snippet.get("channelTitle", ""),
                                published_at=published_at,
                                language=self._normalize_language(
                                    snippet.get("channel", {}).get("language", "en")
                                ),
                                item_type="video",
                                media_type="video",
                                image_url=thumbnail_url,
                                video_url=video_url,
                                raw_metadata={
                                    "videoId": video_id,
                                    "channelId": channel_id,
                                    "playlistItem": item.get("id", ""),
                                },
                                content_hash=content_hash,
                                collection_status="collected",
                            )

                            all_items_from_api.append(item)
                            videos_collected += 1

                        next_page_token = playlist_response.get(
                            "nextPageToken", ""
                        )
                        if not next_page_token:
                            break

                except Exception as e:
                    logger.warning(
                        f"Error collecting YouTube channel {channel_id}: {e}",
                        exc_info=True,
                    )

            # Insert all collected items
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc) if "datetime" in dir() else None
            for item in all_items_from_api:
                if item.collected_at is None:
                    item.collected_at = now
                try:
                    self.db.add(item)
                    self.db.commit()
                    items_inserted += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"DB error inserting YouTube item: {e}")
                    items_duplicate += 1

            items_found = items_inserted + items_duplicate

        except Exception as e:
            error = f"YouTube API collection error: {e}"
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

    def _extract_channel_ids(self) -> list:
        """Extract channel IDs from source configuration."""
        channel_ids = []

        # Try api_url first
        if self.source.api_url:
            api_url = str(self.source.api_url).strip()
            if api_url:
                channel_ids.append(api_url)

        # Try source_url for known channel patterns
        if self.source.source_url and "youtube.com" in self.source.source_url:
            import re
            # Look for UC-prefixed channel IDs in the URL
            matches = re.findall(r"[^&'\"]{34}", self.source.source_url)
            # Filter to likely channel IDs (start with UC)
            for match in matches:
                if match.startswith("UC"):
                    channel_ids.append(match)

        # Deduplicate
        return list(dict.fromkeys(channel_ids))

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