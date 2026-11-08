"""Tests for Instagram redirect and login-wall detection."""

import pytest
from unittest.mock import MagicMock, patch
from src.collectors.instagram import InstagramCollector


class TestInstagramRedirectDetection:
    """Test Instagram HTTP redirect detection."""

    def test_302_redirect_detected(self):
        """Test that HTTP 302 redirects are detected as login wall/rate limit."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        # Mock _make_request to return a 302 response
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.text = ""

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            result = collector.collect()

        assert result.collection_status == "error"
        assert "302" in result.error
        assert "login wall" in result.error.lower() or "redirect" in result.error.lower()
        assert result.http_status == 302

    def test_403_forbidden_detected(self):
        """Test that HTTP 403 is detected as rate limit/blocked."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = ""

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            result = collector.collect()

        assert result.collection_status == "error"
        assert "403" in result.error
        assert result.http_status == 403

    def test_404_not_found(self):
        """Test that HTTP 404 is detected."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/nonexistent/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = ""

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            result = collector.collect()

        assert result.collection_status == "error"
        assert "404" in result.error


class TestInstagramLoginWallDetection:
    """Test Instagram login wall HTML detection."""

    def test_login_wall_detected_in_html(self):
        """Test that login wall text in HTML is detected."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        html_with_login_wall = """
        <html>
        <head><title>Log In • Instagram</title></head>
        <body>
        <h1>Log in to Instagram</h1>
        <p>See what's new from your favorite creators.</p>
        </body>
        </html>
        """

        assert collector._is_instagram_login_wall(html_with_login_wall) is True

    def test_no_login_wall_in_normal_page(self):
        """Test that normal Instagram pages without login wall pass."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        normal_html = """
        <html>
        <head><title>BSP Police (@bsppolicecg) • Instagram photos and videos</title>
        <meta property="og:title" content="BSP Police">
        </head>
        <body>
        <div>Public profile content</div>
        </body>
        </html>
        """

        assert collector._is_instagram_login_wall(normal_html) is False

    def test_private_account_detected(self):
        """Test that private account pages are detected."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/private_account/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        private_html = """
        <html>
        <head><title>This Account is Private</title></head>
        <body>
        <h1>This account is private</h1>
        <p>Follow this account to see their photos and videos.</p>
        </body>
        </html>
        """

        assert collector._is_instagram_login_wall(private_html) is True


class TestInstagramGraphAPIFallback:
    """Test Instagram Graph API fallback behavior."""

    def test_no_graph_api_token_falls_back_to_html(self):
        """Test that missing Graph API token falls back to HTML scraping."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        with patch("src.collectors.instagram.settings") as mock_settings:
            mock_settings.instagram_graph_api_token = ""
            result = collector._collect_via_graph_api("https://www.instagram.com/bsppolicecg/")

        assert result == (None, None)

    def test_graph_api_error_returned(self):
        """Test that Graph API errors are returned properly."""
        source = MagicMock()
        source.source_url = "https://www.instagram.com/bsppolicecg/"
        source.api_url = None
        source.source_type = "social_media"
        source.collection_method = "instagram"
        source.id = 1
        source.source_id = "test_instagram"

        collector = InstagramCollector(source, None)

        with patch("src.collectors.instagram.settings") as mock_settings:
            mock_settings.instagram_graph_api_token = "fake_token"

            with patch("httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_get.return_value = mock_response

                items, error = collector._collect_via_graph_api("https://www.instagram.com/bsppolicecg/")

        assert items is None
        assert error is not None
        assert "401" in error
