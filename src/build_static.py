"""Build static dashboard HTML from collected news data."""

import json
import os
from pathlib import Path
from datetime import datetime

from src.database.base import SessionLocal
from src.database.models import CollectedItems, Sources
from src.registry.source_registry import SourceRegistry


def build_static_dashboard():
    """Build static HTML dashboard from database data."""
    db = SessionLocal()
    try:
        # Get all collected items
        items = db.query(CollectedItems).order_by(CollectedItems.collected_at.desc()).limit(100).all()
        sources = SourceRegistry.list_sources(db, active_only=False)

        # Group by category
        categories = {}
        for item in items:
            cat = item.category or "news"
            categories.setdefault(cat, []).append(item)

        # Build HTML
        html = generate_html(items, sources, categories)

        # Write to docs/index.html
        docs_dir = Path("docs")
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "index.html").write_text(html, encoding="utf-8")

        # Also export JSON
        data_dir = Path("docs/data")
        data_dir.mkdir(parents=True, exist_ok=True)

        news_data = {
            "last_updated": datetime.now().isoformat(),
            "total_items": len(items),
            "active_sources": len([s for s in sources if s.active]),
            "total_sources": len(sources),
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "source": item.source,
                    "category": item.category,
                    "url": item.original_url,
                    "summary": item.summary,
                    "published_at": str(item.published_at) if item.published_at else None,
                    "collected_at": str(item.collected_at) if item.collected_at else None,
                    "image_url": item.image_url,
                }
                for item in items
            ],
            "sources": [
                {
                    "source_id": s.source_id,
                    "source_name": s.source_name,
                    "source_type": s.source_type,
                    "source_category": s.source_category,
                    "active": s.active,
                }
                for s in sources
            ],
        }
        (data_dir / "news-data.json").write_text(json.dumps(news_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Create .nojekyll
        (docs_dir / ".nojekyll").touch()

        logger.info(f"Built static dashboard: {len(items)} items, {len(sources)} sources")
        return True

    finally:
        db.close()


def generate_html(items, sources, categories):
    """Generate HTML for the static dashboard."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bilaspur News Intelligence - News Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #1e3a8a;
            --primary-dark: #1e40af;
            --secondary-color: #059669;
            --accent-color: #d97706;
            --danger-color: #dc2626;
            --warning-color: #d97706;
            --info-color: #0284c7;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border-color: #e2e8f0;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-hover: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --radius: 8px;
            --transition: all 0.3s ease;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 0 1rem; }
        .dashboard-header {
            background: var(--primary-color);
            color: white;
            padding: 1rem 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--shadow);
        }
        .header-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
        }
        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .logo i { font-size: 1.75rem; color: var(--accent-color); }
        .logo-text h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
        .logo-text .subtitle { font-size: 0.875rem; opacity: 0.9; }
        .header-stats {
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
        }
        .stat-item {
            text-align: center;
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.1);
            border-radius: var(--radius);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .stat-item .stat-value { font-size: 1.5rem; font-weight: bold; display: block; }
        .stat-item .stat-label { font-size: 0.75rem; opacity: 0.8; text-transform: uppercase; }
        .menu-toggle {
            background: none;
            border: none;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 4px;
        }
        .menu-toggle:hover { background: rgba(255,255,255,0.1); }
        .filters-container {
            display: flex;
            gap: 1rem;
            padding: 1rem 0;
            flex-wrap: wrap;
            align-items: center;
        }
        .filters-container label { font-size: 0.875rem; font-weight: 600; color: var(--text-secondary); }
        .filters-container select,
        .filters-container input {
            padding: 0.5rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            background: white;
            font-size: 0.875rem;
        }
        .refresh-btn {
            background: var(--primary-color);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: var(--radius);
            cursor: pointer;
            font-size: 0.875rem;
            font-weight: 600;
        }
        .refresh-btn:hover { background: var(--primary-dark); }
        .last-collection {
            text-align: center;
            padding: 1rem 0;
            color: var(--text-secondary);
            font-size: 0.875rem;
            border-bottom: 1px solid var(--border-color);
        }
        .news-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
            padding: 2rem 0;
        }
        .news-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            overflow: hidden;
            transition: var(--shadow-hover);
            display: flex;
            flex-direction: column;
        }
        .news-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }
        .news-card-image {
            height: 200px;
            overflow: hidden;
            background: #f1f5f9;
        }
        .news-card-image img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .news-card-content { padding: 1rem; flex: 1; display: flex; flex-direction: column; }
        .news-card-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        .news-card-source {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--primary-color);
            text-transform: uppercase;
        }
        .news-card-time {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        .news-card-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }
        .news-card-summary {
            font-size: 0.875rem;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-bottom: 1rem;
            flex: 1;
        }
        .news-card-link {
            display: inline-block;
            background: var(--primary-color);
            color: white;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: var(--radius);
            font-size: 0.875rem;
            font-weight: 500;
            text-align: center;
        }
        .news-card-link:hover { background: var(--primary-dark); }
        .category-badge {
            display: inline-block;
            background: #e2e8f0;
            color: var(--text-secondary);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }
        .no-news {
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-secondary);
        }
        .no-news i { font-size: 3rem; margin-bottom: 1rem; color: var(--border-color); }
        .footer {
            text-align: center;
            padding: 2rem 0;
            color: var(--text-secondary);
            font-size: 0.875rem;
            border-top: 1px solid var(--border-color);
        }
        @media (max-width: 768px) {
            .header-content { flex-direction: column; align-items: stretch; }
            .header-stats { justify-content: center; }
            .filters-container { flex-direction: column; align-items: stretch; }
            .news-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <header class="dashboard-header">
        <div class="container">
            <div class="header-content">
                <div class="logo">
                    <i class="fas fa-newspaper"></i>
                    <div class="logo-text">
                        <h1>Bilaspur News Intelligence</h1>
                        <span class="subtitle">News Collection & Monitoring Dashboard</span>
                    </div>
                </div>
                <div class="header-stats">
                    <div class="stat-item">
                        <span class="stat-value">{total_items}</span>
                        <span class="stat-label">News Items</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{active_sources}</span>
                        <span class="stat-label">Active Sources</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{total_sources}</span>
                        <span class="stat-label">Total Sources</span>
                    </div>
                </div>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="filters-container">
            <label>Search News</label>
            <input type="text" id="search-input" placeholder="Search news...">
            <label>Category</label>
            <select id="category-filter">
                <option value="all">All Categories</option>
                {category_options}
            </select>
            <button class="refresh-btn" onclick="location.reload()">
                <i class="fas fa-sync-alt"></i> Refresh
            </button>
        </div>

        <div class="last-collection">
            Last collection: {last_updated}
        </div>

        <div class="news-grid" id="news-grid">
            {news_cards}
        </div>
    </div>

    <footer class="footer">
        Bilaspur News Intelligence Dashboard &bull; Last updated: {last_updated}
    </footer>

    <script>
        document.getElementById('search-input').addEventListener('input', function(e) {
            const term = e.target.value.toLowerCase();
            document.querySelectorAll('.news-card').forEach(card => {
                const title = card.querySelector('.news-card-title').textContent.toLowerCase();
                const summary = card.querySelector('.news-card-summary').textContent.toLowerCase();
                card.style.display = (title.includes(term) || summary.includes(term)) ? 'flex' : 'none';
            });
        });

        document.getElementById('category-filter').addEventListener('change', function(e) {
            const cat = e.target.value;
            document.querySelectorAll('.news-card').forEach(card => {
                const cardCat = card.dataset.category;
                card.style.display = (cat === 'all' || cardCat === cat) ? 'flex' : 'none';
            });
        });
    </script>
</body>
</html>"""

    # Generate category options
    category_options = ""
    for cat in sorted(categories.keys()):
        category_options += f'<option value="{cat}">{cat.title()}</option>\n'

    # Generate news cards
    news_cards = ""
    if items:
        for item in items:
            image_url = item.image_url or "https://via.placeholder.com/350x200?text=No+Image"
            news_cards += f'''
            <div class="news-card" data-category="{item.category or 'news'}">
                <div class="news-card-image">
                    <img src="{image_url}" alt="{item.title}" onerror="this.src='https://via.placeholder.com/350x200?text=No+Image'">
                </div>
                <div class="news-card-content">
                    <div class="news-card-meta">
                        <span class="news-card-source">{item.source or 'Unknown'}</span>
                        <span class="news-card-time">{str(item.collected_at)[:16] if item.collected_at else 'Unknown'}</span>
                    </div>
                    <div class="category-badge">{item.category or 'News'}</div>
                    <h3 class="news-card-title">{item.title or 'No Title'}</h3>
                    <p class="news-card-summary">{item.summary or 'No summary available.'}</p>
                    <a href="{item.original_url or '#'}" class="news-card-link" target="_blank">Read Full Story &rarr;</a>
                </div>
            </div>
            '''
    else:
        news_cards = '''
        <div class="no-news">
            <i class="fas fa-newspaper"></i>
            <h3>No news available yet.</h3>
            <p>Run the collection pipeline to fetch news from active sources.</p>
        </div>
        '''

    html = html.format(
        total_items=len(items),
        active_sources=len([s for s in sources if s.active]),
        total_sources=len(sources),
        last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        category_options=category_options,
        news_cards=news_cards,
    )

    return html


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    build_static_dashboard()
