"""Tests for X API failures."""

import pytest
from unittest.mock import MagicMock, patch
from src.collectors.x import XCollector


class TestXAPIFailures:
    """Test X API v2 error handling."""

    def test_missing_bearer_token(self):
        """Test that missing Bearer Token returns error."""
        source = MagicMock()
        source.source_url = "https://twitter.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        with patch("src.collectors.x.settings") as mock_settings:
            mock_settings.x_api_bearer_token = ""
            result = collector.collect()

        assert result.collection_status == "error"
        assert "bearer token not configured" in result.error.lower()

    def test_401_unauthorized(self):
        """Test that HTTP 401 from X API is detected."""
        source = MagicMock()
        source.source_url = "https://twitter.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        with patch("src.collectors.x.settings") as mock_settings:
            mock_settings.x_api_bearer_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "401" in result.error

    def test_403_forbidden(self):
        """Test that HTTP 403 from X API is detected."""
        source = MagicMock()
        source.source_url = "https://twitter.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        with patch("src.collectors.x.settings") as mock_settings:
            mock_settings.x_api_bearer_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 403
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "403" in result.error

    def test_404_user_not_found(self):
        """Test that HTTP 404 for non-existent user is detected."""
        source = MagicMock()
        source.source_url = "https://twitter.com/nonexistent_usr/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        with patch("src.collectors.x.settings") as mock_settings:
            mock_settings.x_api_bearer_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "404" in result.error

    def test_429_rate_limit(self):
        """Test that HTTP 429 rate limit is detected."""
        source = MagicMock()
        source.source_url = "https://twitter.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        with patch("src.collectors.x.settings") as mock_settings:
            mock_settings.x_api_bearer_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 429
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "429" in result.error

    def test_api_error_in_response(self):
        """Test that X API error JSON in response is detected."""
        source = MagicMock()
        source.source_url = "https://twitter.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        with patch("src.collectors.x.settings") as mock_settings:
            mock_settings.x_api_bearer_token = "fake_token"

            with patch("httpx.get") as mock_get:
                # First call (user lookup) returns error
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "errors": [
                        {"message": "User not found", "code": 50}
                    ]
                }
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "User not found" in result.error

    def test_username_extraction(self):
        """Test that usernames are extracted from X URLs."""
        source = MagicMock()
        source.source_url = "https://twitter.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        assert collector._extract_username("https://twitter.com/bsppolicecg/") == "bsppolicecg"
        assert collector._extract_username("https://twitter.com/bsppolicecg") == "bsppolicecg"
        assert collector._extract_username("https://x.com/bsppolicecg/") == "bsppolicecg"
        assert collector._extract_username("https://x.com/bsppolicecg") == "bsppolicecg"

    def test_non_user_urls_rejected(self):
        """Test that non-user X URLs are rejected."""
        source = MagicMock()
        source.source_url = "https://twitter.com/home/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_x"

        collector = XCollector(source, None)

        assert collector._extract_username("https://twitter.com/home/") is None
        assert collector._extract_username("https://twitter.com/notifications") is None
        assert collector._extract_username("https://twitter.com/search") is None
