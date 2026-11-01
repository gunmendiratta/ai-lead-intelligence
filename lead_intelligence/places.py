"""Google Places API adapter. Uses its documented API, not Google Maps UI scraping."""
import os
import requests

from .extraction import build_session


class GooglePlaces:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")

    @property
    def available(self):
        return bool(self.api_key)

    def text_search(self, query, page_size=20):
        if not self.available:
            raise RuntimeError("Set GOOGLE_PLACES_API_KEY in .env to search Google Maps data.")
        fields = "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.googleMapsUri,places.types"
        response = build_session().post("https://places.googleapis.com/v1/places:searchText", headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": fields}, json={"textQuery": query, "pageSize": min(max(page_size, 1), 20)}, timeout=20)
        response.raise_for_status()
        records = []
        for place in response.json().get("places", []):
            records.append({
                "business_name": place.get("displayName", {}).get("text", ""), "business_address": place.get("formattedAddress", ""),
                "website": place.get("websiteUri", ""), "public_phone": place.get("nationalPhoneNumber", ""),
                "source_url": place.get("googleMapsUri", ""), "category": "; ".join(place.get("types", [])), "discovery_method": "google_places_api",
            })
        return records
