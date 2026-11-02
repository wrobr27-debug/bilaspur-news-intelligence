import sqlite3, os

conn = sqlite3.connect('data/bilaspur_news.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', tables)
for t in tables:
    cursor.execute(f'SELECT sql FROM sqlite_master WHERE type="table" AND name="{t[0]}"')
    sql = cursor.fetchone()
    print(f'\nSQL for {t[0]}:')
    print(sql[0] if sql else 'not found')

conn.close()