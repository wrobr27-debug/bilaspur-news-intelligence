import sys
sys.path.insert(0, '.')
from src.database.base import engine, Base

# Create all tables fresh with checkfirst=False
Base.metadata.create_all(bind=engine, checkfirst=False)
print('Tables created with create_all checkfirst=False')

# Verify tables
from src.database.models import Sources, CollectedItems, CollectionRuns, SourceHealth
print('Models imported OK')

# Check what tables exist
import sqlite3
conn = sqlite3.connect('data/bilaspur_news.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')
    tables = cursor.fetchall()
    print('Tables in DB:', tables)
except Exception as e:
    print('DB query error:', e)
conn.close()