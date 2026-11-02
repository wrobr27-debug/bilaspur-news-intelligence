import sys, time
sys.path.insert(0, '.')
from src.database.base import engine, Base, get_session
from src.database.models import Sources, CollectedItems
from src.registry.source_registry import SourceRegistry

# Small delay to ensure file system release
time.sleep(0.5)

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