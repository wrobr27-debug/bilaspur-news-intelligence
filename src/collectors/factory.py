"""Collector Factory - creates collector instances based on source configuration.

This module avoids circular imports by using lazy imports inside collector classes.
"""

from typing import Dict, Type, Optional


# Collector mapping - mapped by collection_method string
# These are imported lazily to avoid circular imports
_COLLECTOR_MAP: Dict[str, type] = {}


def register_collector(method: str, collector_class: type):
    """Register a collector class for a given collection method."""
    _COLLECTOR_MAP[method] = collector_class


def get_collector_class(method: str) -> type:
    """Get the collector class for a given collection method."""
    return _COLLECTOR_MAP.get(method)


def get_collector(source, db_session) -> Optional[object]:
    """Factory function to get a collector instance for a source."""
    from src.collectors.base import BaseCollector
    
    method = getattr(source, 'collection_method', 'html')
    collector_class = _COLLECTOR_MAP.get(method)
    
    if collector_class is None:
        if method == "instagram":
            from src.collectors.instagram import InstagramCollector
            collector_class = InstagramCollector
        else:
            # Default to WebsiteCollector
            from src.collectors.website import WebsiteCollector
            collector_class = WebsiteCollector
    
    try:
        return collector_class(source, db_session)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not instantiate collector: {e}")
        return None