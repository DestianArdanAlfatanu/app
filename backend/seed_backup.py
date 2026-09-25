"""Backup collection counts before demo reset (run from backend/)."""
from pymongo import MongoClient
import json

d = MongoClient('mongodb://127.0.0.1:27017')['lpk']
counts = {c: d[c].count_documents({}) for c in sorted(d.list_collection_names())}
with open('seed_backup_counts.json', 'w') as f:
    json.dump(counts, f, indent=1)
print(json.dumps(counts, indent=1))
print("saved to backend/seed_backup_counts.json")
