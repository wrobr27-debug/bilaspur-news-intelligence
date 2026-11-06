"""News aggregation pipeline with deduplication and summarization.

Adapted from News-Agent pattern for Bilaspur News Intelligence.
"""

from datetime import datetime
from pathlib import Path
import math
import re
import logging

from src.database.base import SessionLocal, engine
from src.database.models import Sources, CollectedItems, SourceHealth
from src.collectors.factory import get_collector
from src.registry.source_registry import SourceRegistry
from src.config import settings
from src.summarizer import summarize_items

logger = logging.getLogger(__name__)

STOP_WORDS = {
    'in', 'the', 'a', 'of', 'to', 'and', 'is', 'for', 'at', 'by', 'from', 'on', 'with', 'as', 'an', 'it', 'its', 'that', 'this', 'are', 'was', 'were', 'be', 'been', 'has', 'have', 'had', 'will', 'would', 'should', 'can', 'could', 'about', 'after', 'before', 'new', 'news'
}


def _safe_collect(name: str, source, db) -> list:
    """Safely collect from a single source, catching exceptions."""
    try:
        logger.info(f"  {name}...", end=" ")
        collector = get_collector(source, db)
        if not collector:
            logger.info("0 items (no collector)")
            return []
        result = collector.collect()
        logger.info(f"{result.items_found} items (inserted: {result.items_inserted})")
        if result.error:
            logger.warning(f"  {name} error: {result.error}")
        return result.items if hasattr(result, 'items') and result.items else []
    except Exception as e:
        logger.error(f"  {name} ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []


def collect_all(social: bool = False) -> list:
    """Collect items from all active sources."""
    db = SessionLocal()
    items = []
    try:
        sources = SourceRegistry.list_sources(db, active_only=True)
        logger.info(f"Collecting from {len(sources)} active sources...")

        for source in sources:
            source_items = _safe_collect(f"{source.source_id} ({source.source_type})", source, db)
            items.extend(source_items)

        if social or getattr(settings, 'social_scrapers_enabled', False):
            logger.info("  Collecting social media...")
            items += _safe_collect("Twitter", None, db, _scrape_twitter)
            items += _safe_collect("Instagram", None, db, _scrape_instagram)

    finally:
        db.close()

    return items


def _scrape_twitter(db):
    """Scrape Twitter for news."""
    from src.sources.twitter_scraper import scrape_all
    return scrape_all(settings.twitter_handle)


def _scrape_instagram(db):
    """Scrape Instagram for news."""
    from src.sources.instagram_scraper import scrape_all
    return scrape_all()


def tokenize(text: str) -> list:
    """Tokenize text for deduplication."""
    words = re.findall(r'[a-zA-Z0-9\u0900-\u097F]+', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def cosine_similarity(vec1: dict, vec2: dict) -> float:
    """Calculate cosine similarity between two word frequency vectors."""
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum(vec1[w] * vec2[w] for w in intersection)

    sum1 = sum(val ** 2 for val in vec1.values())
    sum2 = sum(val ** 2 for val in vec2.values())

    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    if not denominator:
        return 0.0
    return numerator / denominator


def deduplicate_semantic(items: list, threshold: float = 0.4) -> list:
    """Remove semantically similar items using cosine similarity."""
    if len(items) <= 1:
        return items

    tokenized_docs = [tokenize(f"{item.title} {item.summary or ''}") for item in items]

    # Calculate TF vectors
    tf_vectors = []
    for doc in tokenized_docs:
        tf = {}
        for word in doc:
            tf[word] = tf.get(word, 0) + 1
        tf_vectors.append(tf)

    keep_indices = []
    skipped = set()
    num_docs = len(items)

    for i in range(num_docs):
        if i in skipped:
            continue
        keep_indices.append(i)

        for j in range(i + 1, num_docs):
            if j in skipped:
                continue
            sim = cosine_similarity(tf_vectors[i], tf_vectors[j])
            if sim >= threshold:
                skipped.add(j)
                logger.info(f"Skipping semantic duplicate:\n  Keep: [{items[i].source}] {_safe(items[i].title)}\n  Skip: [{items[j].source}] {_safe(items[j].title)} (Similarity: {sim:.2f})")

    return [items[i] for i in keep_indices]


def deduplicate(items: list) -> list:
    """Remove duplicates using exact match and semantic similarity."""
    candidates = []
    seen_keys = set()
    db = SessionLocal()
    try:
        for item in items:
            unique_id = item.url or item.title
            if not SourceRegistry.is_duplicate(db, item.source, unique_id, ttl_days=30):
                dup_key = (item.source, unique_id)
                if dup_key not in seen_keys:
                    seen_keys.add(dup_key)
                    candidates.append(item)

        unique_items = deduplicate_semantic(candidates, threshold=0.4)

        for item in unique_items:
            unique_id = item.url or item.title
            try:
                SourceRegistry.mark_seen(
                    db, item.source, unique_id, item.title,
                    item.url, item.published_at, item.image_url
                )
            except Exception as e:
                logger.warning(f"Failed to mark seen: {e}")

        db.commit()
    finally:
        db.close()

    return unique_items


def run_pipeline(social: bool = False, log_file: str = "") -> list:
    """Run the full news collection pipeline."""
    log_lines = []

    def log(msg):
        log_lines.append(msg)
        print(msg, flush=True)

    log(f"\n=== Bilaspur News Pipeline — {datetime.now().isoformat()[:16]} ===\n")

    items = collect_all(social=social)
    log(f"\nTotal collected: {len(items)}")

    fresh = deduplicate(items)
    log(f"New items: {len(fresh)}")

    if not fresh:
        log("No new items.")
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            Path(log_file).write_text("\n".join(log_lines), encoding="utf-8")
        return []

    summarized = summarize_items(fresh)
    log(f"Summarized: {len(summarized)} items")

    if summarized:
        try:
            from src.notifier import send_notification
            send_notification(summarized)
        except Exception:
            pass

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        Path(log_file).write_text("\n".join(log_lines), encoding="utf-8")

    return summarized


CATEGORY_SYMBOLS = {
    "government": "[GOV]", "police": "[POL]", "education": "[EDU]",
    "business": "[BIZ]", "event": "[EVT]", "health": "[HLT]",
    "railway": "[RAL]", "infrastructure": "[INF]", "news": "[NEW]",
    "social": "[SOC]", "video": "[VID]",
}


def _safe(text: str, maxlen: int = 80) -> str:
    """Safely truncate text for display."""
    import sys
    s = text[:maxlen]
    try:
        s.encode(sys.stdout.encoding or 'utf-8')
        return s
    except Exception:
        return s.encode('ascii', 'ignore').decode('ascii')


def print_digest(items: list):
    """Print a formatted digest of news items."""
    if not items:
        print("\nNo news today.")
        return

    categories = {}
    for item in items:
        cat = item.category.split(":")[-1].strip() if item.category else "news"
        categories.setdefault(cat, []).append(item)

    print(f"\n{'='*60}")
    print(f"  BILASPUR NEWS DIGEST — {datetime.now().isoformat()[:10]}")
    print(f"{'='*60}\n")

    for cat, cat_items in sorted(categories.items()):
        sym = CATEGORY_SYMBOLS.get(cat, "[*]")
        print(f"  {sym} {cat.upper()} ({len(cat_items)})")
        print(f"  {'-'*50}")
        for item in cat_items[:5]:
            print(f"  * {_safe(item.title, 80)}")
            print(f"    [{item.source}] {_safe(str(item.url), 70)}")
            if item.summary:
                print(f"    {_safe(item.summary, 100)}")
            print()
