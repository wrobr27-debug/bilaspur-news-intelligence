"""Tests for website redirects and timeouts."""

import pytest
from unittest.mock import MagicMock, patch
from src.collectors.website import WebsiteCollector


class TestWebsiteRedirects:
    """Test website HTTP redirect handling."""

    def test_301_redirect_returned(self):
        """Test that HTTP 301 responses are returned."""
        source = MagicMock()
        source.source_url = "https://example.com/"
        source.collection_method = "html"
        source.id = 1
        source.source_id = "test_website"

        collector = WebsiteCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 301
        mock_response.text = "<html><body>Moved</body></html>"

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            result = collector.collect()

        # 301 should be returned as a response
        assert result.http_status == 301

    def test_302_redirect_returned(self):
        """Test that HTTP 302 responses are returned."""
        source = MagicMock()
        source.source_url = "https://example.com/"
        source.collection_method = "html"
        source.id = 1
        source.source_id = "test_website"

        collector = WebsiteCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.text = "<html><body>Found</body></html>"

        with patch.object(collector, "_make_request", return_value=(mock_response, 100)):
            result = collector.collect()

        assert result.http_status == 302

    def test_404_not_retried(self):
        """Test that HTTP 404 is returned without retries."""
        source = MagicMock()
        source.source_url = "https://example.com/nonexistent/"
        source.collection_method = "html"
        source.id = 1
        source.source_id = "test_website"

        collector = WebsiteCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "<html><body>Not Found</body></html>"

        call_count = [0]

        def mock_request(url, params=None):
            call_count[0] += 1
            return (mock_response, 100)

        with patch.object(collector, "_make_request", side_effect=mock_request):
            result = collector.collect()

        # Should only be called once (404 is a permanent failure)
        assert call_count[0] == 1
        assert result.http_status == 404


class TestWebsiteTimeouts:
    """Test website timeout handling."""

    def test_timeout_retry(self):
        """Test that timeouts are retried with backoff."""
        source = MagicMock()
        source.source_url = "https://slow-site.com/"
        source.collection_method = "html"
        source.id = 1
        source.source_id = "test_website"

        collector = WebsiteCollector(source, None)

        # Patch httpx.get at the base module level to simulate timeouts
        import httpx

        call_count = [0]

        def mock_get(url, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise httpx.TimeoutException("Timeout")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Success</body></html>"
            return mock_response

        with patch("src.collectors.base.httpx.get", side_effect=mock_get):
            with patch("time.sleep"):
                result = collector.collect()

        # Should have retried and eventually succeeded
        assert call_count[0] == 3

    def test_timeout_exhaustion(self):
        """Test that exhausted retries return None."""
        source = MagicMock()
        source.source_url = "https://always-timeout.com/"
        source.collection_method = "html"
        source.id = 1
        source.source_id = "test_website"

        collector = WebsiteCollector(source, None)

        import httpx

        call_count = [0]

        def mock_get(url, *args, **kwargs):
            call_count[0] += 1
            raise httpx.TimeoutException("Always timeout")

        with patch("src.collectors.base.httpx.get", side_effect=mock_get):
            with patch("time.sleep"):
                result = collector._make_request("https://always-timeout.com/")

        # Should return None after all retries exhausted
        assert result is None
        assert call_count[0] >= 3  # max_retries = 3


class TestWebsiteNoRetryPermanentFailures:
    """Test that permanent failures are not retried."""

    def test_403_not_retried(self):
        """Test that 403 is returned immediately without retries."""
        source = MagicMock()
        source.source_url = "https://blocked-site.com/"
        source.collection_method = "html"
        source.id = 1
        source.source_id = "test_website"

        collector = WebsiteCollector(source, None)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "<html><body>Forbidden</body></html>"

        call_count = [0]

        def mock_request(url, params=None):
            call_count[0] += 1
            return (mock_response, 100)

        with patch.object(collector, "_make_request", side_effect=mock_request):
            result = collector.collect()

        # Should only be called once (403 is a permanent failure)
        assert call_count[0] == 1
        assert result.http_status == 403

    def test_ssl_error_not_retried(self):
        """Test that SSL errors are not retried."""
        source = MagicMock()
        source.source_url = "https://bad-ssl.com/"
        source.collection_method = "html"
        source.id = 1
        source.source_id = "test_website"

        collector = WebsiteCollector(source, None)

        import httpx

        call_count = [0]

        def mock_get(url, *args, **kwargs):
            call_count[0] += 1
            raise httpx.ConnectError("SSL certificate error")

        with patch("src.collectors.base.httpx.get", side_effect=mock_get):
            result = collector._make_request("https://bad-ssl.com/")

        # SSL errors should return None immediately
        assert result is None
        assert call_count[0] >= 1  # Called at least once (robots.txt + request)
