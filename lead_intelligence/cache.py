import hashlib
import json
import sqlite3
from pathlib import Path


class Cache:
    def __init__(self, path="data/lead_intelligence.sqlite"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS website_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def get(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        row = self.connection.execute("SELECT value FROM website_cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, url, value):
        key = hashlib.sha256(url.encode()).hexdigest()
        self.connection.execute("INSERT OR REPLACE INTO website_cache VALUES (?, ?)", (key, json.dumps(value)))
        self.connection.commit()
