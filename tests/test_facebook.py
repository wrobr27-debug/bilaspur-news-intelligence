"""Tests for Facebook API failures."""

import pytest
from unittest.mock import MagicMock, patch
from src.collectors.facebook import FacebookCollector


class TestFacebookAPIFailures:
    """Test Facebook Graph API error handling."""

    def test_missing_token(self):
        """Test that missing Graph API token returns error."""
        source = MagicMock()
        source.source_url = "https://www.facebook.com/bsppolice/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_facebook"

        collector = FacebookCollector(source, None)

        with patch("src.collectors.facebook.settings") as mock_settings:
            mock_settings.facebook_graph_api_token = ""
            result = collector.collect()

        assert result.collection_status == "error"
        assert "token not configured" in result.error.lower()

    def test_403_forbidden(self):
        """Test that HTTP 403 from Graph API is detected."""
        source = MagicMock()
        source.source_url = "https://www.facebook.com/bsppolice/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_facebook"

        collector = FacebookCollector(source, None)

        with patch("src.collectors.facebook.settings") as mock_settings:
            mock_settings.facebook_graph_api_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 403
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "403" in result.error

    def test_404_not_found(self):
        """Test that HTTP 404 from Graph API is detected."""
        source = MagicMock()
        source.source_url = "https://www.facebook.com/nonexistent/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_facebook"

        collector = FacebookCollector(source, None)

        with patch("src.collectors.facebook.settings") as mock_settings:
            mock_settings.facebook_graph_api_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "404" in result.error

    def test_graph_api_error_response(self):
        """Test that Graph API error JSON is detected."""
        source = MagicMock()
        source.source_url = "https://www.facebook.com/bsppolice/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_facebook"

        collector = FacebookCollector(source, None)

        with patch("src.collectors.facebook.settings") as mock_settings:
            mock_settings.facebook_graph_api_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "error": {
                        "message": "Invalid OAuth access token",
                        "type": "OAuthException",
                        "code": 190,
                    }
                }
                mock_get.return_value = mock_response

                result = collector.collect()

        assert result.collection_status == "error"
        assert "OAuth" in result.error or "authentication" in result.error.lower()

    def test_page_identifier_extraction(self):
        """Test that page identifiers are extracted from URLs."""
        source = MagicMock()
        source.source_url = "https://www.facebook.com/bsppolice/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_facebook"

        collector = FacebookCollector(source, None)

        # Test various URL formats
        assert collector._extract_page_identifier("https://www.facebook.com/bsppolice/") == "bsppolice"
        assert collector._extract_page_identifier("https://www.facebook.com/bsppolice") == "bsppolice"
        assert collector._extract_page_identifier("https://www.facebook.com/pg/bsppolice/") == "bsppolice"
        assert collector._extract_page_identifier("https://www.facebook.com/123456789/") == "123456789"

    def test_non_page_urls_rejected(self):
        """Test that non-page Facebook URLs are not treated as page identifiers."""
        source = MagicMock()
        source.source_url = "https://www.facebook.com/home/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "api"
        source.id = 1
        source.source_id = "test_facebook"

        collector = FacebookCollector(source, None)

        assert collector._extract_page_identifier("https://www.facebook.com/home/") is None
        assert collector._extract_page_identifier("https://www.facebook.com/marketplace") is None
