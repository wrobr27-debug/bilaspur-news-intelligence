from sqlalchemy.orm import Session
from src.database.models import Sources, CollectedItems, CollectionRuns, SourceHealth
from datetime import datetime, timezone


class SourceRegistry:
    """Central Source Registry - manages all registered news sources.

    This module provides CRUD operations and health tracking for the
    central source registry, replacing scattered hardcoded source lists.
    """

    @staticmethod
    def add_source(
        db: Session,
        source_id: str,
        source_name: str,
        publisher_name: str = "",
        source_type: str = "other",
        source_category: str = "general",
        source_url: str = "",
        content_url: str = "",
        rss_url: str = "",
        api_url: str = "",
        sitemap_url: str = "",
        geography: str = "general",
        language: str = "en",
        collection_method: str = "html",
        reliability_level: str = "unverified",
        active: bool = False,
        collection_interval_minutes: int = 60,
        terms_url: str = "",
        notes: str = "",
    ) -> Sources:
        """Add a new source to the registry."""
        from datetime import datetime, timezone
        db_source = Sources(
            source_id=source_id,
            source_name=source_name,
            publisher_name=publisher_name,
            source_type=source_type,
            source_category=source_category,
            source_url=source_url,
            content_url=content_url,
            rss_url=rss_url,
            api_url=api_url,
            sitemap_url=sitemap_url,
            geography=geography,
            language=language,
            collection_method=collection_method,
            reliability_level=reliability_level,
            active=active,
            collection_interval_minutes=collection_interval_minutes,
            last_checked_at=datetime.now(timezone.utc),
            last_success_at=None,
            next_collection_at=datetime.now(timezone.utc),
            last_http_status=None,
            consecutive_failures=0,
            collection_status="pending",
            terms_url=terms_url,
            notes=notes,
        )
        db.add(db_source)
        db.commit()
        db.refresh(db_source)
        return db_source

    @staticmethod
    def get_source(db: Session, source_id: str) -> Sources | None:
        """Get a source by its stable source_id."""
        return db.query(Sources).filter(Sources.source_id == source_id).first()

    @staticmethod
    def get_source_by_id(db: Session, source_id_int: int) -> Sources | None:
        """Get a source by its auto-increment ID."""
        return db.query(Sources).filter(Sources.id == source_id_int).first()

    @staticmethod
    def list_sources(
        db: Session,
        active_only: bool = False,
        source_type: str = None,
        source_category: str = None,
    ) -> list[Sources]:
        """List sources with optional filtering."""
        query = db.query(Sources)
        if active_only:
            query = query.filter(Sources.active == True)
        if source_type:
            query = query.filter(Sources.source_type == source_type)
        if source_category:
            query = query.filter(Sources.source_category == source_category)
        return query.order_by(Sources.source_name).all()

    @staticmethod
    def list_active_sources(db: Session) -> list[Sources]:
        """List all active sources due for collection."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        # Sources due for collection: next_collection_at is None or <= now
        return (
            db.query(Sources)
            .filter(Sources.active == True)
            .filter(
                Sources.next_collection_at.is_(None)
                | Sources.next_collection_at <= now
            )
            .order_by(Sources.collection_interval_minutes)
            .all()
        )

    @staticmethod
    def enable_source(db: Session, source_id: str) -> Sources | None:
        """Enable a source."""
        db_source = SourceRegistry.get_source(db, source_id)
        if db_source:
            db_source.active = True
            db_source.collection_status = "pending"
            db.commit()
            db.refresh(db_source)
        return db_source

    @staticmethod
    def disable_source(db: Session, source_id: str) -> Sources | None:
        """Disable a source."""
        db_source = SourceRegistry.get_source(db, source_id)
        if db_source:
            db_source.active = False
            db_source.collection_status = "inactive"
            db.commit()
            db.refresh(db_source)
        return db_source

    @staticmethod
    def update_source_interval(db: Session, source_id: str, minutes: int) -> Sources | None:
        """Update the collection interval for a source."""
        db_source = SourceRegistry.get_source(db, source_id)
        if db_source:
            db_source.collection_interval_minutes = minutes
            db_source.next_collection_at = None  # Will be recalculated on next collection
            db.commit()
            db.refresh(db_source)
        return db_source

    @staticmethod
    def record_check(
        db: Session,
        source_id: str,
        http_status: int | None,
        items_found: int,
        items_inserted: int,
        error_type: str | None = None,
        error_message: str | None = None,
        collection_status: str = "ok",
    ) -> SourceHealth:
        """Record a collection check for source health tracking."""
        from src.database.models import SourceHealth
        from src.config import settings

        # Calculate next collection time
        interval_map = {
            "government": settings.government_interval,
            "newspaper": settings.newspaper_interval,
            "youtube": settings.youtube_interval,
            "lower_priority": settings.lower_priority_interval,
        }
        # Determine interval based on source type
        source = SourceRegistry.get_source(db, source_id)
        interval = settings.default_collection_interval
        if source:
            if source.source_type in ["government"]:
                interval = settings.government_interval
            elif source.source_type in ["newspaper"]:
                interval = settings.newspaper_interval
            elif source.source_type in ["youtube"]:
                interval = settings.youtube_interval
            else:
                interval = settings.lower_priority_interval

        from datetime import datetime, timezone, timedelta
        next_collection = datetime.now(timezone.utc) + timedelta(minutes=interval)

        health_entry = SourceHealth(
            source_id=source_id,
            status=collection_status,
            http_status=http_status,
            response_time_ms=None,  # Will be set by caller if needed
            items_found=items_found,
            items_inserted=items_inserted,
            error_type=error_type,
            error_message=error_message,
        )
        db.add(health_entry)

        # Update source tracking fields
        db_source = SourceRegistry.get_source(db, source_id)
        if db_source:
            db_source.last_checked_at = datetime.now(timezone.utc)
            db_source.last_success_at = datetime.now(timezone.utc) if collection_status == "ok" and items_inserted > 0 else db_source.last_success_at
            db_source.next_collection_at = next_collection
            db_source.last_http_status = http_status
            if collection_status != "ok":
                db_source.consecutive_failures += 1
            else:
                db_source.consecutive_failures = max(0, db_source.consecutive_failures - 1)
            db_source.collection_status = collection_status
            db.commit()
            db.refresh(db_source)

        return health_entry

    @staticmethod
    def identify_sources_due(db: Session) -> list[Sources]:
        """Identify sources that are due for collection based on intervals."""
        from src.database.models import Sources
        from sqlalchemy import or_
        now = datetime.now(timezone.utc)
        return (
            db.query(Sources)
            .filter(Sources.active == True)
            .filter(
                or_(
                    Sources.next_collection_at.is_(None),
                    Sources.next_collection_at <= now,
                )
            )
            .all()
        )

    @staticmethod
    def update_source_last_success(db: Session, source_id: str) -> Sources | None:
        """Update source last_success_at after successful collection."""
        db_source = SourceRegistry.get_source(db, source_id)
        if db_source:
            db_source.last_success_at = datetime.now(timezone.utc)
            db_source.consecutive_failures = 0
            db_source.collection_status = "ok"
            db.commit()
            db.refresh(db_source)
        return db_source