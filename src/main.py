import sys
import argparse
# uvicorn import lazy-loaded for web server\nfrom pathlib import Path
from src.database.base import get_session, engine, Base
from src.registry.source_registry import SourceRegistry
from src.collectors.rss import RSSCollector
from src.collectors.website import WebsiteCollector, GovtWebsiteCollector
from src.collectors.youtube import YouTubeCollector
from src.config import settings
from src.database.models import Sources, CollectedItems, CollectionRuns, SourceHealth

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_SCHEDULER = True


def init_db():
    """Verify database connectivity.

    Returns True if connection succeeds, False if it fails.

    Schema creation is handled by Alembic migrations (authoritative),
    not by SQLAlchemy create_all(), to avoid schema drift between
    models and migrations on production PostgreSQL.
    """
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception as e:
        print(f"Database initialization failed: {e}")
        return False


def run_collect():
    """Run collection due sources."""
    from src.database.base import get_session
    from src.collectors.factory import get_collector
    from src.database.models import CollectedItems
    
    db = get_session()
    try:
        # Identify sources due for collection
        due_sources = SourceRegistry.identify_sources_due(db)
        
        if not due_sources:
            print("No sources due for collection at this time.")
            return

        print(f"Collecting from {len(due_sources)} sources due...")
        
        total_items_found = 0
        total_items_inserted = 0
        total_items_duplicate = 0
        sources_processed = 0
        
        for source in due_sources:
            sources_processed += 1
            print(f"\n--- Collecting: {source.source_name} ({source.source_type}) ---")
            
            # Determine which collector to use
            collector = get_collector(source, db)
            if not collector:
                print(f"  No collector available for type: {source.source_type}")
                continue
            
            result = collector.collect()
            
            print(f"  Items found: {result.items_found}")
            print(f"  Items inserted: {result.items_inserted}")
            print(f"  Items duplicate: {result.items_duplicate}")
            if result.error:
                print(f"  Error: {result.error}")
            
            total_items_found += result.items_found
            total_items_inserted += result.items_inserted
            total_items_duplicate += result.items_duplicate
            
            # Small delay to avoid rate limiting
            import time
            time.sleep(1)
        
        print(f"\n=== Collection Summary ===")
        print(f"Database dialect: {engine.dialect.name}")
        print(f"Total sources: {len(SourceRegistry.list_sources(db, active_only=False))}")
        active_sources = SourceRegistry.list_sources(db, active_only=True)
        print(f"Active sources: {len(active_sources)}")
        print(f"Due sources: {len(due_sources)}")
        print(f"Sources processed: {sources_processed}")
        print(f"Total items found: {total_items_found}")
        print(f"Total items inserted: {total_items_inserted}")
        print(f"Total items duplicate: {total_items_duplicate}")
        
    except Exception as e:
        print(f"Collection error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def run_collect_source(source_id: str):
    """Collect a specific source by ID."""
    from src.database.base import get_session
    from src.collectors.factory import get_collector
    db = get_session()
    try:
        source = SourceRegistry.get_source(db, source_id)
        if not source:
            print(f"Source not found: {source_id}")
            return
        
        print(f"Collecting: {source.source_name} ({source.source_id})")
        print(f"Type: {source.source_type}, Method: {source.collection_method}")
        
        # Determine collector
        collector = get_collector(source, db)
        if not collector:
            print(f"No collector for type: {source.source_type}")
            return
        
        result = collector.collect()
        
        print(f"\nResult:")
        print(f"  Items found: {result.items_found}")
        print(f"  Items inserted: {result.items_inserted}")
        print(f"  Items duplicate: {result.items_duplicate}")
        if result.error:
            print(f"  Error: {result.error}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def list_sources(source_id: str = None):
    """List all sources or a specific source."""
    from src.database.base import get_session
    db = get_session()
    try:
        if source_id:
            source = SourceRegistry.get_source(db, source_id)
            if source:
                print_source(source)
            else:
                print(f"Source not found: {source_id}")
        else:
            sources = SourceRegistry.list_sources(db, active_only=False)
            print(f"\nTotal sources: {len(sources)}")
            print(f"{'ID':<30} {'Name':<40} {'Type':<15} {'URL':<50} {'Active'}")
            print("-" * 145)
            for s in sources:
                active = "✓" if s.active else "✗"
                print(f"{s.source_id:<30} {s.source_name:<40} {s.source_type:<15} {s.source_url:<50} {active}")
    finally:
        db.close()


def print_source(source: Sources):
    """Print source details."""
    print(f"\nSource Details:")
    print(f"  ID: {source.source_id}")
    print(f"  Name: {source.source_name}")
    print(f"  Publisher: {source.publisher_name or 'N/A'}")
    print(f"  Type: {source.source_type}")
    print(f"  Category: {source.source_category}")
    print(f"  URL: {source.source_url}")
    print(f"  RSS/Atom: {source.rss_url or 'N/A'}")
    print(f"  API: {source.api_url or 'N/A'}")
    print(f"  Collection Method: {source.collection_method}")
    print(f"  Geography: {source.geography or 'N/A'}")
    print(f"  Language: {source.language}")
    print(f"  Reliability: {source.reliability_level}")
    print(f"  Active: {source.active}")
    print(f"  Interval: {source.collection_interval_minutes} min")
    print(f"  Last checked: {source.last_checked_at}")
    print(f"  Last success: {source.last_success_at}")
    print(f"  Next collection: {source.next_collection_at}")
    print(f"  Status: {source.collection_status}")
    print(f"  Notes: {source.notes or 'N/A'}")


def sources_check():
    """Check source health status."""
    from src.database.base import get_session
    db = get_session()
    try:
        sources = SourceRegistry.list_sources(db, active_only=True)
        print(f"\n{'Source':<30} {'Status':<15} {'Last checked':<20} {'Failures':<10} {'Next collection'}")
        print("-" * 120)
        for s in sources:
            next_col = s.next_collection_at or "N/A"
            print(f"{s.source_id:<30} {s.collection_status:<15} {str(s.last_checked_at):<20} {s.consecutive_failures:<10} {str(next_col):<20}")
    finally:
        db.close()


def run_health():
    """Run health check on all sources."""
    from src.database.base import get_session
    from src.registry.source_registry import SourceRegistry
    db = get_session()
    try:
        due = SourceRegistry.identify_sources_due(db)
        print(f"Checking health for {len(due)} due sources...")
        
        for source in due[:5]:  # Check first 5
            print(f"\n{source.source_name}:")
            # Try a simple HTTP check
            import httpx
            try:
                resp = httpx.head(
                    source.source_url,
                    timeout=10,
                    headers={"User-Agent": "BilaspurNewsIntelligence/0.1"}
                )
                print(f"  HTTP {resp.status_code} - {source.source_url[:60]}...")
            except Exception as e:
                print(f"  Error: {e}")
    finally:
        db.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bilaspur News Intelligence - Source Collection System"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Collect command
    collect_parser = subparsers.add_parser("collect", help="Run collection due sources")
    collect_parser.add_argument("--source", type=str, help="Collect specific source by ID")
    
    # List sources
    list_parser = subparsers.add_parser("list", help="List all sources")
    list_parser.add_argument("--source", type=str, help="Show specific source details")
    
    # Check sources
    check_parser = subparsers.add_parser("check", help="Check source health/status")
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Run health check")
    
    # Init DB
    init_parser = subparsers.add_parser("init", help="Initialize database")
    
    # Seed command
    seed_parser = subparsers.add_parser("seed", help="Seed initial sources")
    seed_parser.add_argument("--force", action="store_true", help="Force reseeding")
    
    # Check config command
    check_parser = subparsers.add_parser("check-config", help="Validate deployment configuration")
    
    args = parser.parse_args()
    
    if not init_db():
        print("Cannot proceed without database connection.")
        sys.exit(1)
    
    if args.command == "collect":
        if args.source:
            run_collect_source(args.source)
        else:
            run_collect()
    elif args.command == "list":
        list_sources(args.source)
    elif args.command == "check":
        sources_check()
    elif args.command == "health":
        run_health()
    elif args.command == "init":
        print("Database initialized.")
    elif args.command == "seed":
        from scripts.seed_sources import seed_initial_sources
        seed_initial_sources(force=args.force)
    elif args.command == "check-config":
        # Validate configuration without exposing secrets
        from src.config import settings
        from src.database.base import engine
        import json
        
        print("=== Configuration Validation ===")
        print(f"Database URL: {settings.database_url}")
        
        # Test URL normalization
        url = settings.database_url
        if url.startswith("postgresql://") and "+psycopg" not in url:
            normalized = url.replace("postgresql://", "postgresql+psycopg://", 1)
            print(f"Normalized URL: {normalized}")
        else:
            print(f"URL is already normalized or SQLite: {url}")
        
        # Test engine connection
        try:
            with engine.connect() as conn:
                dialect = conn.dialect.name
                conn.exec_driver_sql("SELECT 1")
                print(f"Database connection: OK ({dialect})")
        except Exception as e:
            print(f"Database connection: Failed - {e}")
            sys.exit(1)
        
        print("Configuration validation complete.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()