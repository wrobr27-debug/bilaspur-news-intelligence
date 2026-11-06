// =========================================
// Bilaspur News Intelligence - Dashboard JS
// =========================================

const API_DATA_URL = 'data/news-data.json';
const REFRESH_INTERVAL = 30000; // 30 seconds

let allNewsData = [];
let currentCategory = 'all';
let currentPage = 1;
const itemsPerPage = 12;

// Category display names and icons
const CATEGORY_CONFIG = {
    all: { name: 'All News', icon: 'fas fa-list' },
    government: { name: 'Government', icon: 'fas fa-building' },
    police: { name: 'Police', icon: 'fas fa-badge-check' },
    newspaper: { name: 'Newspaper', icon: 'fas fa-newspaper' },
    television: { name: 'Television', icon: 'fas fa-tv' },
    education: { name: 'Education', icon: 'fas fa-graduation-cap' },
    transport: { name: 'Transport', icon: 'fas fa-bus' },
    health: { name: 'Health', icon: 'fas fa-hospital' },
    business: { name: 'Business', icon: 'fas fa-chart-line' },
    agriculture: { name: 'Agriculture', icon: 'fas fa-leaf' },
    environment: { name: 'Environment', icon: 'fas fa-recycle' },
    social_media: { name: 'Social Media', icon: 'fas fa-share-alt' },
    youtube: { name: 'YouTube', icon: 'fab fa-youtube', color: '#ff0000' },
    instagram: { name: 'Instagram', icon: 'fab fa-instagram', color: '#e4405f' },
    facebook: { name: 'Facebook', icon: 'fab fa-facebook', color: '#3b5998' },
    twitter: { name: 'Twitter/X', icon: 'fab fa-twitter', color: '#000000' },
    other: { name: 'Other', icon: 'fas fa-folder' }
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    setupEventListeners();
    startAutoRefresh();
});

function setupEventListeners() {
    // Category tabs
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            currentCategory = e.target.dataset.category;
            currentPage = 1;
            renderNews();
        });
    });

    // Search filter
    const searchInput = document.getElementById('search-filter');
    searchInput.addEventListener('input', (e) => {
        currentPage = 1;
        renderNews();
    });

    // Type filter
    document.getElementById('type-filter').addEventListener('change', (e) => {
        currentPage = 1;
        renderNews();
    });

    // Status filter
    document.getElementById('status-filter').addEventListener('change', (e) => {
        currentPage = 1;
        renderNews();
    });

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        loadDashboardData();
    });
}

async function loadDashboardData() {
    try {
        const response = await fetch(`${API_DATA_URL}?t=${new Date().getTime()}`);
        if (!response.ok) throw new Error('Failed to load data');
        
        const data = await response.json();
        allNewsData = data.news_items || [];
        updateDashboardStats(data);
        renderNews();
    } catch (error) {
        console.error('Error loading data:', error);
        showErrorState();
    }
}

function updateDashboardStats(data) {
    // Update stats
    document.getElementById('total-items').textContent = data.total_items || 0;
    document.getElementById('active-sources').textContent = data.active_sources || 0;
    document.getElementById('total-sources').textContent = data.total_sources || 0;
    
    // Update last run info
    const lastRun = data.last_collection_run;
    if (lastRun && lastRun.timestamp) {
        const date = new Date(lastRun.timestamp);
        document.getElementById('last-run').textContent = formatDateTime(date);
        document.getElementById('last-run-time').textContent = formatDateTime(date);
        document.getElementById('footer-last-update').textContent = formatDateTime(date);
        
        const statusEl = document.getElementById('last-run-status');
        statusEl.textContent = lastRun.status || 'unknown';
        statusEl.className = `detail-value status-badge status-${lastRun.status || 'unknown'}`;
        
        document.getElementById('run-items-found').textContent = lastRun.items_found || 0;
        document.getElementById('run-items-inserted').textContent = lastRun.items_inserted || 0;
        document.getElementById('run-sources-processed').textContent = lastRun.sources_processed || 0;
    } else {
        document.getElementById('last-run').textContent = 'Never';
        document.getElementById('last-run-time').textContent = 'Never';
        document.getElementById('footer-last-update').textContent = 'Never';
    }
}

function renderNews() {
    const grid = document.getElementById('news-grid');
    grid.innerHTML = '';

    // Filter data
    let filtered = allNewsData.filter(item => {
        // Category filter
        if (currentCategory !== 'all') {
            if (currentCategory === 'social_media') {
                if (!['youtube', 'instagram', 'facebook', 'twitter'].includes(item.source_type || item.category)) return false;
            } else if (currentCategory === 'youtube' || currentCategory === 'instagram' || currentCategory === 'facebook' || currentCategory === 'twitter') {
                if ((item.source_type || item.category) !== currentCategory) return false;
            } else {
                if ((item.source_type || item.category) !== currentCategory) return false;
            }
        }

        // Search filter
        const searchTerm = document.getElementById('search-filter').value.toLowerCase();
        if (searchTerm) {
            const text = `${item.title} ${item.description} ${item.source_name || ''} ${item.author || ''}`.toLowerCase();
            if (!text.includes(searchTerm)) return false;
        }

        // Type filter
        const typeFilter = document.getElementById('type-filter').value;
        if (typeFilter !== 'all' && item.item_type !== typeFilter) return false;

        // Status filter
        const statusFilter = document.getElementById('status-filter').value;
        if (statusFilter !== 'all' && item.collection_status !== statusFilter) return false;

        return true;
    });

    // Sort by collected_at descending
    filtered.sort((a, b) => new Date(b.collected_at || b.created_at) - new Date(a.collected_at || b.created_at));

    // Update count
    document.getElementById('news-count').textContent = `${filtered.length} item${filtered.length !== 1 ? 's' : ''}`;

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <h3>No news items found</h3>
                <p>Try adjusting your filters or run a new collection.</p>
            </div>
        `;
        return;
    }

    // Paginate
    const totalPages = Math.ceil(filtered.length / itemsPerPage);
    if (currentPage > totalPages) currentPage = totalPages || 1;
    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageItems = filtered.slice(start, end);

    // Render items
    pageItems.forEach((item, index) => {
        const card = createNewsCard(item, index);
        grid.appendChild(card);
    });

    renderPagination(filtered.length, totalPages);
}

function createNewsCard(item, index) {
    const card = document.createElement('div');
    card.className = 'news-card';
    card.style.animationDelay = `${index * 0.05}s`;

    const category = item.source_type || item.category || 'other';
    const catConfig = CATEGORY_CONFIG[category] || CATEGORY_CONFIG.other;
    const itemType = item.item_type || 'article';
    
    const collectedDate = item.collected_at || item.created_at || new Date().toISOString();
    const publishedDate = item.published_at || collectedDate;
    
    const typeClass = `type-${itemType}`;
    const catClass = `cat-${category}`;

    card.innerHTML = `
        <div class="news-card-header">
            <span class="news-card-category ${catClass}">${catConfig.name}</span>
            <span class="news-card-time">${formatRelativeTime(collectedDate)}</span>
        </div>
        <h3>${escapeHtml(item.title || 'Untitled')}</h3>
        ${item.description ? `<p>${escapeHtml(item.description.substring(0, 200))}${item.description.length > 200 ? '...' : ''}</p>` : ''}
        <div class="news-card-meta">
            <div class="news-card-source">
                ${escapeHtml(item.source_name || 'Unknown Source')}
            </div>
            <span class="news-card-type ${typeClass}">${itemType}</span>
        </div>
        ${item.original_url ? `
            <a href="${escapeHtml(item.original_url)}" target="_blank" class="news-card-link">
                <i class="fas fa-external-link-alt"></i> Read Full Story
            </a>
        ` : ''}
        <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-secondary);">
            <span><i class="fas fa-calendar"></i> Published: ${formatDateTime(new Date(publishedDate))}</span>
            ${item.author ? ` | <span><i class="fas fa-user"></i> ${escapeHtml(item.author)}</span>` : ''}
        </div>
    `;

    return card;
}

function renderPagination(totalItems, totalPages) {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';

    if (totalPages <= 1) return;

    // Previous button
    const prevBtn = document.createElement('button');
    prevBtn.textContent = 'Previous';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            renderNews();
        }
    };
    pagination.appendChild(prevBtn);

    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    for (let i = startPage; i <= endPage; i++) {
        const pageBtn = document.createElement('button');
        pageBtn.textContent = i;
        pageBtn.className = i === currentPage ? 'active' : '';
        pageBtn.onclick = () => {
            currentPage = i;
            renderNews();
        };
        pagination.appendChild(pageBtn);
    }

    // Next button
    const nextBtn = document.createElement('button');
    nextBtn.textContent = 'Next';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            renderNews();
        }
    };
    pagination.appendChild(nextBtn);
}

function showErrorState() {
    const grid = document.getElementById('news-grid');
    grid.innerHTML = `
        <div class="empty-state">
            <i class="fas fa-exclamation-triangle"></i>
            <h3>Unable to load data</h3>
            <p>Please check your connection and try refreshing.</p>
            <button class="btn-refresh" onclick="loadDashboardData()">
                <i class="fas fa-sync-alt"></i> Try Again
            </button>
        </div>
    `;
}

// Helper functions
function formatDateTime(date) {
    if (!date) return 'Never';
    const d = new Date(date);
    return d.toLocaleString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function formatRelativeTime(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-IN');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function startAutoRefresh() {
    setInterval(() => {
        loadDashboardData();
    }, REFRESH_INTERVAL);
}