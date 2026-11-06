from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    JSON,
    func,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from src.database.base import Base


class Sources(Base):
    """Source Registry - Central registry of all news sources."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(100), unique=True, nullable=False, index=True)
    source_name = Column(String(200), nullable=False)
    publisher_name = Column(String(200))
    source_type = Column(
        SAEnum(
            "government",
            "police",
            "newspaper",
            "television",
            "youtube",
            "social_media",
            "education",
            "transport",
            "health",
            "business",
            "rural",
            "agriculture",
            "environment",
            "other",
            name="source_type_enum",
        ),
        nullable=False,
        comment="Type: government|police|newspaper|television|youtube|social_media|education|transport|health|business|rural|agriculture|environment|other",
    )
    source_category = Column(
        SAEnum(
            "city",
            "district",
            "state",
            "regional",
            name="source_category_enum",
        ),
        nullable=False,
        comment="Category: city|district|state|regional",
    )
    source_url = Column(String(500), nullable=False)
    content_url = Column(String(500), comment="Specific news/announcement page URL")
    rss_url = Column(String(500), comment="Verified RSS/Atom feed URL")
    api_url = Column(String(500), comment="Official API endpoint")
    sitemap_url = Column(String(500), comment="Verified sitemap.xml URL")
    geography = Column(
        String(50),
        comment="Geographic scope: city|district|state|regional",
    )
    language = Column(String(10), default="en", comment="Language code: en|hi|hi-IN")
    collection_method = Column(
        SAEnum(
            "rss",
            "atom",
            "api",
            "html",
            "instagram",
            "manual",
            name="collection_method_enum",
        ),
        comment="Method: rss|atom|api|html|instagram|manual",
    )
    reliability_level = Column(
        SAEnum(
            "official",
            "established_publisher",
            "independent",
            "unverified",
            name="reliability_level_enum",
        ),
        comment="Official|established_publisher|independent|unverified",
    )
    active = Column(Boolean, default=True)
    collection_interval_minutes = Column(
        Integer,
        default=60,
        comment="How often to collect in minutes",
    )
    last_checked_at = Column(DateTime(timezone=True), server_default=func.now())
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    next_collection_at = Column(DateTime(timezone=True), nullable=True)
    last_http_status = Column(Integer, nullable=True)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    collection_status = Column(
        String(30),
        default="pending",
        comment="pending|ok|error|inactive|blocked",
    )
    terms_url = Column(String(500), comment="Terms of use / robots.txt location")
    notes = Column(Text, comment="Discovery notes / verification status")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships - with explicit primaryjoin to avoid SQLAlchemy auto-detection issues
    collection_runs = relationship(
        "CollectionRuns",
        back_populates="source",
        cascade="all, delete-orphan",
        primaryjoin="Sources.id == CollectionRuns.source_id",
    )
    source_health = relationship(
        "SourceHealth",
        back_populates="source",
        primaryjoin="Sources.id == SourceHealth.source_id",
    )


class CollectedItems(Base):
    """Collected Items - Individual news items collected from sources."""

    __tablename__ = "collected_items"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(200), comment="External ID from source (e.g., video ID, article hash)")
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    external_id = Column(String(200), comment="Normalized external identifier")
    title = Column(String(500), nullable=False)
    original_url = Column(String(500), nullable=False, index=True)
    canonical_url = Column(String(500), comment="Canonical/deduplicated URL")
    description = Column(Text, comment="Brief description/excerpt")
    content_snippet = Column(Text, comment="Short content snippet")
    author = Column(String(200), comment="Article author")
    published_at = Column(DateTime(timezone=True), comment="Original publication timestamp")
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    language = Column(String(10), default="en", comment="Language code")
    item_type = Column(
        SAEnum(
            "article",
            "video",
            "announcement",
            "event",
            name="item_type_enum",
        ),
        default="article",
        comment="article|video|announcement|event",
    )
    media_type = Column(
        SAEnum(
            "image",
            "video",
            "text",
            "audio",
            name="media_type_enum",
        ),
        default="image",
        comment="image|video|text|audio",
    )
    image_url = Column(String(500), comment="Featured image URL")
    video_url = Column(String(500), comment="Video URL (YouTube/Facebook/etc.)")
    raw_metadata = Column(JSON, comment="Full metadata as JSON")
    content_hash = Column(String(64), unique=True, comment="SHA-256 hash for deduplication")
    collection_status = Column(
        String(30),
        default="collected",
        comment="collected|duplicate|skipped|error",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_collected_items_content_hash", "content_hash"),
        Index("ix_collected_items_published_at", "published_at"),
    )

    @property
    def is_duplicate(self) -> bool:
        """Check if this item already exists based on content_hash or canonical_url."""
        return bool(self.content_hash or self.canonical_url)


class CollectionRuns(Base):
    """Collection Runs - Track each collection execution."""

    __tablename__ = "collection_runs"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        String(30),
        default="running",
        comment="running|completed|failed",
    )
    sources_attempted = Column(Integer, default=0, nullable=False)
    sources_succeeded = Column(Integer, default=0, nullable=False)
    sources_failed = Column(Integer, default=0, nullable=False)
    items_discovered = Column(Integer, default=0, nullable=False)
    items_inserted = Column(Integer, default=0, nullable=False)
    items_duplicate = Column(Integer, default=0, nullable=False)
    error_summary = Column(Text, comment="JSON summary of errors")

    # Relationship
    source = relationship("Sources", back_populates="collection_runs")


class SourceHealth(Base):
    """Source Health - Track collection health per source."""

    __tablename__ = "source_health"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String, nullable=False, index=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(
        String(30),
        default="ok",
        comment="ok|blocked|unavailable|error",
    )
    http_status = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    items_found = Column(Integer, default=0, nullable=False)
    items_inserted = Column(Integer, default=0, nullable=False)
    error_type = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_source_health_source_checked", "source_id", "checked_at"),
    )

    # Relationship
    source = relationship("Sources", back_populates="source_health")