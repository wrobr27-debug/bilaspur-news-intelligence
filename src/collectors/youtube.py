"""YouTube Data API Collector.

Uses the official YouTube Data API v3 to collect channel and video metadata.
Does NOT download or transcribe video content (Stage 2).
Quota-aware requests with proper error handling.
"""

from typing import List, Optional
from datetime import datetime, timezone
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import Sources, CollectedItems
from src.config import settings
import logging
import re
import hashlib

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
                http_status=None,
                collection_status="error",
            )

        items = []
        items_found = 0
        items_inserted = 0
        items_duplicate = 0
        error = None
        all_items_from_api = []

        try:
            # Build YouTube API client
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            youtube = build(
                "youtube", "v3",
                developerKey=settings.youtube_api_key,
                cache=None,  # Disable caching for fresh data
            )

            # Collect from configured channels
            channel_ids = self._extract_channel_ids(youtube)

            if not channel_ids:
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

                    # Get uploads playlist ID
                    uploads_playlist_id = (
                        channel.get("contentDetails", {})
                        .get("relatedPlaylist", {})
                        .get("uploads", "")
                    )

                    if not uploads_playlist_id:
                        logger.warning(
                            f"No uploads playlist for channel {channel_id}"
                        )
                        continue

                    # Fetch recent videos from uploads playlist
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
                                    published_at = datetime.now(timezone.utc)

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
                                .filter(CollectedItems.canonical_url == video_url)
                                .filter(CollectedItems.source_id == self.source.id)
                                .first()
                            )
                            if existing_url:
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

                except HttpError as e:
                    error_details = self._parse_youtube_http_error(e)
                    logger.warning(
                        f"YouTube API error for channel {channel_id}: {error_details}"
                    )
                    if error_details.get("quota_exceeded"):
                        error = f"YouTube API quota exceeded: {error_details.get('message', '')}"
                        break  # No point continuing if quota is exceeded
                    elif error_details.get("invalid_key"):
                        error = f"YouTube API key invalid: {error_details.get('message', '')}"
                        break  # No point continuing if key is invalid
                    elif error_details.get("not_found"):
                        logger.warning(f"Channel {channel_id} not found or inaccessible")
                        continue
                    else:
                        logger.warning(
                            f"Error collecting YouTube channel {channel_id}: {error_details}"
                        )
                        continue
                except Exception as e:
                    logger.warning(
                        f"Error collecting YouTube channel {channel_id}: {e}",
                        exc_info=True,
                    )
                    continue

            # Insert all collected items
            now = datetime.now(timezone.utc)
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

        except HttpError as e:
            error_details = self._parse_youtube_http_error(e)
            error = f"YouTube API error: {error_details.get('message', str(e))}"
            logger.error(error, exc_info=True)
        except Exception as e:
            error = f"YouTube API collection error: {e}"
            logger.error(error, exc_info=True)

        return CollectionResult(
            source_id=self.source.source_id,
            items=all_items_from_api,
            items_found=items_found,
            items_inserted=items_inserted,
            items_duplicate=items_duplicate,
            error=error,
            collection_status="ok" if not error else "error",
        )

    def _extract_channel_ids(self, youtube_client=None) -> list:
        """Extract channel IDs from source configuration.

        Supports:
        - Direct channel IDs (UC-prefixed, 24 chars)
        - Channel URLs (youtube.com/channel/UC...)
        - Custom URLs (youtube.com/c/name or youtube.com/@handle)
        - Handle URLs (youtube.com/@handle)

        For custom URLs and handles, attempts to resolve via the YouTube Data API
        search endpoint if a youtube_client is provided.
        """
        channel_ids = []

        # Try api_url first - can be a channel ID, channel URL, or handle
        if self.source.api_url:
            api_url = str(self.source.api_url).strip()
            if api_url:
                extracted = self._parse_channel_identifier(api_url, youtube_client)
                channel_ids.extend(extracted)

        # Try source_url for known channel patterns
        if self.source.source_url and "youtube.com" in self.source.source_url:
            extracted = self._parse_channel_identifier(self.source.source_url, youtube_client)
            channel_ids.extend(extracted)

        # Deduplicate while preserving order
        seen = set()
        result = []
        for cid in channel_ids:
            if cid not in seen:
                seen.add(cid)
                result.append(cid)
        return result

    def _parse_channel_identifier(self, value: str, youtube_client=None) -> list:
        """Parse a channel identifier from various YouTube URL formats.

        Returns a list of resolved channel IDs (UC-prefixed).
        """
        channel_ids = []
        value = value.strip()

        # Direct channel ID: UC-prefixed, 24 chars total
        if value.startswith("UC") and len(value) == 24:
            channel_ids.append(value)
            return channel_ids

        # Channel URL: youtube.com/channel/UC...
        match = re.search(r"youtube\.com/channel/([A-Za-z0-9_-]{24})", value)
        if match:
            channel_ids.append(match.group(1))
            return channel_ids

        # Custom URL: youtube.com/c/name
        match = re.search(r"youtube\.com/c/([A-Za-z0-9_-]+)", value)
        if match:
            custom_name = match.group(1)
            resolved = self._resolve_channel_via_api(custom_name, youtube_client)
            if resolved:
                channel_ids.append(resolved)
            return channel_ids

        # Handle URL: youtube.com/@handle
        match = re.search(r"youtube\.com/@([A-Za-z0-9_.-]+)", value)
        if match:
            handle = match.group(1)
            resolved = self._resolve_channel_via_api(handle, youtube_client)
            if resolved:
                channel_ids.append(resolved)
            return channel_ids

        # Plain handle or name (no URL structure)
        if not value.startswith("http") and len(value) > 1:
            resolved = self._resolve_channel_via_api(value, youtube_client)
            if resolved:
                channel_ids.append(resolved)

        return channel_ids

    def _resolve_channel_via_api(self, identifier: str, youtube_client=None) -> Optional[str]:
        """Resolve a channel name or handle to a channel ID using the YouTube Data API.

        Uses the search endpoint with type=channel to find the channel ID.
        """
        if not youtube_client:
            logger.warning(
                f"YouTube API client not available to resolve '{identifier}' - "
                f"cannot resolve non-channel-ID identifiers"
            )
            return None

        try:
            from googleapiclient.errors import HttpError

            search_response = youtube_client.search().list(
                part="snippet",
                q=identifier,
                type="channel",
                maxResults=1,
            ).execute()

            items = search_response.get("items", [])
            if items:
                channel_id = items[0].get("id", {}).get("channelId", "")
                if channel_id:
                    logger.info(
                        f"Resolved '{identifier}' to channel ID {channel_id}"
                    )
                    return channel_id
            else:
                logger.warning(f"No YouTube channel found for identifier: {identifier}")
        except HttpError as e:
            error_details = self._parse_youtube_http_error(e)
            logger.warning(
                f"YouTube API error resolving '{identifier}': {error_details}"
            )
        except Exception as e:
            logger.warning(f"Error resolving '{identifier}': {e}")

        return None

    def _parse_youtube_http_error(self, exception) -> dict:
        """Parse YouTube API HttpError to extract error details.

        Returns a dict with keys: quota_exceeded, invalid_key, not_found, message
        """
        details = {
            "quota_exceeded": False,
            "invalid_key": False,
            "not_found": False,
            "message": str(exception),
        }

        try:
            import json
            if hasattr(exception, 'content'):
                content = json.loads(exception.content)
                error = content.get("error", {})
                error_message = error.get("message", "")
                errors = error.get("errors", [])

                details["message"] = error_message

                for err in errors:
                    reason = err.get("reason", "")
                    if reason in ("quotaExceeded", "dailyLimitExceeded"):
                        details["quota_exceeded"] = True
                    if reason in ("keyInvalid", "keyExpired"):
                        details["invalid_key"] = True
                    if reason in ("notFound", "resourceNotFound"):
                        details["not_found"] = True

                # Also check message text
                msg_lower = error_message.lower()
                if "quota" in msg_lower:
                    details["quota_exceeded"] = True
                if "invalid" in msg_lower and "key" in msg_lower:
                    details["invalid_key"] = True
                if "not found" in msg_lower:
                    details["not_found"] = True
        except Exception:
            pass

        return details

    @staticmethod
    def _generate_content_hash(title: str, url: str) -> str:
        """Generate a content hash for deduplication."""
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
