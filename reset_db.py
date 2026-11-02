import os, shutil

# Remove old DB completely
path = 'data/bilaspur_news.db'
if os.path.exists(path):
    os.remove(path)
    print('Removed DB file')

# Remove pycache files
for root, dirs, files in os.walk('src'):
    for f in files:
        if f.endswith('.pyc'):
            os.remove(os.path.join(root, f))
print('Cleaned cache')