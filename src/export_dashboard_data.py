"""Export dashboard data from database to JSON for GitHub Pages dashboard.

This script reads collected items, sources, and collection runs from the
database and writes them to a JSON file that the static HTML dashboard
can read directly (no backend server needed for GitHub Pages hosting).
"""

import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.base import get_session, engine
from src.database.models import Sources, CollectedItems, CollectionRuns, SourceHealth
from src.registry.source_registry import SourceRegistry


def export_dashboard_data(output_path: str = "docs/data/news-data.json"):
    """Export all dashboard-relevant data to JSON."""
    db = get_session()
    try:
        # Get all sources
        sources = SourceRegistry.list_sources(db, active_only=False)
        sources_data = []
        for s in sources:
            sources_data.append({
                "id": s.id,
                "source_id": s.source_id,
                "source_name": s.source_name,
                "publisher_name": s.publisher_name,
                "source_type": s.source_type,
                "source_category": s.source_category,
                "source_url": s.source_url,
                "collection_method": s.collection_method,
                "reliability_level": s.reliability_level,
                "active": s.active,
                "collection_interval_minutes": s.collection_interval_minutes,
                "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
                "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
                "next_collection_at": s.next_collection_at.isoformat() if s.next_collection_at else None,
                "last_http_status": s.last_http_status,
                "consecutive_failures": s.consecutive_failures,
                "collection_status": s.collection_status,
                "geography": s.geography,
                "language": s.language,
                "notes": s.notes,
            })

        # Get all collected items joined with source info
        items = (
            db.query(CollectedItems, Sources)
            .join(Sources, CollectedItems.source_id == Sources.id)
            .order_by(CollectedItems.collected_at.desc())
            .all()
        )
        
        news_items = []
        for item, source in items:
            news_items.append({
                "id": item.id,
                "source_id": source.source_id,
                "source_name": source.source_name,
                "source_type": source.source_type,
                "source_category": source.source_category,
                "collection_method": source.collection_method,
                "title": item.title,
                "description": item.description,
                "content_snippet": item.content_snippet,
                "original_url": item.original_url,
                "canonical_url": item.canonical_url,
                "author": item.author,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "discovered_at": item.discovered_at.isoformat() if item.discovered_at else None,
                "collected_at": item.collected_at.isoformat() if item.collected_at else None,
                "language": item.language,
                "item_type": item.item_type,
                "media_type": item.media_type,
                "image_url": item.image_url,
                "video_url": item.video_url,
                "collection_status": item.collection_status,
                "content_hash": item.content_hash,
            })

        # Get latest collection run info
        latest_run = (
            db.query(CollectionRuns)
            .order_by(CollectionRuns.started_at.desc())
            .first()
        )
        
        run_info = None
        if latest_run:
            run_info = {
                "run_id": latest_run.run_id,
                "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
                "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
                "status": latest_run.status,
                "sources_attempted": latest_run.sources_attempted,
                "sources_succeeded": latest_run.sources_succeeded,
                "sources_failed": latest_run.sources_failed,
                "items_discovered": latest_run.items_discovered,
                "items_inserted": latest_run.items_inserted,
                "items_duplicate": latest_run.items_duplicate,
                "timestamp": (latest_run.completed_at or latest_run.started_at or datetime.now(timezone.utc)).isoformat(),
            }

        # Get source health summary
        health_summary = {}
        health_entries = db.query(SourceHealth).all()
        for h in health_entries:
            health_summary[h.source_id] = {
                "status": h.status,
                "http_status": h.http_status,
                "items_found": h.items_found,
                "items_inserted": h.items_inserted,
                "checked_at": h.checked_at.isoformat() if h.checked_at else None,
            }

        # Build export
        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_items": len(news_items),
            "total_sources": len(sources_data),
            "active_sources": len([s for s in sources_data if s["active"]]),
            "news_items": news_items,
            "sources": sources_data,
            "last_collection_run": run_info,
            "source_health": health_summary,
        }

        # Write JSON file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

        print(f"✓ Dashboard data exported to {output_path}")
        print(f"  Total items: {len(news_items)}")
        print(f"  Total sources: {len(sources_data)}")
        print(f"  Active sources: {len([s for s in sources_data if s['active']])}")
        if run_info:
            print(f"  Last run: {run_info['timestamp']}")
            print(f"  Run status: {run_info['status']}")
            print(f"  Items inserted: {run_info['items_inserted']}")

        return export_data

    except Exception as e:
        print(f"✗ Error exporting dashboard data: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()


if __name__ == "__main__":
    export_dashboard_data()