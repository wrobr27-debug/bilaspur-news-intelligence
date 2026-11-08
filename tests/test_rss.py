"""Tests for RSS collection."""

import pytest
from unittest.mock import MagicMock, patch
from src.collectors.rss import RSSCollector


class TestRSSCollection:
    """Test RSS feed collection."""

    def test_no_rss_url(self):
        """Test that missing RSS URL returns error."""
        source = MagicMock()
        source.rss_url = None
        source.collection_method = "rss"
        source.id = 1
        source.source_id = "test_rss"

        collector = RSSCollector(source, None)
        result = collector.collect()

        assert result.collection_status == "error"
        assert "No RSS URL" in result.error

    def test_request_failed(self):
        """Test that failed HTTP request returns error."""
        source = MagicMock()
        source.rss_url = "https://example.com/feed"
        source.collection_method = "rss"
        source.id = 1
        source.source_id = "test_rss"

        collector = RSSCollector(source, None)

        with patch.object(collector, "_make_request", return_value=None):
            result = collector.collect()

        assert result.collection_status == "error"
        assert "RSS request failed" in result.error

    def test_non_200_status(self):
        """Test that non-200 HTTP status returns error."""
        source = MagicMock()
        source.rss_url = "https://example.com/feed"
        source.collection_method = "rss"
        source.id = 1
        source.source_id = "test_rss"

        collector = RSSCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            result = collector.collect()

        assert result.collection_status == "error"
        assert "404" in result.error

    def test_empty_feed(self):
        """Test that empty feed returns ok status with 0 items."""
        source = MagicMock()
        source.rss_url = "https://example.com/feed"
        source.collection_method = "rss"
        source.id = 1
        source.source_id = "test_rss"

        collector = RSSCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b""

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            with patch("feedparser.parse") as mock_parse:
                mock_feed = MagicMock()
                mock_feed.entries = []
                mock_parse.return_value = mock_feed

                result = collector.collect()

        assert result.collection_status == "ok"
        assert result.items_found == 0
        assert result.items == []

    def test_successful_collection(self):
        """Test successful RSS collection."""
        source = MagicMock()
        source.rss_url = "https://example.com/feed"
        source.collection_method = "rss"
        source.id = 1
        source.source_id = "test_rss"

        collector = RSSCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss></rss>"

        mock_entry = MagicMock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article"
        mock_entry.published_parsed = (2026, 1, 1, 0, 0, 0, 0, 0, 0)
        mock_entry.summary = "Test summary"
        mock_entry.description = "Test summary"
        mock_entry.author = "Test Author"
        mock_entry.language = "en"
        mock_entry.id = "article-123"
        mock_entry.tags = []
        mock_entry.enclosures = []
        mock_entry.media_content = None

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            with patch("feedparser.parse") as mock_parse:
                mock_parse.return_value = mock_feed

                # Mock database
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None
                collector.db = mock_db

                result = collector.collect()

        assert result.collection_status == "ok"
        assert result.items_found == 1
        assert result.items_inserted == 1
        assert len(result.items) == 1

    def test_duplicate_detection(self):
        """Test that duplicate RSS items are detected."""
        source = MagicMock()
        source.rss_url = "https://example.com/feed"
        source.collection_method = "rss"
        source.id = 1
        source.source_id = "test_rss"

        collector = RSSCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss></rss>"

        mock_entry = MagicMock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article"
        mock_entry.published_parsed = (2026, 1, 1, 0, 0, 0, 0, 0, 0)
        mock_entry.summary = "Test summary"
        mock_entry.description = "Test summary"
        mock_entry.author = "Test Author"
        mock_entry.language = "en"
        mock_entry.id = "article-123"
        mock_entry.tags = []
        mock_entry.enclosures = []
        mock_entry.media_content = None

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            with patch("feedparser.parse") as mock_parse:
                mock_parse.return_value = mock_feed

                # Mock database - item already exists
                mock_db = MagicMock()
                existing_item = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = existing_item
                collector.db = mock_db

                result = collector.collect()

        assert result.collection_status == "ok"
        assert result.items_duplicate == 1
        assert result.items_inserted == 0

    def test_collection_status_error_on_exception(self):
        """Test that exceptions result in error status."""
        source = MagicMock()
        source.rss_url = "https://example.com/feed"
        source.collection_method = "rss"
        source.id = 1
        source.source_id = "test_rss"

        collector = RSSCollector(source, None)

        with patch.object(collector, "_make_request", return_value=None):
            result = collector.collect()

        assert result.collection_status == "error"
        assert "RSS request failed" in result.error
