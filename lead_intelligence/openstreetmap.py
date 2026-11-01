"""No-key OpenStreetMap/Nominatim search adapter.

Nominatim is public infrastructure with strict usage limits. Keep calls low-volume,
cached where possible, and identify this application with a descriptive User-Agent.
"""
import os

from .extraction import build_session

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class OpenStreetMap:
    def __init__(self):
        self.session = build_session()
        self.session.headers["User-Agent"] = os.getenv(
            "OSM_USER_AGENT",
            "AILeadIntelligence/1.0 (public business verification)",
        )

    def search(self, name, city="", address="", limit=5):
        query = ", ".join(str(value).strip() for value in (name, city, address) if str(value).strip())
        if not query:
            return []
        response = self.session.get(
            NOMINATIM_URL,
            params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": min(max(limit, 1), 10)},
            timeout=20,
        )
        response.raise_for_status()
        records = []
        for item in response.json():
            address_data = item.get("address", {})
            records.append({
                "business_name": item.get("name") or item.get("display_name", "").split(",")[0],
                "business_address": item.get("display_name", ""),
                "city": address_data.get("city") or address_data.get("town") or address_data.get("village") or "",
                "postal_code": address_data.get("postcode", ""),
                "website": "",
                "public_phone": "",
                "source_url": f"https://www.openstreetmap.org/{item.get('osm_type', 'node')}/{item.get('osm_id')}" if item.get("osm_id") else NOMINATIM_URL,
                "category": item.get("type", ""),
                "discovery_method": "openstreetmap_nominatim",
            })
        return records
