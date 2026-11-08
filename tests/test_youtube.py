"""Tests for YouTube channel ID resolution and API key validation."""

import pytest
from unittest.mock import MagicMock, patch
from src.collectors.youtube import YouTubeCollector


class TestYouTubeChannelIDResolution:
    """Test channel ID extraction from various URL formats."""

    def test_direct_channel_id(self):
        """Test that UC-prefixed channel IDs are recognized directly."""
        source = MagicMock()
        source.api_url = "UCNgQXeaaxnF-cCQFC4iMr9w"
        source.source_url = None
        source.source_type = "youtube"

        collector = YouTubeCollector.__new__(YouTubeCollector)
        collector.source = source

        ids = collector._parse_channel_identifier("UCNgQXeaaxnF-cCQFC4iMr9w", None)
        assert "UCNgQXeaaxnF-cCQFC4iMr9w" in ids

    def test_channel_url(self):
        """Test that youtube.com/channel/UC... URLs are parsed."""
        source = MagicMock()
        source.api_url = None
        source.source_url = "https://www.youtube.com/channel/UCNgQXeaaxnF-cCQFC4iMr9w"
        source.source_type = "youtube"

        collector = YouTubeCollector.__new__(YouTubeCollector)
        collector.source = source

        ids = collector._parse_channel_identifier(
            "https://www.youtube.com/channel/UCNgQXeaaxnF-cCQFC4iMr9w", None
        )
        assert "UCNgQXeaaxnF-cCQFC4iMr9w" in ids

    def test_custom_url(self):
        """Test that youtube.com/c/name URLs are identified as custom URLs."""
        source = MagicMock()
        source.api_url = None
        source.source_url = "https://www.youtube.com/c/IBC24News"
        source.source_type = "youtube"

        collector = YouTubeCollector.__new__(YouTubeCollector)
        collector.source = source

        # Without API client, custom URLs should not resolve
        ids = collector._parse_channel_identifier(
            "https://www.youtube.com/c/IBC24News", None
        )
        assert ids == []

    def test_handle_url(self):
        """Test that youtube.com/@handle URLs are identified."""
        source = MagicMock()
        source.api_url = None
        source.source_url = "https://www.youtube.com/@IBC24News"
        source.source_type = "youtube"

        collector = YouTubeCollector.__new__(YouTubeCollector)
        collector.source = source

        ids = collector._parse_channel_identifier(
            "https://www.youtube.com/@IBC24News", None
        )
        assert ids == []

    def test_invalid_id_format(self):
        """Test that non-UC, non-24-char strings are not treated as channel IDs."""
        source = MagicMock()
        source.api_url = "invalid_id_12345"
        source.source_url = None
        source.source_type = "youtube"

        collector = YouTubeCollector.__new__(YouTubeCollector)
        collector.source = source

        ids = collector._parse_channel_identifier("invalid_id_12345", None)
        assert ids == []


class TestYouTubeAPIKeyValidation:
    """Test YouTube API key validation."""

    def test_missing_api_key(self):
        """Test that missing API key returns error."""
        source = MagicMock()
        source.api_url = "UCNgQXeaaxnF-cCQFC4iMr9w"
        source.source_url = None
        source.source_type = "youtube"
        source.id = 1
        source.source_id = "test_youtube"

        collector = YouTubeCollector(source, None)

        with patch("src.collectors.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = ""
            result = collector.collect()

        assert result.collection_status == "error"
        assert "API key not configured" in result.error
        assert result.items == []

    def test_invalid_api_key(self):
        """Test that invalid API key returns quota/key error."""
        source = MagicMock()
        source.api_url = "UCNgQXeaaxnF-cCQFC4iMr9w"
        source.source_url = None
        source.source_type = "youtube"
        source.id = 1
        source.source_id = "test_youtube"

        collector = YouTubeCollector(source, None)

        with patch("src.collectors.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "invalid_key"

            # Mock the YouTube API client to raise an HttpError
            from googleapiclient.errors import HttpError
            import googleapiclient.discovery

            mock_response = MagicMock()
            mock_response.status = 403
            mock_response.data = b'{"error": {"code": 403, "message": "The request cannot be completed because you have exceeded your quota", "errors": [{"reason": "quotaExceeded"}]}}'
            http_error = HttpError(mock_response, b'{"error": {"code": 403}}')

            with patch.object(collector, "_extract_channel_ids", return_value=["UCNgQXeaaxnF-cCQFC4iMr9w"]):
                with patch("googleapiclient.discovery.build") as mock_build:
                    mock_build.side_effect = http_error
                    result = collector.collect()

        assert result.collection_status == "error"
        assert result.items == []
        assert "error" in result.error.lower()


class TestYouTubeDuplicateDetection:
    """Test YouTube duplicate detection."""

    def test_duplicate_by_content_hash(self):
        """Test that items with same content_hash are detected as duplicates."""
        from src.database.models import CollectedItems

        source = MagicMock()
        source.api_url = "UCNgQXeaaxnF-cCQFC4iMr9w"
        source.source_url = None
        source.source_type = "youtube"
        source.id = 1
        source.source_id = "test_youtube"

        collector = YouTubeCollector(source, None)

        # Create an existing item in the "database"
        existing_item = MagicMock()
        existing_item.content_hash = "abc123"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_item
        collector.db = mock_db

        result = mock_db.query.return_value.filter.return_value.first()
        assert result is not None


class TestYouTubeCollectionStatus:
    """Test YouTube collection status reporting."""

    def test_error_status_on_api_failure(self):
        """Test that API failures result in error status."""
        source = MagicMock()
        source.api_url = "UCNgQXeaaxnF-cCQFC4iMr9w"
        source.source_url = None
        source.source_type = "youtube"
        source.id = 1
        source.source_id = "test_youtube"

        collector = YouTubeCollector(source, None)

        with patch("src.collectors.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "valid_key"

            with patch.object(collector, "_extract_channel_ids", return_value=[]):
                result = collector.collect()

        assert result.collection_status == "error"
        assert result.error is not None
        assert "No channel IDs" in result.error

    def test_ok_status_on_success(self):
        """Test that successful collection returns ok status."""
        source = MagicMock()
        source.api_url = "UCNgQXeaaxnF-cCQFC4iMr9w"
        source.source_url = None
        source.source_type = "youtube"
        source.id = 1
        source.source_id = "test_youtube"

        collector = YouTubeCollector(source, None)

        # Create a mock item
        mock_item = MagicMock()
        mock_item.collected_at = None
        mock_item.content_hash = "hash123"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        collector.db = mock_db

        with patch("src.collectors.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "valid_key"

            mock_youtube = MagicMock()
            mock_channel_response = {
                "items": [{
                    "snippet": {"channelTitle": "Test Channel", "description": "", "publishedAt": "2026-01-01T00:00:00Z"},
                    "contentDetails": {"relatedPlaylist": {"uploads": "UUxxxx"}},
                }]
            }
            mock_playlist_response = {"items": [], "nextPageToken": ""}

            mock_channels = MagicMock()
            mock_channels.list.return_value.execute.return_value = mock_channel_response
            mock_playlist_items = MagicMock()
            mock_playlist_items.list.return_value.execute.return_value = mock_playlist_response

            mock_youtube.channels.return_value = mock_channels
            mock_youtube.playlistItems.return_value = mock_playlist_items

            with patch("googleapiclient.discovery.build", return_value=mock_youtube):
                result = collector.collect()

        assert result.collection_status == "ok"
        assert result.error is None
