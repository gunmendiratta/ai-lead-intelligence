"""Approved search-provider adapters; no HTML search-engine scraping."""
import os

import requests


class GoogleProgrammableSearch:
    def __init__(self, api_key=None, search_engine_id=None):
        self.api_key = api_key or os.getenv("GOOGLE_CSE_API_KEY")
        self.search_engine_id = search_engine_id or os.getenv("GOOGLE_CSE_ID")

    @property
    def available(self):
        return bool(self.api_key and self.search_engine_id)

    def find_website(self, name, address="", city=""):
        if not self.available:
            return ""
        query = " ".join(part for part in (name, address, city, "official website") if part)
        response = requests.get("https://www.googleapis.com/customsearch/v1", params={"key": self.api_key, "cx": self.search_engine_id, "q": query, "num": 3}, timeout=15)
        response.raise_for_status()
        for item in response.json().get("items", []):
            url = item.get("link", "")
            if url.startswith(("https://", "http://")):
                return url
        return ""
