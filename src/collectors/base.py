"""Base Collector Class.

Defines the common interface for all collectors. Subclasses must implement
can_collect() and collect() methods.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import logging
import time
import httpx

logger = logging.getLogger(__name__)


class CollectionResult:
    """Result of a collection operation."""

    def __init__(
        self,
        source_id: str,
        items: List = None,
        items_found: int = 0,
        items_inserted: int = 0,
        items_duplicate: int = 0,
        error: str = None,
        http_status: int = None,
        response_time_ms: float = None,
        collection_status: str = "ok",
    ):
        self.source_id = source_id
        self.items = items or []
        self.items_found = items_found
        self.items_inserted = items_inserted
        self.items_duplicate = items_duplicate
        self.error = error
        self.http_status = http_status
        self.response_time_ms = response_time_ms
        self.collection_status = collection_status


class BaseCollector(ABC):
    """Common interface for all collectors.

    Every collector must:
    1. Receive a source configuration.
    2. Check whether the source is active.
    3. Respect its configured collection interval.
    4. Fetch information with timeouts.
    5. Validate the response.
    6. Extract available metadata.
    7. Normalize the output.
    8. Return structured collected records.
    9. Report errors accurately.
    10. Record collection health.
    """

    def __init__(self, source, db_session):
        self.source = source
        self.db = db_session
        from src.config import settings
        self.timeout = settings.http_timeout_seconds
        self.connect_timeout = settings.http_connect_timeout
        self.max_retries = settings.max_retries
        self.backoff_factor = settings.backoff_factor

    @abstractmethod
    def can_collect(self, source) -> bool:
        """Check if this collector can handle the given source type."""
        pass

    @abstractmethod
    def collect(self) -> CollectionResult:
        """Perform the collection and return results."""
        pass

    def _make_request(self, url: str, params: dict = None):
        """Make an HTTP request with retries and timeout."""
        from src.registry.source_registry import SourceRegistry

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                timeout_config = httpx.Timeout(
                    connect=self.connect_timeout,
                    read=self.timeout,
                    write=self.connect_timeout,
                    pool=self.connect_timeout,
                )
                response = httpx.get(
                    url,
                    params=params,
                    timeout=timeout_config,
                    headers={
                        "User-Agent": "BilaspurNewsIntelligence/0.1 "
                        "(+https://github.com/wrobr27-debug/News-Agent)"
                    },
                )
                response_time_ms = (time.time() - start_time) * 1000

                from src.registry.source_registry import SourceRegistry
                SourceRegistry.record_check(
                    db=self.db,
                    source_id=self.source.source_id,
                    http_status=response.status_code,
                    items_found=0,
                    items_inserted=0,
                    error_type=None,
                    error_message=None,
                    collection_status="ok" if response.status_code < 400 else "error",
                )

                if response.status_code == 200:
                    return response, response_time_ms
                else:
                    logger.warning(
                        f"HTTP {response.status_code} from {url} "
                        f"(attempt {attempt + 1})"
                    )
                    if attempt < self.max_retries - 1:
                        backoff = self.backoff_factor ** attempt
                        time.sleep(backoff)
                    continue

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout requesting {url} (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    backoff = self.backoff_factor ** attempt
                    time.sleep(backoff)
                continue
            except httpx.RequestError as e:
                logger.warning(f"Request error for {url} (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    backoff = self.backoff_factor ** attempt
                    time.sleep(backoff)
                continue

        logger.error(f"All {self.max_retries} attempts failed for {url}")
        return None

    @staticmethod
    def _safe_text(text: str, maxlen: int = 500) -> str:
        """Safely truncate text."""
        if not text:
            return ""
        return text[:maxlen].strip()