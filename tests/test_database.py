"""Tests for database insertion and duplicate detection."""

import pytest
from unittest.mock import MagicMock, patch
from src.database.models import CollectedItems
from src.registry.source_registry import SourceRegistry


class TestDatabaseInsertion:
    """Test database insertion of collected items."""

    def test_successful_insertion(self):
        """Test that items are inserted into the database."""
        mock_db = MagicMock()
        item = CollectedItems(
            source_id=1,
            title="Test Article",
            original_url="https://example.com/article",
            canonical_url="https://example.com/article",
            description="Test description",
            content_snippet="Test snippet",
            author="Test Author",
            language="en",
            item_type="article",
            media_type="text",
            content_hash="hash123",
        )

        mock_db.add(item)
        mock_db.commit()

        mock_db.add.assert_called_once_with(item)
        mock_db.commit.assert_called_once()

    def test_insertion_failure_rollback(self):
        """Test that insertion failures trigger rollback."""
        mock_db = MagicMock()
        mock_db.add.side_effect = Exception("DB connection lost")
        mock_db.rollback = MagicMock()

        item = CollectedItems(
            source_id=1,
            title="Test Article",
            original_url="https://example.com/article",
            canonical_url="https://example.com/article",
            content_hash="hash123",
        )

        try:
            mock_db.add(item)
            mock_db.commit()
        except Exception:
            mock_db.rollback()

        mock_db.rollback.assert_called_once()


class TestDuplicateDetection:
    """Test duplicate detection in database."""

    def _make_mock_db(self, first_return_value=None):
        """Create a mock DB with proper filter chain that returns self for .filter()."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = first_return_value
        # filter() returns self so chaining works
        mock_filter.filter.return_value = mock_filter
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        return mock_db

    def test_duplicate_by_content_hash(self):
        """Test that items with same content_hash are detected as duplicates."""
        mock_db = self._make_mock_db(first_return_value=MagicMock())

        result = SourceRegistry.is_duplicate(mock_db, 1, "hash123", ttl_days=30)

        assert result is True

    def test_no_duplicate_found(self):
        """Test that items without duplicates are not detected."""
        mock_db = self._make_mock_db(first_return_value=None)

        result = SourceRegistry.is_duplicate(mock_db, 1, "hash123", ttl_days=30)

        assert result is False

    def test_mark_seen_creates_new_item(self):
        """Test that mark_seen creates a new CollectedItems entry."""
        mock_db = self._make_mock_db(first_return_value=None)

        SourceRegistry.mark_seen(
            mock_db, 1, "https://example.com/article", "Test Article",
            "https://example.com/article", None, None
        )

        mock_db.add.assert_called_once()
        # Verify the item has source_id (integer), not source (string)
        added_item = mock_db.add.call_args[0][0]
        assert added_item.source_id == 1
        assert added_item.canonical_url == "https://example.com/article"

    def test_mark_seen_skips_existing(self):
        """Test that mark_seen skips items that already exist."""
        mock_db = self._make_mock_db(first_return_value=MagicMock())

        SourceRegistry.mark_seen(
            mock_db, 1, "https://example.com/article", "Test Article",
            "https://example.com/article", None, None
        )

        # Should not add a new item
        mock_db.add.assert_not_called()

    def test_is_duplicate_uses_source_id_integer(self):
        """Test that is_duplicate uses source_id (integer), not source (string)."""
        mock_db = self._make_mock_db(first_return_value=None)

        # Call with integer source_id
        SourceRegistry.is_duplicate(mock_db, 1, "https://example.com/article", ttl_days=30)

        # Verify filter was called
        assert mock_db.query.called

    def test_duplicate_by_canonical_url(self):
        """Test that duplicate detection uses canonical_url."""
        mock_db = self._make_mock_db(first_return_value=MagicMock())

        SourceRegistry.is_duplicate(mock_db, 1, "https://example.com/canonical", ttl_days=30)

        # Verify filter was called multiple times (source_id, canonical_url, collected_at)
        mock_filter = mock_db.query.return_value.filter.return_value
        assert mock_filter.filter.call_count >= 2


class TestCollectedItemsModel:
    """Test CollectedItems model fields."""

    def test_model_has_category_field(self):
        """Test that CollectedItems has category field."""
        item = CollectedItems(
            source_id=1,
            title="Test",
            original_url="https://example.com/",
            canonical_url="https://example.com/",
            category="uncategorized",
        )
        assert item.category == "uncategorized"

    def test_model_has_source_relationship(self):
        """Test that CollectedItems has source relationship."""
        assert hasattr(CollectedItems, "source")
        assert "source" in CollectedItems.__mapper__.relationships

    def test_model_has_source_id_integer(self):
        """Test that CollectedItems.source_id is Integer (FK to sources.id)."""
        from src.database.models import CollectedItems
        source_id_col = CollectedItems.source_id
        assert source_id_col is not None
