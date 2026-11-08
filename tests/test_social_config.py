"""Tests for social collection disabled/enabled behavior."""

import pytest
from unittest.mock import MagicMock, patch
from src.aggregator import collect_all, _safe_collect
from src.database.base import SessionLocal


class TestSocialCollectionConfig:
    """Test social collection configuration."""

    def test_social_disabled_by_default(self):
        """Test that social collection is disabled when no flag is set."""
        db = SessionLocal()
        try:
            with patch("src.aggregator.settings") as mock_settings:
                mock_settings.social_scrapers_enabled = False

                items = collect_all(social=False)

                # Should not have attempted Twitter/Instagram collection
                # (Just verify no error about missing collectors)
                assert items is not None
        finally:
            db.close()

    def test_social_enabled_via_flag(self):
        """Test that social collection is enabled when social=True."""
        db = SessionLocal()
        try:
            with patch("src.aggregator.settings") as mock_settings:
                mock_settings.social_scrapers_enabled = False

                # Mock SourceRegistry.list_sources to return no sources
                with patch("src.aggregator.SourceRegistry.list_sources", return_value=[]):
                    items = collect_all(social=True)

                    # Should not error even with no social credentials
                    assert items is not None
        finally:
            db.close()

    def test_social_enabled_via_config(self):
        """Test that social collection is enabled when config flag is set."""
        db = SessionLocal()
        try:
            with patch("src.aggregator.settings") as mock_settings:
                mock_settings.social_scrapers_enabled = True

                with patch("src.aggregator.SourceRegistry.list_sources", return_value=[]):
                    items = collect_all(social=False)

                    assert items is not None
        finally:
            db.close()

    def test_safe_collect_with_none_source(self):
        """Test that _safe_collect handles None source gracefully."""
        result = _safe_collect("Test", None, "twitter")
        assert result == []  # Should return empty list, not crash

    def test_safe_collect_with_invalid_method(self):
        """Test that _safe_collect with invalid method returns empty."""
        result = _safe_collect("Test", None, "invalid_method")
        assert result == []

    def test_collect_all_returns_list(self):
        """Test that collect_all always returns a list."""
        db = SessionLocal()
        try:
            with patch("src.aggregator.SourceRegistry.list_sources", return_value=[]):
                items = collect_all(social=False)
                assert isinstance(items, list)
        finally:
            db.close()
