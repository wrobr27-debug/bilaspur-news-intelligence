import os, sys, time
# Force remove any existing DB
db_path = 'data/bilaspur_news.db'
if os.path.exists(db_path):
    os.remove(db_path)
    print(f'Removed {db_path}')

# Also remove WAL and SHM files
for ext in ['-wal', '-shm']:
    p = db_path + ext
    if os.path.exists(p):
        os.remove(p)
        print(f'Removed {p}')

time.sleep(1)  # Wait for file system to release

sys.path.insert(0, '.')
from src.database.base import engine, Base, get_session
from src.database.models import Sources, CollectedItems
from src.registry.source_registry import SourceRegistry

# Create all tables fresh
Base.metadata.create_all(bind=engine, checkfirst=False)
print('Tables created successfully')

# Test source registry
db = get_session()
try:
    source = SourceRegistry.add_source(
        db=db,
        source_id='test_gov_1',
        source_name='Test Government Source',
        source_type='government',
        source_category='state',
        source_url='https://example.gov',
        collection_method='html',
        reliability_level='official',
        active=False,
        notes='Test source'
    )
    print(f'Added source: {source.source_id}')
    db.close()
    print('Source registry test PASSED')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()